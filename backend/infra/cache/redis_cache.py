from __future__ import annotations
import asyncio
import json
import os
import time
from typing import Any, Optional, Iterable

try:
    import aioredis  # type: ignore
except Exception:
    aioredis = None

REDIS_URL = os.getenv("REDIS_URL")


class Cache:
    def __init__(self) -> None:
        self._mem: dict[str, tuple[int, str]] = {}
        self._mem_lock = asyncio.Lock()  # Async lock for in-memory cache
        self._r = None

    async def _ensure(self):
        if not REDIS_URL or aioredis is None:
            return None
        if self._r is None:
            try:
                self._r = await aioredis.from_url(
                    REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    max_connections=10,
                )
            except Exception:
                self._r = None
                return None
        return self._r

    async def get(self, key: str) -> Optional[str]:
        r = await self._ensure()
        if r:
            return await r.get(key)
        async with self._mem_lock:
            ent = self._mem.get(key)
            if not ent:
                return None
            exp, payload = ent
            if time.time() >= exp:
                self._mem.pop(key, None)
                return None
            return payload

    async def mget(self, keys: Iterable[str]) -> list[Optional[str]]:
        # Convert to list to handle generators and ensure consistent behavior
        keys = list(keys)
        r = await self._ensure()
        if r:
            vals = await r.mget(keys) if keys else []
            return list(vals)
        return [await self.get(k) for k in keys]

    async def setex(self, key: str, ttl_sec: int, value: str) -> None:
        r = await self._ensure()
        if r:
            await r.set(key, value, ex=ttl_sec)
            return
        async with self._mem_lock:
            self._mem[key] = (int(time.time()) + ttl_sec, value)

    async def exists(self, key: str) -> bool:
        r = await self._ensure()
        if r:
            return bool(await r.exists(key))
        return await self.get(key) is not None

    async def delete(self, key: str) -> int:
        r = await self._ensure()
        if r:
            return int(await r.delete(key))
        async with self._mem_lock:
            return 1 if self._mem.pop(key, None) else 0

    # Legacy methods for backward compatibility
    async def get_json(self, key: str) -> Optional[Any]:
        raw = await self.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: Any, ttl_sec: int = 60) -> None:
        await self.setex(key, ttl_sec, json.dumps(value))

    def clear_sync(self) -> None:
        """Synchronously clear in-memory cache. Only affects local cache, not Redis."""
        # Clear in-memory cache synchronously for test usage
        self._mem.clear()

    async def clear_pattern(self, pattern: str) -> int:
        """Clear cache entries matching a pattern. Returns number of keys deleted."""
        r = await self._ensure()
        if r:
            # Use Redis SCAN with pattern matching
            keys = []
            async for key in r.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                return await r.delete(*keys)
            return 0
        else:
            # For in-memory cache, we'll do a simple pattern match
            async with self._mem_lock:
                import fnmatch

                to_delete = [k for k in self._mem.keys() if fnmatch.fnmatch(k, pattern)]
                for k in to_delete:
                    del self._mem[k]
                return len(to_delete)


cache = Cache()
