"""Chat API endpoints with SSE streaming."""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.deps import get_current_user, get_db
from app.models.chat import ChatMessage, ChatSession, ContextWindow, MessageRole
from app.models.user import User
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatSessionUpdate,
    ChatStreamChunk,
    ChatStreamRequest,
    ContextWindowResponse,
)

router = APIRouter()


@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """Create a new chat session.
    
    Args:
        session_data: Chat session creation data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Created chat session
    """
    # Create chat session
    chat_session = ChatSession(
        user_id=current_user.id,
        title=session_data.title,
        model=session_data.model,
        temperature=session_data.temperature,
        context_window_size=session_data.context_window_size,
        is_active=True,
    )
    
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    
    # Create context window
    context_window = ContextWindow(
        session_id=chat_session.id,
        total_tokens=0,
        max_tokens=session_data.context_window_size,
        included_message_ids=[],
        strategy="sliding_window",
    )
    
    db.add(context_window)
    db.commit()
    
    return {
        **ChatSessionResponse.from_orm(chat_session).dict(),
        "message_count": 0,
    }


@router.get("/sessions", response_model=List[ChatSessionResponse])
def list_chat_sessions(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """List user's chat sessions.
    
    Args:
        skip: Number of sessions to skip
        limit: Maximum number of sessions to return
        active_only: Only return active sessions
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        List of chat sessions
    """
    query = db.query(ChatSession).filter(ChatSession.user_id == current_user.id)
    
    if active_only:
        query = query.filter(ChatSession.is_active == True)
    
    sessions = query.order_by(ChatSession.last_message_at.desc()).offset(skip).limit(limit).all()
    
    # Add message counts
    result = []
    for session in sessions:
        message_count = db.query(ChatMessage).filter(ChatMessage.session_id == session.id).count()
        result.append({
            **ChatSessionResponse.from_orm(session).dict(),
            "message_count": message_count,
        })
    
    return result


@router.get("/sessions/{session_id}", response_model=ChatHistoryResponse)
def get_chat_session(
    session_id: int,
    include_messages: bool = True,
    message_limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """Get chat session with message history.
    
    Args:
        session_id: Chat session ID
        include_messages: Include message history
        message_limit: Maximum number of messages to return
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Chat session with history
        
    Raises:
        HTTPException: If session not found or not owned by user
    """
    # Get session
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    # Get messages
    messages = []
    if include_messages:
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.desc()).limit(message_limit).all()
        messages = list(reversed(messages))  # Chronological order
    
    # Get context window
    context_window = db.query(ContextWindow).filter(
        ContextWindow.session_id == session_id
    ).first()
    
    return {
        "session": {
            **ChatSessionResponse.from_orm(session).dict(),
            "message_count": len(messages),
        },
        "messages": [ChatMessageResponse.from_orm(msg) for msg in messages],
        "context_window": ContextWindowResponse.from_orm(context_window) if context_window else None,
    }


@router.put("/sessions/{session_id}", response_model=ChatSessionResponse)
def update_chat_session(
    session_id: int,
    session_update: ChatSessionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """Update chat session.
    
    Args:
        session_id: Chat session ID
        session_update: Update data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Updated chat session
        
    Raises:
        HTTPException: If session not found or not owned by user
    """
    # Get session
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    # Update fields
    update_data = session_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(session, field, value)
    
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    
    message_count = db.query(ChatMessage).filter(ChatMessage.session_id == session.id).count()
    
    return {
        **ChatSessionResponse.from_orm(session).dict(),
        "message_count": message_count,
    }


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete chat session and all its messages.
    
    Args:
        session_id: Chat session ID
        current_user: Current authenticated user
        db: Database session
        
    Raises:
        HTTPException: If session not found or not owned by user
    """
    # Get session
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    # Delete session (cascade will delete messages and context window)
    db.delete(session)
    db.commit()


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
def create_chat_message(
    session_id: int,
    message_data: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """Create a chat message (non-streaming).
    
    Args:
        session_id: Chat session ID
        message_data: Message data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Created message
        
    Raises:
        HTTPException: If session not found or not owned by user
    """
    # Verify session ownership
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    # Create message
    message = ChatMessage(
        session_id=session_id,
        user_id=current_user.id,
        role=message_data.role,
        content=message_data.content,
    )
    
    db.add(message)
    
    # Update session last_message_at
    session.last_message_at = datetime.utcnow()
    
    db.commit()
    db.refresh(message)
    
    return message


async def stream_chat_response(
    session_id: int,
    user_message: str,
    current_user: User,
    db: Session,
    model: str = "gpt-3.5-turbo",
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Stream chat response using SSE.
    
    This is a placeholder implementation that demonstrates the streaming pattern.
    In production, this would integrate with actual LLM providers.
    
    Args:
        session_id: Chat session ID
        user_message: User's message
        current_user: Current user
        db: Database session
        model: LLM model to use
        temperature: Temperature parameter
        
    Yields:
        SSE formatted chat chunks
    """
    try:
        # Save user message
        user_msg = ChatMessage(
            session_id=session_id,
            user_id=current_user.id,
            role=MessageRole.USER,
            content=user_message,
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)
        
        # Send user message confirmation
        yield f"data: {json.dumps(ChatStreamChunk(type='message', message_id=user_msg.id).dict())}\n\n"
        
        # Fetch chat history from database
        history = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at).all()
        
        # Stream response from LLM
        from app.services.llm_service import llm_service
        from app.services.context_manager import create_context_manager
        
        # Create context manager for model
        context_mgr = create_context_manager(model or "gpt-3.5-turbo")
        
        # Prepare messages with context window management
        llm_messages = context_mgr.prepare_messages_for_llm(history, include_system=True)
        
        # Add current user message
        llm_messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Log context stats
        stats = context_mgr.get_context_stats(llm_messages)
        logger.info(
            f"Context window stats: {stats['total_tokens']}/{stats['max_tokens']} tokens "
            f"({stats['utilization_percent']}% utilization)"
        )
        
        # Stream from LLM
        assistant_response = ""
        async for llm_chunk in llm_service.stream_chat(
            model_id=model or "gpt-3.5-turbo",
            messages=llm_messages,
            temperature=temperature
        ):
            if llm_chunk["type"] == "content":
                content = llm_chunk["content"]
                assistant_response += content
                
                chunk = ChatStreamChunk(
                    type="message",
                    content=content,
                )
                yield f"data: {json.dumps(chunk.dict())}\n\n"
            
            elif llm_chunk["type"] == "error":
                error_chunk = ChatStreamChunk(
                    type="error",
                    error=llm_chunk["error"],
                )
                yield f"data: {json.dumps(error_chunk.dict())}\n\n"
                return
        
        # Save assistant message
        assistant_msg = ChatMessage(
            session_id=session_id,
            user_id=current_user.id,
            role=MessageRole.ASSISTANT,
            content=assistant_response,
            model=model,
        )
        db.add(assistant_msg)
        
        # Update session
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session:
            session.last_message_at = datetime.utcnow()
        
        db.commit()
        db.refresh(assistant_msg)
        
        # Send completion
        completion_chunk = ChatStreamChunk(
            type="done",
            message_id=assistant_msg.id,
            content=assistant_response,
        )
        yield f"data: {json.dumps(completion_chunk.dict())}\n\n"
        
    except Exception as e:
        error_chunk = ChatStreamChunk(
            type="error",
            error=str(e),
        )
        yield f"data: {json.dumps(error_chunk.dict())}\n\n"


@router.post("/stream")
async def stream_chat(
    request: ChatStreamRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream chat response using Server-Sent Events (SSE).
    
    Args:
        request: Chat stream request
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        SSE stream response
        
    Raises:
        HTTPException: If session not found or not owned by user
    """
    # Verify session ownership
    session = db.query(ChatSession).filter(
        ChatSession.id == request.session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    # Use session model or request model
    model = request.model or session.model or "gpt-3.5-turbo"
    temperature = request.temperature if request.temperature is not None else float(session.temperature)
    
    return StreamingResponse(
        stream_chat_response(
            session_id=request.session_id,
            user_message=request.message,
            current_user=current_user,
            db=db,
            model=model,
            temperature=temperature,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/sessions/{session_id}/context", response_model=ContextWindowResponse)
def get_context_window(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Any:
    """Get context window information for a session.
    
    Args:
        session_id: Chat session ID
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Context window information
        
    Raises:
        HTTPException: If session not found or not owned by user
    """
    # Verify session ownership
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id,
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found",
        )
    
    # Get context window
    context_window = db.query(ContextWindow).filter(
        ContextWindow.session_id == session_id
    ).first()
    
    if not context_window:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Context window not found",
        )
    
    return context_window