import os
import pytest
from unittest.mock import patch
from backend.core.cache.service import cache_service
from backend.core.cache.keys import generic


@pytest.fixture(autouse=True)
def reset_env():
    """Reset cache environment before each test"""
    original = os.environ.get("CACHE_ENABLED")
    os.environ["CACHE_ENABLED"] = "true"
    os.environ["CACHE_MAX_VALUE_BYTES"] = "262144"
    yield
    if original is not None:
        os.environ["CACHE_ENABLED"] = original
    else:
        os.environ.pop("CACHE_ENABLED", None)


@pytest.mark.asyncio
async def test_set_get_invalidate_roundtrip():
    key = generic("test", "roundtrip")

    # Use patch.multiple to patch time.time in all cache-related modules
    with patch.multiple("time", time=lambda: 1000.0), patch.multiple(
        "backend.infra.cache.redis_cache.time", time=lambda: 1000.0
    ), patch.multiple("backend.core.cache.service.time", time=lambda: 1000.0):
        await cache_service.set_json(key, {"n": 1}, ttl_sec=1)
        v = await cache_service.get_json(key)
        assert v == {"n": 1}

    # Fast forward past expiration
    with patch.multiple("time", time=lambda: 1001.1), patch.multiple(
        "backend.infra.cache.redis_cache.time", time=lambda: 1001.1
    ), patch.multiple("backend.core.cache.service.time", time=lambda: 1001.1):
        v2 = await cache_service.get_json(key)
        assert v2 is None  # expired


@pytest.mark.asyncio
async def test_cached_fetch_hit_miss():
    key = generic("test", "misshit")
    called = {"n": 0}

    async def fetch():
        called["n"] += 1
        return {"value": 42}

    # miss
    res1 = await cache_service.cached_fetch(key, fetcher=fetch, ttl_sec=2)
    assert res1.hit is False and res1.value["value"] == 42 and called["n"] == 1
    # hit
    res2 = await cache_service.cached_fetch(key, fetcher=fetch, ttl_sec=2)
    assert res2.hit is True and res2.value["value"] == 42 and called["n"] == 1


@pytest.mark.asyncio
async def test_cache_disabled():
    # Test cache behavior when disabled
    os.environ["CACHE_ENABLED"] = "false"
    key = generic("test", "disabled")
    called = {"n": 0}

    async def fetch():
        called["n"] += 1
        return {"value": 123}

    # Should always call fetcher when cache is disabled
    res1 = await cache_service.cached_fetch(key, fetcher=fetch, ttl_sec=60)
    assert res1.hit is False and res1.value["value"] == 123 and called["n"] == 1

    res2 = await cache_service.cached_fetch(key, fetcher=fetch, ttl_sec=60)
    assert res2.hit is False and res2.value["value"] == 123 and called["n"] == 2


@pytest.mark.asyncio
async def test_cache_invalidation():
    key = generic("test", "invalidate")
    fetch_count = {"n": 0}

    async def fetch_original():
        fetch_count["n"] += 1
        return "original"

    # Cache initial value
    result = await cache_service.cached_fetch(key, fetcher=fetch_original, ttl_sec=60)
    assert result.hit is False
    assert result.value == "original"
    assert fetch_count["n"] == 1

    # Verify it's cached (should be a hit)
    result2 = await cache_service.cached_fetch(key, fetcher=fetch_original, ttl_sec=60)
    assert result2.hit is True
    assert result2.value == "original"
    assert fetch_count["n"] == 1  # No additional fetch

    # Invalidate
    deleted = await cache_service.del_key(key)
    assert deleted >= 0  # Redis returns count, memory returns 1 or 0

    # Verify it's gone
    val2 = await cache_service.get_json(key)
    assert val2 is None


@pytest.mark.asyncio
async def test_cache_size_limit():
    os.environ["CACHE_MAX_VALUE_BYTES"] = "100"  # Very small limit

    key = generic("test", "large")
    large_value = {"data": "x" * 200}  # Should exceed limit

    # Should not cache large values
    await cache_service.set_json(key, large_value, ttl_sec=60)

    # Should return None since it wasn't cached due to size
    val = await cache_service.get_json(key)
    assert val is None
