from __future__ import annotations
import os
import time
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Simple request-scoped counters (process-local)
_hits = 0
_misses = 0


def _cache_enabled() -> bool:
    return os.getenv("CACHE_ENABLED", "true").lower() == "true"


class CacheMiddleware(BaseHTTPMiddleware):
    """
    Adds cache capability headers and maintains process-local counters.
    (If you later add Prometheus, increment metrics here.)
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        global _hits, _misses
        start = time.time()
        response = await call_next(request)
        # annotate response with coarse cache availability
        response.headers["X-Cache-Enabled"] = "true" if _cache_enabled() else "false"
        # lightweight counters (best-effort)
        response.headers["X-Cache-Hits"] = str(_hits)
        response.headers["X-Cache-Misses"] = str(_misses)

        # Add Server-Timing header properly
        existing_server_timing = response.headers.get("Server-Timing", "")
        app_timing = f"app;dur={(time.time()-start)*1000:.2f}"
        if existing_server_timing.strip():
            response.headers["Server-Timing"] = (
                existing_server_timing + f", {app_timing}"
            )
        else:
            response.headers["Server-Timing"] = app_timing
        return response


def count_hit():
    global _hits
    _hits += 1


def count_miss():
    global _misses
    _misses += 1
