"""
Notification API endpoints.

Provides:
- Real-time SSE notification streaming
- Notification CRUD operations
- User preference management
- Broadcast notifications (admin only)
- Notification statistics
"""
import json
import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_current_user,
    get_db,
    require_permission
)
from app.models.user import User
from app.models.notification import NotificationType, NotificationPriority
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationUpdate,
    NotificationPreferenceResponse,
    NotificationPreferenceListResponse,
    NotificationPreferenceUpdate,
    BroadcastNotificationRequest,
    NotificationStatsResponse
)
from app.services.notification_service import notification_service
from app.core.logging import log_api_call

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "/stream",
    summary="Real-time notification stream (SSE)",
    description="Server-Sent Events endpoint for receiving notifications in real-time"
)
async def stream_notifications(
    current_user: User = Depends(get_current_user)
):
    """
    Stream real-time notifications via Server-Sent Events (SSE).
    
    Keep this connection open to receive notifications as they arrive.
    The stream will send periodic keepalive messages.
    
    **Event Format:**
    ```
    event: notification
    data: {"id": 1, "type": "APPROVAL_REQUESTED", "title": "...", ...}
    
    event: keepalive
    data: {"timestamp": "2024-01-01T12:00:00Z"}
    ```
    """
    logger.info(f"User {current_user.id} connecting to notification stream")
    
    async def event_generator():
        # Register connection
        queue = await notification_service.connect(current_user.id)
        
        try:
            # Send initial connection confirmation
            yield f"event: connected\ndata: {json.dumps({'user_id': current_user.id, 'timestamp': datetime.utcnow().isoformat()})}\n\n"
            
            # Main event loop
            while True:
                try:
                    # Wait for notification with timeout for keepalive
                    notification = await asyncio.wait_for(
                        queue.get(),
                        timeout=30.0  # 30 second keepalive
                    )
                    
                    # Send notification
                    yield f"event: notification\ndata: {json.dumps(notification)}\n\n"
                    
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"event: keepalive\ndata: {json.dumps({'timestamp': datetime.utcnow().isoformat()})}\n\n"
                    
        except asyncio.CancelledError:
            logger.info(f"User {current_user.id} notification stream cancelled")
        except Exception as e:
            logger.error(f"Error in notification stream for user {current_user.id}: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            # Unregister connection
            await notification_service.disconnect(current_user.id, queue)
            logger.info(f"User {current_user.id} disconnected from notification stream")
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="Get notifications",
    description="Retrieve paginated list of notifications for the current user"
)
@log_api_call
async def get_notifications(
    unread_only: bool = Query(False, description="Only return unread notifications"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> NotificationListResponse:
    """
    Get paginated notifications for the current user.
    
    **Query Parameters:**
    - `unread_only`: Filter to only unread notifications
    - `page`: Page number (starts at 1)
    - `page_size`: Number of items per page (max 100)
    
    **Returns:**
    - List of notifications with pagination metadata
    """
    offset = (page - 1) * page_size
    
    notifications, total = await notification_service.get_user_notifications(
        db=db,
        user_id=current_user.id,
        unread_only=unread_only,
        limit=page_size,
        offset=offset
    )
    
    # Count unread
    _, unread_count = await notification_service.get_user_notifications(
        db=db,
        user_id=current_user.id,
        unread_only=True,
        limit=1,
        offset=0
    )
    
    return NotificationListResponse(
        notifications=notifications,
        total=total,
        unread_count=unread_count,
        page=page,
        page_size=page_size
    )


@router.get(
    "/stats",
    response_model=NotificationStatsResponse,
    summary="Get notification statistics",
    description="Get detailed statistics about user's notifications"
)
@log_api_call
async def get_notification_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> NotificationStatsResponse:
    """
    Get notification statistics for the current user.
    
    **Returns:**
    - Total notification count
    - Unread count
    - Breakdown by type
    - Breakdown by priority
    - Recent notifications count (last 24 hours)
    """
    stats = await notification_service.get_notification_stats(db, current_user.id)
    return NotificationStatsResponse(**stats)


@router.patch(
    "/{notification_id}",
    response_model=NotificationResponse,
    summary="Update notification",
    description="Update a notification (e.g., mark as read)"
)
@log_api_call
async def update_notification(
    notification_id: int,
    update: NotificationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> NotificationResponse:
    """
    Update a notification.
    
    Currently supports marking as read/unread.
    
    **Path Parameters:**
    - `notification_id`: ID of the notification to update
    
    **Request Body:**
    ```json
    {
        "is_read": true
    }
    ```
    """
    if update.is_read is not None and update.is_read:
        notification = await notification_service.mark_as_read(
            db=db,
            notification_id=notification_id,
            user_id=current_user.id
        )
        
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        return notification
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No valid update fields provided"
    )


@router.post(
    "/mark-all-read",
    summary="Mark all as read",
    description="Mark all user's notifications as read"
)
@log_api_call
async def mark_all_notifications_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Mark all notifications as read for the current user.
    
    **Returns:**
    - Count of notifications marked as read
    """
    count = await notification_service.mark_all_as_read(db, current_user.id)
    
    return {
        "success": True,
        "marked_read": count,
        "message": f"Marked {count} notifications as read"
    }


@router.delete(
    "/{notification_id}",
    summary="Delete notification",
    description="Delete a specific notification"
)
@log_api_call
async def delete_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Delete a notification.
    
    **Path Parameters:**
    - `notification_id`: ID of the notification to delete
    """
    deleted = await notification_service.delete_notification(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id
    )
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {
        "success": True,
        "message": "Notification deleted successfully"
    }


@router.get(
    "/preferences",
    response_model=NotificationPreferenceListResponse,
    summary="Get notification preferences",
    description="Get user's notification preferences"
)
@log_api_call
async def get_notification_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> NotificationPreferenceListResponse:
    """
    Get all notification preferences for the current user.
    
    **Returns:**
    - List of notification preferences (which types are enabled/disabled)
    """
    preferences = await notification_service.get_user_preferences(db, current_user.id)
    
    return NotificationPreferenceListResponse(
        preferences=preferences,
        total=len(preferences)
    )


@router.put(
    "/preferences/{notification_type}",
    response_model=NotificationPreferenceResponse,
    summary="Update notification preference",
    description="Update preference for a specific notification type"
)
@log_api_call
async def update_notification_preference(
    notification_type: NotificationType,
    update: NotificationPreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> NotificationPreferenceResponse:
    """
    Update or create a notification preference.
    
    **Path Parameters:**
    - `notification_type`: Type of notification (e.g., APPROVAL_REQUESTED)
    
    **Request Body:**
    ```json
    {
        "enabled": true,
        "delivery_method": "realtime"
    }
    ```
    """
    preference = await notification_service.update_preference(
        db=db,
        user_id=current_user.id,
        notification_type=notification_type,
        enabled=update.enabled if update.enabled is not None else True,
        delivery_method=update.delivery_method or "realtime"
    )
    
    return preference


@router.post(
    "/broadcast",
    summary="Send broadcast notification (Admin)",
    description="Send a notification to multiple users (requires admin permission)"
)
@log_api_call
async def broadcast_notification(
    request: BroadcastNotificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("notifications:broadcast"))
) -> dict:
    """
    Send a broadcast notification to multiple users.
    
    **Required Permission:** `notifications:broadcast`
    
    **Request Body:**
    ```json
    {
        "type": "SYSTEM_MAINTENANCE",
        "title": "System Maintenance",
        "message": "The system will undergo maintenance tonight",
        "target_roles": ["ANALYST", "MANAGER"],
        "priority": "high",
        "persist": true
    }
    ```
    
    **Parameters:**
    - `type`: Type of notification
    - `title`: Short title
    - `message`: Detailed message
    - `target_roles`: List of role names (null = all users)
    - `data`: Additional structured data
    - `priority`: Priority level (low, normal, high, urgent)
    - `persist`: Whether to save to database
    
    **Returns:**
    - Count of users notified
    """
    count = await notification_service.send_broadcast_notification(
        db=db,
        notification_type=request.type,
        title=request.title,
        message=request.message,
        target_roles=request.target_roles,
        data=request.data,
        priority=request.priority,
        persist=request.persist
    )
    
    return {
        "success": True,
        "users_notified": count,
        "message": f"Notification sent to {count} users"
    }


@router.get(
    "/health",
    summary="Notification service health",
    description="Check health of notification service"
)
async def notification_health() -> dict:
    """
    Check notification service health.
    
    **Returns:**
    - Service status
    - Active connections count
    - Redis status
    """
    connection_count = sum(
        len(queues) for queues in notification_service._connections.values()
    )
    
    return {
        "status": "healthy",
        "service": "notifications",
        "active_connections": connection_count,
        "redis_configured": notification_service._redis is not None,
        "timestamp": datetime.utcnow().isoformat()
    }