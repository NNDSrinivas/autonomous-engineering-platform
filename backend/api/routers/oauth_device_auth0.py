from __future__ import annotations
import asyncio
import logging
import time
from jwt.algorithms import RSAAlgorithm
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
import httpx
import jwt
from cachetools import TTLCache

from backend.core.auth0 import (
    AUTH0_DOMAIN,
    DEVICE_CODE_URL,
    TOKEN_URL,
    USERINFO_URL,
    AUTH0_DEVICE_CLIENT_ID,
    AUTH0_AUDIENCE,
    AUTH0_ISSUER,
)
from backend.core.jwt_session import SessionJWT

router = APIRouter(prefix="/oauth/device", tags=["oauth-device"])
logger = logging.getLogger(__name__)


def _add_deprecation_headers(response: Response) -> None:
    """Add HTTP deprecation headers to signal legacy endpoint status."""
    response.headers["Deprecation"] = "true"
    response.headers[
        "Sunset"
    ] = "Tue, 01 Dec 2026 00:00:00 GMT"  # RFC 8594 HTTP-date format (9 months notice for enterprise adoption)
    response.headers["Link"] = '<https://docs.navralabs.com/auth/pkce>; rel="sunset"'
    logger.warning(
        "DEPRECATED: Device flow endpoint called. "
        "Extension v0.3.0+ uses PKCE. Device flow will be removed Tue, 01 Dec 2026 00:00:00 GMT."
    )


def _error_detail(
    error: str, description: str, hint: str | None = None
) -> dict[str, str]:
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
    """Validate Auth0 configuration required for device flow."""
    missing = []

    if not AUTH0_DOMAIN:
        missing.append("AUTH0_DOMAIN")
    elif "://" in AUTH0_DOMAIN:
        raise HTTPException(
            status_code=503,
            detail=_error_detail(
                "auth0_configuration_error",
                f"AUTH0_DOMAIN must be a bare host, got '{AUTH0_DOMAIN}'.",
                "Use a value like 'tenant.us.auth0.com' (without https://).",
            ),
        )

    if not AUTH0_DEVICE_CLIENT_ID:
        missing.append("AUTH0_DEVICE_CLIENT_ID")

    if not AUTH0_AUDIENCE:
        missing.append("AUTH0_AUDIENCE")

    if missing:
        raise HTTPException(
            status_code=503,
            detail=_error_detail(
                "auth0_configuration_error",
                "Auth0 device flow is not configured on the backend.",
                f"Missing required settings: {', '.join(missing)}. Set these in environment and restart backend.",
            ),
        )


# JWKS cache with TTL for Auth0 ID token verification
# NOTE: This JWKS cache is process-local. In multi-worker deployments, each worker
# will fetch JWKS independently (acceptable for most use cases). If you need shared
# caching across workers, consider backing with Redis.
_JWKS_CACHE: dict | None = None
_JWKS_CACHE_AT: float = 0.0
_JWKS_CACHE_DOMAIN: str | None = None  # Track which domain the cache is for
_JWKS_TTL_SECONDS = 3600  # 1 hour
_JWKS_LOCK = asyncio.Lock()
AUTH0_JWKS_URL = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"

# Rate limiting for refresh endpoint (per-IP, 60s window)
# IMPORTANT: This rate limiter is process-local (in-memory TTLCache).
# - Single worker: 20 requests/minute per IP (as intended)
# - Multi-worker (e.g., 4 workers): Effective limit is ~80 requests/minute per IP
#   (20 per worker × 4 workers), since each worker maintains its own bucket.
# For strict global rate limiting across workers (e.g., in production with multiple
# Gunicorn/Uvicorn workers), implement Redis-backed rate limiting using a shared
# token bucket (e.g., aioredis with atomic INCR/EXPIRE or Lua scripts).
_REFRESH_LIMIT = TTLCache(maxsize=5000, ttl=60)


