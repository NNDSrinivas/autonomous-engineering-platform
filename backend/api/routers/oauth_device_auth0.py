from __future__ import annotations
import logging
import time
import requests
from jwt.algorithms import RSAAlgorithm
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import jwt

from backend.core.auth0 import (
    AUTH0_DOMAIN,
    DEVICE_CODE_URL,
    TOKEN_URL,
    USERINFO_URL,
    AUTH0_CLIENT_ID,
    AUTH0_DEVICE_CLIENT_ID,
    AUTH0_AUDIENCE,
    AUTH0_ISSUER,
)
from backend.core.jwt_session import SessionJWT

router = APIRouter(prefix="/oauth/device", tags=["oauth-device"])
logger = logging.getLogger(__name__)


def _error_detail(error: str, description: str, hint: str | None = None) -> dict[str, str]:
    detail = {"error": error, "error_description": description}
    if hint:
        detail["hint"] = hint
    return detail


def _auth0_response_error(response: httpx.Response) -> dict[str, str]:
    fallback = f"Auth0 returned HTTP {response.status_code}."
    try:
        payload = response.json()
    except ValueError:
        text = (response.text or "").strip()
        return _error_detail("auth0_error", text or fallback)

    if isinstance(payload, dict):
        error = str(payload.get("error") or "auth0_error")
        description = str(
            payload.get("error_description")
            or payload.get("message")
            or payload.get("detail")
            or fallback
        )
        return _error_detail(error, description)

    return _error_detail("auth0_error", fallback)


def _validate_auth0_settings() -> None:
    if not AUTH0_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail=_error_detail(
                "auth0_configuration_error",
                "AUTH0_CLIENT_ID is not configured on the backend.",
                "Set AUTH0_CLIENT_ID in environment and restart backend.",
            ),
        )
    if not AUTH0_AUDIENCE:
        raise HTTPException(
            status_code=503,
            detail=_error_detail(
                "auth0_configuration_error",
                "AUTH0_AUDIENCE is not configured on the backend.",
                "Set AUTH0_AUDIENCE in environment and restart backend.",
            ),
        )
    if not AUTH0_DOMAIN:
        raise HTTPException(
            status_code=503,
            detail=_error_detail(
                "auth0_configuration_error",
                "AUTH0_DOMAIN is not configured on the backend.",
                "Set AUTH0_DOMAIN in environment and restart backend.",
            ),
        )
    if "://" in AUTH0_DOMAIN:
        raise HTTPException(
            status_code=503,
            detail=_error_detail(
                "auth0_configuration_error",
                f"AUTH0_DOMAIN must be a bare host, got '{AUTH0_DOMAIN}'.",
                "Use a value like 'tenant.us.auth0.com' (without https://).",
            ),
        )


# JWKS cache with TTL for Auth0 ID token verification
_JWKS_CACHE: dict | None = None
_JWKS_CACHE_AT: float = 0.0
_JWKS_TTL_SECONDS = 3600  # 1 hour
AUTH0_JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"


def _get_jwks() -> dict:
    """Fetch JWKS from Auth0 custom domain with TTL cache."""
    global _JWKS_CACHE, _JWKS_CACHE_AT
    now = time.time()
    if _JWKS_CACHE is None or (now - _JWKS_CACHE_AT) > _JWKS_TTL_SECONDS:
        try:
            resp = requests.get(AUTH0_JWKS_URL, timeout=5)
            resp.raise_for_status()
            _JWKS_CACHE = resp.json()
            _JWKS_CACHE_AT = now
        except Exception as e:
            logger.error(f"Failed to fetch JWKS from {AUTH0_JWKS_URL}: {e}")
            raise HTTPException(
                status_code=503,
                detail=_error_detail(
                    "jwks_fetch_failed",
                    "Unable to fetch JWKS for token verification.",
                    "Check AUTH0_DOMAIN / network access.",
                ),
            )
    return _JWKS_CACHE


