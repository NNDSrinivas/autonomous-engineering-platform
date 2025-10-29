"""Helper functions for presence tracking with TTL management."""

from __future__ import annotations

import threading
import time
from typing import Dict, Optional, Tuple

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
    """
    global _cleanup_thread
    if _cleanup_thread is not None and _cleanup_thread.is_alive():
        _cleanup_stop_event.set()
        _cleanup_thread.join(timeout=2.0)
        _cleanup_thread = None


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
