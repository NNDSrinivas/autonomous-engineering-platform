"""
Budget Manager with Redis-backed atomic multi-scope enforcement.

Implements enterprise-grade budget governance with:
- Atomic multi-scope reserve/commit/release (single Lua script)
- Multi-worker safe (all scopes checked + incremented atomically)
- Calendar day buckets (UTC midnight, YYYY-MM-DD)
- 48-hour key TTL (prevents memory leaks)
- Fail-closed by default (configurable via BUDGET_ENFORCEMENT_MODE)
- Midnight-safe commits (BudgetReservationToken captures day)
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

import redis

logger = logging.getLogger(__name__)


class BudgetScope(Enum):
    """Budget scope types for hierarchical enforcement."""

    GLOBAL = "global"
    ORG = "org"
    USER = "user"
    PROVIDER = "provider"
    MODEL = "model"


@dataclass(frozen=True)
class BudgetScopeKey:
    """Immutable budget scope identifier."""

    scope: BudgetScope
    scope_id: str  # e.g., "global", "acme-corp", "user-123", "openai", "openai/gpt-4o"

    def __str__(self) -> str:
        return f"{self.scope.value}:{self.scope_id}"


@dataclass(frozen=True)
class BudgetReservationToken:
    """
    Immutable reservation token for midnight-safe commits.

    Captures day + amount + scopes at reservation time to ensure
    commit/release operates on correct day bucket even if called
    after midnight UTC boundary.
    """

    day: str  # YYYY-MM-DD UTC
    amount: int  # reserved amount (tokens or cost units)
    scopes: List[BudgetScopeKey]


class BudgetExceeded(Exception):
    """Raised when budget limit exceeded."""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.details = details or {}


# Lua script for atomic multi-scope reserve (with 48h TTL to prevent memory leaks)
LUA_RESERVE = """
local n = #KEYS
local amount = tonumber(ARGV[n + 1])
local ttl = 172800  -- 48 hours (allows late commits after midnight)

-- First pass: check all scopes have remaining >= amount
for i=1,n do
  local limit = tonumber(ARGV[i])
  if redis.call("EXISTS", KEYS[i]) == 0 then
    redis.call("HSET", KEYS[i], "limit", limit, "used", 0, "reserved", 0)
  end
  -- CRITICAL: Set TTL on all keys to prevent memory leak
  redis.call("EXPIRE", KEYS[i], ttl)

  local used = tonumber(redis.call("HGET", KEYS[i], "used") or "0")
  local reserved = tonumber(redis.call("HGET", KEYS[i], "reserved") or "0")
  local remaining = limit - used - reserved
  if remaining < amount then
    return {0, i, remaining, limit, used, reserved}  -- denied (which scope failed + details)
  end
end

-- Second pass: reserve in all scopes atomically
for i=1,n do
  redis.call("HINCRBY", KEYS[i], "reserved", amount)
  redis.call("EXPIRE", KEYS[i], ttl)
end
return {1}  -- allowed
"""

# Lua script for atomic multi-scope commit (with overspend handling)
LUA_COMMIT = """
local n = #KEYS
local reserved_amount = tonumber(ARGV[n + 1])
local used_amount = tonumber(ARGV[n + 2])
local ttl = 172800

for i=1,n do
  local limit = tonumber(ARGV[i])
  if redis.call("EXISTS", KEYS[i]) == 0 then
    redis.call("HSET", KEYS[i], "limit", limit, "used", 0, "reserved", 0)
  end
  redis.call("EXPIRE", KEYS[i], ttl)

  -- Decrement reserved
  if reserved_amount > 0 then
    redis.call("HINCRBY", KEYS[i], "reserved", -reserved_amount)
  end

  -- Increment used (may exceed limit if actual > reserved - tracked by overspend metric)
  if used_amount > 0 then
    redis.call("HINCRBY", KEYS[i], "used", used_amount)
  end
end

return {1}
"""

# Lua script for atomic multi-scope release
LUA_RELEASE = """
local n = #KEYS
local reserved_amount = tonumber(ARGV[n + 1])
local ttl = 172800

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


