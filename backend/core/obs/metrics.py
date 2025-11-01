from __future__ import annotations
import os
from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,  # Use default registry
)

PROM_ENABLED = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"

# Core metrics (compatible with existing schema)
REQ_COUNTER = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
)
REQ_LATENCY = Histogram(
    "http_request_latency_seconds",  # Keep existing name for compatibility
    "HTTP request latency (s)",
    ["service", "method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
STREAM_DROPS = Counter(
    "sse_stream_drops_total",
    "SSE drops/backpressure events",
    ["plan_id"],
)
PUB_LATENCY = Histogram(
    "plan_publish_e2e_seconds",
    "Publish→delivery latency (s)",
    ["plan_id"],
)


def metrics_app():
    from starlette.responses import Response, PlainTextResponse
    from starlette.applications import Starlette
    from starlette.routing import Route

    async def metrics(_):
        if not PROM_ENABLED:
            return PlainTextResponse("Prometheus disabled", status_code=404)
        data = generate_latest(REGISTRY)  # Uses default registry
        return Response(data, media_type=CONTENT_TYPE_LATEST)

    return Starlette(routes=[Route("/metrics", metrics)])
