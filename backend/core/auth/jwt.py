"""JWT token verification and user claims extraction."""

from __future__ import annotations

import json
import logging
import time
import urllib.request

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

from backend.core.auth.models import Role
from backend.core.auth.utils import parse_comma_separated
from backend.core.settings import settings

logger = logging.getLogger(__name__)

_JWKS_CACHE: dict[str, object] = {
    "expires_at": 0,
    "keys": None,
}


def _fetch_jwks(jwks_url: str) -> list[dict]:
    """Fetch JWKS from a remote URL with basic caching."""
    now = int(time.time())
    expires_at = int(_JWKS_CACHE.get("expires_at") or 0)
    cached_keys = _JWKS_CACHE.get("keys")
    if cached_keys and now < expires_at:
        return cached_keys  # type: ignore[return-value]

    try:
        with urllib.request.urlopen(jwks_url, timeout=5) as response:  # nosec B310
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        logger.error("jwks.fetch.failed", error=str(exc))
        raise JWTVerificationError("Failed to fetch JWKS") from exc

    keys = payload.get("keys", [])
    if not isinstance(keys, list) or not keys:
        raise JWTVerificationError("JWKS endpoint returned no keys")

    _JWKS_CACHE["keys"] = keys
    _JWKS_CACHE["expires_at"] = now + max(30, settings.JWT_JWKS_CACHE_TTL)
    return keys


def _get_jwks_key(token: str, jwks_url: str) -> dict:
    """Select the correct JWK for a token by kid."""
    try:
        headers = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise JWTVerificationError("Invalid token header") from exc

    kid = headers.get("kid")
    if not kid:
        raise JWTVerificationError("Token missing required 'kid' header")

    keys = _fetch_jwks(jwks_url)
    for key in keys:
        if key.get("kid") == kid:
            return key

    # SECURITY: Fail if kid doesn't match any known key
    raise JWTVerificationError(f"No matching key found for kid: {kid}")


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

    if settings.JWT_JWKS_URL:
        try:
            # SECURITY: Validate algorithm header before decoding
            unverified_header = jwt.get_unverified_header(token)
            alg = unverified_header.get("alg")
            if not alg or alg.lower() == "none":
                raise JWTVerificationError("Token algorithm cannot be 'none'")
            if alg not in ["RS256", "RS384", "RS512"]:
                raise JWTVerificationError(f"Unsupported algorithm: {alg}")

            jwk_key = _get_jwks_key(token, settings.JWT_JWKS_URL)
            payload = jwt.decode(
                token,
                jwk_key,
                algorithms=["RS256", "RS384", "RS512"],
                audience=settings.JWT_AUDIENCE,
                issuer=settings.JWT_ISSUER,
            )

            # SECURITY: Validate authorized party (azp/client_id) for PKCE native app tokens
            # Only tokens from our allowlisted VS Code Native apps should be accepted
            azp = payload.get("azp") or payload.get("client_id")
            if not azp:
                raise JWTVerificationError(
                    "Token missing required authorized party claim (azp/client_id)"
                )

            # Load valid client IDs from config (comma-separated list)
            valid_client_ids = set(parse_comma_separated(settings.auth0_valid_client_ids))
            if not valid_client_ids:
                logger.error("auth0_valid_client_ids not configured - rejecting all tokens")
                raise JWTVerificationError("Server misconfiguration: no valid client IDs configured")

            if azp not in valid_client_ids:
                # Log only prefix for security (avoid leaking full client IDs in logs)
                azp_prefix = azp[:8] if len(azp) > 8 else "***"
                logger.warning(f"Invalid authorized party rejected: {azp_prefix}...")
                raise JWTVerificationError("Invalid authorized party")

            return payload
        except ExpiredSignatureError as e:
            logger.warning("JWT verification failed: token expired")
            raise JWTVerificationError("Token has expired") from e
        except JWTClaimsError as e:
            logger.warning(
                "JWT verification failed: invalid claims",
                extra={
                    "audience": settings.JWT_AUDIENCE,
                    "issuer": settings.JWT_ISSUER,
                }
            )
            raise JWTVerificationError("Invalid token claims") from e
        except JWTError as e:
            logger.warning(f"JWT verification failed: {type(e).__name__}")
            raise JWTVerificationError("Token verification failed") from e

    if not settings.JWT_SECRET:
        raise JWTVerificationError(
            "JWT_SECRET is required when JWT_ENABLED=true and JWT_JWKS_URL is not set"
        )

    secrets = [settings.JWT_SECRET]
    secrets.extend(parse_comma_separated(settings.JWT_SECRET_PREVIOUS))
    secrets = [s for s in secrets if s]

    last_error: Exception | None = None
    for secret in secrets:
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=[settings.JWT_ALGORITHM],
                audience=settings.JWT_AUDIENCE,
                issuer=settings.JWT_ISSUER,
            )
            return payload
        except ExpiredSignatureError as e:
            raise JWTVerificationError("Token has expired") from e
        except JWTClaimsError as e:
            raise JWTVerificationError("Invalid token claims") from e
        except JWTError as e:
            last_error = e
            continue

    logger.warning("JWT verification failed")
    raise JWTVerificationError("Token verification failed") from last_error


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
