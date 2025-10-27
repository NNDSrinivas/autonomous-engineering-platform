"""
Vector search telemetry and metrics (PR-16)

Prometheus metrics for monitoring vector search performance:
- ANN query latency
- Hybrid reranking latency
- Vector backfill progress
- Search result quality metrics
"""

from prometheus_client import Counter, Histogram

# ANN query latency histogram
# Buckets optimized for expected ANN performance (10-800ms)
ANN_LATENCY_MS = Histogram(
    "aep_ann_latency_ms",
    "ANN query latency in milliseconds",
    buckets=(10, 25, 50, 100, 200, 400, 800, 1600),
)

# Hybrid reranking latency histogram
# Buckets for post-retrieval scoring and merging (10-400ms)
HYBRID_RERANK_MS = Histogram(
    "aep_hybrid_rerank_ms",
    "Hybrid reranking latency in milliseconds",
    buckets=(10, 25, 50, 100, 200, 400),
)

# BM25 query latency histogram
BM25_LATENCY_MS = Histogram(
    "aep_bm25_latency_ms",
    "BM25/FTS query latency in milliseconds",
    buckets=(5, 10, 25, 50, 100, 200),
)

# Vector backfill progress counter
BACKFILL_VECTORS_TOTAL = Counter(
    "aep_backfill_vectors_total", "Total number of vectors backfilled from JSON"
)

# Search backend usage counter
SEARCH_BACKEND_CALLS = Counter(
    "aep_search_backend_calls_total",
    "Total search calls by backend type",
    ["backend"],  # Labels: pgvector, faiss, json
)

# Search result quality metrics
SEARCH_RESULTS_RETURNED = Histogram(
    "aep_search_results_returned",
    "Number of results returned per search",
    buckets=(1, 3, 5, 8, 10, 15, 20),
)

SEARCH_EMPTY_RESULTS = Counter(
    "aep_search_empty_results_total",
    "Total number of searches returning zero results",
)

# Context pack metrics
CONTEXT_PACK_LATENCY_MS = Histogram(
    "aep_context_pack_latency_ms",
    "End-to-end context pack generation latency",
    buckets=(50, 100, 200, 300, 500, 800, 1200),
)

CONTEXT_PACK_SIZE_BYTES = Histogram(
    "aep_context_pack_size_bytes",
    "Size of generated context pack in bytes",
    buckets=(1000, 5000, 10000, 25000, 50000, 100000),
)
