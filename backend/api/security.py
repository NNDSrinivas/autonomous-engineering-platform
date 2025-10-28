"""Security dependencies for fine-grained authorization."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status

from backend.core.policy.engine import PolicyEngine, get_policy_engine


def require_policy(action: str, context_fn=None):
    """
    [PLACEHOLDER] Dependency factory to enforce policy guardrails on actions.

    This function is currently not implemented because FastAPI's dependency injection
    system cannot easily extract route arguments for dynamic context building.

    Use `check_policy_inline` instead, which allows explicit context passing within
    the route handler after arguments are available.

    Reserved for future enhancement if a clean dependency-based pattern is found.

    Args:
        action: Action identifier (e.g., "plan.add_step")
        context_fn: Optional callable that would extract context from route args

    Raises:
        NotImplementedError: This function is a placeholder and not yet implemented.
    """
    raise NotImplementedError(
        "require_policy is a placeholder and not yet implemented. "
        "Use check_policy_inline instead for inline policy checks."
    )


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
