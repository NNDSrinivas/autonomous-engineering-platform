"""Security dependencies for fine-grained authorization."""

from typing import Annotated, Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.policy_engine.engine import PolicyEngine, get_policy_engine
from backend.core.jwt_session import SessionJWT


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


bearer = HTTPBearer(auto_error=False)


class UserCtx:
    def __init__(self, sub: str, email: str | None, org: str | None, roles: list[str]):
        self.id = sub
        self.email = email
        self.org_id = org
        self.roles = roles


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> UserCtx:
    if not creds:
        raise HTTPException(401, "Missing Authorization")
    try:
        claims = SessionJWT.decode(creds.credentials)
    except Exception as e:
        raise HTTPException(401, f"Invalid session token: {e}")
    return UserCtx(
        sub=claims["sub"],
        email=claims.get("email"),
        org=claims.get("org"),
        roles=claims.get("roles", []),
    )


def require_role(role: str):
    def _dep(u: UserCtx = Depends(current_user)) -> UserCtx:
        if role not in (u.roles or []):
            raise HTTPException(403, "Insufficient role")
        return u

    return _dep
