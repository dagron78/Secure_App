"""
Notification models for the CDSA application.

Provides models for:
- Notification: Persistent notifications with priority levels
- NotificationPreference: User-specific notification settings
"""
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, 
    ForeignKey, Text, JSON, Index
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class NotificationType(str, Enum):
    """Enum for notification types."""
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_DECISION = "APPROVAL_DECISION"
    DOCUMENT_INDEXED = "DOCUMENT_INDEXED"
    DOCUMENT_PROCESSING_FAILED = "DOCUMENT_PROCESSING_FAILED"
    TOOL_ADDED = "TOOL_ADDED"
    TOOL_UPDATED = "TOOL_UPDATED"
    TOOL_REMOVED = "TOOL_REMOVED"
    SECURITY_ALERT = "SECURITY_ALERT"
    VAULT_SECRET_ADDED = "VAULT_SECRET_ADDED"
    VAULT_SECRET_ACCESSED = "VAULT_SECRET_ACCESSED"
    SYSTEM_MAINTENANCE = "SYSTEM_MAINTENANCE"
    LONG_RUNNING_TASK_COMPLETED = "LONG_RUNNING_TASK_COMPLETED"


class NotificationPriority(str, Enum):
    """Enum for notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Notification(Base):
    """
    Model for storing persistent notifications.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to user who receives the notification
        type: Type of notification (from NotificationType enum)
        title: Short notification title
        message: Detailed notification message
        data: Additional structured data (JSON)
        priority: Notification priority level
        is_read: Whether the notification has been read
        read_at: Timestamp when notification was read
        expires_at: Optional expiration timestamp
        created_at: When notification was created
    """
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(100), nullable=False)
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSON, default=dict)
    priority = Column(String(20), default="normal", nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="notifications")
    
    # Indexes
    __table_args__ = (
        Index('idx_notifications_user', 'user_id'),
        Index('idx_notifications_unread', 'user_id', 'is_read', 'created_at'),
        Index('idx_notifications_type', 'type'),
        Index('idx_notifications_priority', 'priority', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Notification(id={self.id}, user_id={self.user_id}, type={self.type}, title='{self.title}')>"
    
    def mark_as_read(self) -> None:
        """Mark notification as read with current timestamp."""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert notification to dictionary for SSE streaming."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "type": self.type,
            "title": self.title,
            "message": self.message,
            "data": self.data or {},
            "priority": self.priority,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat()
        }


class NotificationPreference(Base):
    """
    Model for user notification preferences.
    
    Allows users to customize which types of notifications they receive
    and how they are delivered.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to user
        notification_type: Type of notification (from NotificationType enum)
        enabled: Whether this notification type is enabled for the user
        delivery_method: How to deliver (realtime, email, etc.)
        created_at: When preference was created
        updated_at: When preference was last updated
    """
    __tablename__ = "notification_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    notification_type = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    delivery_method = Column(String(50), default="realtime", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="notification_preferences")
    
    # Constraints
    __table_args__ = (
        Index('idx_notification_prefs_user_type', 'user_id', 'notification_type', unique=True),
    )
    
    def __repr__(self):
        return f"<NotificationPreference(user_id={self.user_id}, type={self.notification_type}, enabled={self.enabled})>"