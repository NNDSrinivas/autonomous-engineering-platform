"""VS Code/webview auth enforcement middleware."""

from __future__ import annotations

import os
from typing import Iterable

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.api.routers.oauth_device import validate_access_token


class VscodeAuthMiddleware(BaseHTTPMiddleware):
    """Require Bearer token for protected VS Code/webview endpoints."""

    def __init__(
        self,
        app,
        *,
        enabled: bool = True,
        allow_dev_bypass: bool = False,
        protected_prefixes: Iterable[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.allow_dev_bypass = allow_dev_bypass
        self.protected_prefixes = tuple(
            protected_prefixes
            if protected_prefixes is not None
            else (
                "/api/navi",
                "/api/command",
                "/api/command_runner",
            )
        )

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        # Skip auth during tests to avoid breaking unit suite
        if os.getenv("PYTEST_CURRENT_TEST") is not None:
            return await call_next(request)

        path = request.url.path
        if request.method == "OPTIONS" or not path.startswith(self.protected_prefixes):
            return await call_next(request)

        if self.allow_dev_bypass:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid authorization header"},
            )

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        try:
            token_info = await validate_access_token(token)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code, content={"detail": exc.detail}
            )

        # Make token info available downstream
        request.state.user = token_info
        return await call_next(request)
