# backend/auth/auth0.py
from __future__ import annotations
import os
import time
from typing import Dict, Any
import httpx
from cachetools import TTLCache
from jose import jwt, jwk
from jose.utils import base64url_decode
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ---- Environment ----
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "auth.navralabs.com").strip()
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "https://api.navralabs.com").strip()
AUTH0_ISSUER = f"https://{AUTH0_DOMAIN}/"
JWKS_URL = f"{AUTH0_ISSUER}.well-known/jwks.json"

# ---- Caches ----
_jwks_cache: TTLCache[str, Dict[str, Any]] = TTLCache(maxsize=1, ttl=60 * 60)  # 1h
_kid_fail_cache: TTLCache[str, float] = TTLCache(maxsize=64, ttl=10 * 60)  # 10m

bearer = HTTPBearer(auto_error=True)


async def _fetch_jwks() -> Dict[str, Any]:
    cached = _jwks_cache.get("jwks")
    if cached:
        return cached
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(JWKS_URL)
        r.raise_for_status()
        data = r.json()
        _jwks_cache["jwks"] = data
        return data


def _verify_signature(token: str, jwks: Dict[str, Any]) -> Dict[str, Any]:
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    if not kid:
        raise HTTPException(status_code=401, detail="Missing kid in token header")

    # quick negative-cache to avoid repeated bad KIDs
    if kid in _kid_fail_cache:
        raise HTTPException(status_code=401, detail="Unknown signing key")

    key = next((k for k in jwks["keys"] if k.get("kid") == kid), None)
    if not key:
        # refresh once if rotation happened
        _jwks_cache.pop("jwks", None)
        raise HTTPException(status_code=401, detail="Signing key not found")

    message, encoded_sig = token.rsplit(".", 1)
    decoded_sig = base64url_decode(encoded_sig.encode("utf-8"))
    public_key = jwk.construct(key, algorithm=key.get("alg", "RS256"))
    if not public_key.verify(message.encode("utf-8"), decoded_sig):
        _kid_fail_cache[kid] = time.time()
        raise HTTPException(status_code=401, detail="Invalid token signature")

    return jwt.get_unverified_claims(token)


async def _decode_and_validate(token: str) -> Dict[str, Any]:
    jwks = await _fetch_jwks()
    _ = _verify_signature(token, jwks)

    # jose will re-check signature with the key we pass
    # We pass the JWKS set; jose can pick the right one via kid
    claims = jwt.decode(
        token,
        jwks,  # jose accepts JWKS (dict) for RS256
        algorithms=["RS256"],
        audience=AUTH0_AUDIENCE,
        issuer=AUTH0_ISSUER,
        options={"verify_at_hash": False},
    )
    # optional: enforce email_verified/org/role claims if you use them
    return claims


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> Dict[str, Any]:
    try:
        return await _decode_and_validate(credentials.credentials)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Unauthorized: {e}")


def require_role(*allowed_roles: str):
    """
    Usage: `@app.get("/admin")(depends=[Depends(require_role("admin"))])`
    Expects role claims in one of:
      - "https://navralabs.com/roles": ["admin", ...]  (recommended custom claim)
      - "permissions": ["role:admin"]                  (Auth0 RBAC)
    """

    async def _inner(claims: Dict[str, Any] = Depends(require_auth)) -> Dict[str, Any]:
        roles = []
        # Custom claim namespace (recommended)
        ns_roles = claims.get("https://navralabs.com/roles")
        if isinstance(ns_roles, list):
            roles.extend(ns_roles)
        # Auth0 permissions fallback
        perms = claims.get("permissions")
        if isinstance(perms, list):
            roles.extend(
                [p.replace("role:", "") for p in perms if p.startswith("role:")]
            )

        if not any(r in set(roles) for r in allowed_roles):
            raise HTTPException(status_code=403, detail="Insufficient role")
        return claims

    return _inner
