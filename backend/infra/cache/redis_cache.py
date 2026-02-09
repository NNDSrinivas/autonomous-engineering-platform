from __future__ import annotations
import asyncio
import fnmatch
import json
import os
import time
from typing import Any, Optional, Iterable

try:
    from redis import asyncio as aioredis  # type: ignore
    from redis.exceptions import ResponseError  # type: ignore

    aioredis_available = True
except ImportError:
    aioredis = None  # type: ignore
    ResponseError = Exception  # type: ignore - Fallback to base Exception
    aioredis_available = False

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
                self._r = aioredis.Redis.from_url(
                    REDIS_URL,
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

    async def getdel_json(self, key: str) -> Optional[Any]:
        """
        Atomically get and delete a JSON value.

        Uses Redis GETDEL when available (atomic operation).
        Falls back to Lua script for older Redis versions.
        Falls back to locked get-then-delete for in-memory cache.

        Returns:
            The parsed JSON value if found, None otherwise

        TODO: Add comprehensive test coverage for atomic get+delete behavior
        CRITICAL: This method is used for OAuth state management in backend/core/auth/sso_store.py
        where atomic pop semantics prevent replay attacks. Test failures here create security risks.

        Required tests:
        1. GETDEL path: Verify atomic read+delete with Redis 6.2+
        2. Lua fallback: Test fallback when GETDEL raises AttributeError or "unknown command"
        3. In-memory fallback: Ensure atomicity via lock and correct expiration handling
        4. Concurrent consumers: Verify only one consumer gets the value (OAuth state replay protection)
        5. Edge cases: expired keys, missing keys, race conditions
        """
        r = await self._ensure()
        if r:
            # Use Redis GETDEL for atomic read-and-delete (Redis 6.2+)
            try:
                raw = await r.getdel(key)
                # Decode bytes to string if needed (defensive handling for bytes responses)
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                return json.loads(raw) if raw else None
            except AttributeError:
                # redis-py doesn't have getdel method - fall back to Lua script
                pass  # Continue to Lua fallback below
            except ResponseError as e:
                # Only fall back when the Redis server does not recognize the GETDEL command
                msg = str(e).lower()
                if "unknown command" in msg and "getdel" in msg:
                    # Older Redis server without GETDEL support - fall back to Lua script
                    pass  # Continue to Lua fallback below
                else:
                    # Other ResponseError types are real errors and should not be swallowed
                    raise

            # Fallback for Redis/redis-py versions without GETDEL support
            # Use an atomic Lua script to GET and DEL the key
            lua_script = """
            local v = redis.call('GET', KEYS[1])
            if v then
                redis.call('DEL', KEYS[1])
            end
            return v
            """
            raw = await r.eval(lua_script, 1, key)
            # Decode bytes to string if needed (redis-py eval often returns bytes even with decode_responses=True)
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            return json.loads(raw) if raw else None
        else:
            # For in-memory cache, use lock to make operation atomic
            async with self._mem_lock:
                ent = self._mem.get(key)
                if not ent:
                    return None
                exp, payload = ent
                # Check expiration
                if time.time() >= exp:
                    self._mem.pop(key, None)
                    return None
                # Delete and return
                self._mem.pop(key)
                return json.loads(payload)

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
                to_delete = [k for k in self._mem.keys() if fnmatch.fnmatch(k, pattern)]
                for k in to_delete:
                    del self._mem[k]
                return len(to_delete)


cache = Cache()
