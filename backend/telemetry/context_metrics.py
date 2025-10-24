"""Context Pack telemetry

Prometheus metrics for observability
"""
from prometheus_client import Histogram, Gauge

# Context pack retrieval latency (milliseconds)
CTX_LAT_MS = Histogram(
    "context_pack_latency_ms",
    "Latency for context pack retrieval in milliseconds",
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2500, 5000],
)

# Number of context hits returned
CTX_HITS = Histogram(
    "context_pack_hits",
    "Number of context hits returned per query",
    buckets=[0, 1, 3, 5, 10, 20, 50, 100],
)
