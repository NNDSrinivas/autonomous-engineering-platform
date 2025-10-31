from __future__ import annotations
import time, uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from .logging import logger
from .metrics import REQ_COUNTER, REQ_LATENCY

HEADER_REQ_ID = "X-Request-Id"

class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Adds a request ID, records latency metrics, and emits structured logs.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        req_id = request.headers.get(HEADER_REQ_ID) or str(uuid.uuid4())
        start = time.time()

        # attach for downstream use (e.g., audit)
        request.state.request_id = req_id

        try:
            response = await call_next(request)
        except Exception as e:
            dur = time.time() - start
            route = request.url.path
            REQ_COUNTER.labels(method=request.method, route=route, status="500").inc()
            REQ_LATENCY.labels(method=request.method, route=route).observe(dur)
            logger.error("request failed", extra={
                "request_id": req_id, "route": route, "method": request.method, "status": 500
            })
            raise

        # success path
        dur = time.time() - start
        route = request.url.path
        status = str(response.status_code)

        # metrics
        try:
            REQ_COUNTER.labels(method=request.method, route=route, status=status).inc()
            REQ_LATENCY.labels(method=request.method, route=route).observe(dur)
        except Exception:
            pass

        # logs
        try:
            user = getattr(request.state, "user", None)
            logger.info("request", extra={
                "request_id": req_id,
                "route": route,
                "method": request.method,
                "status": int(status),
                "org_id": getattr(user, "org_id", None),
                "user_sub": getattr(user, "id", None),
            })
        except Exception:
            pass

        # headers
        response.headers[HEADER_REQ_ID] = req_id
        response.headers["Server-Timing"] = response.headers.get("Server-Timing","") + f", app_obs;dur={dur*1000:.2f}"
        return response