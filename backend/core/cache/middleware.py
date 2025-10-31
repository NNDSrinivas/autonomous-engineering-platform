from __future__ import annotations
import os
import time
import threading
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Best-effort counters for single process monitoring
# Note: These are process-local and not accurate in multi-worker deployments
#
# Using threading.Lock instead of asyncio.Lock for simple counter operations:
# - Lock is held for nanoseconds (just counter increments)
# - Synchronous operations avoid async overhead for trivial operations
# - AsyncIO event loop handles brief blocking gracefully for such short operations
_hits = 0
_misses = 0
_counter_lock = threading.Lock()


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
        start = time.time()
        response = await call_next(request)
        # annotate response with coarse cache availability
        response.headers["X-Cache-Enabled"] = "true" if _cache_enabled() else "false"
        # lightweight counters (best-effort, thread-safe)
        with _counter_lock:
            response.headers["X-Cache-Hits"] = str(_hits)
            response.headers["X-Cache-Misses"] = str(_misses)

        # Add Server-Timing header properly
        existing_server_timing = response.headers.get("Server-Timing", "")
        app_timing = f"app;dur={(time.time() - start)*1000:.2f}"
        if existing_server_timing.strip():
            response.headers["Server-Timing"] = (
                existing_server_timing + f", {app_timing}"
            )
        else:
            response.headers["Server-Timing"] = app_timing
        return response
