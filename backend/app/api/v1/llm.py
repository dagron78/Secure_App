"""
LLM Gateway API endpoints.
Manages LLM models, configurations, and connections.
"""
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.models.audit import AuditLog
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm"])


# Schemas
class LLMModelResponse(BaseModel):
    """Schema for LLM model information."""
    id: str
    name: str
    provider: str
    context_window: Optional[int] = None
    supports_tools: Optional[bool] = None
    supports_vision: Optional[bool] = None
    available: bool


class LLMModelListResponse(BaseModel):
    """Schema for list of LLM models."""
    models: List[LLMModelResponse]
    total: int


class LLMTestRequest(BaseModel):
    """Schema for testing LLM model."""
    prompt: str = Field(default="Hello, how are you?", max_length=500)


class LLMTestResponse(BaseModel):
    """Schema for LLM test result."""
    model_id: str
    success: bool
    response: Optional[str] = None
    error: Optional[str] = None
    latency_ms: Optional[float] = None


class LLMStatusResponse(BaseModel):
    """Schema for LLM gateway status."""
    total_models: int
    available_models: int
    providers: List[str]
    default_model: Optional[str] = None


# Endpoints

@router.get("/models", response_model=LLMModelListResponse)
async def list_models(
    current_user: User = Depends(get_current_user)
):
    """
    List all available LLM models.
    
    Returns models from all configured providers:
    - OpenAI (GPT-4, GPT-3.5-turbo)
    - Anthropic (Claude 3 family)
    - Local Ollama models
    """
    try:
        models = llm_service.list_models()
        
        # Get detailed info for each model
        detailed_models = []
        for model in models:
            info = await llm_service.get_model_info(model["id"])
            if info:
                detailed_models.append(LLMModelResponse(**info))
        
        return {
            "models": detailed_models,
            "total": len(detailed_models)
        }
        
    except Exception as e:
        logger.error(f"Error listing models: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_id}", response_model=LLMModelResponse)
async def get_model(
    model_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed information about a specific model."""
    try:
        info = await llm_service.get_model_info(model_id)
        
        if not info:
            raise HTTPException(
                status_code=404,
                detail=f"Model '{model_id}' not found"
            )
        
        return LLMModelResponse(**info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model {model_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/{model_id}/test", response_model=LLMTestResponse)
async def test_model(
    model_id: str,
    request: LLMTestRequest = LLMTestRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Test a model by sending a simple prompt.
    
    Verifies:
    - Model availability
    - API connectivity
    - Response latency
    """
    try:
        start_time = datetime.utcnow()
        
        # Check if model exists
        if not llm_service.get_provider(model_id):
            raise HTTPException(
                status_code=404,
                detail=f"Model '{model_id}' not found"
            )
        
        # Test the model
        messages = [{"role": "user", "content": request.prompt}]
        response_text = ""
        error = None
        
        try:
            async for chunk in llm_service.stream_chat(
                model_id=model_id,
                messages=messages,
                temperature=0.7,
                max_tokens=100
            ):
                if chunk["type"] == "content":
                    response_text += chunk["content"]
                elif chunk["type"] == "error":
                    error = chunk["error"]
                    break
            
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Audit log
            audit = AuditLog(
                user_id=current_user.id,
                action="llm.test",
                resource_type="llm",
                resource_id=model_id,
                details={
                    "model_id": model_id,
                    "success": error is None,
                    "latency_ms": latency
                }
            )
            db.add(audit)
            db.commit()
            
            return LLMTestResponse(
                model_id=model_id,
                success=error is None,
                response=response_text if response_text else None,
                error=error,
                latency_ms=latency
            )
            
        except Exception as e:
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"Error testing model {model_id}: {str(e)}", exc_info=True)
            
            return LLMTestResponse(
                model_id=model_id,
                success=False,
                error=str(e),
                latency_ms=latency
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in test endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=LLMStatusResponse)
async def get_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get LLM gateway status.
    
    Returns:
    - Total number of registered models
    - Available models
    - Active providers
    - Default model
    """
    try:
        models = llm_service.list_models()
        
        # Get unique providers
        providers = list(set(model["provider"] for model in models))
        
        # Count available models
        available = sum(1 for model in models if model["available"])
        
        return LLMStatusResponse(
            total_models=len(models),
            available_models=available,
            providers=providers,
            default_model="gpt-3.5-turbo"  # Default fallback
        )
        
    except Exception as e:
        logger.error(f"Error getting LLM status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers")
async def list_providers(
    current_user: User = Depends(get_current_user)
):
    """
    List all configured LLM providers.
    
    Returns information about each provider including:
    - Name and status
    - Available models
    - API connectivity
    """
    try:
        models = llm_service.list_models()
        
        # Group models by provider
        providers_dict = {}
        for model in models:
            provider = model["provider"]
            if provider not in providers_dict:
                providers_dict[provider] = {
                    "name": provider,
                    "models": [],
                    "available": True
                }
            providers_dict[provider]["models"].append(model["id"])
        
        providers = list(providers_dict.values())
        
        return {
            "providers": providers,
            "total": len(providers)
        }
        
    except Exception as e:
        logger.error(f"Error listing providers: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))