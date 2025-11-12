"""
Context Window Manager for managing conversation history within token limits.
Handles intelligent truncation, summarization, and context preservation.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, MessageRole

logger = logging.getLogger(__name__)


class ContextWindowManager:
    """
    Manages conversation context to fit within model token limits.
    
    Features:
    - Token counting and estimation
    - Intelligent message truncation
    - System message preservation
    - Important context retention
    - Conversation summarization
    - Sliding window strategy
    """
    
    # Model context limits (in tokens) - Updated 2024
    MODEL_LIMITS = {
        # OpenAI
        "gpt-4": 128000,
        "gpt-4-turbo": 128000,
        "gpt-3.5-turbo": 16385,
        # Anthropic Claude 3
        "claude-3-opus": 200000,
        "claude-3-sonnet": 200000,
        "claude-3-haiku": 200000,
        # Meta Llama 3.1+ (128K context)
        "llama3": 128000,
        "llama3-70b": 128000,
        "llama3.1": 128000,
        "llama3.3": 128000,
        # Other models
        "mistral": 32000,
        "codellama": 16000,
    }
    
    # Reserve tokens for response
    RESPONSE_RESERVE = 2000
    
    def __init__(self, model_id: str = "gpt-3.5-turbo"):
        """
        Initialize context window manager.
        
        Args:
            model_id: Model identifier for token limit lookup
        """
        self.model_id = model_id
        self.max_tokens = self.MODEL_LIMITS.get(model_id, 4096)
        self.available_tokens = self.max_tokens - self.RESPONSE_RESERVE
        
        logger.info(
            f"ContextWindowManager initialized - Model: {model_id}, "
            f"Max: {self.max_tokens}, Available: {self.available_tokens}"
        )
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Simple estimation: ~4 characters per token.
        For production, use tiktoken for accurate counts.
        """
        return len(text) // 4
    
    def count_message_tokens(self, message: Dict[str, str]) -> int:
        """Count tokens in a single message."""
        # Account for message structure overhead (~4 tokens)
        role_tokens = 4
        content_tokens = self.estimate_tokens(message.get("content", ""))
        return role_tokens + content_tokens
    
    def count_messages_tokens(self, messages: List[Dict[str, str]]) -> int:
        """Count total tokens in message list."""
        return sum(self.count_message_tokens(msg) for msg in messages)
    
    def fits_in_window(
        self,
        messages: List[Dict[str, str]],
        new_message: Optional[str] = None
    ) -> bool:
        """Check if messages fit within context window."""
        total_tokens = self.count_messages_tokens(messages)
        
        if new_message:
            total_tokens += self.estimate_tokens(new_message)
        
        return total_tokens <= self.available_tokens
    
    def truncate_messages(
        self,
        messages: List[Dict[str, str]],
        strategy: str = "sliding"
    ) -> Tuple[List[Dict[str, str]], int]:
        """
        Truncate messages to fit within context window.
        
        Args:
            messages: List of message dicts
            strategy: Truncation strategy ('sliding', 'smart', 'summary')
            
        Returns:
            Tuple of (truncated_messages, tokens_removed)
        """
        if self.fits_in_window(messages):
            return messages, 0
        
        if strategy == "sliding":
            return self._sliding_window_truncate(messages)
        elif strategy == "smart":
            return self._smart_truncate(messages)
        elif strategy == "summary":
            return self._summary_truncate(messages)
        else:
            return self._sliding_window_truncate(messages)
    
    def _sliding_window_truncate(
        self,
        messages: List[Dict[str, str]]
    ) -> Tuple[List[Dict[str, str]], int]:
        """
        Use sliding window to keep most recent messages.
        
        Strategy:
        1. Always keep system messages
        2. Remove oldest user/assistant pairs
        3. Keep most recent N messages that fit
        """
        # Separate system messages from conversation
        system_msgs = [msg for msg in messages if msg["role"] == "system"]
        conv_msgs = [msg for msg in messages if msg["role"] != "system"]
        
        # Start with system messages
        kept_messages = system_msgs.copy()
        current_tokens = self.count_messages_tokens(kept_messages)
        
        # Add conversation messages from most recent
        for msg in reversed(conv_msgs):
            msg_tokens = self.count_message_tokens(msg)
            
            if current_tokens + msg_tokens <= self.available_tokens:
                kept_messages.append(msg)
                current_tokens += msg_tokens
            else:
                break
        
        # Maintain chronological order (except system messages stay first)
        conv_kept = [msg for msg in kept_messages if msg["role"] != "system"]
        conv_kept.reverse()
        kept_messages = system_msgs + conv_kept
        
        original_tokens = self.count_messages_tokens(messages)
        removed_tokens = original_tokens - current_tokens
        
        logger.info(
            f"Sliding window truncation: Kept {len(kept_messages)}/{len(messages)} messages, "
            f"Removed {removed_tokens} tokens"
        )
        
        return kept_messages, removed_tokens
    
    def _smart_truncate(
        self,
        messages: List[Dict[str, str]]
    ) -> Tuple[List[Dict[str, str]], int]:
        """
        Smart truncation preserving important context.
        
        Strategy:
        1. Keep system messages
        2. Keep first user message (context setter)
        3. Keep tool-related messages
        4. Keep most recent messages
        5. Remove middle conversation
        """
        if len(messages) <= 3:
            return self._sliding_window_truncate(messages)
        
        # Identify important messages
        system_msgs = [msg for msg in messages if msg["role"] == "system"]
        first_user = next((msg for msg in messages if msg["role"] == "user"), None)
        tool_msgs = [msg for msg in messages if msg.get("tool_name") or msg["role"] == "tool"]
        
        # Start with critical messages
        kept_messages = system_msgs.copy()
        if first_user:
            kept_messages.append(first_user)
        kept_messages.extend(tool_msgs)
        
        current_tokens = self.count_messages_tokens(kept_messages)
        
        # Add most recent messages
        recent_msgs = []
        for msg in reversed(messages):
            if msg not in kept_messages:
                msg_tokens = self.count_message_tokens(msg)
                if current_tokens + msg_tokens <= self.available_tokens:
                    recent_msgs.insert(0, msg)
                    current_tokens += msg_tokens
                else:
                    break
        
        kept_messages.extend(recent_msgs)
        
        original_tokens = self.count_messages_tokens(messages)
        removed_tokens = original_tokens - current_tokens
        
        logger.info(
            f"Smart truncation: Kept {len(kept_messages)}/{len(messages)} messages, "
            f"Removed {removed_tokens} tokens"
        )
        
        return kept_messages, removed_tokens
    
    def _summary_truncate(
        self,
        messages: List[Dict[str, str]]
    ) -> Tuple[List[Dict[str, str]], int]:
        """
        Truncate with summarization of removed context.
        
        Strategy:
        1. Keep system messages
        2. Summarize oldest messages
        3. Keep recent messages
        4. Insert summary as system message
        
        Note: This is a placeholder. In production, you'd use an LLM
        to generate actual summaries of the removed context.
        """
        # For now, fall back to smart truncation
        # In production, implement actual summarization
        logger.info("Summary truncation requested (using smart truncation as fallback)")
        return self._smart_truncate(messages)
    
    def prepare_messages_for_llm(
        self,
        messages: List[ChatMessage],
        include_system: bool = True,
        max_history: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Prepare database messages for LLM consumption.
        
        Args:
            messages: List of ChatMessage objects from database
            include_system: Whether to include system messages
            max_history: Maximum number of messages to include
            
        Returns:
            List of message dicts ready for LLM
        """
        llm_messages = []
        
        # Add system message if requested
        if include_system:
            llm_messages.append({
                "role": "system",
                "content": "You are a helpful AI assistant with access to various tools and data sources."
            })
        
        # Convert database messages
        for msg in messages[-max_history:] if max_history else messages:
            llm_messages.append({
                "role": msg.role.value,
                "content": msg.content,
                "name": msg.meta_data.get("name") if msg.meta_data else None
            })
        
        # Truncate if needed
        if not self.fits_in_window(llm_messages):
            llm_messages, _ = self.truncate_messages(llm_messages, strategy="smart")
        
        return llm_messages
    
    def get_context_stats(
        self,
        messages: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Get statistics about context usage.
        
        Returns:
            Dict with token counts, utilization, etc.
        """
        total_tokens = self.count_messages_tokens(messages)
        utilization = (total_tokens / self.available_tokens) * 100
        
        return {
            "total_tokens": total_tokens,
            "max_tokens": self.max_tokens,
            "available_tokens": self.available_tokens,
            "utilization_percent": round(utilization, 2),
            "fits_in_window": total_tokens <= self.available_tokens,
            "message_count": len(messages),
            "model_id": self.model_id
        }
    
    def should_truncate(
        self,
        messages: List[Dict[str, str]],
        threshold: float = 0.8
    ) -> bool:
        """
        Check if truncation is recommended.
        
        Args:
            messages: Message list to check
            threshold: Utilization threshold (0.0-1.0)
            
        Returns:
            True if utilization exceeds threshold
        """
        total_tokens = self.count_messages_tokens(messages)
        utilization = total_tokens / self.available_tokens
        return utilization >= threshold


def create_context_manager(model_id: str = "gpt-3.5-turbo") -> ContextWindowManager:
    """Factory function to create context manager for a model."""
    return ContextWindowManager(model_id=model_id)