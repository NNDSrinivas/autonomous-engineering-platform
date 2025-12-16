"""
Org-aware auth helpers.

Extracts org_id from JWT claims or headers and enforces presence for protected routes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException

from backend.core.auth.jwt import verify_token, JWTVerificationError
from backend.core.settings import settings

logger = logging.getLogger(__name__)


def require_org(
    x_org_id: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Require org_id, preferring verified JWT claims when JWT is enabled.
    """
    org_id = None

    if settings.JWT_ENABLED:
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ", 1)[1]
            try:
                claims = verify_token(token)
                org_id = claims.get("org_id") or claims.get("org")
            except JWTVerificationError:
                logger.warning("auth.org_from_jwt_failed")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        # No Authorization header -> fail fast in JWT mode
        if not org_id:
            raise HTTPException(
                status_code=400,
                detail="Missing organization context. Provide a valid JWT with org claim.",
            )
    else:
        # Dev mode: allow header (preferred) or fail if missing
        org_id = x_org_id
        if not org_id:
            logger.warning("auth.org_missing")
            raise HTTPException(
                status_code=400,
                detail="Missing organization context. Provide X-Org-Id header.",
            )

    return {"org_id": org_id}