async def _fetch_jwks() -> dict:
    """Fetch JWKS from Auth0 using async HTTP client."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.get(AUTH0_JWKS_URL)
        r.raise_for_status()
        return r.json()


async def _get_jwks(force_refresh: bool = False) -> dict:
    """Fetch JWKS from Auth0 custom domain with TTL cache and lock protection."""
    global _JWKS_CACHE, _JWKS_CACHE_AT, _JWKS_CACHE_DOMAIN
    now = time.time()

    # Invalidate cache if AUTH0_DOMAIN changed (e.g., test environment switching)
    if _JWKS_CACHE_DOMAIN != AUTH0_DOMAIN:
        _JWKS_CACHE = None
        _JWKS_CACHE_DOMAIN = AUTH0_DOMAIN
        logger.info(
            f"JWKS cache invalidated due to domain change: {_JWKS_CACHE_DOMAIN}"
        )

    # Fast path: cache is valid (skip if force_refresh requested)
    if (
        not force_refresh
        and _JWKS_CACHE is not None
        and (now - _JWKS_CACHE_AT) <= _JWKS_TTL_SECONDS
    ):
        return _JWKS_CACHE

    # Slow path: refresh cache with lock to prevent thundering herd
    async with _JWKS_LOCK:
        # Re-check domain after acquiring lock (in case of concurrent domain change)
        if _JWKS_CACHE_DOMAIN != AUTH0_DOMAIN:
            _JWKS_CACHE = None
            _JWKS_CACHE_DOMAIN = AUTH0_DOMAIN
            logger.info(
                f"JWKS cache invalidated due to domain change: {_JWKS_CACHE_DOMAIN}"
            )

        # Re-check after acquiring lock (another request may have refreshed)
        now = time.time()
        if (
            not force_refresh
            and _JWKS_CACHE is not None
            and (now - _JWKS_CACHE_AT) <= _JWKS_TTL_SECONDS
        ):
            return _JWKS_CACHE

        try:
            _JWKS_CACHE = await _fetch_jwks()
            _JWKS_CACHE_AT = now
            _JWKS_CACHE_DOMAIN = AUTH0_DOMAIN
            return _JWKS_CACHE
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


async def _get_rsa_public_key(id_token: str) -> RSAAlgorithm:
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

    jwks = await _get_jwks()
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(key)

    # Force refresh once in case of key rotation, then retry
    jwks = await _get_jwks(force_refresh=True)
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(key)

    raise HTTPException(
        status_code=401,
        detail=_error_detail("invalid_token", f"No matching JWKS key for kid '{kid}'"),
    )


async def verify_auth0_id_token(id_token: str) -> dict:
    """
    Verify Auth0 ID token signature and claims using custom domain JWKS.

    Returns decoded claims if valid.
    Raises HTTPException if verification fails.
    """
    public_key = await _get_rsa_public_key(id_token)
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


def _get_client_ip(request: Request) -> str:
    """
    Extract client IP address, checking proxy headers first.

    Checks X-Forwarded-For and X-Real-IP headers (set by ALB/nginx)
    before falling back to request.client.host.
    """
    # Check X-Forwarded-For (comma-separated list, first is client)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP (nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fallback to direct connection IP
    return request.client.host if request.client else "unknown"


def _rate_limit_refresh(ip: str, limit: int = 20) -> None:
    """Rate limit refresh attempts per IP (20 requests per 60s window)."""
    count = _REFRESH_LIMIT.get(ip, 0) + 1
    _REFRESH_LIMIT[ip] = count
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail=_error_detail(
                "rate_limited",
                "Too many refresh attempts. Please try again later.",
                "Wait 60 seconds before retrying.",
            ),
        )


class StartOut(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str | None = None
    interval: int | None = None
    expires_in: int | None = None  # Device code expiration (typically 900 seconds)


@router.post("/start", response_model=StartOut)
async def start(response: Response):
    _add_deprecation_headers(response)
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
async def poll(body: PollIn, response: Response):
    _add_deprecation_headers(response)
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
        claims = await verify_auth0_id_token(j["id_token"])
        sub, email, name = claims.get("sub"), claims.get("email"), claims.get("name")
    if not sub:
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                ui = await http.get(
                    USERINFO_URL,
                    headers={"Authorization": f"Bearer {j['access_token']}"},
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
        access_token=aep_token, expires_in=3600, refresh_token=auth0_refresh_token
    )


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, request: Request, response: Response):
    """
    Refresh an expired AEP session using Auth0 refresh token.

    This endpoint:
    1. Exchanges Auth0 refresh_token for new Auth0 tokens
    2. Verifies the new id_token signature and claims (RS256/JWKS)
    3. Mints a fresh AEP session JWT
    4. Returns new refresh_token if Auth0 rotated it

    SECURITY NOTE: For enhanced security, enable the following in Auth0 Dashboard:
    - "Refresh Token Rotation": Auth0 will issue a new refresh_token on each use
      and invalidate the previous one, preventing token replay attacks.
    - "Absolute Expiration": Set a maximum lifetime for refresh tokens (e.g., 30 days)
      to limit exposure if a token is compromised.

    Without rotation enabled, the same refresh_token can be reused indefinitely until
    it expires. This endpoint does NOT validate revocation status with Auth0; if a
    refresh_token has been manually revoked in Auth0, the exchange will fail with
    invalid_grant.
    """
    _add_deprecation_headers(response)
    _validate_auth0_settings()

    # Rate limit refresh attempts per IP (20/min)
    client_ip = _get_client_ip(request)
    _rate_limit_refresh(client_ip)

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
        # Parse Auth0 error response to distinguish transient vs auth failures
        error_body = None
        auth0_error = None
        auth0_desc = None
        try:
            error_body = r.json()
            if isinstance(error_body, dict):
                auth0_error = error_body.get("error")
                auth0_desc = error_body.get("error_description")
        except ValueError:
            pass

        logger.warning(
            f"Auth0 refresh_token exchange failed: HTTP {r.status_code}, "
            f"error={auth0_error!r}, description={auth0_desc!r}"
        )

        # Preserve rate limiting semantics so clients can retry with backoff
        if r.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail=_error_detail(
                    "auth0_rate_limited",
                    "Auth0 is rate limiting refresh attempts. Please retry shortly.",
                    auth0_desc,
                ),
            )

        # Propagate upstream server errors as 503 so callers know it's transient
        if 500 <= r.status_code < 600:
            raise HTTPException(
                status_code=503,
                detail=_error_detail(
                    "auth0_unavailable",
                    "Auth0 token endpoint is temporarily unavailable.",
                    auth0_desc,
                ),
            )

        # Treat invalid_grant as an actual refresh/auth failure
        if auth0_error == "invalid_grant" or r.status_code in (400, 401, 403):
            raise HTTPException(
                status_code=401,
                detail=_error_detail(
                    "refresh_failed",
                    "Unable to refresh session. Please sign in again.",
                    "Refresh token may be expired or revoked.",
                ),
            )

        # Fallback for other unexpected errors from Auth0
        raise HTTPException(
            status_code=502,
            detail=_error_detail(
                "auth0_token_error",
                "Unexpected error from Auth0 during token refresh.",
                auth0_desc,
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

    claims = await verify_auth0_id_token(j["id_token"])
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