class BudgetManager:
    """
    Redis-backed budget manager with atomic multi-scope enforcement.

    Thread-safe and multi-worker safe via Lua atomic scripts.
    Enforces budgets across global, org, user, provider, and model scopes.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        policy: Dict,
        enforcement_mode: Optional[str] = None,
    ):
        """
        Initialize budget manager.

        Args:
            redis_client: Shared Redis client
            policy: Budget policy dict (loaded from budget-policy-{env}.json)
            enforcement_mode: "strict" (default) or "advisory" (allow on Redis errors)
        """
        self.redis = redis_client
        self.policy = policy
        self.enforcement_mode = enforcement_mode or os.getenv(
            "BUDGET_ENFORCEMENT_MODE", "strict"
        )

        # Validate enforcement mode
        valid_modes = {"strict", "advisory", "disabled"}
        if self.enforcement_mode not in valid_modes:
            logger.warning(
                f"Invalid BUDGET_ENFORCEMENT_MODE={self.enforcement_mode}, defaulting to 'strict'"
            )
            self.enforcement_mode = "strict"

        # Pre-register Lua scripts
        try:
            self.reserve_script = self.redis.register_script(LUA_RESERVE)
            self.commit_script = self.redis.register_script(LUA_COMMIT)
            self.release_script = self.redis.register_script(LUA_RELEASE)
        except Exception as e:
            logger.warning(f"Failed to register Lua scripts, will use fallback: {e}")
            self.reserve_script = None
            self.commit_script = None
            self.release_script = None

    def _utc_day_bucket(self) -> str:
        """Get current UTC day in YYYY-MM-DD format."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _build_redis_key(self, scope_key: BudgetScopeKey, day: str) -> str:
        """
        Build Redis key for budget scope and day.

        Model IDs contain slashes (e.g., openai/gpt-4o).
        Replace with __ for debugging clarity.
        """
        scope_id_safe = scope_key.scope_id.replace("/", "__")
        return f"budget:{scope_key.scope.value}:{scope_id_safe}:{day}"

    def _get_limit(self, scope_key: BudgetScopeKey) -> int:
        """Get budget limit for scope from policy."""
        scope = scope_key.scope
        scope_id = scope_key.scope_id

        # Check scope-specific limits
        if scope == BudgetScope.ORG:
            org_limits = self.policy.get("orgs", {})
            if scope_id in org_limits:
                return org_limits[scope_id]["per_day"]

        elif scope == BudgetScope.USER:
            user_limits = self.policy.get("users", {})
            if scope_id in user_limits:
                return user_limits[scope_id]["per_day"]

        elif scope == BudgetScope.PROVIDER:
            provider_limits = self.policy.get("providers", {})
            if scope_id in provider_limits:
                return provider_limits[scope_id]["per_day"]

        elif scope == BudgetScope.MODEL:
            model_limits = self.policy.get("models", {})
            if scope_id in model_limits:
                return model_limits[scope_id]["per_day"]

        # Fallback to default
        return self.policy.get("defaults", {}).get("per_day", 0)

    def reserve(
        self,
        amount: int,
        scopes: List[BudgetScopeKey],
    ) -> BudgetReservationToken:
        """
        Atomically check all scopes and increment reserved.

        IMPORTANT: This is the ONLY authoritative budget enforcement.
        Router budget checks are advisory only (snapshot-based, may race).

        Returns:
            BudgetReservationToken (includes day for midnight-safe commit)

        Raises:
            BudgetExceeded if any scope has insufficient remaining budget
        """
        # Skip entirely if disabled mode
        if self.enforcement_mode == "disabled":
            day = self._utc_day_bucket()
            logger.debug("Budget enforcement disabled, allowing request")
            return BudgetReservationToken(day=day, amount=amount, scopes=scopes)

        day = self._utc_day_bucket()  # Capture reservation day

        # Build Redis keys and limits for all scopes
        keys = [self._build_redis_key(scope, day) for scope in scopes]
        limits = [self._get_limit(scope) for scope in scopes]

        try:
            if self.reserve_script:
                # Use Lua script for atomic multi-scope reserve
                # ARGV = limits (one per scope) + amount
                result = self.reserve_script(keys=keys, args=limits + [amount])

                if result[0] == 0:
                    # Reserve denied
                    failed_index = result[1] - 1  # Lua is 1-indexed
                    remaining = result[2]
                    limit = result[3]
                    used = result[4]
                    reserved = result[5]

                    failed_scope = scopes[failed_index]
                    raise BudgetExceeded(
                        f"Budget exceeded for {failed_scope} (limit={limit}, used={used}, reserved={reserved}, remaining={remaining}, requested={amount})",
                        {
                            "scope": str(failed_scope),
                            "limit": limit,
                            "used": used,
                            "reserved": reserved,
                            "remaining": remaining,
                            "requested": amount,
                        },
                    )

                logger.debug(
                    f"Budget reserved: {amount} for scopes={[str(s) for s in scopes]} day={day}"
                )
                return BudgetReservationToken(day=day, amount=amount, scopes=scopes)

            else:
                # Fallback: non-atomic Python logic (NOT production-grade)
                logger.warning("Using non-atomic budget reserve fallback")
                return self._reserve_fallback(amount, scopes, day, keys, limits)

        except redis.RedisError as e:
            if self.enforcement_mode == "strict":
                raise BudgetExceeded(
                    f"Budget enforcement unavailable (Redis error): {e}"
                )
            else:
                # Advisory mode: log + allow (emit metric)
                logger.warning(
                    f"Budget check skipped (Redis unavailable, advisory mode): {e}"
                )
                # TODO: emit BUDGET_REDIS_ERRORS_TOTAL metric
                return BudgetReservationToken(day=day, amount=amount, scopes=scopes)

    def commit(
        self,
        token: BudgetReservationToken,
        used_amount: int,
    ) -> None:
        """
        Decrement reserved, increment used.

        Uses token.day (NOT current day) for midnight-safe commit.

        If used_amount > token.amount (overspend):
          - Emit BUDGET_OVERSPEND_DELTA metric
          - Allow overspend (don't block response after provider succeeded)
          - Safety clamp: log CRITICAL if overspend > 5x reserved (anomaly detection)
        """
        if used_amount > token.amount:
            delta = used_amount - token.amount
            overspend_ratio = used_amount / token.amount if token.amount > 0 else float('inf')

            # Safety clamp: detect provider anomalies (streaming runaway, etc.)
            if overspend_ratio > 5.0:
                logger.critical(
                    f"BUDGET ANOMALY: Massive overspend detected! "
                    f"reserved={token.amount}, used={used_amount}, "
                    f"delta={delta}, ratio={overspend_ratio:.2f}x"
                )
                # TODO: emit BUDGET_ANOMALY_TOTAL metric
            else:
                logger.warning(
                    f"Budget overspend: reserved={token.amount}, used={used_amount}, "
                    f"delta={delta}, ratio={overspend_ratio:.2f}x"
                )

            # TODO: emit BUDGET_OVERSPEND_DELTA.observe(delta)

        # Build Redis keys using token.day (midnight-safe)
        keys = [self._build_redis_key(scope, token.day) for scope in token.scopes]
        limits = [self._get_limit(scope) for scope in token.scopes]

        try:
            if self.commit_script:
                # ARGV = limits (one per scope) + reserved_amount + used_amount
                self.commit_script(
                    keys=keys, args=limits + [token.amount, used_amount]
                )

                logger.debug(
                    f"Budget committed: reserved={token.amount}, used={used_amount}, day={token.day}"
                )
            else:
                # Fallback
                logger.warning("Using non-atomic budget commit fallback")
                self._commit_fallback(token, used_amount, keys)

        except redis.RedisError as e:
            logger.error(f"Budget commit failed (Redis error): {e}", exc_info=True)
            # TODO: emit BUDGET_COMMIT_FAILURES_TOTAL metric

    def release(
        self,
        token: BudgetReservationToken,
    ) -> None:
        """
        Decrement reserved (error/timeout case).

        Uses token.day for consistency.
        """
        # Build Redis keys using token.day
        keys = [self._build_redis_key(scope, token.day) for scope in token.scopes]
        limits = [self._get_limit(scope) for scope in token.scopes]

        try:
            if self.release_script:
                # ARGV = limits (one per scope) + reserved_amount
                self.release_script(keys=keys, args=limits + [token.amount])

                logger.debug(
                    f"Budget released: amount={token.amount}, day={token.day}"
                )
            else:
                # Fallback
                logger.warning("Using non-atomic budget release fallback")
                self._release_fallback(token, keys)

        except redis.RedisError as e:
            logger.error(f"Budget release failed (Redis error): {e}", exc_info=True)
            # TODO: emit BUDGET_RELEASE_FAILURES_TOTAL metric

    def snapshot(
        self,
        scopes: List[BudgetScopeKey],
        day: Optional[str] = None,
    ) -> Dict[str, Dict[str, int]]:
        """
        Non-atomic read for debugging/metrics export.

        IMPORTANT: Advisory only, not authoritative.
        Near midnight UTC, snapshot day may differ from execution reserve day.
        Router uses this for budget decisions, but execution reserve() is final.

        Returns:
            {
                "budget:org:acme:2025-02-16": {
                    "limit": 1000000,
                    "used": 50000,
                    "reserved": 2500,
                    "remaining": 947500
                },
                ...
            }
        """
        day = day or self._utc_day_bucket()
        result = {}

        for scope in scopes:
            key = self._build_redis_key(scope, day)
            limit = self._get_limit(scope)

            try:
                if self.redis.exists(key):
                    used = int(self.redis.hget(key, "used") or 0)
                    reserved = int(self.redis.hget(key, "reserved") or 0)
                else:
                    used = 0
                    reserved = 0

                remaining = limit - used - reserved

                result[key] = {
                    "limit": limit,
                    "used": used,
                    "reserved": reserved,
                    "remaining": remaining,
                }

            except redis.RedisError as e:
                logger.error(f"Snapshot failed for {key}: {e}")
                result[key] = {
                    "limit": limit,
                    "used": 0,
                    "reserved": 0,
                    "remaining": limit,
                    "error": str(e),
                }

        return result

    # Fallback methods (non-atomic, for when Lua scripts unavailable)

    def _reserve_fallback(
        self,
        amount: int,
        scopes: List[BudgetScopeKey],
        day: str,
        keys: List[str],
        limits: List[int],
    ) -> BudgetReservationToken:
        """Non-atomic fallback for reserve (WARNING: race conditions possible)."""
        # Check all scopes first
        for i, (key, limit) in enumerate(zip(keys, limits)):
            if not self.redis.exists(key):
                self.redis.hset(key, mapping={"limit": limit, "used": 0, "reserved": 0})
            self.redis.expire(key, 172800)

            used = int(self.redis.hget(key, "used") or 0)
            reserved = int(self.redis.hget(key, "reserved") or 0)
            remaining = limit - used - reserved

            if remaining < amount:
                raise BudgetExceeded(
                    f"Budget exceeded for {scopes[i]} (limit={limit}, remaining={remaining}, requested={amount})",
                    {
                        "scope": str(scopes[i]),
                        "limit": limit,
                        "used": used,
                        "reserved": reserved,
                        "remaining": remaining,
                        "requested": amount,
                    },
                )

        # Reserve in all scopes (NOT atomic across scopes)
        for key in keys:
            self.redis.hincrby(key, "reserved", amount)

        return BudgetReservationToken(day=day, amount=amount, scopes=scopes)

    def _commit_fallback(
        self, token: BudgetReservationToken, used_amount: int, keys: List[str]
    ) -> None:
        """Non-atomic fallback for commit."""
        for key in keys:
            if token.amount > 0:
                self.redis.hincrby(key, "reserved", -token.amount)
            if used_amount > 0:
                self.redis.hincrby(key, "used", used_amount)

    def _release_fallback(
        self, token: BudgetReservationToken, keys: List[str]
    ) -> None:
        """Non-atomic fallback for release."""
        for key in keys:
            if token.amount > 0:
                self.redis.hincrby(key, "reserved", -token.amount)
