"""
Optional Redis cache utility with in-memory fallback.

Provides simple key-value caching for role resolution and other
frequently-accessed data. Falls back to in-process dict if Redis
is not configured or unavailable.
"""

import json
import os
import time
import threading
from typing import Any, Optional

try:
    from redis import asyncio as aioredis

    HAS_REDIS = True
except ImportError:
    aioredis: Optional[Any] = None
    HAS_REDIS = False

REDIS_URL = os.getenv("REDIS_URL")


class Cache:
    """
    Simple async cache with Redis backend and memory fallback.

    Automatically uses Redis if REDIS_URL is set and aioredis is installed,
    otherwise falls back to in-process memory cache with TTL support.
    """

    def __init__(self) -> None:
        self._mem: dict[str, tuple[int, str]] = {}
        self._mem_lock = threading.Lock()  # Protect in-memory cache operations
        # Redis client instance (redis.asyncio.Redis) or None if not configured
        self._r: Optional[Any] = None

    async def _ensure(self) -> Optional[Any]:
        """
        Ensure Redis connection is established if configured.

        Returns:
            Redis client instance if successfully connected, None otherwise.
        """
        if not REDIS_URL or not HAS_REDIS:
            return None
        if self._r is None:
            try:
                self._r = await aioredis.from_url(  # type: ignore[attr-defined]
                    REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5.0,
                    socket_timeout=5.0,
                    max_connections=50,
                )
            except Exception:
                # If Redis connection fails, fall back to in-memory cache
                return None
        return self._r

    async def get_json(self, key: str) -> Optional[Any]:
        """
        Retrieve a JSON value from cache.

        Args:
            key: Cache key

        Returns:
            Parsed JSON value or None if not found/expired
        """
        r = await self._ensure()
        if r:
            val = await r.get(key)
            return json.loads(val) if val else None

        # Fallback to in-memory cache
        with self._mem_lock:
            entry = self._mem.get(key)
            if not entry:
                return None
            exp_ts, payload = entry
            if time.time() >= exp_ts:
                self._mem.pop(key, None)
                return None
            return json.loads(payload)

    async def set_json(self, key: str, value: Any, ttl_sec: int = 60) -> None:
        """
        Store a JSON-serializable value in cache with TTL.

        Args:
            key: Cache key
            value: JSON-serializable value
            ttl_sec: Time-to-live in seconds (default: 60)
        """
        r = await self._ensure()
        payload = json.dumps(value)
        if r:
            await r.set(key, payload, ex=ttl_sec)
            return

        # Fallback to in-memory cache
        with self._mem_lock:
            self._mem[key] = (int(time.time()) + ttl_sec, payload)

    async def delete(self, key: str) -> None:
        """
        Delete a key from cache.

        Args:
            key: Cache key to delete
        """
        r = await self._ensure()
        if r:
            await r.delete(key)
        else:
            with self._mem_lock:
                self._mem.pop(key, None)

    async def clear(self) -> None:
        """
        Clear all cached entries.

        Useful for testing and cache invalidation scenarios.
        """
        r = await self._ensure()
        if r:
            await r.flushdb()
        else:
            with self._mem_lock:
                self._mem.clear()

    async def clear_pattern(self, pattern: str) -> None:
        """
        Clear cached entries matching a pattern.

        Args:
            pattern: Pattern to match (supports * wildcards for Redis,
                     simple prefix matching for in-memory cache)
        """
        r = await self._ensure()
        if r:
            # Use Redis SCAN with pattern matching
            async for key in r.scan_iter(match=pattern):
                await r.delete(key)
        else:
            # For in-memory cache, implement simple prefix matching
            # Convert Redis pattern to prefix (remove trailing *)
            prefix = pattern.rstrip("*")
            with self._mem_lock:
                self._mem = {
                    k: v for k, v in self._mem.items() if not k.startswith(prefix)
                }

    def clear_sync(self) -> None:
        """
        Synchronous version of clear for testing.

        Only clears in-memory cache since Redis requires async operations.
        """
        with self._mem_lock:
            self._mem.clear()


# Global cache instance
cache = Cache()
