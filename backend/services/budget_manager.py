from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class BudgetExceeded(Exception):
    """
    code:
      - BUDGET_EXCEEDED
      - BUDGET_ENFORCEMENT_UNAVAILABLE
    """

    def __init__(self, message: str, *, code: str, details: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class BudgetScope:
    scope: str       # global|org|user|provider|model
    scope_id: str    # e.g. global, org:123, user:abc, openai, openai/gpt-4o
    per_day_limit: int


@dataclass(frozen=True)
class BudgetReservationToken:
    """
    Captures reservation day (UTC) so commit/release are midnight-safe.
    """
    day: str  # YYYY-MM-DD UTC
    amount: int
    scopes: Tuple[BudgetScope, ...]


def _utc_day_bucket(dt: Optional[datetime] = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d")


def _safe_id(raw: str) -> str:
    # allow slashes (e.g. model ids) while keeping Redis keys readable
    return raw.replace("/", "__")


class BudgetManager:
    """
    Redis-backed budget manager using atomic Lua across multiple scopes.

    Each scope key is a Redis hash:
      limit: int
      used: int
      reserved: int

    Invariants:
      - reserve checks (limit - used - reserved) >= amount for ALL scopes
      - reserve increments reserved by amount for ALL scopes atomically
      - commit decrements reserved by reserved_amount and increments used by used_amount
      - release decrements reserved by reserved_amount
      - TTL is refreshed on every operation (reserve/commit/release)
    """

    TTL_SECONDS = 172800  # 48 hours

    LUA_RESERVE = r"""
local n = #KEYS
local amount = tonumber(ARGV[n + 1])
local ttl = tonumber(ARGV[n + 2])

-- Pass 1: check all scopes
for i=1,n do
  local limit = tonumber(ARGV[i])

  if redis.call("EXISTS", KEYS[i]) == 0 then
    redis.call("HSET", KEYS[i], "limit", limit, "used", 0, "reserved", 0)
  end
  redis.call("EXPIRE", KEYS[i], ttl)

  local used = tonumber(redis.call("HGET", KEYS[i], "used") or "0")
  local reserved = tonumber(redis.call("HGET", KEYS[i], "reserved") or "0")
  local remaining = limit - used - reserved
  if remaining < amount then
    return {0, i, remaining}
  end
end

-- Pass 2: reserve
for i=1,n do
  redis.call("HINCRBY", KEYS[i], "reserved", amount)
end
return {1}
"""

    LUA_COMMIT = r"""
local n = #KEYS
local reserved_amount = tonumber(ARGV[n + 1])
local used_amount = tonumber(ARGV[n + 2])
local ttl = tonumber(ARGV[n + 3])

for i=1,n do
  local limit = tonumber(ARGV[i])
  if redis.call("EXISTS", KEYS[i]) == 0 then
    redis.call("HSET", KEYS[i], "limit", limit, "used", 0, "reserved", 0)
  end
  redis.call("EXPIRE", KEYS[i], ttl)

  if reserved_amount > 0 then
    redis.call("HINCRBY", KEYS[i], "reserved", -reserved_amount)
  end
  if used_amount > 0 then
    redis.call("HINCRBY", KEYS[i], "used", used_amount)
  end
end
return {1}
"""

    LUA_RELEASE = r"""
local n = #KEYS
local reserved_amount = tonumber(ARGV[n + 1])
local ttl = tonumber(ARGV[n + 2])

for i=1,n do
  local limit = tonumber(ARGV[i])
  if redis.call("EXISTS", KEYS[i]) == 0 then
    redis.call("HSET", KEYS[i], "limit", limit, "used", 0, "reserved", 0)
  end
  redis.call("EXPIRE", KEYS[i], ttl)

  if reserved_amount > 0 then
    redis.call("HINCRBY", KEYS[i], "reserved", -reserved_amount)
  end
end
return {1}
"""

    def __init__(self, redis_client: redis.Redis, *, enforcement_mode: str, policy: dict):
        self._r = redis_client
        self.enforcement_mode = enforcement_mode  # strict|advisory|disabled
        self.policy = policy

    def _key_for(self, scope: BudgetScope, day: str) -> str:
        return f"budget:{scope.scope}:{_safe_id(scope.scope_id)}:{day}"

    async def reserve(self, amount: int, scopes: List[BudgetScope]) -> BudgetReservationToken:
        day = _utc_day_bucket()

        if amount <= 0:
            return BudgetReservationToken(day=day, amount=0, scopes=tuple(scopes))

        if self.enforcement_mode == "disabled":
            return BudgetReservationToken(day=day, amount=amount, scopes=tuple(scopes))

        keys = [self._key_for(s, day) for s in scopes]
        limits = [s.per_day_limit for s in scopes]
        argv = [*map(str, limits), str(amount), str(self.TTL_SECONDS)]

        try:
            res = await self._r.eval(self.LUA_RESERVE, len(keys), *keys, *argv)
        except Exception as e:
            if self.enforcement_mode == "strict":
                raise BudgetExceeded(
                    "Budget enforcement unavailable (Redis/Lua error)",
                    code="BUDGET_ENFORCEMENT_UNAVAILABLE",
                    details={"error": str(e)},
                )
            logger.warning("Budget reserve skipped (advisory mode): %s", e)
            return BudgetReservationToken(day=day, amount=amount, scopes=tuple(scopes))

        if isinstance(res, list) and len(res) >= 1 and int(res[0]) == 0:
            failed_index = int(res[1])
            remaining = int(res[2])
            failed_scope = scopes[failed_index - 1] if 0 <= failed_index - 1 < len(scopes) else None
            raise BudgetExceeded(
                "Budget exceeded",
                code="BUDGET_EXCEEDED",
                details={
                    "failed_index": failed_index,
                    "remaining": remaining,
                    "failed_scope": {
                        "scope": failed_scope.scope,
                        "scope_id": failed_scope.scope_id,
                    } if failed_scope else None,
                },
            )

        logger.info("Budget reserved: amount=%s day=%s scopes=%s", amount, day, [(s.scope, s.scope_id) for s in scopes])
        return BudgetReservationToken(day=day, amount=amount, scopes=tuple(scopes))

    async def commit(self, token: BudgetReservationToken, used_amount: int) -> None:
        if token.amount <= 0:
            return
        if self.enforcement_mode == "disabled":
            return

        used_amount = int(used_amount) if used_amount is not None else token.amount
        if used_amount <= 0:
            used_amount = token.amount  # conservative fallback

        if used_amount > token.amount:
            ratio = (used_amount / token.amount) if token.amount else 999999.0
            if ratio >= 5.0:
                logger.critical(
                    "BUDGET ANOMALY: Massive overspend detected reserved=%s used=%s ratio=%.2fx",
                    token.amount, used_amount, ratio,
                )
            else:
                logger.warning("Budget overspend: reserved=%s used=%s", token.amount, used_amount)

        keys = [self._key_for(s, token.day) for s in token.scopes]
        limits = [s.per_day_limit for s in token.scopes]
        argv = [*map(str, limits), str(token.amount), str(used_amount), str(self.TTL_SECONDS)]

        try:
            await self._r.eval(self.LUA_COMMIT, len(keys), *keys, *argv)
        except Exception as e:
            # Provider already responded; do not fail user response
            logger.error("Budget commit failed (non-blocking): %s", e)
            return

        logger.info("Budget committed: reserved=%s used=%s day=%s", token.amount, used_amount, token.day)

    async def release(self, token: BudgetReservationToken) -> None:
        if token.amount <= 0:
            return
        if self.enforcement_mode == "disabled":
            return

        keys = [self._key_for(s, token.day) for s in token.scopes]
        limits = [s.per_day_limit for s in token.scopes]
        argv = [*map(str, limits), str(token.amount), str(self.TTL_SECONDS)]

        try:
            await self._r.eval(self.LUA_RELEASE, len(keys), *keys, *argv)
        except Exception as e:
            logger.error("Budget release failed (reservation may leak): %s", e)
            return

        logger.info("Budget released: amount=%s day=%s", token.amount, token.day)

    async def snapshot(self, scopes: List[BudgetScope], day: Optional[str] = None) -> Dict[str, Dict[str, int]]:
        day = day or _utc_day_bucket()
        out: Dict[str, Dict[str, int]] = {}
        for s in scopes:
            key = self._key_for(s, day)
            try:
                data = await self._r.hgetall(key)
            except Exception:
                data = {}

            limit = int(data.get(b"limit", b"0")) if data else s.per_day_limit
            used = int(data.get(b"used", b"0")) if data else 0
            reserved = int(data.get(b"reserved", b"0")) if data else 0
            remaining = limit - used - reserved
            out[key] = {"limit": limit, "used": used, "reserved": reserved, "remaining": remaining}
        return out
