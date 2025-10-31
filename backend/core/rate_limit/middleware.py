"""
FastAPI middleware for rate limiting and throttling.

Integrates with the authentication system to provide per-user and per-org
rate limiting with configurable rules and graceful degradation.
"""

import asyncio
import logging
import time
from typing import Callable, Dict, Optional, Tuple

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.core.auth.models import User
from backend.core.rate_limit.config import RateLimitCategory, DEFAULT_RATE_LIMITS
from backend.core.rate_limit.service import rate_limit_service
from backend.core.rate_limit.metrics import (
    rate_limit_metrics,
    log_rate_limit_decision,
    log_rate_limit_middleware_error,
)

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for distributed rate limiting."""

    def __init__(
        self,
        app,
        enabled: bool = True,
        track_metrics: bool = True,
    ):
        super().__init__(app)
        self.enabled = enabled
        self.track_metrics = track_metrics
        self._request_start_times: Dict[str, float] = {}

    def _categorize_endpoint(self, method: str, path: str) -> RateLimitCategory:
        """Categorize an endpoint for rate limiting rules."""

        # Authentication endpoints
        if any(
            auth_path in path for auth_path in ["/auth/", "/login", "/token", "/logout"]
        ):
            return RateLimitCategory.AUTH

        # Admin endpoints
        if "/admin/" in path or "/rbac/" in path:
            return RateLimitCategory.ADMIN

        # Presence/heartbeat endpoints
        if any(
            presence_path in path
            for presence_path in ["/presence", "/heartbeat", "/cursor"]
        ):
            return RateLimitCategory.PRESENCE

        # Upload/file endpoints
        if any(
            upload_path in path for upload_path in ["/upload", "/file", "/attachment"]
        ):
            return RateLimitCategory.UPLOAD

        # Export/reporting endpoints
        if any(
            export_path in path for export_path in ["/export", "/report", "/download"]
        ):
            return RateLimitCategory.EXPORT

        # Search endpoints
        if any(search_path in path for search_path in ["/search", "/query", "/find"]):
            return RateLimitCategory.SEARCH

        # Categorize by HTTP method
        if method in ["GET", "HEAD", "OPTIONS"]:
            # Health checks and status endpoints get read category
            if any(
                health_path in path for health_path in ["/health", "/status", "/ping"]
            ):
                return RateLimitCategory.READ
            return RateLimitCategory.READ

        elif method in ["POST", "PUT", "PATCH", "DELETE"]:
            return RateLimitCategory.WRITE

        # Default to read for unknown methods
        return RateLimitCategory.READ

    def _extract_user_info(
        self, request: Request
    ) -> Tuple[Optional[str], Optional[str], bool]:
        """Extract user and org info from request."""
        user: Optional[User] = getattr(request.state, "user", None)

        if not user:
            # For unauthenticated requests, use IP-based limiting
            client_ip = self._get_client_ip(request)
            return f"anonymous:{client_ip}", "anonymous", False

        # TODO: Determine premium status from user/org attributes
        is_premium = getattr(user, "is_premium", False)

        return user.user_id, user.org_id, is_premium

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address, handling proxies."""
        # Check for forwarded headers (common in load balancers)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct client
        client_host = request.client.host if request.client else "unknown"
        return client_host

    def _create_rate_limit_response(
        self,
        result,
        category: RateLimitCategory,
        path: str,
    ) -> JSONResponse:
        """Create a 429 rate limit exceeded response."""

        # Get the actual rate limit from configuration
        rule = DEFAULT_RATE_LIMITS.user_rules[category]
        limit = rule.requests_per_minute  # Use per-minute limit for the header

        headers = {
            "X-RateLimit-Limit": str(limit),  # Actual rate limit
            "X-RateLimit-Remaining": str(result.requests_remaining),
            "X-RateLimit-Reset": str(result.reset_time),
        }

        if result.retry_after:
            headers["Retry-After"] = str(result.retry_after)

        # Add queue depth for debugging
        if result.queue_depth > 0:
            headers["X-RateLimit-Queue-Depth"] = str(result.queue_depth)

        error_response = {
            "detail": f"Rate limit exceeded for {category.value} requests",
            "error_code": "RATE_LIMIT_EXCEEDED",
            "retry_after": result.retry_after,
            "category": category.value,
            "path": path,
        }

        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=error_response,
            headers=headers,
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through rate limiting middleware."""

        # Skip rate limiting if disabled
        if not self.enabled:
            return await call_next(request)

        # Skip rate limiting for certain paths
        path = request.url.path
        if any(
            skip_path in path
            for skip_path in ["/health", "/metrics", "/docs", "/openapi.json"]
        ):
            return await call_next(request)

        method = request.method
        category = self._categorize_endpoint(method, path)
        user_id, org_id, is_premium = self._extract_user_info(request)

        # Skip rate limiting if we can't identify the user/org
        if not user_id or not org_id:
            logger.warning(f"Could not extract user info for rate limiting: {path}")
            return await call_next(request)

        try:
            # Check rate limit
            start_time = time.time()
            result = await rate_limit_service.check_rate_limit(
                user_id=user_id,
                org_id=org_id,
                category=category,
                is_premium=is_premium,
            )

            rate_check_duration = time.time() - start_time

            # Log slow rate limit checks
            if rate_check_duration > 0.1:  # 100ms
                logger.warning(
                    f"Slow rate limit check: {rate_check_duration:.3f}s for {user_id}/{category.value}"
                )

            if not result.allowed:
                # Log rate limit exceeded
                log_rate_limit_decision(
                    user_id=user_id,
                    org_id=org_id,
                    category=category,
                    allowed=False,
                    requests_remaining=result.requests_remaining,
                    reset_time=result.reset_time,
                    queue_depth=result.queue_depth,
                    retry_after=result.retry_after,
                )

                # Track rate limit metrics
                if self.track_metrics:
                    rate_limit_metrics.record_request(
                        user_id=user_id,
                        org_id=org_id,
                        category=category,
                        allowed=False,
                        response_time_ms=rate_check_duration * 1000,
                        queue_depth=result.queue_depth,
                    )

                return self._create_rate_limit_response(result, category, path)

            # Request allowed - track start time for completion recording
            request_id = f"{user_id}:{org_id}:{time.time()}"
            self._request_start_times[request_id] = time.time()

            # Add rate limit headers to successful responses
            response = await call_next(request)

            # Get the actual rate limit from configuration
            rule = DEFAULT_RATE_LIMITS.user_rules[category]
            limit = rule.requests_per_minute  # Use per-minute limit for the header

            # Add rate limit info to response headers
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(result.requests_remaining)
            response.headers["X-RateLimit-Reset"] = str(result.reset_time)
            response.headers["X-RateLimit-Category"] = category.value

            # Record request completion
            success = response.status_code < 500  # Don't penalize for server errors
            asyncio.create_task(
                rate_limit_service.record_request_completion(
                    user_id=user_id,
                    org_id=org_id,
                    category=category,
                    success=success,
                )
            )

            # Clean up tracking
            self._request_start_times.pop(request_id, None)

            # Track metrics
            if self.track_metrics:
                rate_limit_metrics.record_request(
                    user_id=user_id,
                    org_id=org_id,
                    category=category,
                    allowed=True,
                    response_time_ms=rate_check_duration * 1000,
                    queue_depth=result.queue_depth,
                )

            return response

        except Exception as e:
            log_rate_limit_middleware_error(str(e), path, method)
            # On rate limiting errors, allow the request through
            # This ensures the system remains available even if rate limiting fails
            return await call_next(request)
