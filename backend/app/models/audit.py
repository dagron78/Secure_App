"""Audit logging models."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class AuditAction(str, enum.Enum):
    """Audit action types."""
    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"
    
    # User management
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_ROLE_ASSIGN = "user_role_assign"
    USER_ROLE_REMOVE = "user_role_remove"
    
    # Tool execution
    TOOL_EXECUTE = "tool_execute"
    TOOL_APPROVE = "tool_approve"
    TOOL_REJECT = "tool_reject"
    TOOL_CANCEL = "tool_cancel"
    
    # Data access
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"
    
    # Secrets management
    SECRET_CREATE = "secret_create"
    SECRET_READ = "secret_read"
    SECRET_UPDATE = "secret_update"
    SECRET_DELETE = "secret_delete"
    
    # Chat
    CHAT_CREATE = "chat_create"
    CHAT_DELETE = "chat_delete"
    MESSAGE_SEND = "message_send"
    
    # System
    SYSTEM_CONFIG_CHANGE = "system_config_change"
    SYSTEM_ERROR = "system_error"
    API_CALL = "api_call"


class AuditLog(Base):
    """Audit log model for compliance and security tracking."""
    
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # User context
    user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    username = Column(String(100), nullable=True, index=True)  # Denormalized for historical record
    
    # Action details
    action = Column(SQLEnum(AuditAction), nullable=False, index=True)
    resource_type = Column(String(50), nullable=True, index=True)  # e.g., 'tool', 'secret', 'user'
    resource_id = Column(String(100), nullable=True, index=True)
    
    # Request context
    ip_address = Column(String(45), nullable=True, index=True)  # IPv6 compatible
    user_agent = Column(String(500), nullable=True)
    session_id = Column(String(255), nullable=True, index=True)
    
    # Action metadata
    details = Column(JSON, nullable=True)  # Additional context
    changes = Column(JSON, nullable=True)  # Before/after for updates
    
    # Result
    success = Column(String(20), nullable=False, default="success", index=True)  # success, failure, error
    error_message = Column(Text, nullable=True)
    
    # Associated tool execution (if applicable)
    tool_execution_id = Column(Integer, ForeignKey('tool_executions.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # Compliance flags
    sensitive_data = Column(String(20), nullable=False, default="false", index=True)  # For GDPR/compliance
    retention_days = Column(Integer, default=2555)  # 7 years default for compliance
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    tool_execution = relationship("ToolExecution", back_populates="audit_logs")
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, user={self.username}, action={self.action}, success={self.success})>"
    
    @property
    def age_days(self) -> int:
        """Calculate age of log entry in days."""
        return (datetime.utcnow() - self.created_at).days
    
    @property
    def should_be_retained(self) -> bool:
        """Check if log should still be retained."""
        return self.age_days < self.retention_days


class SystemMetric(Base):
    """System metrics for monitoring and performance tracking."""
    
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, index=True)
    
    # Metric details
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(String(50), nullable=False)
    metric_unit = Column(String(20), nullable=True)
    
    # Context
    component = Column(String(50), nullable=True, index=True)  # e.g., 'api', 'worker', 'database'
    tags = Column(JSON, nullable=True)  # Additional tags for filtering
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self) -> str:
        return f"<SystemMetric(id={self.id}, metric={self.metric_name}, value={self.metric_value})>"