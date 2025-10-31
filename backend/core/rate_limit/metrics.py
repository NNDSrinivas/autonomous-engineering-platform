"""
Rate limiting metrics and monitoring.

Provides Prometheus metrics and structured logging for rate limiting
to enable observability and alerting on rate limiting behavior.
"""

import logging
import time
from typing import Dict, Optional

from backend.core.rate_limit.config import RateLimitCategory

logger = logging.getLogger(__name__)

# In a production system, these would be Prometheus metrics
# For now, we'll use simple counters and logging


class RateLimitMetrics:
    """Rate limiting metrics collection."""

    def __init__(self):
        self._request_counts: Dict[str, int] = {}
        self._rate_limit_hits: Dict[str, int] = {}
        self._response_times: Dict[str, list] = {}
        self._last_reset = time.time()

    def record_request(
        self,
        user_id: str,
        org_id: str,
        category: RateLimitCategory,
        allowed: bool,
        response_time_ms: float,
        queue_depth: int = 0,
    ):
        """Record a rate limiting decision."""

        # Create metric keys
        user_key = f"user:{user_id}:{category.value}"
        org_key = f"org:{org_id}:{category.value}"
        category_key = f"category:{category.value}"

        # Increment request counters
        self._request_counts[user_key] = self._request_counts.get(user_key, 0) + 1
        self._request_counts[org_key] = self._request_counts.get(org_key, 0) + 1
        self._request_counts[category_key] = (
            self._request_counts.get(category_key, 0) + 1
        )

        if not allowed:
            # Record rate limit hits
            self._rate_limit_hits[user_key] = self._rate_limit_hits.get(user_key, 0) + 1
            self._rate_limit_hits[org_key] = self._rate_limit_hits.get(org_key, 0) + 1
            self._rate_limit_hits[category_key] = (
                self._rate_limit_hits.get(category_key, 0) + 1
            )

            # Log rate limit exceeded with structured data
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "user_id": user_id,
                    "org_id": org_id,
                    "category": category.value,
                    "queue_depth": queue_depth,
                    "response_time_ms": response_time_ms,
                    "event_type": "rate_limit_exceeded",
                },
            )

        # Record response times for performance monitoring
        if category_key not in self._response_times:
            self._response_times[category_key] = []

        self._response_times[category_key].append(response_time_ms)

        # Keep only recent response times (last 1000 requests)
        if len(self._response_times[category_key]) > 1000:
            self._response_times[category_key] = self._response_times[category_key][
                -1000:
            ]

        # Log slow rate limit checks
        if response_time_ms > 100:  # 100ms
            logger.warning(
                "Slow rate limit check",
                extra={
                    "user_id": user_id,
                    "org_id": org_id,
                    "category": category.value,
                    "response_time_ms": response_time_ms,
                    "event_type": "slow_rate_limit_check",
                },
            )

    def record_fallback_usage(self, reason: str):
        """Record when fallback rate limiting is used."""
        logger.info(
            "Rate limiting fallback activated",
            extra={
                "reason": reason,
                "event_type": "rate_limit_fallback",
            },
        )

    def record_redis_error(self, error: str, operation: str):
        """Record Redis errors in rate limiting."""
        logger.error(
            "Rate limiting Redis error",
            extra={
                "error": error,
                "operation": operation,
                "event_type": "rate_limit_redis_error",
            },
        )

    def get_stats_summary(self) -> Dict:
        """Get a summary of rate limiting statistics."""
        current_time = time.time()
        uptime_hours = (current_time - self._last_reset) / 3600

        # Calculate rate limit hit rates
        rate_limit_rates = {}
        for key, hits in self._rate_limit_hits.items():
            total_requests = self._request_counts.get(key, 1)
            rate_limit_rates[key] = (hits / total_requests) * 100

        # Calculate average response times
        avg_response_times = {}
        for category, times in self._response_times.items():
            if times:
                avg_response_times[category] = sum(times) / len(times)

        return {
            "uptime_hours": uptime_hours,
            "total_requests": sum(self._request_counts.values()),
            "total_rate_limit_hits": sum(self._rate_limit_hits.values()),
            "rate_limit_hit_rates": rate_limit_rates,
            "average_response_times_ms": avg_response_times,
            "active_keys": len(self._request_counts),
        }

    def reset_stats(self):
        """Reset all statistics."""
        self._request_counts.clear()
        self._rate_limit_hits.clear()
        self._response_times.clear()
        self._last_reset = time.time()

        logger.info(
            "Rate limiting statistics reset",
            extra={"event_type": "rate_limit_stats_reset"},
        )


# Global metrics instance
rate_limit_metrics = RateLimitMetrics()


def log_rate_limit_decision(
    user_id: str,
    org_id: str,
    category: RateLimitCategory,
    allowed: bool,
    requests_remaining: int,
    reset_time: int,
    queue_depth: int = 0,
    retry_after: Optional[int] = None,
):
    """Log a rate limiting decision with structured data."""

    log_data = {
        "user_id": user_id,
        "org_id": org_id,
        "category": category.value,
        "allowed": allowed,
        "requests_remaining": requests_remaining,
        "reset_time": reset_time,
        "queue_depth": queue_depth,
        "event_type": "rate_limit_decision",
    }

    if retry_after is not None:
        log_data["retry_after"] = retry_after

    if allowed:
        logger.debug("Rate limit check passed", extra=log_data)
    else:
        logger.warning("Rate limit check failed", extra=log_data)


def log_rate_limit_config_load(config_name: str, rules_count: int):
    """Log rate limiting configuration loading."""
    logger.info(
        "Rate limiting configuration loaded",
        extra={
            "config_name": config_name,
            "rules_count": rules_count,
            "event_type": "rate_limit_config_load",
        },
    )


def log_rate_limit_middleware_error(error: str, path: str, method: str):
    """Log rate limiting middleware errors."""
    logger.error(
        "Rate limiting middleware error",
        extra={
            "error": error,
            "path": path,
            "method": method,
            "event_type": "rate_limit_middleware_error",
        },
    )
