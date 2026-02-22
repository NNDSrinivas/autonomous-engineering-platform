"""
Role-Based Access Control (RBAC) middleware.
Enforces permissions based on user roles from Auth0.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
import jwt
from jwt import PyJWKClient
import logging

from backend.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

security = HTTPBearer()


class PermissionDenied(HTTPException):
    """Permission denied exception."""

    def __init__(self, detail: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class UnauthorizedException(HTTPException):
    """Unauthorized exception."""

    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


def verify_jwt_token(token: str) -> dict:
    """
    Verify JWT token from Auth0.

    Returns:
        dict: Decoded token payload with user info and permissions
    """

    try:
        # Get Auth0 domain and audience
        auth0_domain = getattr(settings, "auth0_issuer_base_url", "").replace("https://", "")
        auth0_audience = getattr(settings, "auth0_audience", "")

        if not auth0_domain or not auth0_audience:
            raise UnauthorizedException("Auth0 not configured")

        # Get signing key from Auth0
        jwks_url = f"https://{auth0_domain}/.well-known/jwks.json"
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Verify and decode token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=auth0_audience,
            issuer=f"https://{auth0_domain}/"
        )

        return payload

    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Token has expired")
    except jwt.InvalidTokenError as e:
        raise UnauthorizedException(f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise UnauthorizedException("Token verification failed")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Get current user from JWT token.

    Returns:
        dict: User info from token
    """

    token = credentials.credentials
    payload = verify_jwt_token(token)

    # Extract user info
    user = {
        "sub": payload.get("sub"),  # Auth0 user ID
        "email": payload.get("email"),
        "name": payload.get("name"),
        "permissions": payload.get("permissions", []),
        "roles": payload.get("https://navralabs.com/roles", []),
        "plan": payload.get("https://navralabs.com/plan", "free")
    }

    return user


def require_permission(permission: str):
    """
    Decorator to require a specific permission.

    Usage:
        @router.get("/admin/users")
        async def get_users(user: dict = Depends(require_permission("admin:users"))):
            pass
    """

    async def permission_checker(
        user: dict = Depends(get_current_user)
    ) -> dict:
        """Check if user has required permission."""

        user_permissions = user.get("permissions", [])

        if permission not in user_permissions:
            raise PermissionDenied(
                f"Missing required permission: {permission}"
            )

        return user

    return permission_checker


def require_any_permission(*permissions: str):
    """
    Decorator to require ANY of the specified permissions.

    Usage:
        @router.get("/content")
        async def get_content(
            user: dict = Depends(require_any_permission("read:content", "admin:all"))
        ):
            pass
    """

    async def permission_checker(
        user: dict = Depends(get_current_user)
    ) -> dict:
        """Check if user has any of the required permissions."""

        user_permissions = user.get("permissions", [])

        has_permission = any(
            perm in user_permissions for perm in permissions
        )

        if not has_permission:
            raise PermissionDenied(
                f"Missing required permissions: {', '.join(permissions)}"
            )

        return user

    return permission_checker


def require_all_permissions(*permissions: str):
    """
    Decorator to require ALL of the specified permissions.

    Usage:
        @router.delete("/admin/critical")
        async def critical_operation(
            user: dict = Depends(require_all_permissions("admin:write", "admin:delete"))
        ):
            pass
    """

    async def permission_checker(
        user: dict = Depends(get_current_user)
    ) -> dict:
        """Check if user has all required permissions."""

        user_permissions = user.get("permissions", [])

        missing_permissions = [
            perm for perm in permissions
            if perm not in user_permissions
        ]

        if missing_permissions:
            raise PermissionDenied(
                f"Missing required permissions: {', '.join(missing_permissions)}"
            )

        return user

    return permission_checker


def require_role(role: str):
    """
    Decorator to require a specific role.

    Usage:
        @router.get("/admin/dashboard")
        async def admin_dashboard(user: dict = Depends(require_role("Admin"))):
            pass
    """

    async def role_checker(
        user: dict = Depends(get_current_user)
    ) -> dict:
        """Check if user has required role."""

        user_roles = user.get("roles", [])

        if role not in user_roles:
            raise PermissionDenied(
                f"Missing required role: {role}"
            )

        return user

    return role_checker


def require_plan(min_plan: str):
    """
    Decorator to require a minimum subscription plan.

    Plan hierarchy: free < premium < enterprise

    Usage:
        @router.post("/premium-feature")
        async def premium_feature(user: dict = Depends(require_plan("premium"))):
            pass
    """

    plan_hierarchy = {
        "free": 0,
        "premium": 1,
        "enterprise": 2
    }

    async def plan_checker(
        user: dict = Depends(get_current_user)
    ) -> dict:
        """Check if user has required plan."""

        user_plan = user.get("plan", "free")

        user_plan_level = plan_hierarchy.get(user_plan, 0)
        required_plan_level = plan_hierarchy.get(min_plan, 0)

        if user_plan_level < required_plan_level:
            raise PermissionDenied(
                f"This feature requires {min_plan} plan or higher"
            )

        return user

    return plan_checker


# Optional user (for public endpoints that can work with/without auth)
async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[dict]:
    """
    Get current user if authenticated, None otherwise.

    Usage:
        @router.get("/public-content")
        async def get_content(user: Optional[dict] = Depends(get_optional_user)):
            if user:
                # Return personalized content
            else:
                # Return public content
    """

    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = verify_jwt_token(token)

        return {
            "sub": payload.get("sub"),
            "email": payload.get("email"),
            "name": payload.get("name"),
            "permissions": payload.get("permissions", []),
            "roles": payload.get("https://navralabs.com/roles", []),
            "plan": payload.get("https://navralabs.com/plan", "free")
        }
    except:
        return None
