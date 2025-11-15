"""
Integration tests for Redis caching functionality.

Tests cache manager, decorators, and cache invalidation.
"""
import pytest
from app.core.cache import (
    cache_manager,
    cached,
    cache_invalidate,
    get_cached,
    set_cached,
    delete_cached
)


@pytest.fixture(autouse=True)
async def setup_cache():
    """Setup and teardown cache for each test."""
    await cache_manager.connect()
    yield
    # Clear all test cache keys
    await cache_manager.delete_pattern("*")
    await cache_manager.disconnect()


class TestCacheManager:
    """Test CacheManager functionality."""
    
    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Test basic set and get operations."""
        key = "test:key"
        value = "test_value"
        
        success = await cache_manager.set(key, value)
        assert success
        
        cached_value = await cache_manager.get(key)
        assert cached_value == value
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """Test getting nonexistent key returns None."""
        value = await cache_manager.get("nonexistent:key")
        assert value is None
    
    @pytest.mark.asyncio
    async def test_set_with_ttl(self):
        """Test setting value with TTL."""
        key = "test:ttl"
        value = "test_value"
        
        await cache_manager.set(key, value, ttl=1)
        
        # Should exist immediately
        assert await cache_manager.exists(key)
        
        # Check TTL
        ttl = await cache_manager.get_ttl(key)
        assert ttl > 0 and ttl <= 1
    
    @pytest.mark.asyncio
    async def test_delete_key(self):
        """Test deleting a key."""
        key = "test:delete"
        value = "test_value"
        
        await cache_manager.set(key, value)
        assert await cache_manager.exists(key)
        
        await cache_manager.delete(key)
        assert not await cache_manager.exists(key)
    
    @pytest.mark.asyncio
    async def test_delete_pattern(self):
        """Test deleting keys by pattern."""
        # Set multiple keys
        await cache_manager.set("user:1", "data1")
        await cache_manager.set("user:2", "data2")
        await cache_manager.set("product:1", "data3")
        
        # Delete all user keys
        deleted = await cache_manager.delete_pattern("user:*")
        assert deleted == 2
        
        # User keys should be gone
        assert not await cache_manager.exists("user:1")
        assert not await cache_manager.exists("user:2")
        
        # Product key should remain
        assert await cache_manager.exists("product:1")
    
    @pytest.mark.asyncio
    async def test_cache_complex_objects(self):
        """Test caching complex objects."""
        key = "test:complex"
        value = {
            "id": 1,
            "name": "Test",
            "nested": {
                "key": "value"
            },
            "list": [1, 2, 3]
        }
        
        await cache_manager.set(key, value)
        cached_value = await cache_manager.get(key)
        
        assert cached_value == value
        assert cached_value["nested"]["key"] == "value"
        assert cached_value["list"] == [1, 2, 3]
    
    @pytest.mark.asyncio
    async def test_increment_counter(self):
        """Test incrementing a counter."""
        key = "test:counter"
        
        count1 = await cache_manager.increment(key, 1)
        assert count1 == 1
        
        count2 = await cache_manager.increment(key, 5)
        assert count2 == 6


class TestCachedDecorator:
    """Test @cached decorator."""
    
    @pytest.mark.asyncio
    async def test_function_result_cached(self):
        """Test that function result is cached."""
        call_count = 0
        
        @cached(ttl=60, key_prefix="test:func")
        async def expensive_function(arg1: str):
            nonlocal call_count
            call_count += 1
            return f"result_{arg1}"
        
        # First call executes function
        result1 = await expensive_function("test")
        assert result1 == "result_test"
        assert call_count == 1
        
        # Second call uses cache
        result2 = await expensive_function("test")
        assert result2 == "result_test"
        assert call_count == 1  # Not called again
    
    @pytest.mark.asyncio
    async def test_different_args_different_cache(self):
        """Test that different arguments use different cache entries."""
        call_count = 0
        
        @cached(ttl=60, key_prefix="test:args")
        async def get_data(arg: str):
            nonlocal call_count
            call_count += 1
            return f"data_{arg}"
        
        # Call with different args
        result1 = await get_data("a")
        result2 = await get_data("b")
        result3 = await get_data("a")  # Cache hit
        
        assert result1 == "data_a"
        assert result2 == "data_b"
        assert result3 == "data_a"
        assert call_count == 2  # Only 'a' and 'b', not third call


class TestCacheInvalidateDecorator:
    """Test @cache_invalidate decorator."""
    
    @pytest.mark.asyncio
    async def test_cache_invalidated_after_update(self):
        """Test that cache is cleared after update operation."""
        # Set some cached data
        await cache_manager.set("data:1", "old_value")
        await cache_manager.set("data:2", "old_value")
        
        @cache_invalidate("data")
        async def update_data():
            return "updated"
        
        # Verify data is cached
        assert await cache_manager.exists("data:1")
        assert await cache_manager.exists("data:2")
        
        # Call update function
        await update_data()
        
        # Cache should be cleared
        assert not await cache_manager.exists("data:1")
        assert not await cache_manager.exists("data:2")


class TestCacheUtilityFunctions:
    """Test cache utility functions."""
    
    @pytest.mark.asyncio
    async def test_get_set_delete_cached(self):
        """Test utility functions."""
        key = "test:util"
        value = "test_value"
        
        # Set
        success = await set_cached(key, value, ttl=60)
        assert success
        
        # Get
        cached = await get_cached(key)
        assert cached == value
        
        # Delete
        deleted = await delete_cached(key)
        assert deleted
        
        # Verify deleted
        cached = await get_cached(key)
        assert cached is None