"""Tool execution and approval models."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean, JSON, Enum as SQLEnum, Float
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class ToolStatus(str, enum.Enum):
    """Tool registration status enum."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class ExecutionStatus(str, enum.Enum):
    """Tool execution status enum."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(str, enum.Enum):
    """Approval request status enum."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ToolCategory(str, enum.Enum):
    """Tool category enum."""
    DATA_ACCESS = "data_access"
    DATA_ANALYSIS = "data_analysis"
    FILE_OPERATIONS = "file_operations"
    API_CALLS = "api_calls"
    CODE_EXECUTION = "code_execution"
    SYSTEM_COMMANDS = "system_commands"
    DATABASE_OPERATIONS = "database_operations"


# Keep old name for backward compatibility
ToolExecutionStatus = ExecutionStatus


class Tool(Base):
    """Tool definition model."""
    
    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True, index=True)
    
    # Tool configuration
    config = Column(JSON, nullable=True)
    input_schema = Column(JSON, nullable=True)
    output_schema = Column(JSON, nullable=True)
    requires_approval = Column(Boolean, default=False, nullable=False)
    is_dangerous = Column(Boolean, default=False, nullable=False)
    
    # Tool status
    status = Column(SQLEnum(ToolStatus), default=ToolStatus.ACTIVE, nullable=False, index=True)
    
    # Execution limits
    timeout_seconds = Column(Integer, default=300)
    max_retries = Column(Integer, default=3)
    
    # Statistics
    execution_count = Column(Integer, default=0, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    failure_count = Column(Integer, default=0, nullable=False)
    avg_execution_time = Column(Float, nullable=True)
    last_executed_at = Column(DateTime, nullable=True)
    
    # Ownership
    created_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    executions = relationship("ToolExecution", back_populates="tool", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Tool(id={self.id}, name={self.name}, status={self.status})>"


class ToolExecution(Base):
    """Tool execution model."""
    
    __tablename__ = "tool_executions"

    id = Column(Integer, primary_key=True, index=True)
    tool_id = Column(Integer, ForeignKey('tools.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=True, index=True)
    
    # Execution details
    status = Column(SQLEnum(ExecutionStatus), default=ExecutionStatus.PENDING, nullable=False, index=True)
    input_data = Column(JSON, nullable=False)  # Tool input parameters
    output_data = Column(JSON, nullable=True)  # Tool execution result
    error_message = Column(Text, nullable=True)  # Error message if failed
    
    # Execution metadata
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    execution_time = Column(Float, nullable=True)  # Execution time in seconds
    retry_count = Column(Integer, default=0, nullable=False)
    
    # Approval tracking (if required)
    requires_approval = Column(Boolean, default=False, nullable=False)
    approval_id = Column(Integer, ForeignKey('tool_approvals.id', ondelete='SET NULL'), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    tool = relationship("Tool", back_populates="executions")
    user = relationship("User")
    session = relationship("ChatSession")
    approval = relationship("ToolApproval", back_populates="execution", foreign_keys=[approval_id])
    chat_messages = relationship("ChatMessage", back_populates="tool_execution", foreign_keys="ChatMessage.tool_execution_id")
    audit_logs = relationship("AuditLog", back_populates="tool_execution")
    
    def __repr__(self) -> str:
        return f"<ToolExecution(id={self.id}, tool_id={self.tool_id}, status={self.status})>"
    
    @property
    def is_pending(self) -> bool:
        """Check if execution is pending approval."""
        return self.status == ExecutionStatus.PENDING
    
    @property
    def is_running(self) -> bool:
        """Check if execution is currently running."""
        return self.status == ExecutionStatus.RUNNING
    
    @property
    def is_complete(self) -> bool:
        """Check if execution is complete (success or failure)."""
        return self.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]


class ToolApproval(Base):
    """Tool execution approval model."""
    
    __tablename__ = "tool_approvals"

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey('tool_executions.id', ondelete='CASCADE'), nullable=False, index=True)
    requested_by = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)  # User requesting approval
    
    # Approval details
    status = Column(SQLEnum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False, index=True)
    approved_by = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    reason = Column(Text, nullable=True)  # Reason for approval request
    notes = Column(Text, nullable=True)  # Approver notes
    
    # Timestamps
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    responded_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)  # Approval request expiration
    
    # Relationships
    execution = relationship("ToolExecution", back_populates="approval", foreign_keys=[execution_id])
    user = relationship("User", foreign_keys=[requested_by], back_populates="tool_approvals")
    approver = relationship("User", foreign_keys=[approved_by])
    
    def __repr__(self) -> str:
        return f"<ToolApproval(id={self.id}, execution_id={self.execution_id}, status={self.status})>"
    
    @property
    def is_pending(self) -> bool:
        """Check if approval is still pending."""
        return self.status == ApprovalStatus.PENDING
    
    @property
    def is_expired(self) -> bool:
        """Check if approval request has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at and self.status == ApprovalStatus.PENDING


class ToolCache(Base):
    """Tool execution result cache model."""
    
    __tablename__ = "tool_cache"

    id = Column(Integer, primary_key=True, index=True)
    tool_id = Column(Integer, ForeignKey('tools.id', ondelete='CASCADE'), nullable=False, index=True)
    cache_key = Column(String(255), unique=True, nullable=False, index=True)
    input_hash = Column(String(64), nullable=False, index=True)
    
    # Cached data
    output_data = Column(JSON, nullable=False)
    
    # Cache metadata
    hit_count = Column(Integer, default=0, nullable=False)
    last_hit_at = Column(DateTime, nullable=True)
    
    # Cache expiration
    expires_at = Column(DateTime, nullable=True, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<ToolCache(id={self.id}, tool_id={self.tool_id}, hits={self.hit_count})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at