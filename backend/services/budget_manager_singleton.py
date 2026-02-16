from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

import redis.asyncio as redis

from .budget_manager import BudgetManager

logger = logging.getLogger(__name__)

_BUDGET_MANAGER: Optional[BudgetManager] = None


def _load_policy(app_env: str) -> dict:
    # backend/services/ -> backend/ -> repo_root/
    repo_root = Path(__file__).resolve().parents[2]

    fname = {
        "prod": "budget-policy-prod.json",
        "production": "budget-policy-prod.json",
        "staging": "budget-policy-staging.json",
        "stage": "budget-policy-staging.json",
        "dev": "budget-policy-dev.json",
        "development": "budget-policy-dev.json",
    }.get(app_env.lower(), "budget-policy-dev.json")

    p = repo_root / "shared" / fname
    return json.loads(p.read_text("utf-8"))


async def init_budget_manager() -> Optional[BudgetManager]:
    """
    Initialize singleton. Startup must not crash app.
    Strict/advisory behavior is enforced during reserve().
    """
    global _BUDGET_MANAGER
    if _BUDGET_MANAGER is not None:
        return _BUDGET_MANAGER

    enforcement = os.getenv("BUDGET_ENFORCEMENT_MODE", "strict").lower()
    if enforcement not in ("strict", "advisory", "disabled"):
        enforcement = "strict"

    app_env = os.getenv("APP_ENV", "dev")
    try:
        policy = _load_policy(app_env)
    except Exception as e:
        logger.error("Failed to load budget policy (budgets disabled): %s", e)
        _BUDGET_MANAGER = None
        return None

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    try:
        r = redis.from_url(redis_url, decode_responses=False)
        await r.ping()
        _BUDGET_MANAGER = BudgetManager(r, enforcement_mode=enforcement, policy=policy)
        logger.info("Budget manager initialized: mode=%s env=%s redis=%s", enforcement, app_env, redis_url)
        return _BUDGET_MANAGER
    except Exception as e:
        if enforcement == "disabled":
            r = redis.from_url(redis_url, decode_responses=False)
            _BUDGET_MANAGER = BudgetManager(r, enforcement_mode="disabled", policy=policy)
            logger.warning("Budget manager init: disabled mode (Redis unreachable): %s", e)
            return _BUDGET_MANAGER

        if enforcement == "advisory":
            r = redis.from_url(redis_url, decode_responses=False)
            _BUDGET_MANAGER = BudgetManager(r, enforcement_mode="advisory", policy=policy)
            logger.warning("Budget manager init: advisory mode (Redis unreachable): %s", e)
            return _BUDGET_MANAGER

        # strict + redis down => keep None (endpoint maps to 503)
        logger.error("Budget manager unavailable in strict mode: %s", e)
        _BUDGET_MANAGER = None
        return None


def get_budget_manager() -> Optional[BudgetManager]:
    return _BUDGET_MANAGER


async def close_budget_manager() -> None:
    global _BUDGET_MANAGER
    if _BUDGET_MANAGER is None:
        return
    try:
        r = getattr(_BUDGET_MANAGER, "_r", None)
        if r is not None:
            await r.close()
    except Exception:
        pass
    _BUDGET_MANAGER = None
