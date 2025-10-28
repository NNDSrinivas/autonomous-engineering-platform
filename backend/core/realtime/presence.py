"""Helper functions for presence tracking with TTL management."""

from __future__ import annotations

import time
from typing import Dict, Tuple

from backend.core.settings import settings

# In-process cache for quick TTL checks (authoritative broadcast is Redis)
# key = (plan_id, user_id) -> last heartbeat ts
_presence_cache: Dict[Tuple[str, str], int] = {}


def presence_channel(plan_id: str) -> str:
    """Get Redis channel name for presence events."""
    return f"presence:{settings.PLAN_CHANNEL_PREFIX}{plan_id}"


def cursor_channel(plan_id: str) -> str:
    """Get Redis channel name for cursor events."""
    return f"cursor:{settings.PLAN_CHANNEL_PREFIX}{plan_id}"


def note_heartbeat(plan_id: str, user_id: str) -> None:
    """Record heartbeat timestamp for a user in a plan."""
    _presence_cache[(plan_id, user_id)] = int(time.time())


def is_expired(plan_id: str, user_id: str) -> bool:
    """Check if a user's presence has expired based on TTL."""
    ts = _presence_cache.get((plan_id, user_id))
    if ts is None:
        return True
    return (int(time.time()) - ts) > settings.PRESENCE_TTL_SEC
