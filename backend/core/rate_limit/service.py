"""
Redis-based rate limiting service with sliding window algorithm.

Implements token bucket and sliding window rate limiting using Redis
for distributed rate limiting across multiple application instances.
"""

import logging
import time
from typing import Dict, Optional, Tuple

from backend.core.rate_limit.config import (
    DEFAULT_RATE_LIMITS,
    PREMIUM_RATE_LIMITS,
    RateLimitCategory,
    RateLimitQuota,
    RateLimitRule,
)
from backend.core.settings import settings

try:
    from redis import asyncio as aioredis

    HAS_REDIS = True
except ImportError:
    aioredis = None
    HAS_REDIS = False

logger = logging.getLogger(__name__)


class RateLimitResult:
    """Result of a rate limit check."""

    def __init__(
        self,
        allowed: bool,
        requests_remaining: int,
        reset_time: int,
        retry_after: Optional[int] = None,
        queue_depth: int = 0,
    ):
        self.allowed = allowed
        self.requests_remaining = requests_remaining
        self.reset_time = reset_time
        self.retry_after = retry_after
        self.queue_depth = queue_depth


class RateLimitService:
    """Redis-based distributed rate limiting service."""

    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._fallback_cache: Dict[str, Dict] = {}
        self._last_cleanup = time.time()

    async def _get_redis(self) -> Optional[aioredis.Redis]:
        """Get Redis connection, creating if needed."""
        if not HAS_REDIS or not settings.REDIS_URL:
            return None

        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    retry_on_timeout=True,
                    socket_keepalive=True,
                    socket_keepalive_options={},
                )
                # Test connection
                await self._redis.ping()
                logger.info("Connected to Redis for rate limiting")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis for rate limiting: {e}")
                self._redis = None

        return self._redis

    def _get_rate_quota(self, is_premium: bool = False) -> RateLimitQuota:
        """Get rate limiting quota based on user/org tier."""
        return PREMIUM_RATE_LIMITS if is_premium else DEFAULT_RATE_LIMITS

    def _generate_keys(
        self,
        user_id: str,
        org_id: str,
        category: RateLimitCategory,
        window_type: str = "minute",
    ) -> Tuple[str, str, str]:
        """Generate Redis keys for rate limiting."""
        timestamp = int(time.time())

        if window_type == "minute":
            window = timestamp // 60  # 1-minute windows
        elif window_type == "hour":
            window = timestamp // 3600  # 1-hour windows
        else:
            window = timestamp // 60  # Default to minute

        user_key = f"rate_limit:user:{user_id}:{category.value}:{window_type}:{window}"
        org_key = f"rate_limit:org:{org_id}:{category.value}:{window_type}:{window}"
        queue_key = f"rate_limit:queue:{org_id}:{category.value}"

        return user_key, org_key, queue_key

    async def _check_redis_rate_limit(
        self,
        user_id: str,
        org_id: str,
        category: RateLimitCategory,
        rule: RateLimitRule,
        is_premium: bool = False,
    ) -> RateLimitResult:
        """Check rate limit using Redis sliding window."""
        redis = await self._get_redis()
        if not redis:
            return await self._check_fallback_rate_limit(
                user_id, org_id, category, rule, is_premium
            )

        try:
            # Check both minute and hour windows
            minute_user_key, minute_org_key, queue_key = self._generate_keys(
                user_id, org_id, category, "minute"
            )
            hour_user_key, hour_org_key, _ = self._generate_keys(
                user_id, org_id, category, "hour"
            )

            # Use Redis pipeline for atomic operations
            pipe = redis.pipeline()

            # Get current counts
            pipe.get(minute_user_key)
            pipe.get(hour_user_key)
            pipe.get(minute_org_key)
            pipe.get(hour_org_key)
            pipe.llen(queue_key)

            results = await pipe.execute()

            minute_user_count = int(results[0] or 0)
            hour_user_count = int(results[1] or 0)
            minute_org_count = int(results[2] or 0)
            hour_org_count = int(results[3] or 0)
            queue_depth = int(results[4] or 0)

            # Calculate org limits (simplified - assumes 5 active users per org)
            quota = self._get_rate_quota(is_premium)
            estimated_active_users = 5  # TODO: Get from active user tracking
            org_minute_limit = int(
                rule.requests_per_minute * quota.org_multiplier * estimated_active_users
            )
            org_hour_limit = int(
                rule.requests_per_hour * quota.org_multiplier * estimated_active_users
            )

            # Check if request would exceed limits
            would_exceed_user_minute = minute_user_count >= rule.requests_per_minute
            would_exceed_user_hour = hour_user_count >= rule.requests_per_hour
            would_exceed_org_minute = minute_org_count >= org_minute_limit
            would_exceed_org_hour = hour_org_count >= org_hour_limit
            would_exceed_queue = queue_depth >= rule.queue_depth_limit

            # Allow burst if within burst allowance
            burst_allowed = (
                minute_user_count < rule.requests_per_minute + rule.burst_allowance
                and hour_user_count < rule.requests_per_hour
            )

            if (
                would_exceed_user_minute
                or would_exceed_user_hour
                or would_exceed_org_minute
                or would_exceed_org_hour
                or would_exceed_queue
            ):

                if not burst_allowed:
                    # Calculate retry after (time until next window)
                    current_time = int(time.time())
                    next_minute_window = ((current_time // 60) + 1) * 60
                    retry_after = next_minute_window - current_time

                    return RateLimitResult(
                        allowed=False,
                        requests_remaining=max(
                            0, rule.requests_per_minute - minute_user_count
                        ),
                        reset_time=next_minute_window,
                        retry_after=retry_after,
                        queue_depth=queue_depth,
                    )

            # Request allowed - increment counters atomically
            pipe = redis.pipeline()

            # Increment user counters
            pipe.incr(minute_user_key)
            pipe.expire(minute_user_key, 120)  # Keep for 2 minutes
            pipe.incr(hour_user_key)
            pipe.expire(hour_user_key, 7200)  # Keep for 2 hours

            # Increment org counters
            pipe.incr(minute_org_key)
            pipe.expire(minute_org_key, 120)
            pipe.incr(hour_org_key)
            pipe.expire(hour_org_key, 7200)

            # Track in processing queue
            pipe.lpush(queue_key, f"{user_id}:{int(time.time())}")
            pipe.ltrim(queue_key, 0, rule.queue_depth_limit - 1)
            pipe.expire(queue_key, 300)  # Keep queue for 5 minutes

            await pipe.execute()

            # Calculate remaining requests
            requests_remaining = max(
                0, rule.requests_per_minute - (minute_user_count + 1)
            )
            reset_time = ((int(time.time()) // 60) + 1) * 60

            return RateLimitResult(
                allowed=True,
                requests_remaining=requests_remaining,
                reset_time=reset_time,
                queue_depth=queue_depth + 1,
            )

        except Exception as e:
            logger.error(f"Redis rate limiting error: {e}")
            # Fallback to in-memory rate limiting on Redis errors
            return await self._check_fallback_rate_limit(
                user_id, org_id, category, rule, is_premium
            )

    async def _check_fallback_rate_limit(
        self,
        user_id: str,
        org_id: str,
        category: RateLimitCategory,
        rule: RateLimitRule,
        is_premium: bool = False,
    ) -> RateLimitResult:
        """Fallback in-memory rate limiting when Redis is unavailable."""
        current_time = time.time()

        # Clean up old entries periodically
        if current_time - self._last_cleanup > 60:
            self._cleanup_fallback_cache(current_time)
            self._last_cleanup = current_time

        user_key = f"{user_id}:{category.value}"

        if user_key not in self._fallback_cache:
            self._fallback_cache[user_key] = {
                "minute_requests": [],
                "hour_requests": [],
            }

        user_data = self._fallback_cache[user_key]

        # Remove old requests outside the window
        minute_ago = current_time - 60
        hour_ago = current_time - 3600

        user_data["minute_requests"] = [
            req_time
            for req_time in user_data["minute_requests"]
            if req_time > minute_ago
        ]
        user_data["hour_requests"] = [
            req_time for req_time in user_data["hour_requests"] if req_time > hour_ago
        ]

        minute_count = len(user_data["minute_requests"])
        hour_count = len(user_data["hour_requests"])

        # Check limits
        if (
            minute_count >= rule.requests_per_minute
            or hour_count >= rule.requests_per_hour
        ):

            next_minute = int((current_time // 60 + 1) * 60)
            retry_after = next_minute - int(current_time)

            return RateLimitResult(
                allowed=False,
                requests_remaining=max(0, rule.requests_per_minute - minute_count),
                reset_time=next_minute,
                retry_after=retry_after,
            )

        # Allow request
        user_data["minute_requests"].append(current_time)
        user_data["hour_requests"].append(current_time)

        requests_remaining = rule.requests_per_minute - (minute_count + 1)
        reset_time = int((current_time // 60 + 1) * 60)

        return RateLimitResult(
            allowed=True,
            requests_remaining=max(0, requests_remaining),
            reset_time=reset_time,
        )

    def _cleanup_fallback_cache(self, current_time: float):
        """Clean up old entries from fallback cache."""
        hour_ago = current_time - 3600

        keys_to_remove = []
        for key, data in self._fallback_cache.items():
            # Remove requests older than 1 hour
            data["hour_requests"] = [
                req_time for req_time in data["hour_requests"] if req_time > hour_ago
            ]

            # Remove entries with no recent activity
            if not data["hour_requests"]:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._fallback_cache[key]

    async def check_rate_limit(
        self,
        user_id: str,
        org_id: str,
        category: RateLimitCategory,
        is_premium: bool = False,
    ) -> RateLimitResult:
        """
        Check if a request is allowed under rate limiting rules.

        Args:
            user_id: User identifier
            org_id: Organization identifier
            category: Rate limit category for the endpoint
            is_premium: Whether this is a premium user/org

        Returns:
            RateLimitResult with allowed status and metadata
        """
        quota = self._get_rate_quota(is_premium)
        rule = quota.user_rules.get(category)

        if not rule:
            logger.warning(f"No rate limit rule found for category: {category}")
            # Default to allowing request if no rule configured
            return RateLimitResult(
                allowed=True,
                requests_remaining=1000,
                reset_time=int(time.time()) + 3600,
            )

        return await self._check_redis_rate_limit(
            user_id, org_id, category, rule, is_premium
        )

    async def record_request_completion(
        self,
        user_id: str,
        org_id: str,
        category: RateLimitCategory,
        success: bool = True,
    ):
        """Record completion of a request for queue management."""
        redis = await self._get_redis()
        if not redis:
            return

        try:
            _, _, queue_key = self._generate_keys(user_id, org_id, category)

            # Remove completed request from queue
            # In a more sophisticated implementation, we'd track specific request IDs
            await redis.rpop(queue_key)

        except Exception as e:
            logger.error(f"Error recording request completion: {e}")


# Global rate limiting service instance
rate_limit_service = RateLimitService()
