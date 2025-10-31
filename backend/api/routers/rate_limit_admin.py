"""
Rate limiting administration and monitoring endpoints.

Provides endpoints for viewing rate limiting statistics,
adjusting quotas, and monitoring system health.
"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.core.auth.deps import require_role
from backend.core.auth.models import Role, User
from backend.core.rate_limit.config import (
    RateLimitCategory,
    DEFAULT_RATE_LIMITS,
    PREMIUM_RATE_LIMITS,
)
from backend.core.rate_limit.metrics import rate_limit_metrics
from backend.core.rate_limit.service import rate_limit_service

logger = logging.getLogger(__name__)

# Import Redis exceptions for proper error handling
try:
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
except ImportError:
    # Fallback if redis is not available
    RedisError = Exception
    RedisConnectionError = Exception

router = APIRouter(prefix="/api/admin/rate-limit", tags=["rate-limiting"])


class RateLimitStatsResponse(BaseModel):
    """Rate limiting statistics response."""

    uptime_hours: float
    total_requests: int
    total_rate_limit_hits: int
    rate_limit_hit_rates: Dict[str, float]
    average_response_times_ms: Dict[str, float]
    active_keys: int


class RateLimitRuleResponse(BaseModel):
    """Rate limiting rule response."""

    category: str
    requests_per_minute: int
    requests_per_hour: int
    burst_allowance: int
    queue_depth_limit: int


class RateLimitQuotaResponse(BaseModel):
    """Rate limiting quota response."""

    tier: str
    org_multiplier: float
    global_requests_per_second: int
    rules: List[RateLimitRuleResponse]


class RateLimitTestRequest(BaseModel):
    """Rate limit test request."""

    user_id: str
    org_id: str
    category: RateLimitCategory
    is_premium: bool = False


class RateLimitTestResponse(BaseModel):
    """Rate limit test response."""

    allowed: bool
    requests_remaining: int
    reset_time: int
    retry_after: Optional[int] = None
    queue_depth: int = 0


@router.get("/stats", response_model=RateLimitStatsResponse)
async def get_rate_limit_stats(
    user: User = Depends(require_role(Role.ADMIN)),
) -> RateLimitStatsResponse:
    """
    Get rate limiting statistics.

    Admin-only endpoint that provides insights into rate limiting
    behavior across the platform.
    """
    stats = rate_limit_metrics.get_stats_summary()
    return RateLimitStatsResponse(**stats)


@router.post("/stats/reset")
async def reset_rate_limit_stats(
    user: User = Depends(require_role(Role.ADMIN)),
) -> Dict[str, str]:
    """
    Reset rate limiting statistics.

    Admin-only endpoint to reset all rate limiting metrics
    and start fresh collection.
    """
    rate_limit_metrics.reset_stats()
    return {"message": "Rate limiting statistics reset successfully"}


@router.get("/quotas", response_model=List[RateLimitQuotaResponse])
async def get_rate_limit_quotas(
    user: User = Depends(require_role(Role.ADMIN)),
) -> List[RateLimitQuotaResponse]:
    """
    Get configured rate limiting quotas.

    Returns the current rate limiting configuration for
    different user tiers.
    """
    quotas = []

    # Default tier
    default_rules = [
        RateLimitRuleResponse(
            category=category.value,
            requests_per_minute=rule.requests_per_minute,
            requests_per_hour=rule.requests_per_hour,
            burst_allowance=rule.burst_allowance,
            queue_depth_limit=rule.queue_depth_limit,
        )
        for category, rule in DEFAULT_RATE_LIMITS.user_rules.items()
    ]

    quotas.append(
        RateLimitQuotaResponse(
            tier="default",
            org_multiplier=DEFAULT_RATE_LIMITS.org_multiplier,
            global_requests_per_second=DEFAULT_RATE_LIMITS.global_requests_per_second,
            rules=default_rules,
        )
    )

    # Premium tier
    premium_rules = [
        RateLimitRuleResponse(
            category=category.value,
            requests_per_minute=rule.requests_per_minute,
            requests_per_hour=rule.requests_per_hour,
            burst_allowance=rule.burst_allowance,
            queue_depth_limit=rule.queue_depth_limit,
        )
        for category, rule in PREMIUM_RATE_LIMITS.user_rules.items()
    ]

    quotas.append(
        RateLimitQuotaResponse(
            tier="premium",
            org_multiplier=PREMIUM_RATE_LIMITS.org_multiplier,
            global_requests_per_second=PREMIUM_RATE_LIMITS.global_requests_per_second,
            rules=premium_rules,
        )
    )

    return quotas


@router.post("/test", response_model=RateLimitTestResponse)
async def test_rate_limit(
    request: RateLimitTestRequest,
    user: User = Depends(require_role(Role.ADMIN)),
) -> RateLimitTestResponse:
    """
    Test rate limiting for a specific user/org/category.

    Admin-only endpoint for testing rate limiting behavior
    without actually affecting the user's quota.
    """
    try:
        result = await rate_limit_service.check_rate_limit(
            user_id=request.user_id,
            org_id=request.org_id,
            category=request.category,
            is_premium=request.is_premium,
        )

        return RateLimitTestResponse(
            allowed=result.allowed,
            requests_remaining=result.requests_remaining,
            reset_time=result.reset_time,
            retry_after=result.retry_after,
            queue_depth=result.queue_depth,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rate limit test failed: {str(e)}",
        )


@router.get("/health")
async def rate_limit_health_check(
    user: User = Depends(require_role(Role.ADMIN)),
) -> Dict[str, str]:
    """
    Check rate limiting system health.

    Admin-only endpoint to verify that rate limiting
    components are functioning properly.
    """
    try:
        # Test Redis connection
        redis = await rate_limit_service._get_redis()
        redis_status = "connected" if redis else "unavailable"

        if redis:
            # Test Redis ping
            await redis.ping()
            redis_latency = "healthy"
        else:
            redis_latency = "n/a"

        # Test fallback cache
        fallback_status = "available"

        return {
            "status": "healthy",
            "redis_status": redis_status,
            "redis_latency": redis_latency,
            "fallback_status": fallback_status,
            "message": "Rate limiting system is operational",
        }

    except (RedisError, RedisConnectionError, OSError) as e:
        logger.exception(
            "Redis-related exception during rate limit health check: %s", e
        )
        return {
            "status": "degraded",
            "redis_status": "error",
            "redis_latency": "error",
            "fallback_status": "available",
            "message": "Redis connection issues detected. Fallback cache available.",
        }
    except Exception as e:
        logger.exception("Unexpected exception during rate limit health check: %s", e)
        # Re-raise programming errors instead of masking them
        if isinstance(e, (AttributeError, TypeError, ValueError)):
            raise
        return {
            "status": "error",
            "redis_status": "unknown",
            "redis_latency": "unknown",
            "fallback_status": "unknown",
            "message": "Unexpected error in rate limiting system. Check server logs.",
        }
