from __future__ import annotations
import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional, Callable, Awaitable

from backend.infra.cache.redis_cache import cache as redis

DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL_SEC", "600"))  # 10m default

# singleflight map to prevent dogpiling
_singleflight: dict[str, asyncio.Lock] = {}
_singleflight_lock = asyncio.Lock()  # Protects singleflight dict creation
_max_singleflight_size = 1000  # Limit singleflight dict size


async def _cleanup_singleflight():
    """Remove unused locks from singleflight dict to prevent memory leaks."""
    async with _singleflight_lock:
        if len(_singleflight) > _max_singleflight_size:
            # Remove locks that are not currently locked (best effort cleanup)
            to_remove = []
            for key, lock in _singleflight.items():
                if not lock.locked():
                    to_remove.append(key)
                # Only remove half to avoid too aggressive cleanup
                if len(to_remove) >= len(_singleflight) // 2:
                    break

            for key in to_remove:
                _singleflight.pop(key, None)


@dataclass
class CacheResult:
    hit: bool
    value: Any
    age_sec: int = 0


async def _sf_lock(key: str) -> asyncio.Lock:
    # Fast path - check if lock already exists
    lock = _singleflight.get(key)
    if lock is not None:
        return lock

    # Slow path - create lock with protection against race conditions
    async with _singleflight_lock:
        # Double-check after acquiring the lock
        lock = _singleflight.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _singleflight[key] = lock

            # Periodic cleanup to prevent memory leaks
            if len(_singleflight) > _max_singleflight_size:
                asyncio.create_task(_cleanup_singleflight())
        return lock


def _fits(v: Any) -> bool:
    try:
        max_bytes = int(os.getenv("CACHE_MAX_VALUE_BYTES", "262144"))
        return len(json.dumps(v)) <= max_bytes
    except Exception:
        return False


def _cache_enabled() -> bool:
    return os.getenv("CACHE_ENABLED", "true").lower() == "true"


class CacheService:
    async def get_json(self, key: str) -> Optional[Any]:
        if not _cache_enabled():
            return None
        raw = await redis.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: Any, ttl_sec: int | None = None) -> None:
        if not _cache_enabled():
            return
        if not _fits(value):
            return
        await redis.setex(key, ttl_sec or DEFAULT_TTL, json.dumps(value))

    async def del_key(self, key: str) -> int:
        return await redis.delete(key)

    async def cached_fetch(
        self,
        key: str,
        fetcher: Callable[[], Awaitable[Any]],
        ttl_sec: int | None = None,
    ) -> CacheResult:
        if not _cache_enabled():
            return CacheResult(hit=False, value=await fetcher(), age_sec=0)

        # fast path
        val = await self.get_json(key)
        if val is not None:
            ts = val.get("__cached_at")
            age = int(time.time()) - int(ts) if ts else 0
            return CacheResult(hit=True, value=val["data"], age_sec=age)

        # singleflight
        lock = await _sf_lock(key)
        async with lock:
            # re-check after lock
            val = await self.get_json(key)
            if val is not None:
                ts = val.get("__cached_at")
                age = int(time.time()) - int(ts) if ts else 0
                return CacheResult(hit=True, value=val["data"], age_sec=age)

            data = await fetcher()
            await self.set_json(
                key,
                {"data": data, "__cached_at": int(time.time())},
                ttl_sec or DEFAULT_TTL,
            )
            return CacheResult(hit=False, value=data, age_sec=0)


cache_service = CacheService()