def _get_rsa_public_key(id_token: str):
    """Get the RSA public key from JWKS that matches the token's kid."""
    try:
        headers = jwt.get_unverified_header(id_token)
        kid = headers.get("kid")
        if not kid:
            raise ValueError("missing kid")
    except Exception:
        raise HTTPException(
            status_code=401,
            detail=_error_detail("invalid_token", "Malformed ID token header"),
        )

    jwks = _get_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(key)

    # Force refresh once in case of key rotation, then retry
    global _JWKS_CACHE
    _JWKS_CACHE = None
    jwks = _get_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(key)

    raise HTTPException(
        status_code=401,
        detail=_error_detail("invalid_token", f"No matching JWKS key for kid '{kid}'"),
    )


def verify_auth0_id_token(id_token: str) -> dict:
    """
    Verify Auth0 ID token signature and claims using custom domain JWKS.

    Returns decoded claims if valid.
    Raises HTTPException if verification fails.
    """
    public_key = _get_rsa_public_key(id_token)
    try:
        return jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=AUTH0_DEVICE_CLIENT_ID,  # ID token audience is the client_id
            issuer=AUTH0_ISSUER,  # Custom domain issuer with trailing slash
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail=_error_detail("token_expired", "ID token has expired"),
        )
    except InvalidTokenError as e:
        logger.warning(f"Auth0 ID token verification failed: {e}")
        raise HTTPException(
            status_code=401,
            detail=_error_detail("invalid_token", f"ID token verification failed: {e}"),
        )


class StartOut(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str | None = None
    interval: int | None = None
    expires_in: int | None = None  # Device code expiration (typically 900 seconds)


@router.post("/start", response_model=StartOut)
async def start():
    _validate_auth0_settings()
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            r = await http.post(
                DEVICE_CODE_URL,
                data={
                    "client_id": AUTH0_DEVICE_CLIENT_ID,
                    "audience": AUTH0_AUDIENCE,
                    "scope": "openid profile email offline_access",
                },
            )
    except httpx.RequestError as exc:
        logger.warning("Auth0 device start request failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=_error_detail(
                "auth0_unreachable",
                f"Unable to reach Auth0 device endpoint for domain '{AUTH0_DOMAIN}'.",
                "Verify AUTH0_DOMAIN DNS and outbound network access from backend.",
            ),
        ) from exc

    if r.status_code != 200:
        raise HTTPException(r.status_code, _auth0_response_error(r))

    j = r.json()
    return StartOut(
        device_code=j["device_code"],
        user_code=j["user_code"],
        verification_uri=j["verification_uri"],
        verification_uri_complete=j.get("verification_uri_complete"),
        interval=j.get("interval"),
        expires_in=j.get("expires_in"),
    )


class PollIn(BaseModel):
    device_code: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str  # AEP session token
    expires_in: int
    token_type: str = "Bearer"
    refresh_token: str | None = None  # Auth0 refresh token for token refresh flow


