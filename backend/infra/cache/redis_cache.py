from __future__ import annotations
import json, os, time
from typing import Any, Optional, Iterable

try:
    import aioredis  # type: ignore
except Exception:
    aioredis = None

REDIS_URL = os.getenv("REDIS_URL")

class Cache:
    def __init__(self) -> None:
        self._mem: dict[str, tuple[int, str]] = {}
        self._r = None

    async def _ensure(self):
        if not REDIS_URL or aioredis is None:
            return None
        if self._r is None:
            self._r = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        return self._r

    async def get(self, key: str) -> Optional[str]:
        r = await self._ensure()
        if r:
            return await r.get(key)
        ent = self._mem.get(key)
        if not ent: return None
        exp, payload = ent
        if time.time() > exp:
            self._mem.pop(key, None); return None
        return payload

    async def mget(self, keys: Iterable[str]) -> list[Optional[str]]:
        r = await self._ensure()
        if r:
            vals = await r.mget(*keys) if keys else []
            return list(vals)
        return [await self.get(k) for k in keys]

    async def setex(self, key: str, ttl_sec: int, value: str) -> None:
        r = await self._ensure()
        if r:
            await r.set(key, value, ex=ttl_sec); return
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
        return 1 if self._mem.pop(key, None) else 0

    # Legacy methods for backward compatibility
    async def get_json(self, key: str) -> Optional[Any]:
        raw = await self.get(key)
        return json.loads(raw) if raw else None

    async def set_json(self, key: str, value: Any, ttl_sec: int = 60) -> None:
        await self.setex(key, ttl_sec, json.dumps(value))

cache = Cache()
