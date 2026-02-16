"""
Redis-backed circuit breaker for multi-worker provider health tracking.

Implements classic circuit breaker pattern (CLOSED → OPEN → HALF_OPEN) with:
- Lua atomic scripts for race-free state updates
- Sliding window failure tracking
- Shared state across workers
- Prometheus metrics integration
"""

import logging
import time
from enum import Enum

import redis

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = 0  # Normal operation
    OPEN = 1  # Blocking requests due to failures
    HALF_OPEN = 2  # Testing recovery


# Lua script for atomic circuit breaker updates
# Ensures race-free state transitions across multiple workers
RECORD_CALL_LUA = """
local key_prefix = KEYS[1]
local now = tonumber(ARGV[1])
local window_sec = tonumber(ARGV[2])
local failure_threshold = tonumber(ARGV[3])
local open_duration_sec = tonumber(ARGV[4])
local call_result = ARGV[5]  -- "success", "failure", or "timeout"

local state_key = key_prefix .. ":state"
local window_key = key_prefix .. ":window"
local open_at_key = key_prefix .. ":open_at"

-- Get current state (default CLOSED=0)
local state = tonumber(redis.call("GET", state_key) or "0")

-- OPEN state: check if recovery window elapsed
if state == 1 then
    local open_at = tonumber(redis.call("GET", open_at_key) or "0")
    if now - open_at >= open_duration_sec then
        -- Transition to HALF_OPEN
        redis.call("SET", state_key, "2")
        redis.call("EXPIRE", state_key, 86400)  -- 24h TTL to prevent indefinite persistence
        state = 2
    else
        -- Still open, block request
        return {state, 0, 0}
    end
end

-- HALF_OPEN state: single probe request
-- NOTE: Only the FIRST call result causes state transition (CLOSED or OPEN).
-- If multiple workers call record_call concurrently in HALF_OPEN:
-- - First call: transitions to CLOSED (success) or OPEN (failure)
-- - Subsequent calls: see new state and process normally (sliding window for CLOSED)
-- The probe lease in try_acquire_probe_lease() prevents concurrent calls,
-- but this handles the edge case where calls were already in flight.
if state == 2 then
    if call_result == "success" then
        -- Recovery successful → CLOSED
        redis.call("SET", state_key, "0")
        redis.call("EXPIRE", state_key, 86400)  -- 24h TTL
        redis.call("DEL", window_key)
        redis.call("DEL", open_at_key)
        return {0, 1, 0}
    else
        -- Probe failed → back to OPEN
        redis.call("SET", state_key, "1")
        redis.call("EXPIRE", state_key, 86400)  -- 24h TTL
        redis.call("SET", open_at_key, tostring(now))
        redis.call("EXPIRE", open_at_key, 86400)  -- 24h TTL
        return {1, 0, 1}
    end
end

-- CLOSED state: sliding window tracking
-- Remove old entries outside window
redis.call("ZREMRANGEBYSCORE", window_key, "-inf", tostring(now - window_sec))

-- Add current call with unique member to prevent collisions under high QPS
local score = now
local seq = redis.call("INCR", key_prefix .. ":seq")
local member = tostring(now) .. ":" .. call_result .. ":" .. tostring(seq)
redis.call("ZADD", window_key, score, member)
redis.call("EXPIRE", window_key, window_sec * 2)
redis.call("EXPIRE", key_prefix .. ":seq", window_sec * 2)

-- Count failures in window
local all_calls = redis.call("ZRANGE", window_key, 0, -1)
local failure_count = 0
for _, call in ipairs(all_calls) do
    if string.match(call, ":failure:") or string.match(call, ":timeout:") then
        failure_count = failure_count + 1
    end
end

-- Check if threshold exceeded
if failure_count >= failure_threshold then
    -- Transition to OPEN
    redis.call("SET", state_key, "1")
    redis.call("EXPIRE", state_key, 86400)  -- 24h TTL to prevent memory leaks
    redis.call("SET", open_at_key, tostring(now))
    redis.call("EXPIRE", open_at_key, 86400)  -- 24h TTL
    return {1, 0, failure_count}
end

-- Still CLOSED
return {0, #all_calls, failure_count}
"""


