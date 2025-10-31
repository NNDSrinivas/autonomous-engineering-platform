from __future__ import annotations
import asyncio
import json
import os
import time
import threading
from dataclasses import dataclass
from typing import Any, Optional, Callable, Awaitable

from backend.infra.cache.redis_cache import cache as redis

DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL_SEC", "600"))  # 10m default

# singleflight map to prevent dogpiling with last access tracking
_singleflight: dict[str, tuple[asyncio.Lock, float]] = (
    {}
)  # key -> (lock, last_access_time)
_singleflight_lock = asyncio.Lock()  # Protects singleflight dict creation
_max_singleflight_size = 1000  # Limit singleflight dict size
_singleflight_ttl = 300  # Remove locks not accessed for 5 minutes

# Cache hit/miss counters - shared with middleware
_cache_hits = 0
_cache_misses = 0
_cache_counter_lock = threading.Lock()


def _increment_hit_counter():
    """Increment cache hit counter (thread-safe)."""
    global _cache_hits
    with _cache_counter_lock:
        _cache_hits += 1


def _increment_miss_counter():
    """Increment cache miss counter (thread-safe)."""
    global _cache_misses
    with _cache_counter_lock:
        _cache_misses += 1


def get_cache_stats() -> tuple[int, int]:
    """Get current cache hit/miss stats (thread-safe)."""
    with _cache_counter_lock:
        return _cache_hits, _cache_misses


async def _cleanup_singleflight():
    """Remove stale locks from singleflight dict to prevent memory leaks."""
    try:
        async with _singleflight_lock:
            if len(_singleflight) > _max_singleflight_size:
                current_time = time.time()
                # Remove locks that haven't been accessed for TTL duration
                to_remove = []
                for key, (lock, last_access) in _singleflight.items():
                    if current_time - last_access > _singleflight_ttl:
                        to_remove.append(key)
                    # Only remove half to avoid too aggressive cleanup
                    if len(to_remove) >= len(_singleflight) // 2:
                        break

                for key in to_remove:
                    _singleflight.pop(key, None)
    except Exception as e:
        # Log error but don't raise to avoid crashing the task
        import logging

        logging.warning(f"Error during singleflight cleanup: {e}")


@dataclass
class CacheResult:
    hit: bool
    value: Any
    age_sec: int = 0


async def _sf_lock(key: str) -> asyncio.Lock:
    current_time = time.time()

    # Fast path - check if lock already exists
    lock_tuple = _singleflight.get(key)
    if lock_tuple is not None:
        lock, _ = lock_tuple
        # Skip access time update on fast path to avoid race condition
        # Access time will be updated in slow path when lock is acquired
        return lock

    # Slow path - create lock with protection against race conditions
    async with _singleflight_lock:
        # Double-check after acquiring the lock
        lock_tuple = _singleflight.get(key)
        if lock_tuple is None:
            lock = asyncio.Lock()
            _singleflight[key] = (lock, current_time)

            # Periodic cleanup to prevent memory leaks
            if len(_singleflight) > _max_singleflight_size:
                asyncio.create_task(_cleanup_singleflight())
        else:
            lock, _ = lock_tuple
            # Update access time
            _singleflight[key] = (lock, current_time)
        return lock


def _fits(v: Any) -> bool:
    try:
        max_bytes = int(os.getenv("CACHE_MAX_VALUE_BYTES", "262144"))
        return len(json.dumps(v)) <= max_bytes
    except Exception:
        return False


def _cache_enabled() -> bool:
    return os.getenv("CACHE_ENABLED", "true").lower() == "true"


def _calculate_age(cached_timestamp: Any) -> int:
    """Calculate age in seconds from cached timestamp."""
    try:
        return (
            int(time.time()) - int(cached_timestamp)
            if cached_timestamp is not None
            else 0
        )
    except (ValueError, TypeError):
        # Handle invalid timestamp gracefully
        return 0


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
            age = _calculate_age(ts)
            _increment_hit_counter()
            return CacheResult(hit=True, value=val["data"], age_sec=age)

        # singleflight
        lock = await _sf_lock(key)
        async with lock:
            # re-check after lock
            val = await self.get_json(key)
            if val is not None:
                ts = val.get("__cached_at")
                age = _calculate_age(ts)
                _increment_hit_counter()
                return CacheResult(hit=True, value=val["data"], age_sec=age)

            data = await fetcher()
            await self.set_json(
                key,
                {"data": data, "__cached_at": int(time.time())},
                ttl_sec or DEFAULT_TTL,
            )
            _increment_miss_counter()
            return CacheResult(hit=False, value=data, age_sec=0)


cache_service = CacheService()
