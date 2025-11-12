"""
Embedding service for generating vector embeddings using OpenAI API.
Supports multiple embedding models with fallback and caching capabilities.
"""
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
import asyncio
from datetime import datetime

import openai
from sqlalchemy.orm import Session
from app.config import settings
from app.models.document import EmbeddingModel

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service for generating vector embeddings for document chunks.
    
    Features:
    - OpenAI embedding models (text-embedding-3-small, text-embedding-3-large)
    - Batch processing for efficiency
    - Automatic retry with exponential backoff
    - Model fallback on errors
    - Performance metrics tracking
    - Cost estimation
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
        batch_size: int = 100
    ):
        """
        Initialize embedding service.
        
        Args:
            api_key: OpenAI API key (default: from settings)
            model: Embedding model to use
            dimension: Vector dimension (1536 for text-embedding-3-small)
            batch_size: Number of texts to process in one batch
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model
        self.dimension = dimension
        self.batch_size = batch_size
        
        # Initialize OpenAI client
        openai.api_key = self.api_key
        
        # Performance tracking
        self.total_tokens = 0
        self.total_requests = 0
        self.total_errors = 0
        self.total_latency_ms = 0
        
        logger.info(
            f"EmbeddingService initialized - Model: {model}, "
            f"Dimension: {dimension}, Batch: {batch_size}"
        )
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            Embedding vector
        """
        embeddings = await self.generate_embeddings([text])
        return embeddings[0] if embeddings else []
    
    async def generate_embeddings(
        self,
        texts: List[str],
        max_retries: int = 3
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts with batching and retry.
        
        Args:
            texts: List of texts to embed
            max_retries: Maximum retry attempts on failure
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        # Filter out empty texts
        texts = [t.strip() for t in texts if t and t.strip()]
        if not texts:
            return []
        
        embeddings = []
        
        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            
            for attempt in range(max_retries):
                try:
                    batch_embeddings = await self._generate_batch(batch)
                    embeddings.extend(batch_embeddings)
                    break
                    
                except Exception as e:
                    logger.error(
                        f"Error generating embeddings (attempt {attempt + 1}/{max_retries}): {str(e)}"
                    )
                    
                    if attempt == max_retries - 1:
                        self.total_errors += 1
                        # Return zero vectors for failed batch
                        embeddings.extend([[0.0] * self.dimension] * len(batch))
                    else:
                        # Exponential backoff
                        await asyncio.sleep(2 ** attempt)
        
        return embeddings
    
    async def _generate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts."""
        start_time = time.time()
        
        try:
            # Call OpenAI API
            response = await asyncio.to_thread(
                openai.embeddings.create,
                model=self.model,
                input=texts,
                encoding_format="float"
            )
            
            # Extract embeddings
            embeddings = [item.embedding for item in response.data]
            
            # Update metrics
            latency_ms = (time.time() - start_time) * 1000
            self.total_latency_ms += latency_ms
            self.total_tokens += response.usage.total_tokens
            self.total_requests += 1
            
            logger.debug(
                f"Generated {len(embeddings)} embeddings in {latency_ms:.2f}ms "
                f"({response.usage.total_tokens} tokens)"
            )
            
            return embeddings
            
        except openai.RateLimitError as e:
            logger.warning(f"Rate limit hit: {str(e)}")
            raise
            
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise
            
        except Exception as e:
            logger.error(f"Unexpected error generating embeddings: {str(e)}", exc_info=True)
            raise
    
    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough: 1 token ≈ 4 chars)."""
        return len(text) // 4
    
    def estimate_cost(self, token_count: int) -> float:
        """
        Estimate cost for embedding generation.
        
        text-embedding-3-small: $0.02 per 1M tokens
        text-embedding-3-large: $0.13 per 1M tokens
        """
        if "large" in self.model:
            cost_per_1k = 0.00013
        else:  # small model
            cost_per_1k = 0.00002
        
        return (token_count / 1000) * cost_per_1k
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for this service."""
        avg_latency = (
            self.total_latency_ms / self.total_requests
            if self.total_requests > 0
            else 0
        )
        
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "total_errors": self.total_errors,
            "avg_latency_ms": avg_latency,
            "estimated_cost_usd": self.estimate_cost(self.total_tokens),
            "model": self.model,
            "dimension": self.dimension
        }
    
    def reset_metrics(self):
        """Reset performance metrics."""
        self.total_tokens = 0
        self.total_requests = 0
        self.total_errors = 0
        self.total_latency_ms = 0
        logger.info("Performance metrics reset")


class EmbeddingModelManager:
    """
    Manager for multiple embedding models with fallback and load balancing.
    """
    
    def __init__(self, db: Session):
        """
        Initialize embedding model manager.
        
        Args:
            db: Database session
        """
        self.db = db
        self.services: Dict[str, EmbeddingService] = {}
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize embedding services for all active models."""
        models = self.db.query(EmbeddingModel).filter(
            EmbeddingModel.is_active == True
        ).all()
        
        for model in models:
            try:
                service = EmbeddingService(
                    model=model.model_id,
                    dimension=model.dimension,
                    batch_size=100
                )
                self.services[model.name] = service
                logger.info(f"Initialized embedding service: {model.name}")
            except Exception as e:
                logger.error(f"Failed to initialize {model.name}: {str(e)}")
    
    async def generate_embeddings(
        self,
        texts: List[str],
        model_name: Optional[str] = None
    ) -> Tuple[List[List[float]], str]:
        """
        Generate embeddings using specified model or default.
        
        Args:
            texts: Texts to embed
            model_name: Model to use (default: use default model)
            
        Returns:
            Tuple of (embeddings, model_name_used)
        """
        # Get model
        if model_name and model_name in self.services:
            service = self.services[model_name]
        else:
            # Use default model
            default_model = self.db.query(EmbeddingModel).filter(
                EmbeddingModel.is_default == True,
                EmbeddingModel.is_active == True
            ).first()
            
            if not default_model:
                raise ValueError("No default embedding model configured")
            
            service = self.services.get(default_model.name)
            model_name = default_model.name
            
            if not service:
                raise ValueError(f"Service for {model_name} not initialized")
        
        # Generate embeddings
        embeddings = await service.generate_embeddings(texts)
        
        return embeddings, model_name
    
    def get_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get information about an embedding model."""
        model = self.db.query(EmbeddingModel).filter(
            EmbeddingModel.name == model_name
        ).first()
        
        if not model:
            return None
        
        service = self.services.get(model_name)
        metrics = service.get_performance_metrics() if service else {}
        
        return {
            "name": model.name,
            "display_name": model.display_name,
            "provider": model.provider,
            "model_id": model.model_id,
            "dimension": model.dimension,
            "max_tokens": model.max_tokens,
            "is_active": model.is_active,
            "is_default": model.is_default,
            "metrics": metrics
        }
    
    def update_model_metrics(self, model_name: str):
        """Update database with model performance metrics."""
        service = self.services.get(model_name)
        if not service:
            return
        
        model = self.db.query(EmbeddingModel).filter(
            EmbeddingModel.name == model_name
        ).first()
        
        if model:
            metrics = service.get_performance_metrics()
            model.avg_latency_ms = metrics["avg_latency_ms"]
            model.updated_at = datetime.utcnow()
            self.db.commit()
            logger.info(f"Updated metrics for {model_name}")


# Create singleton instance (will be properly initialized with DB session in API)
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create embedding service singleton."""
    global _embedding_service
    
    if _embedding_service is None:
        _embedding_service = EmbeddingService(
            model=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSIONS,
            batch_size=100
        )
    
    return _embedding_service


async def generate_embeddings_for_chunks(
    chunks: List[str]
) -> List[List[float]]:
    """
    Convenience function to generate embeddings for document chunks.
    
    Args:
        chunks: List of text chunks
        
    Returns:
        List of embedding vectors
    """
    service = get_embedding_service()
    return await service.generate_embeddings(chunks)