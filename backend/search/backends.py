"""
Vector search backends with hybrid ranking (PR-16)

Supports multiple vector search backends:
- pgvector: PostgreSQL extension for ANN search (production-ready)
- faiss: Facebook AI Similarity Search (optional, for local development)
- json: Fallback to JSON-stored vectors with linear scan

Implements hybrid ranking with configurable weights:
- Semantic similarity (55%)
- BM25 keyword matching (25%)
- Recency scoring (12%)
- Authority scoring (8%)
"""

import json
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import settings

# Import embeddings at module level to avoid circular dependency
# This is safe because embeddings.py doesn't import from backends
from .embeddings import embed_texts


# Hybrid ranking weights (configurable via PR-15 constants)
SEMANTIC_WEIGHT = 0.55
KEYWORD_WEIGHT = 0.25
RECENCY_WEIGHT = 0.12
AUTHORITY_WEIGHT = 0.08

# Recency scoring parameters
RECENCY_HALF_LIFE_DAYS = 30.0  # Days until recency score decays by 50%

# JSON vector fallback parameters
JSON_VECTOR_SCAN_LIMIT = 8000  # Maximum rows to scan in linear search
EXCERPT_MAX_LENGTH = 700  # Maximum excerpt length in characters


def _recency_score(timestamp: float, now: float) -> float:
    """Calculate recency score with exponential decay

    Args:
        timestamp: Unix timestamp of the item
        now: Current unix timestamp

    Returns:
        Score between 0.0 (exclusive) and 1.0 (1.0 = recent, approaches 0.0 for old items)
    """
    days_old = max(0.0, (now - timestamp) / 86400.0)
    return 1.0 / (1.0 + days_old / RECENCY_HALF_LIFE_DAYS)


def _authority_score(meta: Dict[str, Any]) -> float:
    """Calculate authority score from metadata

    Args:
        meta: Metadata dictionary with authority signals

    Returns:
        Score between 0.0 and 0.5. Individual signals may sum to more than 0.5,
        but the final score is capped at 0.5 before being returned.
    """
    score = 0.0

    # Completed work signals quality
    if meta.get("ticket_status") in ("Done", "Merged", "Closed"):
        score += 0.3

    # High engagement signals importance
    if meta.get("replies", 0) > 5:
        score += 0.2

    # View count indicates relevance
    if meta.get("views", 0) > 50:
        score += 0.1

    return min(0.5, score)


def _bm25(
    db: Session, org_id: str, query: str, sources: Optional[List[str]], limit: int
) -> Dict[Tuple[str, str], float]:
    """BM25 keyword search using PostgreSQL full-text search

    Args:
        db: Database session
        org_id: Organization ID for tenant isolation
        query: Search query string
        sources: Optional list of sources to filter (e.g., ["github", "jira"])
        limit: Maximum number of results

    Returns:
        Dictionary mapping (source, foreign_id) tuples to BM25 scores
    """
    if not settings.bm25_enabled:
        return {}

    dialect = db.bind.dialect.name

    if dialect == "postgresql":
        # Use PostgreSQL native full-text search with ts_rank
        source_filter = "AND mo.source = ANY(:src)" if sources else ""
        rows = (
            db.execute(
                text(
                    f"""
          SELECT mo.source, mo.foreign_id, 
                 ts_rank(to_tsvector('english', mc.text), plainto_tsquery('english', :q)) AS rnk
          FROM memory_chunk mc
          JOIN memory_object mo ON mo.id = mc.object_id
          WHERE mo.org_id = :o {source_filter}
          ORDER BY rnk DESC NULLS LAST
          LIMIT :lim
        """
                ),
                {"o": org_id, "q": query, "src": sources, "lim": limit},
            )
            .mappings()
            .all()
        )
        return {(r["source"], r["foreign_id"]): float(r["rnk"] or 0.0) for r in rows}
    else:
        # SQLite fallback: simple keyword overlap scoring
        # TODO: Implement FTS5 for SQLite if needed
        return {}


def semantic_pgvector(
    db: Session,
    org_id: str,
    query_vec: List[float],
    sources: Optional[List[str]],
    limit: int,
) -> List[Tuple[float, Dict[str, Any]]]:
    """Semantic search using pgvector ANN

    Args:
        db: Database session
        org_id: Organization ID
        query_vec: Query embedding vector
        sources: Optional source filters
        limit: Maximum results

    Returns:
        List of (similarity_score, row_dict) tuples
    """
    source_filter = "AND mo.source = ANY(:src)" if sources else ""

    # Use cosine distance operator (<->) for ANN search
    # pgvector will use HNSW or IVFFLAT index automatically
    # Cast :qvec to vector type to resolve operator type ambiguity
    rows = (
        db.execute(
            text(
                f"""
      SELECT mo.source, mo.foreign_id, mo.title, mo.url, mo.meta_json, 
             mc.text, mc.seq,
             EXTRACT(EPOCH FROM mc.created_at) AS cts,
             (embedding_vec <-> :qvec::vector) AS dist
      FROM memory_chunk mc
      JOIN memory_object mo ON mo.id = mc.object_id
      WHERE mo.org_id = :o {source_filter}
      ORDER BY embedding_vec <-> :qvec::vector
      LIMIT :lim
    """
            ),
            {
                "o": org_id,
                "src": sources,
                "lim": limit,
                "qvec": f'[{",".join(str(x) for x in query_vec)}]',
            },
        )
        .mappings()
        .all()
    )

    # Convert cosine distance to similarity (1 - distance)
    results = []
    for r in rows:
        similarity = 1.0 - float(r["dist"])
        results.append((similarity, dict(r)))

    return results


