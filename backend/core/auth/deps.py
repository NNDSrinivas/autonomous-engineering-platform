"""FastAPI dependencies for authentication and authorization."""

import os
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status

from backend.core.auth.models import Role, User


def get_current_user(
    x_org_id: Annotated[Optional[str], Header()] = None,
) -> User:
    """
    Extract current user from request context.
    
    Phase 1 (this PR): Uses DEV_* environment variables as auth shim.
    Phase 2 (future): Will parse JWT tokens from Authorization header.
    
    Args:
        x_org_id: Optional organization ID from X-Org-Id header
        
    Returns:
        User object with role and context
        
    Raises:
        HTTPException: If DEV_USER_ID is missing (required for dev mode)
    """
    # Dev shim: read from environment variables
    user_id = os.getenv("DEV_USER_ID")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="DEV_USER_ID environment variable required in dev mode",
        )

    email = os.getenv("DEV_USER_EMAIL")
    
    # Role: read from DEV_USER_ROLE env, default to viewer (secure-by-default)
    role_str = os.getenv("DEV_USER_ROLE", "viewer").lower()
    try:
        role = Role(role_str)
    except ValueError:
        # Invalid role in env → default to viewer
        role = Role.VIEWER

    # Org: prefer X-Org-Id header, fallback to DEV_ORG_ID env
    org_id = x_org_id or os.getenv("DEV_ORG_ID")

    # Projects: comma-separated list from env
    projects_str = os.getenv("DEV_PROJECTS", "")
    projects = [p.strip() for p in projects_str.split(",") if p.strip()]

    return User(
        user_id=user_id,
        email=email,
        role=role,
        org_id=org_id,
        projects=projects,
    )


def require_role(minimum_role: Role):
    """
    Dependency factory to enforce minimum role requirement.
    
    Usage:
        @router.post("/plan/{plan_id}/publish")
        async def publish(user: User = Depends(require_role(Role.PLANNER))):
            # Only planner+ can execute this endpoint
            ...
    
    Args:
        minimum_role: Minimum role required (viewer, planner, or admin)
        
    Returns:
        FastAPI dependency that validates user role
        
    Raises:
        HTTPException 403: If user's role is insufficient
    """

    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role < minimum_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {minimum_role.value} role or higher "
                f"(you have {user.role.value})",
            )
        return user

    return role_checker
