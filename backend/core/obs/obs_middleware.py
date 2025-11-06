from __future__ import annotations
import re
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from .obs_logging import logger
from .obs_metrics import REQ_COUNTER, REQ_LATENCY

HEADER_REQ_ID = "X-Request-Id"
HTTP_STATUS_INTERNAL_ERROR = "500"

# UUID pattern for validating request IDs
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


def validate_request_id(req_id: str) -> bool:
    """Validate request ID to prevent injection attacks."""
    if not req_id:
        return False

    # Check length (reasonable limit)
    if len(req_id) > 100:
        return False

    # Check if it's a valid UUID format
    return UUID_PATTERN.match(req_id) is not None


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Adds a request ID, records latency metrics, and emits structured logs.
    """

    def __init__(self, app, service_name: str = "core"):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Validate incoming request ID, generate new one if invalid
        incoming_req_id = request.headers.get(HEADER_REQ_ID)
        if incoming_req_id and validate_request_id(incoming_req_id):
            req_id = incoming_req_id
        else:
            req_id = str(uuid.uuid4())
            if incoming_req_id:
                logger.warning(
                    f"Invalid request ID received, generated new one: {req_id}"
                )

        start = time.time()

        # attach for downstream use (e.g., audit)
        request.state.request_id = req_id
        request.state.req_id = req_id  # Backward compatibility for AuditMiddleware

        try:
            response = await call_next(request)
        except Exception:
            dur = time.time() - start
            route = request.url.path
            REQ_COUNTER.labels(
                service=self.service_name,
                method=request.method,
                path=route,
                status=HTTP_STATUS_INTERNAL_ERROR,
            ).inc()
            REQ_LATENCY.labels(
                service=self.service_name,
                method=request.method,
                path=route,
                status=HTTP_STATUS_INTERNAL_ERROR,
            ).observe(dur)
            logger.error(
                "request failed",
                extra={
                    "request_id": req_id,
                    "route": route,
                    "method": request.method,
                    "status": int(HTTP_STATUS_INTERNAL_ERROR),
                },
            )
            raise

        # success path
        dur = time.time() - start
        route = request.url.path
        status = str(response.status_code)

        # metrics
        try:
            REQ_COUNTER.labels(
                service=self.service_name,
                method=request.method,
                path=route,
                status=status,
            ).inc()
            REQ_LATENCY.labels(
                service=self.service_name,
                method=request.method,
                path=route,
                status=status,
            ).observe(dur)
        except Exception:
            logger.warning(
                "Failed to record metrics", exc_info=True, extra={"request_id": req_id}
            )

        # logs
        try:
            user = getattr(request.state, "user", None)
            logger.info(
                "request",
                extra={
                    "request_id": req_id,
                    "route": route,
                    "method": request.method,
                    "status": int(status),
                    "org_id": getattr(user, "org_id", None),
                    "user_sub": getattr(user, "id", None),
                },
            )
        except Exception:
            logger.warning(
                "Logging request info failed",
                exc_info=True,
                extra={"request_id": req_id},
            )

        # headers
        response.headers[HEADER_REQ_ID] = req_id
        existing_server_timing = response.headers.get("Server-Timing", "")
        dur_ms = f"{dur * 1000:.2f}"

        # Handle Server-Timing header properly
        trimmed = existing_server_timing.strip()
        if trimmed:
            if trimmed.endswith(","):
                response.headers["Server-Timing"] = f"{trimmed} app_obs;dur={dur_ms}"
            else:
                response.headers["Server-Timing"] = f"{trimmed}, app_obs;dur={dur_ms}"
        else:
            response.headers["Server-Timing"] = f"app_obs;dur={dur_ms}"
        return response
