from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from .budget_manager import BudgetExceeded, BudgetManager, BudgetReservationToken, BudgetScope

logger = logging.getLogger(__name__)


def _policy_limit(policy: dict, section: str, key: str, default_limit: int) -> int:
    try:
        d = policy.get(section, {})
        if key in d:
            return int(d[key]["per_day"])
    except Exception:
        pass
    return default_limit


def build_budget_scopes(
    *,
    budget_manager: BudgetManager,
    org_id: Optional[str],
    user_id: Optional[str],
    provider_id: Optional[str],
    model_id: Optional[str],
) -> List[BudgetScope]:
    policy = budget_manager.policy
    default_limit = int(policy.get("defaults", {}).get("per_day", 0))

    scopes: List[BudgetScope] = []

    # Global
    scopes.append(BudgetScope(scope="global", scope_id="global", per_day_limit=default_limit))

    # Org (safe default)
    org_key = org_id or "org:unknown"
    org_limit = _policy_limit(policy, "orgs", org_key, default_limit)
    scopes.append(BudgetScope(scope="org", scope_id=org_key, per_day_limit=org_limit))

    # User optional
    if user_id:
        user_limit = _policy_limit(policy, "users", user_id, default_limit)
        scopes.append(BudgetScope(scope="user", scope_id=user_id, per_day_limit=user_limit))

    # Provider optional
    if provider_id:
        provider_limit = _policy_limit(policy, "providers", provider_id, default_limit)
        scopes.append(BudgetScope(scope="provider", scope_id=provider_id, per_day_limit=provider_limit))

    # Model optional
    if model_id:
        model_limit = _policy_limit(policy, "models", model_id, default_limit)
        scopes.append(BudgetScope(scope="model", scope_id=model_id, per_day_limit=model_limit))

    return scopes


@asynccontextmanager
async def budget_guard(
    budget_manager: BudgetManager,
    scopes: List[BudgetScope],
    estimated_tokens: int,
    *,
    pre_reserved_token: Optional[BudgetReservationToken] = None,
) -> Dict:
    """
    Single terminal action invariant:
      - reserve fails: raises BudgetExceeded, no commit/release
      - reserve succeeds:
          normal exit => commit exactly once
          exception/cancel => release exactly once

    budget_ctx:
      - set budget_ctx["actual_tokens"] during streaming (cumulative/total)
      - if not set, commit uses estimated_tokens (conservative fallback)
    """
    token: Optional[BudgetReservationToken] = None
    finalized = False

    budget_ctx: Dict = {
        "estimated_tokens": int(estimated_tokens),
        "actual_tokens": None,
        "token_day": None,
        "finalized": False,
    }

    try:
        token = pre_reserved_token or await budget_manager.reserve(int(estimated_tokens), scopes)
        budget_ctx["token_day"] = token.day

        # Deterministic concurrency hold (dev-only test)
        if os.getenv("BUDGET_TEST_HOLD_STREAM") == "1":
            await asyncio.sleep(2)

        yield budget_ctx

        if token is not None and not finalized:
            used = budget_ctx.get("actual_tokens")
            if used is None or int(used) <= 0:
                used = int(estimated_tokens)  # conservative fallback
            await budget_manager.commit(token, int(used))
            finalized = True
            budget_ctx["finalized"] = True

    except BudgetExceeded:
        # Reserve failure OR enforcement unavailable in strict.
        # If token exists (defensive), release it.
        if token is not None and not finalized:
            try:
                await budget_manager.release(token)
            except Exception:
                pass
        raise

    except BaseException:
        # cancellation/errors after reserve must release
        if token is not None and not finalized:
            try:
                await budget_manager.release(token)
            except Exception:
                pass
        raise
