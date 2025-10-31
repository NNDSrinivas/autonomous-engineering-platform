from __future__ import annotations
import os, time
from typing import Callable
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

PROM_ENABLED = os.getenv("PROMETHEUS_ENABLED", "true").lower() == "true"
REGISTRY = CollectorRegistry(auto_describe=True)

# Core metrics
REQ_COUNTER = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "route", "status"], registry=REGISTRY
)
REQ_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency (s)", ["method", "route"], buckets=(0.01,0.05,0.1,0.25,0.5,1,2,5), registry=REGISTRY
)
STREAM_DROPS = Counter(
    "sse_stream_drops_total", "SSE drops/backpressure events", ["plan_id"], registry=REGISTRY
)
PUB_LATENCY = Histogram(
    "plan_publish_e2e_seconds", "Publish→delivery latency (s)", ["plan_id"], registry=REGISTRY
)

def metrics_app():
    from starlette.responses import Response, PlainTextResponse
    from starlette.applications import Starlette
    from starlette.routing import Route

    async def metrics(_):
        if not PROM_ENABLED:
            return PlainTextResponse("prometheus disabled", status_code=404)
        data = generate_latest(REGISTRY)
        return Response(data, media_type=CONTENT_TYPE_LATEST)

    return Starlette(routes=[Route("/metrics", metrics)])