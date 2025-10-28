"""Helper functions for presence tracking with TTL management."""

from __future__ import annotations

import threading
import time
from typing import Dict, Tuple

from backend.core.settings import settings

# In-process cache for quick TTL checks (authoritative broadcast is Redis)
# key = (plan_id, user_id) -> last heartbeat ts
#
# LIMITATION: This cache is per-server instance. In horizontal scaling (multi-server),
# each server maintains separate state. For production multi-server deployments,
# consider storing presence state in Redis with SETEX for automatic TTL expiration.
# Current implementation is suitable for single-server or development environments.
_presence_cache: Dict[Tuple[str, str], int] = {}
_cache_lock = threading.Lock()


def _cleanup_presence_cache() -> None:
    """
    Periodic cleanup task to remove expired presence entries.
    Prevents memory leaks in long-running servers.

    Cleanup interval is configurable via PRESENCE_CLEANUP_INTERVAL_SEC setting.
    """
    while True:
        time.sleep(settings.PRESENCE_CLEANUP_INTERVAL_SEC)
        now = int(time.time())
        with _cache_lock:
            keys_to_delete = [
                key
                for key, ts in _presence_cache.items()
                if (now - ts) > settings.PRESENCE_TTL_SEC
            ]
            for key in keys_to_delete:
                del _presence_cache[key]


# Start background cleanup thread on module import
_cleanup_thread = threading.Thread(target=_cleanup_presence_cache, daemon=True)
_cleanup_thread.start()


def presence_channel(plan_id: str) -> str:
    """Get Redis channel name for presence events."""
    return f"presence:{settings.PLAN_CHANNEL_PREFIX}{plan_id}"


def cursor_channel(plan_id: str) -> str:
    """Get Redis channel name for cursor events."""
    return f"cursor:{settings.PLAN_CHANNEL_PREFIX}{plan_id}"


def note_heartbeat(plan_id: str, user_id: str) -> None:
    """
    Record heartbeat timestamp for a user in a plan.

    Thread-safe operation using lock to prevent race conditions.
    """
    with _cache_lock:
        _presence_cache[(plan_id, user_id)] = int(time.time())


def is_expired(plan_id: str, user_id: str) -> bool:
    """
    Check if a user's presence has expired based on TTL.

    Thread-safe operation using lock to prevent race conditions.
    """
    with _cache_lock:
        ts = _presence_cache.get((plan_id, user_id))
        if ts is None:
            return True
        return (int(time.time()) - ts) > settings.PRESENCE_TTL_SEC
