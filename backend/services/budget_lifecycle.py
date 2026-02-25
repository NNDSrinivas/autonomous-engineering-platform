from __future__ import annotations

import logging
from typing import List, Optional

from .budget_manager import BudgetManager, BudgetScope

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
    scopes.append(
        BudgetScope(scope="global", scope_id="global", per_day_limit=default_limit)
    )

    # Org (safe default)
    org_key = org_id or "org:unknown"
    org_limit = _policy_limit(policy, "orgs", org_key, default_limit)
    scopes.append(BudgetScope(scope="org", scope_id=org_key, per_day_limit=org_limit))

    # User optional
    if user_id:
        user_limit = _policy_limit(policy, "users", user_id, default_limit)
        scopes.append(
            BudgetScope(scope="user", scope_id=user_id, per_day_limit=user_limit)
        )

    # Provider optional
    if provider_id:
        provider_limit = _policy_limit(policy, "providers", provider_id, default_limit)
        scopes.append(
            BudgetScope(
                scope="provider", scope_id=provider_id, per_day_limit=provider_limit
            )
        )

    # Model optional
    if model_id:
        model_limit = _policy_limit(policy, "models", model_id, default_limit)
        scopes.append(
            BudgetScope(scope="model", scope_id=model_id, per_day_limit=model_limit)
        )

    return scopes
