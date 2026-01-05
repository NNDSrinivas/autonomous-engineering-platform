"""FastAPI dependency injection providers."""

from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from backend.orchestrator import NaviOrchestrator

from fastapi import Header

from backend.infra.broadcast.base import Broadcast, BroadcastRegistry
from backend.infra.broadcast.memory import InMemoryBroadcaster
from backend.infra.broadcast.redis import RedisBroadcaster
from backend.core.settings import settings

# Re-export database session dependency for convenience
from backend.database.session import get_db  # noqa: F401

__all__ = ["get_broadcaster", "get_db", "get_current_user", "get_orchestrator"]

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


# ---------------------------------------------------------------------------
# Authentication Dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_org_id: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Get current authenticated user from request headers.

    For now, this is a simple implementation that accepts any authorization.
    In production, this would validate JWT tokens or API keys.
    """

    # Simple authentication for development
    # In production, implement proper JWT/API key validation
    user_id = "default_user"

    if authorization:
        # Extract user info from Bearer token (simplified)
        if authorization.startswith("Bearer "):
            token = authorization[7:]
            # In production: validate and decode JWT token
            user_id = f"user_{hash(token) % 10000}"

    if x_api_key:
        # Use API key as user identifier (simplified)
        user_id = f"api_user_{hash(x_api_key) % 10000}"

    return {
        "user_id": user_id,
        "authenticated": True,
        "permissions": ["intent:classify", "models:list", "agent:use"],
        "org_id": x_org_id or None,
    }


# ---------------------------------------------------------------------------
# NAVI Orchestrator Dependencies
# ---------------------------------------------------------------------------

_orchestrator_instance: Optional["NaviOrchestrator"] = None
_orchestrator_lock = threading.Lock()


def get_orchestrator() -> "NaviOrchestrator":
    """
    Get a singleton NAVI orchestrator instance.

    This creates a default orchestrator for API endpoints.
    Individual requests can override settings via parameters.
    """
    global _orchestrator_instance

    # Fast path: instance already created
    if _orchestrator_instance is not None:
        return _orchestrator_instance

    # Slow path: create instance (with lock)
    with _orchestrator_lock:
        # Double-check
        if _orchestrator_instance is not None:
            return _orchestrator_instance

        try:
            from backend.orchestrator import NaviOrchestrator
            from backend.agent.planner_v3 import SimplePlanner
            from backend.agent.tool_executor_real import RealToolExecutor
            from backend.ai.intent_llm_classifier import LLMIntentClassifier
            from backend.core.db import get_db

            # Create production orchestrator with real tool execution
            db = next(get_db())  # Get database session for tools
            _orchestrator_instance = NaviOrchestrator(
                planner=SimplePlanner(),
                tool_executor=RealToolExecutor(db=db),
                llm_classifier=LLMIntentClassifier(),
                # Optional components will be auto-initialized if available
            )

            logger.info(
                "[Deps] Created production NAVI orchestrator with real tool execution"
            )

        except ImportError as e:
            logger.warning(f"[Deps] Could not create production orchestrator: {e}")

            # Fallback to minimal orchestrator with simple components
            from backend.orchestrator import NaviOrchestrator
            from backend.agent.planner_v3 import SimplePlanner
            from backend.agent.tool_executor_real import RealToolExecutor
            from backend.core.db import get_db

            db = next(get_db())  # Get database session for tools
            _orchestrator_instance = NaviOrchestrator(
                planner=SimplePlanner(),
                tool_executor=RealToolExecutor(db=db),
                # No LLM classifier - will use heuristic fallback
            )

        return _orchestrator_instance
