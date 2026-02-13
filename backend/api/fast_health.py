"""
Ultra-fast health check endpoint with minimal overhead.

This endpoint provides a lightweight health check with no external
dependencies, making it suitable for load balancers and monitoring systems.
Note: In FastAPI, middleware applies to all routes regardless of registration order.
"""

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health-fast"])


@router.get("/ping", include_in_schema=False)
def ping() -> Response:
    """Minimal ping endpoint for load balancer health checks."""
    return Response(content="pong", media_type="text/plain", status_code=200)


@router.get("/health-fast")
def health_fast() -> Response:
    """Fast health check with no external dependencies (database, cache, etc.)."""
    return JSONResponse(
        {
            "status": "ok",
            "service": "core",
            "checks": {"self": "ok"},
        },
        status_code=200,
    )
