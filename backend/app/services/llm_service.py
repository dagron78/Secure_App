"""
LLM Service for unified interface to multiple AI providers.
Supports OpenAI, Anthropic, Google Gemini, and local Ollama models.
"""
import logging
from typing import List, Dict, Any, Optional, AsyncIterator
from datetime import datetime
import asyncio

import openai

try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)


class LLMProvider:
    """Base class for LLM providers."""
    
    def __init__(self, model_id: str, **kwargs):
        self.model_id = model_id
        self.kwargs = kwargs
    
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream completion from LLM."""
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """OpenAI API provider (GPT-4, GPT-3.5, etc.)."""
    
    def __init__(self, model_id: str, api_key: Optional[str] = None):
        super().__init__(model_id)
        self.client = openai.AsyncOpenAI(api_key=api_key or settings.OPENAI_API_KEY)
        logger.info(f"Initialized OpenAI provider with model: {model_id}")
    
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream completion from OpenAI."""
        try:
            params = {
                "model": self.model_id,
                "messages": messages,
                "temperature": temperature,
                "stream": True,
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            
            if tools:
                params["tools"] = tools
                params["tool_choice"] = "auto"
            
            stream = await self.client.chat.completions.create(**params)
            
            async for chunk in stream:
                if not chunk.choices:
                    continue
                
                choice = chunk.choices[0]
                delta = choice.delta
                
                # Handle content
                if delta.content:
                    yield {
                        "type": "content",
                        "content": delta.content,
                        "finish_reason": choice.finish_reason
                    }
                
                # Handle tool calls
                if delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        yield {
                            "type": "tool_call",
                            "tool_call": {
                                "id": tool_call.id,
                                "name": tool_call.function.name if tool_call.function else None,
                                "arguments": tool_call.function.arguments if tool_call.function else None
                            }
                        }
                
                # Handle finish
                if choice.finish_reason:
                    yield {
                        "type": "done",
                        "finish_reason": choice.finish_reason
                    }
                    
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            yield {"type": "error", "error": str(e)}
        except Exception as e:
            logger.error(f"Error streaming from OpenAI: {str(e)}", exc_info=True)
            yield {"type": "error", "error": str(e)}


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""
    
    def __init__(self, model_id: str, api_key: Optional[str] = None):
        super().__init__(model_id)
        self.client = AsyncAnthropic(api_key=api_key or settings.ANTHROPIC_API_KEY)
        logger.info(f"Initialized Anthropic provider with model: {model_id}")
    
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream completion from Anthropic."""
        try:
            # Convert OpenAI-style messages to Anthropic format
            system_message = None
            anthropic_messages = []
            
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    anthropic_messages.append({
                        "role": msg["role"],
                        "content": msg["content"]
                    })
            
            params = {
                "model": self.model_id,
                "messages": anthropic_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,
                "stream": True
            }
            
            if system_message:
                params["system"] = system_message
            
            if tools:
                # Convert tools to Anthropic format
                params["tools"] = self._convert_tools(tools)
            
            async with self.client.messages.stream(**params) as stream:
                async for event in stream:
                    if hasattr(event, 'type'):
                        if event.type == "content_block_delta":
                            if hasattr(event.delta, 'text'):
                                yield {
                                    "type": "content",
                                    "content": event.delta.text,
                                    "finish_reason": None
                                }
                        elif event.type == "message_stop":
                            yield {
                                "type": "done",
                                "finish_reason": "stop"
                            }
                            
        except Exception as e:
            logger.error(f"Error streaming from Anthropic: {str(e)}", exc_info=True)
            yield {"type": "error", "error": str(e)}
    
    def _convert_tools(self, tools: List[Dict]) -> List[Dict]:
        """Convert OpenAI tool format to Anthropic format."""
        anthropic_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {})
                })
        return anthropic_tools


class OllamaProvider(LLMProvider):
    """Ollama local model provider."""
    
    def __init__(self, model_id: str, base_url: Optional[str] = None):
        super().__init__(model_id)
        self.base_url = base_url or settings.OLLAMA_BASE_URL or "http://localhost:11434"
        self.client = httpx.AsyncClient(timeout=60.0)
        logger.info(f"Initialized Ollama provider with model: {model_id} at {self.base_url}")
    
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream completion from Ollama."""
        try:
            url = f"{self.base_url}/api/chat"
            
            payload = {
                "model": self.model_id,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": temperature,
                }
            }
            
            if max_tokens:
                payload["options"]["num_predict"] = max_tokens
            
            async with self.client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    error_msg = await response.aread()
                    logger.error(f"Ollama error: {error_msg}")
                    yield {"type": "error", "error": f"HTTP {response.status_code}"}
                    return
                
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    
                    try:
                        import json
                        data = json.loads(line)
                        
                        if "message" in data and "content" in data["message"]:
                            yield {
                                "type": "content",
                                "content": data["message"]["content"],
                                "finish_reason": None
                            }
                        
                        if data.get("done", False):
                            yield {
                                "type": "done",
                                "finish_reason": "stop"
                            }
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing Ollama response: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error streaming from Ollama: {str(e)}", exc_info=True)
            yield {"type": "error", "error": str(e)}
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()


