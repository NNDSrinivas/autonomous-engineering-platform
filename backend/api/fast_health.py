"""
Ultra-fast health check endpoint that bypasses all middleware.

This endpoint is registered directly on the app before any middleware
is added, ensuring minimal latency for health checks.
"""

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health-fast"])


@router.get("/health-fast")
def health_fast() -> Response:
    """Fast health check (no middleware, no external dependencies)."""
    return JSONResponse(
        {
            "status": "ok",
            "service": "core",
            "checks": {"self": "ok"},
        },
        status_code=200,
    )
