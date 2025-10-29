"""Helper functions for presence tracking with TTL management."""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional, Tuple

from backend.core.settings import settings

logger = logging.getLogger(__name__)

# In-process cache for quick TTL checks (authoritative broadcast is Redis)
# key = (plan_id, user_id) -> last heartbeat ts
#
# DESIGN TRADEOFF: Using in-memory cache instead of Redis for presence state.
# - Pros: Fast local checks, simpler implementation, no Redis SETEX overhead
# - Cons: State is per-server in horizontal scaling (each server has separate view)
# - Current: Acceptable for single-server deployments and development
# - Future: If multi-server consistency is required, migrate to Redis with SETEX for
#   automatic TTL expiration. This would require:
#   1. Replace _presence_cache with Redis SETEX calls
#   2. Use Redis key expiration instead of cleanup thread
#   3. Handle Redis connection failures gracefully
_presence_cache: Dict[Tuple[str, str], int] = {}
_cache_lock = threading.Lock()
_cleanup_thread: Optional[threading.Thread] = None
_cleanup_stop_event = threading.Event()


def _cleanup_presence_cache() -> None:
    """
    Periodic cleanup task to remove expired presence entries.
    Prevents memory leaks in long-running servers.

    Cleanup interval is configurable via PRESENCE_CLEANUP_INTERVAL_SEC setting.
    Stops when _cleanup_stop_event is set.
    """
    while not _cleanup_stop_event.is_set():
        _cleanup_stop_event.wait(timeout=settings.PRESENCE_CLEANUP_INTERVAL_SEC)
        if _cleanup_stop_event.is_set():
            break
        now = int(time.time())
        with _cache_lock:
            keys_to_delete = [
                key
                for key, ts in _presence_cache.items()
                if (now - ts) > settings.PRESENCE_TTL_SEC
            ]
            for key in keys_to_delete:
                del _presence_cache[key]


def start_cleanup_thread() -> None:
    """
    Start the background cleanup thread.

    Safe to call multiple times - will not create duplicate threads.
    Called automatically from application startup (see backend/api/main.py).
    """
    global _cleanup_thread
    with _cache_lock:
        if _cleanup_thread is None or not _cleanup_thread.is_alive():
            _cleanup_stop_event.clear()
            _cleanup_thread = threading.Thread(
                target=_cleanup_presence_cache, daemon=True, name="presence-cleanup"
            )
            _cleanup_thread.start()


def stop_cleanup_thread() -> None:
    """
    Stop the background cleanup thread gracefully.

    Called during application shutdown or in tests for cleanup.
    Logs a warning if the thread doesn't terminate within timeout.
    """
    global _cleanup_thread
    if _cleanup_thread is not None and _cleanup_thread.is_alive():
        _cleanup_stop_event.set()
        _cleanup_thread.join(timeout=2.0)
        if _cleanup_thread.is_alive():
            logger.warning(
                "Presence cleanup thread did not terminate within 2s timeout. "
                "Thread will continue running as daemon and be terminated on process exit."
            )
        _cleanup_thread = None


def presence_channel(plan_id: str) -> str:
    """
    Get Redis channel name for presence events.

    Format: presence:plan:{plan_id}
    Note: `PLAN_CHANNEL_PREFIX` is defined in settings and already includes the
    trailing colon (for example "plan:"). This function simply prepends the
    namespace and appends the plan id. Example: presence_channel("pz1") ->
    "presence:plan:pz1"
    """
    return f"presence:{settings.PLAN_CHANNEL_PREFIX}{plan_id}"


def cursor_channel(plan_id: str) -> str:
    """
    Get Redis channel name for cursor events.

    Format: cursor:plan:{plan_id}
    Note: `PLAN_CHANNEL_PREFIX` is defined in settings and already includes the
    trailing colon (for example "plan:"). This function simply prepends the
    namespace and appends the plan id. Example: cursor_channel("pz1") ->
    "cursor:plan:pz1"
    """
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
