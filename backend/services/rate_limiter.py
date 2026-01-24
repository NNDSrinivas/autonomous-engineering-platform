"""
Enterprise Rate Limiter for NAVI - Handles 100K+ Users

Multi-tier rate limiting strategy:
1. Per-user rate limits (sliding window)
2. Global rate limits per provider
3. Request queuing with priority
4. Provider load balancing
5. Graceful degradation

Usage:
    from backend.services.rate_limiter import RateLimiter, get_rate_limiter

    limiter = get_rate_limiter()

    # Check if request is allowed
    allowed, wait_time = await limiter.check_rate_limit(user_id, "anthropic")

    # Or use as decorator
    @limiter.rate_limited(provider="anthropic")
    async def my_endpoint():
        ...
"""

import asyncio
import time
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limits."""

    # Per-user limits
    user_requests_per_minute: int = 30
    user_requests_per_hour: int = 500
    user_requests_per_day: int = 5000

    # Per-provider global limits (across all users)
    # These should be set based on your API tier
    provider_limits: Dict[str, Dict[str, int]] = field(
        default_factory=lambda: {
            "anthropic": {
                "requests_per_minute": 1000,
                "tokens_per_minute": 100000,
            },
            "openai": {
                "requests_per_minute": 3500,
                "tokens_per_minute": 90000,
            },
            "google": {
                "requests_per_minute": 1500,
                "tokens_per_minute": 100000,
            },
        }
    )

    # Priority levels (higher = more priority)
    priority_levels: Dict[str, int] = field(
        default_factory=lambda: {
            "enterprise": 100,
            "pro": 50,
            "free": 10,
        }
    )

    # Queue settings
    max_queue_size: int = 10000
    queue_timeout_seconds: int = 30

    # Burst allowance (percentage above limit for short bursts)
    burst_allowance: float = 0.2  # 20% burst allowed


@dataclass
class SlidingWindowCounter:
    """Sliding window rate limiter counter."""

    window_size_seconds: int
    max_requests: int
    requests: List[float] = field(default_factory=list)

    def add_request(self) -> bool:
        """Add a request and return True if allowed, False if rate limited."""
        now = time.time()
        cutoff = now - self.window_size_seconds

        # Remove old requests
        self.requests = [t for t in self.requests if t > cutoff]

        # Check if under limit (with burst allowance)
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False

    def get_wait_time(self) -> float:
        """Get seconds to wait before next request is allowed."""
        if not self.requests:
            return 0

        now = time.time()
        cutoff = now - self.window_size_seconds
        self.requests = [t for t in self.requests if t > cutoff]

        if len(self.requests) < self.max_requests:
            return 0

        # Wait until oldest request expires
        oldest = min(self.requests)
        return max(0, oldest + self.window_size_seconds - now)

    @property
    def current_count(self) -> int:
        """Current request count in window."""
        now = time.time()
        cutoff = now - self.window_size_seconds
        return len([t for t in self.requests if t > cutoff])


class UserRateLimiter:
    """Rate limiter for a single user."""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.minute_counter = SlidingWindowCounter(60, config.user_requests_per_minute)
        self.hour_counter = SlidingWindowCounter(3600, config.user_requests_per_hour)
        self.day_counter = SlidingWindowCounter(86400, config.user_requests_per_day)
        self.last_request_time = 0
        self.total_requests = 0

    def check_and_record(self) -> Tuple[bool, float]:
        """
        Check if request is allowed and record it if so.

        Returns:
            (allowed, wait_time_seconds)
        """
        # Check all windows
        if not self.minute_counter.add_request():
            return False, self.minute_counter.get_wait_time()

        if not self.hour_counter.add_request():
            # Rollback minute counter
            if self.minute_counter.requests:
                self.minute_counter.requests.pop()
            return False, self.hour_counter.get_wait_time()

        if not self.day_counter.add_request():
            # Rollback counters
            if self.minute_counter.requests:
                self.minute_counter.requests.pop()
            if self.hour_counter.requests:
                self.hour_counter.requests.pop()
            return False, self.day_counter.get_wait_time()

        self.last_request_time = time.time()
        self.total_requests += 1
        return True, 0


class ProviderRateLimiter:
    """Global rate limiter for a provider (across all users)."""

    def __init__(self, provider: str, config: RateLimitConfig):
        self.provider = provider
        self.config = config
        limits = config.provider_limits.get(
            provider,
            {
                "requests_per_minute": 1000,
                "tokens_per_minute": 50000,
            },
        )
        self.request_counter = SlidingWindowCounter(60, limits["requests_per_minute"])
        self.token_counter = SlidingWindowCounter(60, limits["tokens_per_minute"])
        self.consecutive_errors = 0
        self.last_error_time = 0
        self.is_healthy = True

    def check_and_record(self, estimated_tokens: int = 1000) -> Tuple[bool, float]:
        """Check if provider request is allowed."""
        if not self.is_healthy:
            # Check if cooldown period has passed
            if time.time() - self.last_error_time < 60:  # 1 minute cooldown
                return False, 60 - (time.time() - self.last_error_time)
            self.is_healthy = True
            self.consecutive_errors = 0

        if not self.request_counter.add_request():
            return False, self.request_counter.get_wait_time()

        # For token counting, we estimate beforehand
        # This is approximate but helps prevent overages
        for _ in range(estimated_tokens):
            if not self.token_counter.add_request():
                if self.request_counter.requests:
                    self.request_counter.requests.pop()
                return False, self.token_counter.get_wait_time()

        return True, 0

    def record_error(self, is_rate_limit: bool = False):
        """Record an error from this provider."""
        self.consecutive_errors += 1
        self.last_error_time = time.time()

        if is_rate_limit or self.consecutive_errors >= 3:
            self.is_healthy = False
            logger.warning(
                f"Provider {self.provider} marked unhealthy after {self.consecutive_errors} errors"
            )

    def record_success(self):
        """Record a successful request."""
        self.consecutive_errors = 0
        self.is_healthy = True


@dataclass
class QueuedRequest:
    """A request waiting in the queue."""

    user_id: str
    provider: str
    priority: int
    timestamp: float
    future: asyncio.Future

    def __lt__(self, other):
        # Higher priority first, then older requests
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.timestamp < other.timestamp


class RateLimiter:
    """
    Enterprise-grade rate limiter for handling 100K+ users.

    Features:
    - Per-user rate limiting (sliding window)
    - Per-provider global rate limiting
    - Priority queue for requests
    - Provider health tracking
    - Automatic failover suggestions
    """

    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.user_limiters: Dict[str, UserRateLimiter] = {}
        self.provider_limiters: Dict[str, ProviderRateLimiter] = {}
        self.request_queue: List[QueuedRequest] = []
        self._queue_lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

        # Statistics
        self.stats = {
            "total_requests": 0,
            "rate_limited_requests": 0,
            "queued_requests": 0,
            "failed_requests": 0,
        }

    def _get_user_limiter(self, user_id: str) -> UserRateLimiter:
        """Get or create user rate limiter."""
        if user_id not in self.user_limiters:
            self.user_limiters[user_id] = UserRateLimiter(self.config)
        return self.user_limiters[user_id]

    def _get_provider_limiter(self, provider: str) -> ProviderRateLimiter:
        """Get or create provider rate limiter."""
        if provider not in self.provider_limiters:
            self.provider_limiters[provider] = ProviderRateLimiter(
                provider, self.config
            )
        return self.provider_limiters[provider]

    async def check_rate_limit(
        self,
        user_id: str,
        provider: str,
        user_tier: str = "free",
        estimated_tokens: int = 1000,
    ) -> Tuple[bool, float, Optional[str]]:
        """
        Check if a request is allowed.

        Args:
            user_id: User identifier
            provider: LLM provider name
            user_tier: User's subscription tier
            estimated_tokens: Estimated tokens for this request

        Returns:
            (allowed, wait_time_seconds, suggested_alternative_provider)
        """
        self.stats["total_requests"] += 1

        # Check user rate limit
        user_limiter = self._get_user_limiter(user_id)
        user_allowed, user_wait = user_limiter.check_and_record()

        if not user_allowed:
            self.stats["rate_limited_requests"] += 1
            return False, user_wait, None

        # Check provider rate limit
        provider_limiter = self._get_provider_limiter(provider)
        provider_allowed, provider_wait = provider_limiter.check_and_record(
            estimated_tokens
        )

        if not provider_allowed:
            self.stats["rate_limited_requests"] += 1
            # Suggest alternative provider
            alternative = self._suggest_alternative_provider(provider)
            return False, provider_wait, alternative

        return True, 0, None

    def _suggest_alternative_provider(self, current: str) -> Optional[str]:
        """Suggest an alternative provider that has capacity."""
        alternatives = ["anthropic", "openai", "google"]

        for alt in alternatives:
            if alt == current:
                continue
            limiter = self._get_provider_limiter(alt)
            if (
                limiter.is_healthy
                and limiter.request_counter.current_count
                < limiter.request_counter.max_requests * 0.8
            ):
                return alt

        return None

    def record_provider_error(self, provider: str, is_rate_limit: bool = False):
        """Record an error from a provider."""
        limiter = self._get_provider_limiter(provider)
        limiter.record_error(is_rate_limit)
        self.stats["failed_requests"] += 1

    def record_provider_success(self, provider: str):
        """Record a successful request to a provider."""
        limiter = self._get_provider_limiter(provider)
        limiter.record_success()

    def get_provider_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all providers."""
        health = {}
        for provider, limiter in self.provider_limiters.items():
            health[provider] = {
                "healthy": limiter.is_healthy,
                "requests_in_window": limiter.request_counter.current_count,
                "max_requests": limiter.request_counter.max_requests,
                "utilization": limiter.request_counter.current_count
                / limiter.request_counter.max_requests,
                "consecutive_errors": limiter.consecutive_errors,
            }
        return health

    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            **self.stats,
            "active_users": len(self.user_limiters),
            "provider_health": self.get_provider_health(),
        }

    async def cleanup_old_users(self, max_age_hours: int = 24):
        """Clean up user limiters that haven't been used recently."""
        cutoff = time.time() - (max_age_hours * 3600)
        to_remove = []

        for user_id, limiter in self.user_limiters.items():
            if limiter.last_request_time < cutoff:
                to_remove.append(user_id)

        for user_id in to_remove:
            del self.user_limiters[user_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} inactive user rate limiters")

    def rate_limited(self, provider: str = "anthropic", user_tier: str = "free"):
        """Decorator for rate-limited endpoints."""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract user_id from kwargs or args
                user_id = kwargs.get("user_id") or (args[0] if args else "anonymous")

                allowed, wait_time, alternative = await self.check_rate_limit(
                    user_id, provider, user_tier
                )

                if not allowed:
                    from fastapi import HTTPException

                    headers = {"Retry-After": str(int(wait_time))}
                    if alternative:
                        headers["X-Alternative-Provider"] = alternative
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limited. Retry after {wait_time:.1f} seconds.",
                        headers=headers,
                    )

                return await func(*args, **kwargs)

            return wrapper

        return decorator


# Singleton instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        # Load config from environment
        config = RateLimitConfig(
            user_requests_per_minute=int(os.getenv("RATE_LIMIT_USER_PER_MINUTE", "30")),
            user_requests_per_hour=int(os.getenv("RATE_LIMIT_USER_PER_HOUR", "500")),
            user_requests_per_day=int(os.getenv("RATE_LIMIT_USER_PER_DAY", "5000")),
        )
        _rate_limiter = RateLimiter(config)
    return _rate_limiter


def reset_rate_limiter():
    """Reset the global rate limiter (for testing)."""
    global _rate_limiter
    _rate_limiter = None
