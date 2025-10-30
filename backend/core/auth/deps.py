"""FastAPI dependencies for authentication and authorization."""

import logging
import os
import threading
import time
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.core.auth.jwt import JWTVerificationError, verify_token
from backend.core.auth.models import Role, User
from backend.core.auth.utils import parse_comma_separated
from backend.core.settings import settings

logger = logging.getLogger(__name__)

# Rate-limited logging to avoid log spam in non-multi-tenant deployments
_log_timestamps: dict[str, float] = {}
_log_lock = threading.Lock()
# Configurable throttle period: default 5 minutes, override via LOG_THROTTLE_SECONDS env var
log_throttle_env = os.getenv("LOG_THROTTLE_SECONDS", "300")
try:
    _LOG_THROTTLE_SECONDS = int(log_throttle_env)
except ValueError:
    logger.warning(
        f"Invalid value for LOG_THROTTLE_SECONDS: {log_throttle_env}; "
        "must be an integer. Falling back to default (300 seconds)."
    )
    _LOG_THROTTLE_SECONDS = 300

# Cleanup multiplier: remove entries older than 2x throttle period to prevent memory leaks
_CLEANUP_MULTIPLIER = 2

# Cleanup interval: perform cleanup every 60 seconds to avoid O(n) overhead
_CLEANUP_INTERVAL_SECONDS = 60

# Last cleanup time for periodic cleanup optimization
_last_cleanup_time: float = 0.0

# HTTP Bearer token scheme for JWT authentication
security = HTTPBearer(auto_error=False)


def _log_once(message: str, level: int = logging.WARNING) -> None:
    """
    Log a message at most once per _LOG_THROTTLE_SECONDS.

    Prevents log spam for recurring warnings in long-running applications.
    Thread-safe via lock to prevent race conditions.
    Cleanup is performed periodically to avoid O(n) overhead on every call.
    """
    with _log_lock:
        # global is required here because we reassign _last_cleanup_time below, not just modify it
        global _last_cleanup_time
        now = time.time()
        # Periodic cleanup: only clean every interval to avoid O(n) overhead
        if now - _last_cleanup_time >= _CLEANUP_INTERVAL_SECONDS:
            cutoff_time = now - (_CLEANUP_MULTIPLIER * _LOG_THROTTLE_SECONDS)
            # Use clear and update to modify in-place instead of reassignment
            old_timestamps = _log_timestamps.copy()
            _log_timestamps.clear()
            _log_timestamps.update(
                {k: v for k, v in old_timestamps.items() if v >= cutoff_time}
            )
            _last_cleanup_time = now  # Update last cleanup time for next interval check

        last_logged = _log_timestamps.get(message, 0)

        if now - last_logged >= _LOG_THROTTLE_SECONDS:
            logger.log(level, message)
            _log_timestamps[message] = now


def clear_log_timestamps() -> None:
    """
    Clear all log timestamps for testing purposes.

    This is a public API for tests to reset the log throttling state
    without accessing private module variables directly.
    """
    with _log_lock:
        _log_timestamps.clear()


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
        """
        Validate user has required role by resolving effective role from JWT + DB.

        This function is async despite using a synchronous SQLAlchemy Session.
        This is a FastAPI best practice where:
        - Sync dependencies (get_db) are automatically run in a threadpool
        - Async operations (resolve_effective_role) are awaited normally
        - No event loop blocking occurs due to FastAPI's automatic handling

        See: https://fastapi.tiangolo.com/async/#very-technical-details
        """
        # Import here to avoid circular dependency
        from sqlalchemy.exc import OperationalError, SQLAlchemyError

        from backend.core.auth.role_service import resolve_effective_role

        try:
            # Warn if org_id is missing but continue with fallback
            if user.org_id is None:
                _log_once(
                    "User org_id is None when resolving effective role. "
                    "Falling back to JWT-only authorization. "
                    "This may indicate a configuration issue or non-multi-tenant setup.",
                    level=logging.INFO,
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
                # Simplify message when JWT and effective roles are the same
                if user.role == effective_role:
                    detail_msg = (
                        f"Requires {minimum_role.value} role or higher "
                        f"(you have {user.role.value})"
                    )
                else:
                    detail_msg = (
                        f"Requires {minimum_role.value} role or higher "
                        f"(JWT: {user.role.value}, effective: {effective_role.value})"
                    )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=detail_msg,
                )

            # Update user object with effective role for downstream use
            user.role = effective_role
            return user

        except (OperationalError, SQLAlchemyError) as e:
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

    # Lazy import to avoid circular dependencies.
    # Uses yield from to efficiently forward the generator without creating additional indirection.
    # This preserves the cleanup behavior and context management of the original generator.
    yield from get_db()
