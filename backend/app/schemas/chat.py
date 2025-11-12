"""Chat Pydantic schemas."""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field

from app.models.chat import MessageRole


class ChatSessionCreate(BaseModel):
    """Schema for creating a chat session."""
    title: str = Field(..., min_length=1, max_length=500)
    model: Optional[str] = Field(None, max_length=100)
    temperature: Optional[str] = "0.7"
    context_window_size: Optional[int] = 4096


class ChatSessionUpdate(BaseModel):
    """Schema for updating a chat session."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    model: Optional[str] = Field(None, max_length=100)
    temperature: Optional[str] = None
    is_active: Optional[bool] = None


class ChatSessionResponse(BaseModel):
    """Schema for chat session response."""
    id: int
    user_id: int
    title: str
    model: Optional[str]
    temperature: str
    context_window_size: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime
    message_count: int = 0
    
    class Config:
        from_attributes = True


class ChatMessageCreate(BaseModel):
    """Schema for creating a chat message."""
    content: str = Field(..., min_length=1)
    role: MessageRole = MessageRole.USER


class ChatMessageResponse(BaseModel):
    """Schema for chat message response."""
    id: int
    session_id: int
    user_id: int
    role: MessageRole
    content: str
    tokens: Optional[int]
    model: Optional[str]
    meta_data: Optional[dict]
    tool_execution_id: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatStreamRequest(BaseModel):
    """Schema for chat streaming request."""
    session_id: int
    message: str = Field(..., min_length=1)
    model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0, le=8192)
    tools_enabled: bool = True


class ChatStreamChunk(BaseModel):
    """Schema for chat stream chunk (SSE event)."""
    type: str  # "message", "tool_call", "tool_result", "error", "done"
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    tool_result: Optional[dict] = None
    error: Optional[str] = None
    message_id: Optional[int] = None
    tokens: Optional[int] = None


class ContextWindowResponse(BaseModel):
    """Schema for context window response."""
    id: int
    session_id: int
    total_tokens: int
    max_tokens: int
    usage_percentage: float
    is_near_limit: bool
    included_message_ids: List[int]
    strategy: str
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    """Schema for chat history response."""
    session: ChatSessionResponse
    messages: List[ChatMessageResponse]
    context_window: Optional[ContextWindowResponse]