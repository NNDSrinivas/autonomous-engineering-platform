"""FastAPI dependency injection providers."""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from backend.infra.broadcast.base import Broadcast, BroadcastRegistry
from backend.infra.broadcast.memory import InMemoryBroadcaster
from backend.infra.broadcast.redis import RedisBroadcaster
from backend.core.settings import settings

logger = logging.getLogger(__name__)

BROADCAST_KEY = "plan_broadcast"


@lru_cache
def _make_broadcaster() -> Broadcast:
    """
    Create and register a broadcaster instance.

    Automatically selects Redis if REDIS_URL is set, otherwise uses in-memory.
    """
    redis_url = settings.REDIS_URL or os.getenv("REDIS_URL")

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