@router.post("/poll", response_model=TokenOut)
async def poll(body: PollIn):
    _validate_auth0_settings()
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            r = await http.post(
                TOKEN_URL,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": body.device_code,
                    "client_id": AUTH0_DEVICE_CLIENT_ID,
                },
            )
    except httpx.RequestError as exc:
        logger.warning("Auth0 device poll request failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=_error_detail(
                "auth0_unreachable",
                f"Unable to reach Auth0 token endpoint for domain '{AUTH0_DOMAIN}'.",
                "Verify AUTH0_DOMAIN DNS and outbound network access from backend.",
            ),
        ) from exc

    # 400 during pending/slow_down/expired — surface as 428 to keep polling client-side
    if r.status_code == 400:
        raise HTTPException(428, _auth0_response_error(r))
    if r.status_code != 200:
        raise HTTPException(r.status_code, _auth0_response_error(r))
    j = r.json()

    # Prefer id_token for profile; otherwise /userinfo
    sub = email = name = None
    if "id_token" in j:
        claims = verify_auth0_id_token(j["id_token"])
        sub, email, name = claims.get("sub"), claims.get("email"), claims.get("name")
    if not sub:
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                ui = await http.get(
                    USERINFO_URL, headers={"Authorization": f"Bearer {j['access_token']}"}
                )
        except httpx.RequestError as exc:
            logger.warning("Auth0 userinfo request failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail=_error_detail(
                    "auth0_unreachable",
                    f"Unable to reach Auth0 userinfo endpoint for domain '{AUTH0_DOMAIN}'.",
                    "Verify AUTH0_DOMAIN DNS and outbound network access from backend.",
                ),
            ) from exc

        if ui.status_code == 200:
            u = ui.json()
            sub, email, name = u.get("sub"), u.get("email"), u.get("name")
    if not sub:
        raise HTTPException(500, "Unable to resolve user identity")

    org = email.split("@", 1)[1] if email and "@" in email else "public"
    aep_token = SessionJWT.mint(
        sub=sub, email=email, org=org, name=name, roles=["viewer"]
    )

    # Extract Auth0 refresh token for client-side token refresh flow
    auth0_refresh_token = j.get("refresh_token")
    if not auth0_refresh_token:
        logger.warning(
            "Auth0 did not return refresh_token. Ensure offline_access scope is requested "
            "and Refresh Token grant is enabled in Auth0 application settings."
        )

    return TokenOut(
        access_token=aep_token,
        expires_in=3600,
        refresh_token=auth0_refresh_token
    )


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn):
    """
    Refresh an expired AEP session using Auth0 refresh token.

    This endpoint:
    1. Exchanges Auth0 refresh_token for new Auth0 tokens
    2. Verifies the new id_token signature and claims (RS256/JWKS)
    3. Mints a fresh AEP session JWT
    4. Returns new refresh_token if Auth0 rotated it
    """
    _validate_auth0_settings()

    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            r = await http.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": AUTH0_DEVICE_CLIENT_ID,
                    "refresh_token": body.refresh_token,
                },
            )
    except httpx.RequestError as exc:
        logger.warning("Auth0 refresh_token request failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=_error_detail(
                "auth0_unreachable",
                f"Unable to reach Auth0 token endpoint for domain '{AUTH0_DOMAIN}'.",
                "Verify AUTH0_DOMAIN DNS and outbound network access from backend.",
            ),
        ) from exc

    if r.status_code != 200:
        logger.warning(f"Auth0 refresh_token exchange failed: HTTP {r.status_code}")
        raise HTTPException(
            status_code=401,
            detail=_error_detail(
                "refresh_failed",
                "Unable to refresh session. Please sign in again.",
                "Refresh token may be expired or revoked.",
            ),
        )

    j = r.json()

    # Verify the new id_token (same verification as device flow)
    if "id_token" not in j:
        raise HTTPException(
            status_code=401,
            detail=_error_detail(
                "invalid_token",
                "Auth0 did not return id_token in refresh response.",
            ),
        )

    claims = verify_auth0_id_token(j["id_token"])
    sub = claims.get("sub")
    email = claims.get("email")
    name = claims.get("name")

    if not sub:
        raise HTTPException(
            status_code=401,
            detail=_error_detail(
                "invalid_token",
                "Missing sub claim in verified id_token.",
            ),
        )

    # Mint fresh AEP session JWT (same as device flow)
    org = email.split("@", 1)[1] if email and "@" in email else "public"
    aep_token = SessionJWT.mint(
        sub=sub, email=email, org=org, name=name, roles=["viewer"]
    )

    # Auth0 may rotate refresh tokens if rotation is enabled
    new_refresh_token = j.get("refresh_token")
    if not new_refresh_token:
        logger.info(
            "Auth0 did not return new refresh_token (rotation may not be enabled). "
            "Client should continue using existing refresh_token."
        )

    return TokenOut(
        access_token=aep_token,
        expires_in=3600,
        refresh_token=new_refresh_token,
    )
