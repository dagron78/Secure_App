"""
Redis caching utilities with decorators for API endpoints.

Provides:
- Simple function result caching with TTL
- Cache invalidation patterns
- Cache key generation strategies
- Statistics tracking
"""
import json
import hashlib
import logging
import functools
from typing import Any, Optional, Callable, Union
from datetime import timedelta

import redis.asyncio as aioredis
from fastapi import Request

from app.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages Redis connections and provides caching utilities.
    
    Features:
    - Automatic key prefixing by environment
    - TTL support with default values
    - JSON serialization for complex objects
    - Cache statistics tracking
    - Bulk operations support
    """
    
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self.redis: Optional[aioredis.Redis] = None
        self.default_ttl = 300  # 5 minutes
        self.key_prefix = f"{settings.ENV}:cache:"
        
    async def connect(self):
        """Initialize Redis connection."""
        if not self.redis:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            logger.info("Redis cache connected")
    
    async def disconnect(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()
            logger.info("Redis cache disconnected")
    
    def _make_key(self, key: str) -> str:
        """Generate prefixed cache key."""
        return f"{self.key_prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        if not self.redis:
            await self.connect()
        
        try:
            cache_key = self._make_key(key)
            value = await self.redis.get(cache_key)
            
            if value:
                # Try to deserialize JSON
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            
            return None
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized if not string)
            ttl: Time to live in seconds (default: 300)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            await self.connect()
        
        try:
            cache_key = self._make_key(key)
            ttl = ttl or self.default_ttl
            
            # Serialize complex objects
            if not isinstance(value, str):
                value = json.dumps(value, default=str)
            
            await self.redis.setex(cache_key, ttl, value)
            return True
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False otherwise
        """
        if not self.redis:
            await self.connect()
        
        try:
            cache_key = self._make_key(key)
            await self.redis.delete(cache_key)
            return True
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching pattern.
        
        Args:
            pattern: Key pattern (e.g., "user:*")
            
        Returns:
            Number of keys deleted
        """
        if not self.redis:
            await self.connect()
        
        try:
            cache_pattern = self._make_key(pattern)
            keys = []
            async for key in self.redis.scan_iter(match=cache_pattern):
                keys.append(key)
            
            if keys:
                await self.redis.delete(*keys)
            
            return len(keys)
            
        except Exception as e:
            logger.error(f"Cache delete_pattern error for pattern {pattern}: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if not self.redis:
            await self.connect()
        
        try:
            cache_key = self._make_key(key)
            return await self.redis.exists(cache_key) > 0
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False
    
    async def get_ttl(self, key: str) -> int:
        """Get remaining TTL for a key in seconds."""
        if not self.redis:
            await self.connect()
        
        try:
            cache_key = self._make_key(key)
            return await self.redis.ttl(cache_key)
        except Exception as e:
            logger.error(f"Cache get_ttl error for key {key}: {e}")
            return -1
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter in cache."""
        if not self.redis:
            await self.connect()
        
        try:
            cache_key = self._make_key(key)
            return await self.redis.incrby(cache_key, amount)
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return 0
    
    async def get_stats(self) -> dict:
        """Get cache statistics."""
        if not self.redis:
            await self.connect()
        
        try:
            info = await self.redis.info("stats")
            return {
                "total_commands": info.get("total_commands_processed", 0),
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": info.get("keyspace_hits", 0) / 
                           (info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0) + 1) * 100
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}


# Global cache manager instance
cache_manager = CacheManager()


def generate_cache_key(*args, **kwargs) -> str:
    """
    Generate a cache key from function arguments.
    
    Creates a hash of the arguments to use as a cache key.
    """
    # Create a string representation of args and kwargs
    key_parts = []
    
    for arg in args:
        if isinstance(arg, Request):
            # Skip Request objects
            continue
        key_parts.append(str(arg))
    
    for k, v in sorted(kwargs.items()):
        if k in ['db', 'current_user', 'request']:
            # Skip common FastAPI dependency objects
            continue
        key_parts.append(f"{k}={v}")
    
    key_string = ":".join(key_parts)
    
    # Create hash for long keys
    if len(key_string) > 100:
        return hashlib.md5(key_string.encode()).hexdigest()
    
    return key_string


def cached(
    ttl: int = 300,
    key_prefix: Optional[str] = None,
    key_builder: Optional[Callable] = None
):
    """
    Decorator to cache function results.
    
    Args:
        ttl: Time to live in seconds (default: 300)
        key_prefix: Optional prefix for cache keys
        key_builder: Optional custom function to build cache keys
        
    Example:
        @cached(ttl=600, key_prefix="user")
        async def get_user(user_id: int):
            # ... expensive operation
            return user
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Build cache key
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                func_key = f"{func.__module__}.{func.__name__}"
                arg_key = generate_cache_key(*args, **kwargs)
                cache_key = f"{key_prefix or func_key}:{arg_key}"
            
            # Try to get from cache
            cached_value = await cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT for key: {cache_key}")
                return cached_value
            
            # Execute function
            logger.debug(f"Cache MISS for key: {cache_key}")
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache_manager.set(cache_key, result, ttl)
            
            return result
        
        # Add cache management methods
        wrapper.cache_key_prefix = key_prefix or f"{func.__module__}.{func.__name__}"
        wrapper.invalidate = lambda *args, **kwargs: cache_manager.delete(
            f"{wrapper.cache_key_prefix}:{generate_cache_key(*args, **kwargs)}"
        )
        wrapper.invalidate_all = lambda: cache_manager.delete_pattern(
            f"{wrapper.cache_key_prefix}:*"
        )
        
        return wrapper
    
    return decorator


def cache_invalidate(key_prefix: str):
    """
    Decorator to invalidate cache after function execution.
    
    Useful for write operations that should clear related caches.
    
    Example:
        @cache_invalidate("user")
        async def update_user(user_id: int, data: dict):
            # ... update user
            return updated_user
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)
            
            # Invalidate cache
            deleted = await cache_manager.delete_pattern(f"{key_prefix}:*")
            logger.info(f"Invalidated {deleted} cache entries for prefix: {key_prefix}")
            
            return result
        
        return wrapper
    
    return decorator


# Utility functions for direct use

async def get_cached(key: str) -> Optional[Any]:
    """Get value from cache."""
    return await cache_manager.get(key)


async def set_cached(key: str, value: Any, ttl: int = 300) -> bool:
    """Set value in cache."""
    return await cache_manager.set(key, value, ttl)


async def delete_cached(key: str) -> bool:
    """Delete value from cache."""
    return await cache_manager.delete(key)


async def clear_cache_pattern(pattern: str) -> int:
    """Clear all cache entries matching pattern."""
    return await cache_manager.delete_pattern(pattern)


async def get_cache_stats() -> dict:
    """Get cache statistics."""
    return await cache_manager.get_stats()