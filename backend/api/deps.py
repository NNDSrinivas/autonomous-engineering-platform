"""FastAPI dependency injection providers."""

from __future__ import annotations

import logging
import os
import threading

from backend.infra.broadcast.base import Broadcast, BroadcastRegistry
from backend.infra.broadcast.memory import InMemoryBroadcaster
from backend.infra.broadcast.redis import RedisBroadcaster
from backend.core.settings import settings

# Re-export database session dependency for convenience
from backend.database.session import get_db  # noqa: F401

__all__ = ["get_broadcaster", "get_db"]

logger = logging.getLogger(__name__)

BROADCAST_KEY = "plan_broadcast"

# Thread-safe singleton pattern
_broadcaster_instance: Broadcast | None = None
_broadcaster_lock = threading.Lock()


def _make_broadcaster() -> Broadcast:
    """
    Create and register a broadcaster instance.

    Automatically selects Redis if REDIS_URL is set, otherwise uses in-memory.
    Thread-safe initialization using double-checked locking pattern.
    """
    global _broadcaster_instance

    # Fast path: instance already created (no lock needed)
    if _broadcaster_instance is not None:
        return _broadcaster_instance

    # Slow path: need to create instance (acquire lock)
    with _broadcaster_lock:
        # Double-check: another thread might have created it while we waited
        if _broadcaster_instance is not None:
            return _broadcaster_instance

        redis_url = settings.REDIS_URL

        if redis_url:
            logger.info(f"Using Redis broadcaster: {redis_url}")
            inst = RedisBroadcaster(redis_url)
        else:
            logger.info("Using in-memory broadcaster (dev mode)")
            if os.getenv("ENV") in {"production", "prod", "staging"}:
                logger.warning(
                    "Production environment detected but REDIS_URL not set! "
                    "In-memory broadcaster will NOT work with multiple server instances."
                )
            inst = InMemoryBroadcaster()

        BroadcastRegistry.set(BROADCAST_KEY, inst)
        _broadcaster_instance = inst
        return inst


def get_broadcaster() -> Broadcast:
    """
    FastAPI dependency to get the singleton broadcaster instance.

    Usage:
        @router.get("/stream")
        async def stream(bc: Broadcast = Depends(get_broadcaster)):
            ...
    """
    inst = BroadcastRegistry.get(BROADCAST_KEY)
    if inst is None:
        inst = _make_broadcaster()
    return inst