class LLMService:
    """
    Unified LLM service for managing multiple AI providers.
    
    Supports:
    - OpenAI (GPT-4, GPT-3.5-turbo, etc.)
    - Anthropic (Claude 3 Opus, Sonnet, Haiku)
    - Google Gemini (via OpenAI-compatible API)
    - Ollama (Local models: Llama 3, Mistral, etc.)
    """
    
    def __init__(self):
        self.providers: Dict[str, LLMProvider] = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available LLM providers."""
        # OpenAI models
        if settings.OPENAI_API_KEY:
            self.providers["gpt-4"] = OpenAIProvider("gpt-4-turbo-preview")
            self.providers["gpt-4-turbo"] = OpenAIProvider("gpt-4-turbo-preview")
            self.providers["gpt-3.5-turbo"] = OpenAIProvider("gpt-3.5-turbo")
            logger.info("OpenAI models registered")
        
        # Anthropic models
        if settings.ANTHROPIC_API_KEY:
            self.providers["claude-3-opus"] = AnthropicProvider("claude-3-opus-20240229")
            self.providers["claude-3-sonnet"] = AnthropicProvider("claude-3-sonnet-20240229")
            self.providers["claude-3-haiku"] = AnthropicProvider("claude-3-haiku-20240307")
            logger.info("Anthropic models registered")
        
        # Ollama local models
        try:
            # Try to connect to Ollama
            self.providers["llama3"] = OllamaProvider("llama3:8b")
            self.providers["llama3-70b"] = OllamaProvider("llama3:70b")
            self.providers["mistral"] = OllamaProvider("mistral:latest")
            self.providers["codellama"] = OllamaProvider("codellama:latest")
            logger.info("Ollama models registered")
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
    
    def get_provider(self, model_id: str) -> Optional[LLMProvider]:
        """Get provider for a specific model."""
        return self.providers.get(model_id)
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all available models."""
        models = []
        for model_id, provider in self.providers.items():
            provider_name = provider.__class__.__name__.replace("Provider", "")
            models.append({
                "id": model_id,
                "name": model_id,
                "provider": provider_name,
                "available": True
            })
        return models
    
    async def stream_chat(
        self,
        model_id: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream chat completion from specified model.
        
        Args:
            model_id: Model identifier (e.g., 'gpt-4', 'claude-3-opus', 'llama3')
            messages: Chat messages in OpenAI format
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            tools: Optional tool definitions for function calling
            
        Yields:
            Stream chunks with type and content
        """
        provider = self.get_provider(model_id)
        
        if not provider:
            logger.error(f"Model not found: {model_id}")
            yield {
                "type": "error",
                "error": f"Model '{model_id}' not available. Use /api/v1/llm/models to see available models."
            }
            return
        
        try:
            async for chunk in provider.stream_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                **kwargs
            ):
                yield chunk
                
        except Exception as e:
            logger.error(f"Error in LLM stream: {str(e)}", exc_info=True)
            yield {"type": "error", "error": str(e)}
    
    async def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific model."""
        provider = self.get_provider(model_id)
        if not provider:
            return None
        
        provider_name = provider.__class__.__name__.replace("Provider", "")
        
        # Model capabilities and limits
        capabilities = {
            "gpt-4": {"context": 128000, "supports_tools": True, "supports_vision": True},
            "gpt-4-turbo": {"context": 128000, "supports_tools": True, "supports_vision": True},
            "gpt-3.5-turbo": {"context": 16385, "supports_tools": True, "supports_vision": False},
            "claude-3-opus": {"context": 200000, "supports_tools": True, "supports_vision": True},
            "claude-3-sonnet": {"context": 200000, "supports_tools": True, "supports_vision": True},
            "claude-3-haiku": {"context": 200000, "supports_tools": True, "supports_vision": True},
            "llama3": {"context": 8192, "supports_tools": False, "supports_vision": False},
            "llama3-70b": {"context": 8192, "supports_tools": False, "supports_vision": False},
            "mistral": {"context": 32000, "supports_tools": False, "supports_vision": False},
            "codellama": {"context": 16000, "supports_tools": False, "supports_vision": False},
        }
        
        info = capabilities.get(model_id, {"context": 4096, "supports_tools": False, "supports_vision": False})
        
        return {
            "id": model_id,
            "name": model_id,
            "provider": provider_name,
            "context_window": info["context"],
            "supports_tools": info["supports_tools"],
            "supports_vision": info["supports_vision"],
            "available": True
        }


# Create singleton instance
llm_service = LLMService()