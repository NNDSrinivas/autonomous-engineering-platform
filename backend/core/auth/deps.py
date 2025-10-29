"""FastAPI dependencies for authentication and authorization."""

import logging
import os
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.auth.jwt import JWTVerificationError, verify_token
from backend.core.auth.models import Role, User
from backend.core.settings import settings

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme for JWT authentication
security = HTTPBearer(auto_error=False)


def get_current_user(
    x_org_id: Annotated[Optional[str], Header()] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    """
    Extract current user from request context.

    Mode 1 (JWT_ENABLED=true): Parse JWT token from Authorization header
    Mode 2 (JWT_ENABLED=false): Use DEV_* environment variables (dev shim)

    Args:
        x_org_id: Optional organization ID from X-Org-Id header (dev mode only)
        credentials: Bearer token from Authorization header (JWT mode)

    Returns:
        User object with role and context

    Raises:
        HTTPException 401: If authentication fails
    """
    if settings.JWT_ENABLED:
        # JWT mode: require and verify bearer token
        if not credentials or not credentials.credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            # Verify token and extract claims
            # Note: verify_token returns processed claims with 'display_name' key
            # (transformed from JWT's 'name' field by extract_user_claims)
            claims = verify_token(credentials.credentials)

            return User(
                user_id=claims["user_id"],
                email=claims.get("email"),
                display_name=claims.get("display_name"),
                role=Role(claims["role"]),
                org_id=claims["org_id"],
                projects=claims.get("projects", []),
            )

        except JWTVerificationError as e:
            logger.warning(f"JWT verification failed: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired token: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    else:
        # Dev shim mode: read from environment variables
        user_id = os.getenv("DEV_USER_ID")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="DEV_USER_ID environment variable required in dev mode",
            )

        email = os.getenv("DEV_USER_EMAIL")
        display_name = os.getenv("DEV_USER_DISPLAY_NAME")

        # Role: read from DEV_USER_ROLE env, default to viewer (secure-by-default)
        role_str = os.getenv("DEV_USER_ROLE", "viewer").lower()
        valid_roles = {"viewer", "planner", "admin"}
        if role_str not in valid_roles:
            logger.warning(
                f"Invalid DEV_USER_ROLE '{role_str}' specified. "
                f"Valid roles are: {', '.join(valid_roles)}. Defaulting to 'viewer'."
            )
            role_str = "viewer"

        role = Role(role_str)

        # Org: prefer X-Org-Id header, fallback to DEV_ORG_ID env
        org_id = x_org_id or os.getenv("DEV_ORG_ID")

        # Projects: comma-separated list from env
        projects_str = os.getenv("DEV_PROJECTS", "")
        projects = [p.strip() for p in projects_str.split(",") if p.strip()]

        return User(
            user_id=user_id,
            email=email,
            display_name=display_name,
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
