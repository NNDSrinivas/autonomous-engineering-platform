"""
Rate limiting configuration and models.

Defines rate limiting rules, quotas, and categories for different
types of API endpoints and user roles.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict


class RateLimitCategory(str, Enum):
    """Categories of API endpoints with different rate limit rules."""

    # High-frequency operations
    READ = "read"  # GET requests, health checks
    PRESENCE = "presence"  # Heartbeat, cursor updates

    # Medium-frequency operations
    WRITE = "write"  # POST/PUT/DELETE requests
    SEARCH = "search"  # Search and query operations

    # Low-frequency operations
    ADMIN = "admin"  # Administrative operations
    AUTH = "auth"  # Authentication operations

    # Special categories
    UPLOAD = "upload"  # File uploads, bulk operations
    EXPORT = "export"  # Data export, report generation


@dataclass
class RateLimitRule:
    """Rate limiting rule configuration."""

    requests_per_minute: int
    requests_per_hour: int
    burst_allowance: int  # Extra requests allowed in short bursts

    # Back-pressure controls
    queue_depth_limit: int = 100
    enable_graceful_degradation: bool = True


@dataclass
class RateLimitQuota:
    """Rate limiting quotas for different user types and organizations."""

    # Per-user limits
    user_rules: Dict[RateLimitCategory, RateLimitRule]

    # Per-organization limits (aggregate across all users)
    org_multiplier: float = (
        10.0  # Org limit = user_limit * org_multiplier * active_users
    )

    # Global system limits
    global_requests_per_second: int = 1000


# Default rate limiting configuration
DEFAULT_RATE_LIMITS = RateLimitQuota(
    user_rules={
        RateLimitCategory.READ: RateLimitRule(
            requests_per_minute=300,  # 5 requests/second sustained
            requests_per_hour=10000,  # ~2.8 requests/second average
            burst_allowance=50,  # Allow short bursts
            queue_depth_limit=200,
        ),
        RateLimitCategory.PRESENCE: RateLimitRule(
            requests_per_minute=120,  # 2 requests/second for heartbeats
            requests_per_hour=3600,  # 1 request/second average
            burst_allowance=10,  # Small burst allowance
            queue_depth_limit=50,
        ),
        RateLimitCategory.WRITE: RateLimitRule(
            requests_per_minute=60,  # 1 request/second sustained
            requests_per_hour=2000,  # Conservative for mutations
            burst_allowance=20,
            queue_depth_limit=100,
        ),
        RateLimitCategory.SEARCH: RateLimitRule(
            requests_per_minute=120,  # 2 requests/second
            requests_per_hour=3600,
            burst_allowance=30,
            queue_depth_limit=150,
        ),
        RateLimitCategory.ADMIN: RateLimitRule(
            requests_per_minute=30,  # 0.5 requests/second
            requests_per_hour=500,  # Very conservative for admin ops
            burst_allowance=10,
            queue_depth_limit=20,
        ),
        RateLimitCategory.AUTH: RateLimitRule(
            requests_per_minute=20,  # ~0.33 requests/second
            requests_per_hour=200,  # Login attempts, token refresh
            burst_allowance=5,
            queue_depth_limit=30,
        ),
        RateLimitCategory.UPLOAD: RateLimitRule(
            requests_per_minute=10,  # Large operations
            requests_per_hour=100,
            burst_allowance=3,
            queue_depth_limit=10,
        ),
        RateLimitCategory.EXPORT: RateLimitRule(
            requests_per_minute=5,  # Very expensive operations
            requests_per_hour=50,
            burst_allowance=2,
            queue_depth_limit=5,
        ),
    },
    org_multiplier=15.0,  # Organizations get 15x individual user limits per active user
    global_requests_per_second=2000,
)


# Premium tier with higher limits
PREMIUM_RATE_LIMITS = RateLimitQuota(
    user_rules={
        RateLimitCategory.READ: RateLimitRule(
            requests_per_minute=600,  # 10 requests/second
            requests_per_hour=25000,
            burst_allowance=100,
            queue_depth_limit=500,
        ),
        RateLimitCategory.PRESENCE: RateLimitRule(
            requests_per_minute=240,  # 4 requests/second
            requests_per_hour=7200,
            burst_allowance=20,
            queue_depth_limit=100,
        ),
        RateLimitCategory.WRITE: RateLimitRule(
            requests_per_minute=180,  # 3 requests/second
            requests_per_hour=6000,
            burst_allowance=50,
            queue_depth_limit=300,
        ),
        RateLimitCategory.SEARCH: RateLimitRule(
            requests_per_minute=300,  # 5 requests/second
            requests_per_hour=10000,
            burst_allowance=75,
            queue_depth_limit=400,
        ),
        RateLimitCategory.ADMIN: RateLimitRule(
            requests_per_minute=90,  # 1.5 requests/second
            requests_per_hour=1500,
            burst_allowance=30,
            queue_depth_limit=50,
        ),
        RateLimitCategory.AUTH: RateLimitRule(
            requests_per_minute=60,  # 1 request/second
            requests_per_hour=600,
            burst_allowance=15,
            queue_depth_limit=75,
        ),
        RateLimitCategory.UPLOAD: RateLimitRule(
            requests_per_minute=30,
            requests_per_hour=300,
            burst_allowance=10,
            queue_depth_limit=25,
        ),
        RateLimitCategory.EXPORT: RateLimitRule(
            requests_per_minute=15,
            requests_per_hour=150,
            burst_allowance=5,
            queue_depth_limit=15,
        ),
    },
    org_multiplier=25.0,  # Premium orgs get higher multipliers
    global_requests_per_second=5000,
)
