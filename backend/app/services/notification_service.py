"""
Notification service for real-time notifications with SSE streaming.

Provides:
- Real-time Server-Sent Events (SSE) streaming
- Multi-instance support via Redis pub/sub
- Persistent notification storage
- User preference management
- Targeted and broadcast notifications
- Integration mixins for other services
"""
import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Set, List, Optional, AsyncIterator, Any
from collections import defaultdict

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.notification import (
    Notification, NotificationPreference, 
    NotificationType, NotificationPriority
)
from app.models.user import User, Role

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Service for managing and delivering notifications.
    
    Features:
    - Real-time SSE delivery to connected clients
    - Redis pub/sub for horizontal scaling
    - Persistent database storage
    - User preference management
    - Priority-based delivery
    - Role-based broadcasting
    """
    
    def __init__(self):
        """Initialize notification service."""
        # Active SSE connections: {user_id: [queue1, queue2, ...]}
        self._connections: Dict[int, List[asyncio.Queue]] = defaultdict(list)
        # Redis client for pub/sub (to be injected)
        self._redis = None
        # Background task for Redis subscription
        self._redis_task: Optional[asyncio.Task] = None
        logger.info("NotificationService initialized")
    
    def set_redis(self, redis_client):
        """
        Set Redis client for pub/sub.
        
        Args:
            redis_client: Redis async client instance
        """
        self._redis = redis_client
        logger.info("Redis client configured for notifications")
    
    async def start_redis_listener(self):
        """Start background task to listen for Redis pub/sub notifications."""
        if not self._redis:
            logger.warning("Redis not configured, skipping pub/sub listener")
            return
        
        self._redis_task = asyncio.create_task(self._redis_subscriber())
        logger.info("Redis pub/sub listener started")
    
    async def stop_redis_listener(self):
        """Stop the Redis pub/sub listener."""
        if self._redis_task:
            self._redis_task.cancel()
            try:
                await self._redis_task
            except asyncio.CancelledError:
                pass
            logger.info("Redis pub/sub listener stopped")
    
    async def _redis_subscriber(self):
        """Background task to subscribe to Redis notifications channel."""
        try:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe("notifications")
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        notification_data = json.loads(message["data"])
                        await self._deliver_to_local_connections(notification_data)
                    except Exception as e:
                        logger.error(f"Error processing Redis notification: {e}")
        except asyncio.CancelledError:
            logger.info("Redis subscriber cancelled")
        except Exception as e:
            logger.error(f"Redis subscriber error: {e}")
    
    async def connect(self, user_id: int) -> asyncio.Queue:
        """
        Register a new SSE connection for a user.
        
        Args:
            user_id: ID of the user connecting
            
        Returns:
            asyncio.Queue for receiving notifications
        """
        queue = asyncio.Queue()
        self._connections[user_id].append(queue)
        logger.info(f"User {user_id} connected (total connections: {len(self._connections[user_id])})")
        return queue
    
    async def disconnect(self, user_id: int, queue: asyncio.Queue):
        """
        Remove an SSE connection for a user.
        
        Args:
            user_id: ID of the user disconnecting
            queue: The queue to remove
        """
        if user_id in self._connections:
            try:
                self._connections[user_id].remove(queue)
                if not self._connections[user_id]:
                    del self._connections[user_id]
                logger.info(f"User {user_id} disconnected")
            except ValueError:
                pass
    
    async def send_notification(
        self,
        db: AsyncSession,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        persist: bool = True,
        expires_at: Optional[datetime] = None
    ) -> Optional[Notification]:
        """
        Send a notification to a specific user.
        
        Args:
            db: Database session
            user_id: Target user ID
            notification_type: Type of notification
            title: Short notification title
            message: Detailed message
            data: Additional structured data
            priority: Notification priority level
            persist: Whether to save to database
            expires_at: Optional expiration timestamp
            
        Returns:
            Created notification if persisted, None otherwise
        """
        notification_dict = {
            "user_id": user_id,
            "type": notification_type.value,
            "title": title,
            "message": message,
            "data": data or {},
            "priority": priority.value,
            "created_at": datetime.utcnow().isoformat(),
            "is_read": False,
            "read_at": None,
            "expires_at": expires_at.isoformat() if expires_at else None
        }
        
        notification_obj = None
        
        # Check user preferences
        if await self._check_user_preferences(db, user_id, notification_type):
            # Persist to database if requested
            if persist:
                notification_obj = await self._save_to_database(db, notification_dict)
                notification_dict["id"] = notification_obj.id
            
            # Publish to Redis for multi-instance delivery
            if self._redis:
                try:
                    await self._redis.publish(
                        "notifications",
                        json.dumps(notification_dict)
                    )
                except Exception as e:
                    logger.error(f"Failed to publish to Redis: {e}")
            
            # Deliver to local connections
            await self._deliver_to_local_connections(notification_dict)
            
            logger.info(
                f"Notification sent to user {user_id}: {notification_type.value} - {title}"
            )
        else:
            logger.debug(
                f"Notification {notification_type.value} disabled for user {user_id}"
            )
        
        return notification_obj
    
    async def send_broadcast_notification(
        self,
        db: AsyncSession,
        notification_type: NotificationType,
        title: str,
        message: str,
        target_roles: Optional[List[str]] = None,
        data: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        persist: bool = True
    ) -> int:
        """
        Send a notification to multiple users based on roles.
        
        Args:
            db: Database session
            notification_type: Type of notification
            title: Short notification title
            message: Detailed message
            target_roles: List of role names to target (None = all users)
            data: Additional structured data
            priority: Notification priority level
            persist: Whether to save to database
            
        Returns:
            Number of notifications sent
        """
        # Get target users
        users = await self._get_users_by_roles(db, target_roles)
        
        count = 0
        for user in users:
            await self.send_notification(
                db=db,
                user_id=user.id,
                notification_type=notification_type,
                title=title,
                message=message,
                data=data,
                priority=priority,
                persist=persist
            )
            count += 1
        
        logger.info(
            f"Broadcast notification sent to {count} users: {notification_type.value}"
        )
        return count
    
    async def _deliver_to_local_connections(self, notification: Dict[str, Any]):
        """
        Deliver notification to all active SSE connections for the user.
        
        Args:
            notification: Notification data dictionary
        """
        user_id = notification["user_id"]
        if user_id in self._connections:
            for queue in self._connections[user_id]:
                try:
                    await queue.put(notification)
                except Exception as e:
                    logger.error(f"Failed to deliver notification to queue: {e}")
    
    async def _save_to_database(
        self,
        db: AsyncSession,
        notification_dict: Dict[str, Any]
    ) -> Notification:
        """
        Save notification to database.
        
        Args:
            db: Database session
            notification_dict: Notification data
            
        Returns:
            Created notification object
        """
        # Convert ISO strings back to datetime if needed
        created_at = notification_dict.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        
        expires_at = notification_dict.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        notification = Notification(
            user_id=notification_dict["user_id"],
            type=notification_dict["type"],
            title=notification_dict["title"],
            message=notification_dict["message"],
            data=notification_dict.get("data", {}),
            priority=notification_dict["priority"],
            is_read=notification_dict.get("is_read", False),
            created_at=created_at or datetime.utcnow(),
            expires_at=expires_at
        )
        
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        return notification
    
    async def _check_user_preferences(
        self,
        db: AsyncSession,
        user_id: int,
        notification_type: NotificationType
    ) -> bool:
        """
        Check if user has enabled this notification type.
        
        Args:
            db: Database session
            user_id: User ID
            notification_type: Type of notification
            
        Returns:
            True if notification should be sent, False otherwise
        """
        result = await db.execute(
            select(NotificationPreference).where(
                and_(
                    NotificationPreference.user_id == user_id,
                    NotificationPreference.notification_type == notification_type.value
                )
            )
        )
        preference = result.scalar_one_or_none()
        
        # If no preference exists, default to enabled
        return preference.enabled if preference else True
    
    async def _get_users_by_roles(
        self,
        db: AsyncSession,
        target_roles: Optional[List[str]] = None
    ) -> List[User]:
        """
        Get users based on role filters.
        
        Args:
            db: Database session
            target_roles: List of role names (None = all active users)
            
        Returns:
            List of matching users
        """
        query = select(User).where(User.is_active == True)
        
        if target_roles:
            query = query.join(User.roles).where(Role.name.in_(target_roles))
        
        result = await db.execute(query)
        return result.scalars().unique().all()
    
    async def get_user_notifications(
        self,
        db: AsyncSession,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[Notification], int]:
        """
        Retrieve user's notifications from database.
        
        Args:
            db: Database session
            user_id: User ID
            unread_only: Only return unread notifications
            limit: Maximum number of notifications
            offset: Pagination offset
            
        Returns:
            Tuple of (notifications list, total count)
        """
        # Build query
        query = select(Notification).where(Notification.user_id == user_id)
        
        if unread_only:
            query = query.where(Notification.is_read == False)
        
        # Remove expired notifications
        query = query.where(
            or_(
                Notification.expires_at == None,
                Notification.expires_at > datetime.utcnow()
            )
        )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results
        query = query.order_by(Notification.created_at.desc())
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        notifications = result.scalars().all()
        
        return notifications, total
    
    async def mark_as_read(
        self,
        db: AsyncSession,
        notification_id: int,
        user_id: int
    ) -> Optional[Notification]:
        """
        Mark a notification as read.
        
        Args:
            db: Database session
            notification_id: Notification ID
            user_id: User ID (for ownership verification)
            
        Returns:
            Updated notification or None if not found
        """
        result = await db.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id
                )
            )
        )
        notification = result.scalar_one_or_none()
        
        if notification and not notification.is_read:
            notification.mark_as_read()
            await db.commit()
            await db.refresh(notification)
            logger.info(f"Notification {notification_id} marked as read")
        
        return notification
    
    async def mark_all_as_read(
        self,
        db: AsyncSession,
        user_id: int
    ) -> int:
        """
        Mark all user's notifications as read.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Number of notifications updated
        """
        result = await db.execute(
            select(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False
                )
            )
        )
        notifications = result.scalars().all()
        
        count = 0
        for notification in notifications:
            notification.mark_as_read()
            count += 1
        
        await db.commit()
        logger.info(f"Marked {count} notifications as read for user {user_id}")
        return count
    
    async def delete_notification(
        self,
        db: AsyncSession,
        notification_id: int,
        user_id: int
    ) -> bool:
        """
        Delete a notification.
        
        Args:
            db: Database session
            notification_id: Notification ID
            user_id: User ID (for ownership verification)
            
        Returns:
            True if deleted, False if not found
        """
        result = await db.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id
                )
            )
        )
        notification = result.scalar_one_or_none()
        
        if notification:
            await db.delete(notification)
            await db.commit()
            logger.info(f"Notification {notification_id} deleted")
            return True
        
        return False
    
    async def get_notification_stats(
        self,
        db: AsyncSession,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Get notification statistics for a user.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Dictionary with notification statistics
        """
        # Total notifications
        total_result = await db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == user_id
            )
        )
        total = total_result.scalar()
        
        # Unread count
        unread_result = await db.execute(
            select(func.count()).select_from(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False
                )
            )
        )
        unread = unread_result.scalar()
        
        # By type
        type_result = await db.execute(
            select(
                Notification.type,
                func.count(Notification.id)
            ).where(
                Notification.user_id == user_id
            ).group_by(Notification.type)
        )
        by_type = {row[0]: row[1] for row in type_result}
        
        # By priority
        priority_result = await db.execute(
            select(
                Notification.priority,
                func.count(Notification.id)
            ).where(
                Notification.user_id == user_id
            ).group_by(Notification.priority)
        )
        by_priority = {row[0]: row[1] for row in priority_result}
        
        # Recent (last 24 hours)
        recent_result = await db.execute(
            select(func.count()).select_from(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.created_at >= datetime.utcnow() - timedelta(hours=24)
                )
            )
        )
        recent = recent_result.scalar()
        
        return {
            "total_notifications": total,
            "unread_count": unread,
            "by_type": by_type,
            "by_priority": by_priority,
            "recent_count": recent
        }
    
    async def get_user_preferences(
        self,
        db: AsyncSession,
        user_id: int
    ) -> List[NotificationPreference]:
        """
        Get all notification preferences for a user.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            List of notification preferences
        """
        result = await db.execute(
            select(NotificationPreference).where(
                NotificationPreference.user_id == user_id
            ).order_by(NotificationPreference.notification_type)
        )
        return result.scalars().all()
    
    async def update_preference(
        self,
        db: AsyncSession,
        user_id: int,
        notification_type: NotificationType,
        enabled: bool,
        delivery_method: str = "realtime"
    ) -> NotificationPreference:
        """
        Update or create a notification preference.
        
        Args:
            db: Database session
            user_id: User ID
            notification_type: Type of notification
            enabled: Whether notification is enabled
            delivery_method: Delivery method (realtime, email, etc.)
            
        Returns:
            Updated or created preference
        """
        result = await db.execute(
            select(NotificationPreference).where(
                and_(
                    NotificationPreference.user_id == user_id,
                    NotificationPreference.notification_type == notification_type.value
                )
            )
        )
        preference = result.scalar_one_or_none()
        
        if preference:
            preference.enabled = enabled
            preference.delivery_method = delivery_method
            preference.updated_at = datetime.utcnow()
        else:
            preference = NotificationPreference(
                user_id=user_id,
                notification_type=notification_type.value,
                enabled=enabled,
                delivery_method=delivery_method
            )
            db.add(preference)
        
        await db.commit()
        await db.refresh(preference)
        
        logger.info(
            f"Preference updated for user {user_id}: {notification_type.value} = {enabled}"
        )
        return preference


