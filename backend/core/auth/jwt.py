"""JWT token verification and user claims extraction."""

from __future__ import annotations

import logging

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

from backend.core.auth.models import Role
from backend.core.auth.utils import parse_comma_separated
from backend.core.settings import settings

logger = logging.getLogger(__name__)

# Valid role values from Role enum - computed once at module load for performance
# Note: If Role enum is modified, the module must be reloaded for changes to take effect
_VALID_ROLES = frozenset(r.value for r in Role)


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

    secrets = _get_jwt_secrets()
    if not secrets:
        raise JWTVerificationError(
            "JWT_SECRET (or JWT_SECRET_PREVIOUS) is required when JWT_ENABLED=true"
        )

    try:
        for secret in secrets:
            try:
                # Decode and verify token (includes expiration check)
                payload = jwt.decode(
                    token,
                    secret,
                    algorithms=[settings.JWT_ALGORITHM],
                    audience=settings.JWT_AUDIENCE,
                    issuer=settings.JWT_ISSUER,
                )
                return payload
            except ExpiredSignatureError:
                raise JWTVerificationError("Token has expired")
            except JWTClaimsError:
                # Note: Detailed error information not logged to avoid leaking JWT validation logic
                raise JWTVerificationError("Invalid token claims")
            except JWTError:
                continue

        logger.warning("JWT verification failed")
        # Note: Detailed error information not logged to avoid leaking sensitive JWT structure/config
        raise JWTVerificationError("Token verification failed")
    except JWTVerificationError:
        raise
    except JWTError:
        logger.warning("JWT verification failed")
        raise JWTVerificationError("Token verification failed")


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

    # Role validation: default to viewer if missing or invalid
    role = payload.get("role", "viewer")
    if role not in _VALID_ROLES:
        logger.warning(
            f"Invalid role '{role}' in JWT (valid: {_VALID_ROLES}), defaulting to 'viewer'"
        )
        role = "viewer"

    # Optional claims
    email = payload.get("email")
    # Transform JWT's 'name' claim to 'display_name' for consistency with User model
    display_name = payload.get("name")
    projects = parse_comma_separated(payload.get("projects"))

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


def _get_jwt_secrets() -> list[str]:
    secrets: list[str] = []
    if settings.JWT_SECRET:
        secrets.append(settings.JWT_SECRET)
    if settings.JWT_SECRET_PREVIOUS:
        secrets.extend(parse_comma_separated(settings.JWT_SECRET_PREVIOUS))

    # Preserve order while removing duplicates
    seen: set[str] = set()
    ordered: list[str] = []
    for secret in secrets:
        if secret and secret not in seen:
            seen.add(secret)
            ordered.append(secret)
    return ordered
