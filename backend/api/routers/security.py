"""Security dependencies for fine-grained authorization."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status

from backend.core.policy_engine.engine import PolicyEngine, get_policy_engine


def check_policy_inline(
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
            check_policy_inline(
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