# Global singleton instance
notification_service = NotificationService()


# Integration Mixins for other services
class ApprovalNotificationMixin:
    """Mixin for approval workflow notifications."""
    
    async def notify_approval_requested(
        self,
        db: AsyncSession,
        manager_id: int,
        requester_name: str,
        tool_name: str,
        approval_id: int
    ):
        """Notify manager of new approval request."""
        await notification_service.send_notification(
            db=db,
            user_id=manager_id,
            notification_type=NotificationType.APPROVAL_REQUESTED,
            title="Approval Required",
            message=f"{requester_name} requests approval to run '{tool_name}'",
            data={
                "requester_name": requester_name,
                "tool_name": tool_name,
                "approval_id": approval_id,
                "action_url": f"/approvals/{approval_id}"
            },
            priority=NotificationPriority.HIGH
        )
    
    async def notify_approval_decision(
        self,
        db: AsyncSession,
        requester_id: int,
        approver_name: str,
        tool_name: str,
        decision: str,
        approval_id: int
    ):
        """Notify requester of approval decision."""
        priority = NotificationPriority.HIGH if decision == "APPROVED" else NotificationPriority.NORMAL
        await notification_service.send_notification(
            db=db,
            user_id=requester_id,
            notification_type=NotificationType.APPROVAL_DECISION,
            title=f"Approval {decision}",
            message=f"{approver_name} has {decision.lower()} your request to run '{tool_name}'",
            data={
                "approver_name": approver_name,
                "tool_name": tool_name,
                "decision": decision,
                "approval_id": approval_id
            },
            priority=priority
        )


