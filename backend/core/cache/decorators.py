from __future__ import annotations
import functools
from typing import Callable, Awaitable, Any

from .service import cache_service


def cached(key_fn: Callable[..., str], ttl_sec: int | None = None):
    """
    @cached(lambda plan_id: plan_key(plan_id), ttl_sec=300)
    async def read_plan(plan_id: str): ...
    """

    def wrap(fn: Callable[..., Awaitable[Any]]):
        @functools.wraps(fn)
        async def inner(*args, **kwargs):
            key = key_fn(*args, **kwargs)
            res = await cache_service.cached_fetch(
                key, lambda: fn(*args, **kwargs), ttl_sec
            )
            return res.value

        return inner

    return wrap


def invalidate(key_fn: Callable[..., str]):
    """
    @invalidate(lambda plan_id: plan_key(plan_id))
    async def write_plan(plan_id: str, ...): ...
    """

    def wrap(fn: Callable[..., Awaitable[Any]]):
        @functools.wraps(fn)
        async def inner(*args, **kwargs):
            key = key_fn(*args, **kwargs)
            out = await fn(*args, **kwargs)
            # best-effort cache invalidation
            try:
                await cache_service.del_key(key)
            except Exception:
                # Ignore cache invalidation errors to avoid disrupting business logic
                # The cache entry will expire naturally via TTL
                pass
            return out

        return inner

    return wrap