def semantic_json(
    db: Session,
    org_id: str,
    query_vec: List[float],
    sources: Optional[List[str]],
    limit: int,
) -> List[Tuple[float, Dict[str, Any]]]:
    """Semantic search using JSON-stored vectors (fallback)

    Linear scan with cosine similarity computation in Python.
    Slower than pgvector but works without extensions.

    Args:
        db: Database session
        org_id: Organization ID
        query_vec: Query embedding vector
        sources: Optional source filters
        limit: Maximum results

    Returns:
        List of (similarity_score, row_dict) tuples
    """
    source_filter = "AND mo.source = ANY(:src)" if sources else ""
    scan_limit = getattr(settings, "json_vector_scan_limit", JSON_VECTOR_SCAN_LIMIT)

    rows = (
        db.execute(
            text(
                f"""
      SELECT mo.source, mo.foreign_id, mo.title, mo.url, mo.meta_json, 
             mc.text, mc.seq,
             EXTRACT(EPOCH FROM mc.created_at) AS cts, 
             mc.embedding
      FROM memory_chunk mc
      JOIN memory_object mo ON mo.id = mc.object_id
      WHERE mo.org_id = :o {source_filter}
      LIMIT :scan_limit
    """
            ),
            {"o": org_id, "src": sources, "scan_limit": scan_limit},
        )
        .mappings()
        .all()
    )

    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors"""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a)) if any(a) else 1.0
        norm_b = math.sqrt(sum(x * x for x in b)) if any(b) else 1.0
        return dot_product / (norm_a * norm_b)

    scored = []
    for r in rows:
        vec = json.loads(bytes(r["embedding"]).decode("utf-8"))
        similarity = cosine_similarity(query_vec, vec)
        scored.append((similarity, dict(r)))

    # Sort by similarity descending and return top-k
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]


def semantic(
    db: Session,
    org_id: str,
    query_vec: List[float],
    sources: Optional[List[str]],
    limit: int,
) -> List[Tuple[float, Dict[str, Any]]]:
    """Route to appropriate semantic search backend

    Args:
        db: Database session
        org_id: Organization ID
        query_vec: Query embedding vector
        sources: Optional source filters
        limit: Maximum results

    Returns:
        List of (similarity_score, row_dict) tuples
    """
    backend = settings.vector_backend.lower()

    if backend == "pgvector":
        return semantic_pgvector(db, org_id, query_vec, sources, limit)
    elif backend == "faiss":
        # TODO: Implement FAISS backend (optional for PR-16)
        # from .faiss_index import semantic_faiss
        # return semantic_faiss(db, org_id, query_vec, sources, limit)
        # Fallback to JSON for now
        return semantic_json(db, org_id, query_vec, sources, limit)
    else:
        # Default to JSON backend
        return semantic_json(db, org_id, query_vec, sources, limit)


def hybrid_search(
    db: Session, org_id: str, query: str, sources: Optional[List[str]], k: int
) -> List[Dict[str, Any]]:
    """Hybrid search combining semantic, BM25, recency, and authority

    Implements the hybrid ranking formula:
    final_score = 0.55*semantic + 0.25*bm25 + 0.12*recency + 0.08*authority

    Args:
        db: Database session
        org_id: Organization ID for tenant isolation
        query: Search query string
        sources: Optional list of sources to filter
        k: Number of results to return

    Returns:
        List of result dictionaries with scores and metadata
    """
    # Generate query embedding
    query_vec = embed_texts([query])[0]

    # Current timestamp for recency scoring
    now = time.time()

    # Fetch semantic results (overfetch for reranking)
    sem_results = semantic(db, org_id, query_vec, sources, limit=5 * k)

    # Fetch BM25 keyword scores
    bm25_scores = _bm25(db, org_id, query, sources, limit=5 * k)

    # Group results by (source, foreign_id) for deduplication
    buckets: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for similarity, row in sem_results:
        key = (row["source"], row["foreign_id"])
        if key not in buckets:
            buckets[key] = {"best_sim": similarity, "best_row": row, "rows": []}
        buckets[key]["rows"].append((similarity, row))
        # Track best similarity score for this document
        if similarity > buckets[key]["best_sim"]:
            buckets[key]["best_sim"] = similarity
            buckets[key]["best_row"] = row

    # Compute hybrid scores
    hybrid_results = []
    for key, data in buckets.items():
        row = data["best_row"]
        sem_score = data["best_sim"]

        # Parse metadata
        meta = json.loads(row["meta_json"] or "{}")

        # Compute component scores
        rec_score = _recency_score(row["cts"] or now, now)
        auth_score = _authority_score(meta)
        bm25_score = bm25_scores.get(key, 0.0)

        # Normalize BM25 to [0, 1] range (ts_rank typically < 1.0)
        bm25_score = min(1.0, bm25_score)

        # Compute final hybrid score
        final_score = (
            SEMANTIC_WEIGHT * sem_score
            + KEYWORD_WEIGHT * bm25_score
            + RECENCY_WEIGHT * rec_score
            + AUTHORITY_WEIGHT * auth_score
        )

        hybrid_results.append((final_score, row))

    # Sort by hybrid score descending
    hybrid_results.sort(key=lambda x: x[0], reverse=True)

    # Deduplicate and format results
    output = []
    seen = set()

    for score, row in hybrid_results:
        key = (row["source"], row["foreign_id"])
        if key in seen:
            continue
        seen.add(key)

        output.append(
            {
                "source": row["source"],
                "foreign_id": row["foreign_id"],
                "title": row["title"],
                "url": row["url"],
                "excerpt": (row["text"] or "")[:EXCERPT_MAX_LENGTH],
                "score": float(f"{score:.4f}"),
                "meta": json.loads(row["meta_json"] or "{}"),
            }
        )

        if len(output) >= k:
            break

    return output
