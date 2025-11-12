"""
Notification schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

from app.models.notification import NotificationType, NotificationPriority


class NotificationBase(BaseModel):
    """Base notification schema."""
    type: NotificationType
    title: str = Field(..., min_length=1, max_length=500)
    message: str = Field(..., min_length=1)
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    priority: NotificationPriority = NotificationPriority.NORMAL


class NotificationCreate(NotificationBase):
    """Schema for creating a notification."""
    user_id: int
    expires_at: Optional[datetime] = None


class NotificationResponse(NotificationBase):
    """Schema for notification response."""
    id: int
    user_id: int
    is_read: bool
    read_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class NotificationUpdate(BaseModel):
    """Schema for updating a notification."""
    is_read: Optional[bool] = None


class NotificationListResponse(BaseModel):
    """Schema for paginated notification list."""
    notifications: List[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)


class NotificationPreferenceBase(BaseModel):
    """Base notification preference schema."""
    notification_type: NotificationType
    enabled: bool = True
    delivery_method: str = Field(default="realtime", max_length=50)


class NotificationPreferenceCreate(NotificationPreferenceBase):
    """Schema for creating a notification preference."""
    pass


class NotificationPreferenceUpdate(BaseModel):
    """Schema for updating a notification preference."""
    enabled: Optional[bool] = None
    delivery_method: Optional[str] = Field(None, max_length=50)


class NotificationPreferenceResponse(NotificationPreferenceBase):
    """Schema for notification preference response."""
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class NotificationPreferenceListResponse(BaseModel):
    """Schema for notification preferences list."""
    preferences: List[NotificationPreferenceResponse]
    total: int
    
    model_config = ConfigDict(from_attributes=True)


class BroadcastNotificationRequest(BaseModel):
    """Schema for broadcast notification request."""
    type: NotificationType
    title: str = Field(..., min_length=1, max_length=500)
    message: str = Field(..., min_length=1)
    target_roles: Optional[List[str]] = None
    data: Optional[Dict[str, Any]] = Field(default_factory=dict)
    priority: NotificationPriority = NotificationPriority.NORMAL
    persist: bool = True


class NotificationStatsResponse(BaseModel):
    """Schema for notification statistics."""
    total_notifications: int
    unread_count: int
    by_type: Dict[str, int]
    by_priority: Dict[str, int]
    recent_count: int  # Last 24 hours