class RedisCircuitBreaker:
    """
    Redis-backed circuit breaker for provider health tracking.

    Config:
        window_sec: Sliding window duration for failure tracking (default 60s)
        failure_threshold: Failures to trigger OPEN state (default 5)
        open_duration_sec: How long to stay OPEN before HALF_OPEN probe (default 30s)
        probe_lease_ttl: TTL for HALF_OPEN probe lease in seconds (default 5s)
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        provider_id: str,
        window_sec: int = 60,
        failure_threshold: int = 5,
        open_duration_sec: int = 30,
        probe_lease_ttl: int = 5,
    ):
        self.redis = redis_client
        self.provider_id = provider_id
        self.window_sec = window_sec
        self.failure_threshold = failure_threshold
        self.open_duration_sec = open_duration_sec
        self.probe_lease_ttl = probe_lease_ttl
        # Use Redis hash tag so all related keys share the same cluster hash slot
        self.key_prefix = f"circuit:{{{provider_id}}}"

        # Pre-register Lua script
        try:
            self.record_call_script = self.redis.register_script(RECORD_CALL_LUA)
        except Exception as e:
            logger.warning(
                f"Failed to register Lua script for {provider_id}, "
                f"will use fallback: {e}"
            )
            self.record_call_script = None

    def record_success(self) -> CircuitState:
        """Record successful call, returns new circuit state"""
        return self._record_call("success")

    def record_failure(self) -> CircuitState:
        """Record failed call, returns new circuit state"""
        return self._record_call("failure")

    def record_timeout(self) -> CircuitState:
        """Record timeout, returns new circuit state"""
        return self._record_call("timeout")

    def get_state(self) -> CircuitState:
        """Get current circuit state without recording a call"""
        try:
            state_key = f"{self.key_prefix}:state"
            open_at_key = f"{self.key_prefix}:open_at"

            state_val = self.redis.get(state_key)
            state = int(state_val) if state_val else 0

            # Check if OPEN → HALF_OPEN transition due
            # NOTE: Race window exists - multiple workers can concurrently:
            #   1) observe state == OPEN
            #   2) see that open_duration_sec has elapsed
            #   3) perform SET to transition to HALF_OPEN
            # This doesn't corrupt state (all write "2" for HALF_OPEN), but
            # means multiple workers may believe they triggered the transition.
            # Correctness is enforced by try_acquire_probe_lease() which uses
            # SET NX to ensure only one worker actually probes.
            if state == 1:
                open_at = self.redis.get(open_at_key)
                if open_at:
                    elapsed = time.time() - float(open_at)
                    if elapsed >= self.open_duration_sec:
                        # Transition to HALF_OPEN (atomically via SET)
                        self.redis.set(state_key, "2")
                        return CircuitState.HALF_OPEN

            return CircuitState(state)

        except Exception as e:
            logger.error(
                f"Error getting circuit state for {self.provider_id}: {e}",
                exc_info=True,
            )
            # Fail-safe: assume CLOSED (allow traffic) on error
            return CircuitState.CLOSED

    def try_acquire_probe_lease(self, ttl_sec: int = None) -> bool:
        """
        Atomically try to acquire probe lease for HALF_OPEN state.

        Args:
            ttl_sec: Optional TTL override (uses self.probe_lease_ttl if not provided)

        Returns:
            True if lease acquired (this worker can send probe request)
            False if lease already held by another worker

        The lease expires after ttl_sec to allow retry if probe hangs/fails.
        """
        try:
            probe_key = f"{self.key_prefix}:probe_lease"
            ttl = ttl_sec if ttl_sec is not None else self.probe_lease_ttl
            # SET NX EX: atomically set only if not exists, with expiration
            result = self.redis.set(probe_key, "1", nx=True, ex=ttl)
            return result is True
        except Exception as e:
            logger.error(
                f"Error acquiring probe lease for {self.provider_id}: {e}",
                exc_info=True,
            )
            # Fail-safe: allow probe on error
            return True

    def _record_call(self, result: str) -> CircuitState:
        """
        Record call result and update circuit state atomically.

        Args:
            result: "success", "failure", or "timeout"

        Returns:
            New CircuitState after update
        """
        try:
            if self.record_call_script:
                # Use Lua script for atomic update
                state_val, total_calls, failure_count = self.record_call_script(
                    keys=[self.key_prefix],
                    args=[
                        time.time(),
                        self.window_sec,
                        self.failure_threshold,
                        self.open_duration_sec,
                        result,
                    ],
                )
                new_state = CircuitState(int(state_val))

                logger.debug(
                    f"Circuit breaker for {self.provider_id}: "
                    f"result={result}, state={new_state.name}, "
                    f"total={total_calls}, failures={failure_count}"
                )

                return new_state
            else:
                # Fallback: non-atomic Python logic
                return self._record_call_fallback(result)

        except Exception as e:
            logger.error(
                f"Error recording call for {self.provider_id}: {e}", exc_info=True
            )
            # Fail-safe: assume CLOSED (allow traffic) on error
            return CircuitState.CLOSED

    def _record_call_fallback(self, result: str) -> CircuitState:
        """
        Non-atomic fallback for when Lua script unavailable.
        WARNING: Not race-free in multi-worker scenario.
        """
        state_key = f"{self.key_prefix}:state"
        window_key = f"{self.key_prefix}:window"
        open_at_key = f"{self.key_prefix}:open_at"

        now = time.time()
        state_val = self.redis.get(state_key)
        state = int(state_val) if state_val else 0

        # OPEN → HALF_OPEN check
        if state == 1:
            open_at = self.redis.get(open_at_key)
            if open_at and (now - float(open_at)) >= self.open_duration_sec:
                self.redis.set(state_key, "2")
                state = 2

        # HALF_OPEN: probe result
        if state == 2:
            if result == "success":
                self.redis.set(state_key, "0")
                self.redis.delete(window_key, open_at_key)
                return CircuitState.CLOSED
            else:
                self.redis.set(state_key, "1")
                self.redis.set(open_at_key, str(now))
                return CircuitState.OPEN

        # CLOSED: sliding window
        self.redis.zremrangebyscore(window_key, "-inf", now - self.window_sec)
        # Use sequence number to prevent collisions under high QPS
        seq = self.redis.incr(f"{self.key_prefix}:seq")
        self.redis.zadd(window_key, {f"{now}:{result}:{seq}": now})
        self.redis.expire(window_key, self.window_sec * 2)
        self.redis.expire(f"{self.key_prefix}:seq", self.window_sec * 2)

        all_calls = self.redis.zrange(window_key, 0, -1)
        failure_count = sum(
            1
            for call in all_calls
            if (
                (
                    isinstance(call, bytes)
                    and (b":failure:" in call or b":timeout:" in call)
                )
                or (
                    isinstance(call, str)
                    and (":failure:" in call or ":timeout:" in call)
                )
            )
        )

        if failure_count >= self.failure_threshold:
            self.redis.set(state_key, "1")
            self.redis.set(open_at_key, str(now))
            return CircuitState.OPEN

        return CircuitState.CLOSED
