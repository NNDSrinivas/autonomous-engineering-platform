import pytest, asyncio
from backend.core.resilience.circuit import CircuitBreaker


@pytest.mark.asyncio
async def test_circuit_opens_then_half_open_then_closes():
    c = CircuitBreaker("test", fail_threshold=2, open_sec=1, success_to_close=1)

    async def fail():
        raise RuntimeError("boom")

    # trigger opens
    with pytest.raises(RuntimeError):
        await c.call(fail)
    with pytest.raises(RuntimeError):
        await c.call(fail)
    assert c.is_open() is True

    # while open, we expect open errors
    with pytest.raises(RuntimeError):
        await c.call(fail)

    # wait to half-open
    await asyncio.sleep(1.05)

    # first success closes (success_to_close=1)
    async def ok():
        return "ok"

    out = await c.call(ok)
    assert out == "ok"
    assert c.is_open() is False


@pytest.mark.asyncio
async def test_circuit_fallback():
    c = CircuitBreaker("test", fail_threshold=1, open_sec=1)

    async def fail():
        raise RuntimeError("boom")

    async def fallback(e):
        return "fallback-result"

    # trigger open
    result = await c.call(fail, fallback)
    assert result == "fallback-result"
    assert c.is_open() is True

    # while open, fallback should be called
    result = await c.call(fail, fallback)
    assert result == "fallback-result"


@pytest.mark.asyncio
async def test_circuit_success_path():
    c = CircuitBreaker("test", fail_threshold=3, success_to_close=2)

    async def succeed():
        return "success"

    # should work normally when closed
    result = await c.call(succeed)
    assert result == "success"
    assert c.is_open() is False
