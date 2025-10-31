"""
Distributed caching system for Autonomous Engineering Platform.

This module provides a Redis-based caching layer with adaptive TTL policies,
comprehensive metrics, and entity-specific optimizations for improved performance.
"""

from .service import cache_service as cache
from .decorators import cached, invalidate
from .keys import plan_key, user_key, role_key, org_key_val, generic
from .middleware import CacheMiddleware

__all__ = [
    "cache",
    "cached", 
    "invalidate",
    "plan_key",
    "user_key", 
    "role_key",
    "org_key_val",
    "generic",
    "CacheMiddleware"
]
