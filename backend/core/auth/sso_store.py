"""
SSO state store backed by Redis.

Uses the shared cache abstraction so multi-node deployments share state.
"""

from __future__ import annotations

import secrets
import time
from typing import Optional

from backend.infra.cache.redis_cache import cache


_STATE_TTL_SECONDS = 600


def _state_key(state: str) -> str:
    return f"sso:state:{state}"


async def create_state(provider_id: str, code_verifier: str) -> str:
    state = secrets.token_urlsafe(24)
    payload = {
        "provider_id": provider_id,
        "code_verifier": code_verifier,
        "created_at": time.time(),
    }
    await cache.set_json(_state_key(state), payload, ttl_sec=_STATE_TTL_SECONDS)
    return state


async def pop_state(state: str) -> Optional[dict]:
    """
    Atomically retrieve and delete OAuth state.

    Uses atomic getdel operation to prevent race conditions where
    multiple consumers could read the same state before deletion.
    """
    key = _state_key(state)
    return await cache.getdel_json(key)
