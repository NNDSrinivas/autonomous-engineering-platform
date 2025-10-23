"""Ingestion Metrics - Prometheus counters for document indexing"""

from prometheus_client import Counter

INGEST_DOCS = Counter("aep_ingest_docs_total", "Docs ingested into memory", ["source"])
INGEST_ERRORS = Counter("aep_ingest_errors_total", "Ingestion errors", ["source"])