class DocumentNotificationMixin:
    """Mixin for document-related notifications."""
    
    async def notify_document_indexed(
        self,
        db: AsyncSession,
        user_id: int,
        document_id: int,
        document_title: str
    ):
        """Notify user that document has been indexed."""
        await notification_service.send_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.DOCUMENT_INDEXED,
            title="Document Indexed",
            message=f"'{document_title}' has been successfully indexed and is now searchable",
            data={
                "document_id": document_id,
                "document_title": document_title,
                "action_url": f"/documents/{document_id}"
            },
            priority=NotificationPriority.NORMAL
        )
    
    async def notify_document_failed(
        self,
        db: AsyncSession,
        user_id: int,
        document_id: int,
        document_title: str,
        error_message: str
    ):
        """Notify user that document processing failed."""
        await notification_service.send_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.DOCUMENT_PROCESSING_FAILED,
            title="Document Processing Failed",
            message=f"Failed to process '{document_title}': {error_message}",
            data={
                "document_id": document_id,
                "document_title": document_title,
                "error_message": error_message
            },
            priority=NotificationPriority.HIGH
        )


class ToolNotificationMixin:
    """Mixin for tool registry notifications."""
    
    async def notify_tool_added(
        self,
        db: AsyncSession,
        tool_name: str,
        tool_description: str,
        target_roles: Optional[List[str]] = None
    ):
        """Notify users of new tool availability."""
        await notification_service.send_broadcast_notification(
            db=db,
            notification_type=NotificationType.TOOL_ADDED,
            title="New Tool Available",
            message=f"A new tool '{tool_name}' has been added: {tool_description}",
            target_roles=target_roles,
            data={
                "tool_name": tool_name,
                "tool_description": tool_description,
                "action_url": f"/tools/{tool_name}"
            },
            priority=NotificationPriority.NORMAL
        )