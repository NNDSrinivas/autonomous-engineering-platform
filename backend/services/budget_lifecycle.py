"""
Budget lifecycle helpers for LLM request wrapping.

Provides reserve/commit/release context manager for clean budget enforcement.
"""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING, AsyncContextManager
from contextlib import asynccontextmanager

if TYPE_CHECKING:
    from backend.services.budget_manager import (
        BudgetManager,
        BudgetReservationToken,
        BudgetScopeKey,
    )

logger = logging.getLogger(__name__)


@asynccontextmanager
async def budget_guard(
    budget_manager: Optional["BudgetManager"],
    scopes: list["BudgetScopeKey"],
    estimated_tokens: int,
) -> AsyncContextManager[dict]:
    """
    Context manager for budget reserve/commit/release lifecycle.

    Usage:
        async with budget_guard(mgr, scopes, 2500) as budget_ctx:
            # Call LLM
            response = await llm_call()
            # Track actual tokens
            budget_ctx["actual_tokens"] = response.usage.total_tokens

    On exit:
    - If actual_tokens set: commits with actual usage
    - If exception raised: releases reservation
    - If actual > reserved: allows overspend but logs warning

    Args:
        budget_manager: BudgetManager instance (None = skip enforcement)
        scopes: List of budget scopes to check
        estimated_tokens: Conservative token estimate for reservation

    Yields:
        dict with keys:
            - "reservation": BudgetReservationToken (or None if budget disabled)
            - "actual_tokens": Set this to actual token usage after LLM call
    """
    if not budget_manager or not scopes:
        # Budget enforcement disabled or unavailable
        yield {"reservation": None, "actual_tokens": None}
        return

    # Import here to avoid circular dependency
    from backend.services.budget_manager import BudgetExceeded

    token: Optional["BudgetReservationToken"] = None
    context = {"reservation": None, "actual_tokens": None}

    try:
        # Phase 4: AUTHORITATIVE budget reserve (atomic check + increment)
        token = budget_manager.reserve(estimated_tokens, scopes)
        context["reservation"] = token
        logger.info(
            f"Budget reserved: {estimated_tokens} tokens across {len(scopes)} scopes"
        )

        yield context

        # Normal path: commit with actual usage
        actual_tokens = context.get("actual_tokens")
        if actual_tokens is not None:
            budget_manager.commit(token, used_amount=int(actual_tokens))
            logger.info(
                f"Budget committed: reserved={estimated_tokens}, actual={actual_tokens}"
            )
        else:
            # LLM call completed but didn't set actual_tokens (streaming edge case)
            # Commit the reserved amount as a conservative fallback
            budget_manager.commit(token, used_amount=estimated_tokens)
            logger.warning(
                f"Budget committed with estimated tokens (actual not tracked): {estimated_tokens}"
            )

    except BudgetExceeded as e:
        # Budget check failed - re-raise to caller
        logger.warning(f"Budget exceeded: {e}", exc_info=False)
        raise

    except Exception:
        # LLM call or other error - release reservation
        if token:
            try:
                budget_manager.release(token)
                logger.info(f"Budget released due to error: {estimated_tokens} tokens")
            except Exception as release_err:
                logger.error(f"Budget release failed: {release_err}", exc_info=True)
        raise


def build_budget_scopes(
    org_id: Optional[str],
    user_id: Optional[str],
    provider: str,
    model_id: str,
) -> list["BudgetScopeKey"]:
    """
    Build budget scope keys for hierarchical enforcement.

    Phase 4: Multi-scope enforcement (all checked atomically).

    Args:
        org_id: Organization ID (e.g., "acme-corp")
        user_id: User ID (e.g., "user-123")
        provider: Provider ID (e.g., "openai", "anthropic")
        model_id: Full model ID (e.g., "openai/gpt-4o")

    Returns:
        List of BudgetScopeKey (empty list if budget enforcement disabled)
    """
    from backend.services.budget_manager import BudgetScope, BudgetScopeKey

    scopes: list[BudgetScopeKey] = []

    # Always add global scope
    scopes.append(BudgetScopeKey(BudgetScope.GLOBAL, "global"))

    # Add org scope if available
    if org_id and org_id.strip():
        scopes.append(BudgetScopeKey(BudgetScope.ORG, org_id))

    # Add user scope if available
    if user_id and user_id.strip():
        scopes.append(BudgetScopeKey(BudgetScope.USER, user_id))

    # Add provider scope
    scopes.append(BudgetScopeKey(BudgetScope.PROVIDER, provider))

    # Add model scope
    scopes.append(BudgetScopeKey(BudgetScope.MODEL, model_id))

    return scopes
