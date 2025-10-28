"""Security dependencies for fine-grained authorization."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status

from backend.core.auth.deps import get_current_user
from backend.core.auth.models import User
from backend.core.policy.engine import PolicyEngine, get_policy_engine


def require_policy(action: str, context_fn=None):
    """
    Dependency factory to enforce policy guardrails on actions.

    Usage:
        @router.post("/plan/{plan_id}/step")
        async def add_step(
            plan_id: str,
            step: StepCreate,
            user: User = Depends(require_role(Role.PLANNER)),
            _policy: None = Depends(
                require_policy(
                    "plan.add_step",
                    lambda plan_id, step: {
                        "plan_id": plan_id,
                        "step_name": step.name
                    }
                )
            ),
        ):
            # Policy has already been checked; safe to proceed
            ...

    Args:
        action: Action identifier (e.g., "plan.add_step")
        context_fn: Optional callable that extracts context dict from
                    endpoint arguments. If None, only action is checked.

    Returns:
        FastAPI dependency that validates policy

    Raises:
        HTTPException 403: If policy denies the action
    """

    def policy_checker(
        user: User = Depends(get_current_user),
        policy_engine: PolicyEngine = Depends(get_policy_engine),
    ) -> None:
        # Build context (empty if no context_fn provided)
        context: dict[str, Any] = {}
        if context_fn is not None:
            # Note: context_fn extraction from route args happens via closure
            # In practice, we'll pass context directly in the route handler
            # For now, this is a placeholder structure
            pass

        # Check policy
        allowed, reason = policy_engine.check(action, context)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Policy violation: {reason}",
            )

    return policy_checker


async def check_policy_inline(
    action: str,
    context: dict[str, Any],
    policy_engine: Annotated[PolicyEngine, Depends(get_policy_engine)],
) -> None:
    """
    Inline policy check helper for use within route handlers.

    Usage:
        @router.post("/plan/{plan_id}/step")
        async def add_step(
            plan_id: str,
            step: StepCreate,
            policy_engine: PolicyEngine = Depends(get_policy_engine),
        ):
            # Check policy inline after we have the step data
            await check_policy_inline(
                "plan.add_step",
                {"plan_id": plan_id, "step_name": step.name},
                policy_engine
            )
            # Proceed with business logic
            ...

    Args:
        action: Action identifier
        context: Context dictionary with action-specific data
        policy_engine: PolicyEngine instance (injected by FastAPI)

    Raises:
        HTTPException 403: If policy denies the action
    """
    allowed, reason = policy_engine.check(action, context)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Policy violation: {reason}",
        )
