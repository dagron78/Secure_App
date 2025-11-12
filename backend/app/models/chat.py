"""Chat and conversation models."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base


class MessageRole(str, enum.Enum):
    """Message role enum."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ChatSession(Base):
    """Chat session model for grouping related messages."""
    
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    
    # Session metadata
    context_window_size = Column(Integer, default=4096)
    model = Column(String(100))  # LLM model used
    temperature = Column(String(10), default="0.7")
    
    # Session status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_message_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan", order_by="ChatMessage.created_at")
    
    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, user_id={self.user_id}, title={self.title})>"


class ChatMessage(Base):
    """Chat message model."""
    
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # Message content
    role = Column(SQLEnum(MessageRole), nullable=False, index=True)
    content = Column(Text, nullable=False)
    
    # Message metadata
    tokens = Column(Integer)  # Token count for this message
    model = Column(String(100))  # LLM model that generated this (for assistant messages)
    meta_data = Column(JSON)  # Additional metadata (tool calls, citations, etc.)
    
    # Tool execution reference (if this message triggered a tool)
    tool_execution_id = Column(Integer, ForeignKey('tool_executions.id', ondelete='SET NULL'), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    session = relationship("ChatSession", back_populates="messages")
    user = relationship("User", back_populates="chat_messages")
    tool_execution = relationship("ToolExecution", back_populates="chat_messages", foreign_keys=[tool_execution_id])
    
    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, session_id={self.session_id}, role={self.role})>"


class ContextWindow(Base):
    """Context window tracking for managing token limits."""
    
    __tablename__ = "context_windows"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey('chat_sessions.id', ondelete='CASCADE'), nullable=False, index=True, unique=True)
    
    # Token tracking
    total_tokens = Column(Integer, default=0, nullable=False)
    max_tokens = Column(Integer, default=4096, nullable=False)
    
    # Message tracking
    included_message_ids = Column(JSON)  # List of message IDs currently in context
    
    # Strategy
    strategy = Column(String(50), default="sliding_window")  # sliding_window, summarization, hybrid
    
    # Timestamps
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self) -> str:
        return f"<ContextWindow(id={self.id}, session_id={self.session_id}, tokens={self.total_tokens}/{self.max_tokens})>"
    
    @property
    def usage_percentage(self) -> float:
        """Calculate context window usage percentage."""
        if self.max_tokens == 0:
            return 0.0
        return (self.total_tokens / self.max_tokens) * 100
    
    @property
    def is_near_limit(self) -> bool:
        """Check if context window is near limit (>80%)."""
        return self.usage_percentage > 80