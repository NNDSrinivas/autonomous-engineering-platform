"""
Unit tests for response caching module.

Tests cache functionality including:
- Basic get/set operations
- TTL expiration
- LRU eviction
- Multi-tenancy scoping
- Thread safety
- Metrics tracking
"""

import time
import threading
import pytest
from backend.core.response_cache import (
    generate_cache_key,
    get_cached_response,
    set_cached_response,
    clear_cache,
    get_cache_stats,
    reset_cache_stats,
    _max_cache_size,
)


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset cache before each test."""
    clear_cache()
    reset_cache_stats()
    yield
    clear_cache()
    reset_cache_stats()


class TestCacheKeyGeneration:
    """Test cache key generation with proper scoping."""

    def test_basic_key_generation(self):
        """Test that basic cache key is generated consistently."""
        key1 = generate_cache_key("test message")
        key2 = generate_cache_key("test message")
        assert key1 == key2
        assert isinstance(key1, str)
        assert len(key1) == 64  # SHA256 hex digest length

    def test_message_normalization(self):
        """Test that whitespace is normalized."""
        key1 = generate_cache_key("  test message  ")
        key2 = generate_cache_key("test message")
        assert key1 == key2

    def test_case_sensitivity(self):
        """Test that message case is preserved for code identifiers."""
        key1 = generate_cache_key("TestClass")
        key2 = generate_cache_key("testclass")
        assert key1 != key2  # Case should matter for code

    def test_mode_scoping(self):
        """Test that different modes generate different keys."""
        key1 = generate_cache_key("test", mode="agent")
        key2 = generate_cache_key("test", mode="chat")
        assert key1 != key2

    def test_multi_tenancy_scoping(self):
        """Test that org_id and user_id create separate cache namespaces."""
        key1 = generate_cache_key("test", org_id="org1", user_id="user1")
        key2 = generate_cache_key("test", org_id="org2", user_id="user1")
        key3 = generate_cache_key("test", org_id="org1", user_id="user2")

        assert key1 != key2  # Different orgs
        assert key1 != key3  # Different users
        assert key2 != key3  # Different combinations

    def test_workspace_scoping(self):
        """Test that workspace_path affects cache key."""
        key1 = generate_cache_key("test", workspace_path="/project/a")
        key2 = generate_cache_key("test", workspace_path="/project/b")
        assert key1 != key2

    def test_model_and_provider_scoping(self):
        """Test that model and provider affect cache key."""
        key1 = generate_cache_key("test", model="gpt-4", provider="openai")
        key2 = generate_cache_key("test", model="claude-3", provider="anthropic")
        assert key1 != key2


class TestBasicCacheOperations:
    """Test basic cache get/set operations."""

    def test_cache_miss(self):
        """Test that missing key returns None."""
        result = get_cached_response("nonexistent_key")
        assert result is None

        # Verify metrics
        stats = get_cache_stats()
        assert stats["misses"] == 1
        assert stats["hits"] == 0

    def test_cache_set_and_get(self):
        """Test basic set and get operations."""
        key = generate_cache_key("test message")
        test_data = {"content": "test response", "model": "gpt-4"}

        set_cached_response(key, test_data)
        result = get_cached_response(key)

        assert result == test_data

        # Verify metrics
        stats = get_cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 0
        assert stats["size"] == 1

    def test_cache_overwrite(self):
        """Test that setting same key overwrites previous value."""
        key = generate_cache_key("test message")

        set_cached_response(key, "first value")
        set_cached_response(key, "second value")

        result = get_cached_response(key)
        assert result == "second value"

        # Should still be only 1 item
        stats = get_cache_stats()
        assert stats["size"] == 1

    def test_cache_with_complex_data(self):
        """Test caching complex nested data structures."""
        key = generate_cache_key("complex query")
        complex_data = {
            "content": "response",
            "metadata": {
                "tokens": {"input": 100, "output": 200},
                "model": "gpt-4",
                "latency_ms": 1234,
            },
            "context": ["item1", "item2", "item3"],
        }

        set_cached_response(key, complex_data)
        result = get_cached_response(key)

        assert result == complex_data
        assert result["metadata"]["tokens"]["input"] == 100


class TestCacheTTL:
    """Test cache TTL (time-to-live) expiration."""

    def test_cache_expiration(self):
        """Test that expired entries are removed and counted."""
        key = generate_cache_key("test message")

        set_cached_response(key, "test data")

        # Manually expire the cache by manipulating global state
        from backend.core import response_cache

        # Backup original TTL
        original_ttl = response_cache._cache_ttl_seconds

        # Set TTL to 0.1 seconds for testing
        response_cache._cache_ttl_seconds = 0.1

        # Wait for expiration
        time.sleep(0.2)

        # Should return None and increment expiration counter
        result = get_cached_response(key)
        assert result is None

        stats = get_cache_stats()
        assert stats["expirations"] == 1
        assert stats["misses"] == 1  # Expiration also counts as miss

        # Restore original TTL
        response_cache._cache_ttl_seconds = original_ttl


class TestLRUEviction:
    """Test LRU (Least Recently Used) eviction behavior."""

    def test_lru_eviction_at_capacity(self):
        """Test that least recently used items are evicted first."""
        # Fill cache to capacity
        keys = []
        for i in range(_max_cache_size):
            key = generate_cache_key(f"message {i}")
            keys.append(key)
            set_cached_response(key, f"response {i}")

        stats = get_cache_stats()
        assert stats["size"] == _max_cache_size
        assert stats["evictions"] == 0

        # Add one more item, should evict the oldest (first added)
        new_key = generate_cache_key("new message")
        set_cached_response(new_key, "new response")

        stats = get_cache_stats()
        assert stats["size"] == _max_cache_size  # Still at max
        assert stats["evictions"] == 1

        # First item should be evicted, last items should remain
        assert get_cached_response(keys[0]) is None  # Evicted
        assert get_cached_response(keys[-1]) is not None  # Still there
        assert get_cached_response(new_key) is not None  # New item there

    def test_lru_with_access_pattern(self):
        """Test that accessing items updates LRU order."""
        # Add items
        keys = []
        for i in range(10):
            key = generate_cache_key(f"message {i}")
            keys.append(key)
            set_cached_response(key, f"response {i}")

        # Access the first item (making it most recently used)
        get_cached_response(keys[0])

        # Fill cache to capacity with new items
        for i in range(10, _max_cache_size + 1):
            key = generate_cache_key(f"message {i}")
            set_cached_response(key, f"response {i}")

        # First item should still be there (was accessed recently)
        # Second item should be evicted (least recently used)
        assert get_cached_response(keys[0]) is not None  # Recently accessed
        assert get_cached_response(keys[1]) is None  # Should be evicted


class TestCacheMetrics:
    """Test cache metrics tracking."""

    def test_hit_rate_calculation(self):
        """Test that hit rate is calculated correctly."""
        key = generate_cache_key("test")
        set_cached_response(key, "data")

        # 1 hit, 0 misses initially (from get during set doesn't count)
        get_cached_response(key)  # hit
        get_cached_response(key)  # hit
        get_cached_response("nonexistent1")  # miss
        get_cached_response("nonexistent2")  # miss

        stats = get_cache_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 2
        assert stats["total_requests"] == 4
        assert stats["hit_rate_percent"] == 50.0

    def test_utilization_percent(self):
        """Test cache utilization percentage."""
        # Add 10 items
        for i in range(10):
            key = generate_cache_key(f"message {i}")
            set_cached_response(key, f"response {i}")

        stats = get_cache_stats()
        expected_utilization = (10 / _max_cache_size) * 100
        assert stats["utilization_percent"] == expected_utilization

    def test_reset_stats(self):
        """Test that resetting stats clears counters but not cache."""
        key = generate_cache_key("test")
        set_cached_response(key, "data")
        get_cached_response(key)
        get_cached_response("nonexistent")

        # Should have hits and misses
        stats = get_cache_stats()
        assert stats["hits"] > 0 or stats["misses"] > 0
        assert stats["size"] == 1

        # Reset stats
        reset_cache_stats()

        stats = get_cache_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["evictions"] == 0
        assert stats["expirations"] == 0
        assert stats["size"] == 1  # Cache data still there


class TestThreadSafety:
    """Test thread safety of cache operations."""

    def test_concurrent_reads_and_writes(self):
        """Test that concurrent reads and writes don't corrupt cache."""
        results = []
        errors = []

        def reader_thread(thread_id: int):
            """Read from cache repeatedly."""
            try:
                for i in range(100):
                    key = generate_cache_key(f"message {i % 10}")
                    result = get_cached_response(key)
                    if result is not None:
                        results.append((thread_id, result))
            except Exception as e:
                errors.append((thread_id, str(e)))

        def writer_thread(thread_id: int):
            """Write to cache repeatedly."""
            try:
                for i in range(100):
                    key = generate_cache_key(f"message {i % 10}")
                    set_cached_response(key, f"response {i}")
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Start multiple reader and writer threads
        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=reader_thread, args=(i,)))
            threads.append(threading.Thread(target=writer_thread, args=(i + 5,)))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should have no errors
        assert len(errors) == 0

        # Cache should still be functional
        key = generate_cache_key("test")
        set_cached_response(key, "test data")
        result = get_cached_response(key)
        assert result == "test data"


class TestCacheClear:
    """Test cache clearing functionality."""

    def test_clear_cache(self):
        """Test that clearing cache removes all items."""
        # Add items
        for i in range(10):
            key = generate_cache_key(f"message {i}")
            set_cached_response(key, f"response {i}")

        stats = get_cache_stats()
        assert stats["size"] == 10

        # Clear cache
        clear_cache()

        stats = get_cache_stats()
        assert stats["size"] == 0

        # All items should be gone
        for i in range(10):
            key = generate_cache_key(f"message {i}")
            assert get_cached_response(key) is None
