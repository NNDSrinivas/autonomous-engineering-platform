import pytest, asyncio
from backend.core.cache.decorators import cached, invalidate
from backend.core.cache.keys import generic

# Use global counter that we reset per test
_test_counter = {"get": 0}

def make_cached_plan_fn(test_name):
    @cached(lambda pid: generic("test_plan", test_name, pid), ttl_sec=2)
    async def get_plan(pid: str):
        _test_counter["get"] += 1
        return {"id": pid, "v": 1}
    return get_plan

def make_invalidate_plan_fn(test_name):
    @invalidate(lambda pid, v: generic("test_plan", test_name, pid))
    async def update_plan(pid: str, v: int):
        return {"ok": True, "v": v}
    return update_plan

@pytest.mark.asyncio
async def test_decorator_flow():
    # Reset counter and create test-specific functions
    _test_counter["get"] = 0
    get_plan = make_cached_plan_fn("flow")
    update_plan = make_invalidate_plan_fn("flow")
    
    a = await get_plan("A")
    b = await get_plan("A")
    assert a == b and _test_counter["get"] == 1  # hit

    await update_plan("A", 2)
    c = await get_plan("A")
    assert _test_counter["get"] == 2  # re-fetched after invalidation

@pytest.mark.asyncio
async def test_cached_decorator_different_args():
    _test_counter["get"] = 0
    get_plan = make_cached_plan_fn("different")
    
    # Different args should cache separately
    a1 = await get_plan("A")
    b1 = await get_plan("B")
    
    # Both should be cache misses
    assert _test_counter["get"] == 2
    
    # Same args should hit cache
    a2 = await get_plan("A")
    b2 = await get_plan("B")
    
    assert a1 == a2
    assert b1 == b2
    assert _test_counter["get"] == 2  # No additional calls

@pytest.mark.asyncio
async def test_invalidate_decorator_no_error():
    # Test that invalidate decorator doesn't fail even if cache key doesn't exist
    update_plan = make_invalidate_plan_fn("noerror")
    result = await update_plan("nonexistent", 999)
    assert result == {"ok": True, "v": 999}