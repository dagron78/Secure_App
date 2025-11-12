"""Database models for CDSA Backend."""
from app.db.base import Base
from app.models.user import User, Role, Permission, Session
from app.models.chat import ChatSession, ChatMessage, ContextWindow, MessageRole
from app.models.tool import (
    Tool,
    ToolExecution,
    ToolApproval,
    ToolCache,
    ToolStatus,
    ExecutionStatus,
    ApprovalStatus,
    ToolCategory,
    ToolExecutionStatus,  # Backward compatibility alias
)
from app.models.audit import AuditLog, AuditAction, SystemMetric
from app.models.secret import Secret, SecretVersion, SecretAccessLog, SecretType
from app.models.document import (
    Document,
    DocumentChunk,
    SearchResult,
    EmbeddingModel,
)
from app.models.notification import (
    Notification,
    NotificationPreference,
    NotificationType,
    NotificationPriority,
)

__all__ = [
    # Base
    "Base",
    # User & Auth
    "User",
    "Role",
    "Permission",
    "Session",
    # Chat
    "ChatSession",
    "ChatMessage",
    "ContextWindow",
    "MessageRole",
    # Tools
    "Tool",
    "ToolExecution",
    "ToolApproval",
    "ToolCache",
    "ToolStatus",
    "ExecutionStatus",
    "ApprovalStatus",
    "ToolCategory",
    "ToolExecutionStatus",  # Backward compatibility
    # Audit
    "AuditLog",
    "AuditAction",
    "SystemMetric",
    # Secrets
    "Secret",
    "SecretVersion",
    "SecretAccessLog",
    "SecretType",
    # Documents & RAG
    "Document",
    "DocumentChunk",
    "SearchResult",
    "EmbeddingModel",
    # Notifications
    "Notification",
    "NotificationPreference",
    "NotificationType",
    "NotificationPriority",
]