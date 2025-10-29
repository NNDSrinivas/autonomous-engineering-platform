"""FastAPI dependencies for authentication and authorization."""

import logging
import os
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.core.auth.jwt import JWTVerificationError, verify_token
from backend.core.auth.models import Role, User
from backend.core.auth.utils import parse_comma_separated
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
            # Verify token and extract claims (includes 'display_name' key)
            claims = verify_token(credentials.credentials)

            return User(
                user_id=claims["user_id"],
                email=claims.get("email"),
                display_name=claims.get("display_name"),
                role=Role(claims["role"]),
                org_id=claims["org_id"],
                projects=claims.get("projects", []),
            )

        except JWTVerificationError:
            logger.warning("JWT verification failed due to invalid or expired token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
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
        valid_roles = {r.value for r in Role}
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
        projects = parse_comma_separated(os.getenv("DEV_PROJECTS"))

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

    Integrates with role resolution service to merge JWT roles with
    database-assigned roles, using the maximum precedence (when RBAC tables exist).

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
        HTTPException 403: If user's effective role is insufficient
    """

    async def role_checker(
        user: User = Depends(get_current_user),
        db: Session = Depends(_get_db_for_auth),
    ) -> User:
        # Import here to avoid circular dependency
        from backend.core.auth.role_service import resolve_effective_role

        try:
            # Warn if org_id is missing but continue with fallback
            if user.org_id is None:
                logger.warning(
                    "User org_id is None when resolving effective role. "
                    "Falling back to JWT-only authorization. "
                    "This may indicate a configuration issue or non-multi-tenant setup."
                )
                # Use JWT role only if org_id is missing
                if user.role < minimum_role:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Requires {minimum_role.value} role or higher "
                        f"(you have {user.role.value})",
                    )
                return user

            # Resolve effective role (merges JWT + DB roles)
            # Falls back to JWT role if RBAC tables don't exist or aren't populated
            effective_role_name = await resolve_effective_role(
                session=db,
                sub=user.user_id,  # JWT subject
                org_key=user.org_id,  # Organization key
                jwt_role=user.role.value,  # JWT role as baseline
            )

            # Convert resolved role name to Role enum
            effective_role = Role(effective_role_name)

            # Check if effective role meets minimum requirement
            if effective_role < minimum_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires {minimum_role.value} role or higher "
                    f"(you have {user.role.value} in JWT, "
                    f"effective role: {effective_role.value})",
                )

            # Update user object with effective role for downstream use
            user.role = effective_role
            return user

        except Exception as e:
            # If role resolution fails (e.g., DB not available, tables don't exist),
            # fall back to JWT-only authorization for backward compatibility
            logger.debug(f"Role resolution failed, using JWT-only auth: {e}")
            if user.role < minimum_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires {minimum_role.value} role or higher "
                    f"(you have {user.role.value})",
                )
            return user

    return role_checker


def _get_db_for_auth():
    """
    Database session dependency for auth checks.

    Lazy import to avoid circular dependencies.
    """
    from backend.database.session import get_db

    # get_db is a generator that yields a session.
    # We use 'yield from' here to forward the generator, and this indirection
    # is necessary to avoid circular imports between auth and database modules.
    yield from get_db()
