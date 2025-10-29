"""JWT token verification and claims extraction."""

import logging

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

from backend.core.settings import settings

logger = logging.getLogger(__name__)


class JWTVerificationError(Exception):
    """Raised when JWT token verification fails."""


def decode_jwt(token: str) -> dict:
    """
    Decode and verify JWT token.

    Args:
        token: JWT token string (without "Bearer " prefix)

    Returns:
        Dictionary of decoded claims

    Raises:
        JWTVerificationError: If token is invalid, expired, or verification fails
    """
    if not settings.JWT_ENABLED:
        raise JWTVerificationError("JWT authentication is not enabled")

    if not settings.JWT_SECRET:
        raise JWTVerificationError("JWT_SECRET is required when JWT_ENABLED=true")

    try:
        # Decode and verify token (includes expiration check)
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )

        return payload

    except ExpiredSignatureError:
        raise JWTVerificationError("Token has expired")
    except JWTClaimsError as e:
        raise JWTVerificationError(f"Invalid token claims: {str(e)}")
    except JWTError as e:
        logger.warning(f"JWT verification failed: {str(e)}")
        raise JWTVerificationError(f"Token verification failed: {str(e)}")


def extract_user_claims(payload: dict) -> dict:
    """
    Extract user claims from JWT payload.

    Expected claims:
    - sub (subject): user_id
    - email: user's email address
    - name: display name
    - org_id: organization ID
    - role: user role (viewer/planner/admin)
    - projects: list of accessible project IDs (optional)

    Args:
        payload: Decoded JWT payload dictionary

    Returns:
        Dictionary with extracted user information

    Raises:
        JWTVerificationError: If required claims are missing
    """
    # Required claims
    user_id = payload.get("sub")
    if not user_id:
        raise JWTVerificationError("Missing required claim: 'sub' (user_id)")

    org_id = payload.get("org_id")
    if not org_id:
        raise JWTVerificationError("Missing required claim: 'org_id'")

    role = payload.get("role", "viewer")  # Default to viewer for security
    if role not in {"viewer", "planner", "admin"}:
        logger.warning(f"Invalid role '{role}' in JWT, defaulting to 'viewer'")
        role = "viewer"

    # Optional claims
    email = payload.get("email")
    display_name = payload.get("name")
    projects = payload.get("projects", [])
    if isinstance(projects, str):
        # Support comma-separated string
        projects = [p.strip() for p in projects.split(",") if p.strip()]

    return {
        "user_id": user_id,
        "email": email,
        "display_name": display_name,
        "org_id": org_id,
        "role": role,
        "projects": projects,
    }


def verify_token(token: str) -> dict:
    """
    Verify JWT token and extract user claims.

    Convenience function that combines decode_jwt and extract_user_claims.

    Args:
        token: JWT token string (without "Bearer " prefix)

    Returns:
        Dictionary with user information

    Raises:
        JWTVerificationError: If token is invalid or verification fails
    """
    payload = decode_jwt(token)
    return extract_user_claims(payload)
