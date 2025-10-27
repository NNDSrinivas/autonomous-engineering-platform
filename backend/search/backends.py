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
import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import settings

# Import embeddings at module level to avoid circular dependency
# This is safe because embeddings.py doesn't import from backends
from .embeddings import embed_texts


logger = logging.getLogger(__name__)

# Hybrid ranking weights
SEMANTIC_WEIGHT = 0.55
KEYWORD_WEIGHT = 0.25
RECENCY_WEIGHT = 0.12
AUTHORITY_WEIGHT = 0.08

# Recency scoring parameters
RECENCY_HALF_LIFE_DAYS = 30.0  # Half-life parameter in recency decay formula (score reaches 0.5 when days == RECENCY_HALF_LIFE_DAYS)

# Authority scoring parameters
AUTHORITY_COMPLETED_STATUSES = frozenset(("Done", "Merged", "Closed"))
AUTHORITY_HIGH_REPLIES_THRESHOLD = 5
AUTHORITY_HIGH_VIEWS_THRESHOLD = 50
AUTHORITY_COMPLETED_SCORE = 0.3
AUTHORITY_HIGH_REPLIES_SCORE = 0.2
AUTHORITY_HIGH_VIEWS_SCORE = 0.1
AUTHORITY_MAX_SCORE = 0.5

# Hybrid search overfetch multiplier
# Fetch 5x more results than requested to allow for:
# - Deduplication of chunks from same document (keeps best chunk per doc)
# - Reranking with hybrid scores (semantic + BM25 + recency + authority)
# - Filtering that may remove some results
# Note: 5x is a conservative constant. Could be made adaptive based on deduplication
# rates, but would require tracking historical metrics and adds complexity.
HYBRID_OVERFETCH_MULTIPLIER = 5

# JSON vector fallback parameters
# WARNING: Linear scan can be slow on large tables. Use pgvector for production.
JSON_VECTOR_SCAN_LIMIT = 2000  # Maximum rows to scan in linear search
EXCERPT_MAX_LENGTH = 700  # Maximum excerpt length in characters

# Numerical stability parameters
EPSILON = 1e-8  # Small value to prevent division by zero in cosine similarity


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors

    Args:
        a: First vector
        b: Second vector

    Returns:
        Cosine similarity score between -1.0 and 1.0, or 0.0 for zero vectors

    Raises:
        ValueError: If vectors have different dimensions
    """
    if len(a) != len(b):
        raise ValueError(f"Vectors must have same dimension, got {len(a)} and {len(b)}")

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    # Return 0.0 for zero vectors instead of masking with 1.0
    if norm_a <= EPSILON or norm_b <= EPSILON:
        return 0.0
    return dot_product / (norm_a * norm_b)


def _recency_score(timestamp: float, now: float) -> float:
    """Calculate recency score with hyperbolic decay

    Args:
        timestamp: Unix timestamp of the item
        now: Current unix timestamp

    Returns:
        Score between 0.0 and 1.0 (1.0 = recent, asymptotically approaches 0.0 for old items)
    """
    days_old = max(0.0, (now - timestamp) / 86400.0)
    return 1.0 / (1.0 + days_old / RECENCY_HALF_LIFE_DAYS)


def _authority_score(meta: Dict[str, Any]) -> float:
    """Calculate authority score from metadata

    Args:
        meta: Metadata dictionary with authority signals

    Returns:
        Score between 0.0 and 0.5 based on authority signals (capped at 0.5)
    """
    score = 0.0

    # Completed work signals quality
    if meta.get("ticket_status") in AUTHORITY_COMPLETED_STATUSES:
        score += AUTHORITY_COMPLETED_SCORE

    # High engagement signals importance
    if meta.get("replies", 0) > AUTHORITY_HIGH_REPLIES_THRESHOLD:
        score += AUTHORITY_HIGH_REPLIES_SCORE

    # View count indicates relevance
    if meta.get("views", 0) > AUTHORITY_HIGH_VIEWS_THRESHOLD:
        score += AUTHORITY_HIGH_VIEWS_SCORE

    return min(AUTHORITY_MAX_SCORE, score)


def _normalize_bm25_score(score: float) -> float:
    """Normalize BM25/ts_rank score to [0, 1) range using x/(1+x) transformation

    This smooth normalization avoids the hard ceiling of min(1.0, x) and produces
    values that asymptotically approach 1.0 as x increases to infinity.

    Args:
        score: Raw BM25/ts_rank score (non-negative, unbounded)

    Returns:
        Normalized score in [0, 1) range for consistent weighting with other components
    """
    score = max(0.0, score)
    return score / (1.0 + score)


def _ts_rank_score(
    db: Session, org_id: str, query: str, sources: Optional[List[str]], limit: int
) -> Dict[Tuple[str, str], float]:
    """Full-text search using PostgreSQL's ts_rank (BM25 approximation)

    Note: This uses ts_rank as an approximation of BM25. While BM25 has built-in
    length normalization, ts_rank uses a different algorithm. The scores are later
    normalized using x/(1+x) transformation for hybrid ranking.

    Args:
        db: Database session
        org_id: Organization ID for tenant isolation
        query: Search query string
        sources: Optional list of sources to filter (e.g., ["github", "jira"])
        limit: Maximum number of results

    Returns:
        Dictionary mapping (source, foreign_id) tuples to ts_rank scores
    """
    # Early return if BM25 is disabled - avoid unnecessary processing
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
          ORDER BY rnk DESC
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
        return {}


def semantic_pgvector(
    db: Session,
    org_id: str,
    query_vec: List[float],
    sources: Optional[List[str]],
    limit: int,
) -> List[Tuple[float, Dict[str, Any]]]:
    """Semantic search using pgvector ANN

    Uses the pgvector <-> (cosine distance) operator which returns values in
    the range [0, 2] for normalized vectors. These distances are converted to
    similarity scores via similarity = 1 - distance, resulting in scores in the
    range [-1, 1], where:
    - 1.0 = identical vectors (distance 0)
    - 0.0 = orthogonal vectors (distance 1)
    - -1.0 = opposite vectors (distance 2)

    Note: Assumes embedding vectors are L2-normalized (standard for most
    embedding models like OpenAI, Cohere, sentence-transformers).

    Args:
        db: Database session
        org_id: Organization ID
        query_vec: Query embedding vector
        sources: Optional source filters
        limit: Maximum results

    Returns:
        List of (similarity_score, row_dict) tuples with scores in [-1, 1]
    """
    source_filter = "AND mo.source = ANY(:src)" if sources else ""

    # pgvector will use HNSW or IVFFLAT index automatically
    # When using parameter binding, PostgreSQL cannot automatically determine whether :qvec is a text[] or a vector type.
    # Explicitly casting :qvec to vector (::vector) is necessary to resolve operator type ambiguity and ensure pgvector uses the correct similarity operator.
    rows = (
        db.execute(
            text(
                f"""
      SELECT mo.source, mo.foreign_id, mo.title, mo.url, mo.meta_json, 
             mc.text, mc.seq,
             EXTRACT(EPOCH FROM mc.created_at) AS cts,
             -- pgvector <-> operator returns cosine distance in [0, 2] for normalized vectors
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
                "qvec": "[" + ",".join(map(str, query_vec)) + "]",
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
            {"o": org_id, "src": sources, "scan_limit": JSON_VECTOR_SCAN_LIMIT},
        )
        .mappings()
        .all()
    )

    scored = []
    for r in rows:
        # Handle different types returned by database (str, bytes, memoryview)
        embedding_data = r["embedding"]
        if isinstance(embedding_data, str):
            vec = json.loads(embedding_data)
        elif isinstance(embedding_data, memoryview):
            vec = json.loads(embedding_data.tobytes().decode("utf-8"))
        elif isinstance(embedding_data, bytes):
            vec = json.loads(embedding_data.decode("utf-8"))
        else:
            # Unsupported type - log error and raise exception
            logger.error(
                f"Unsupported embedding_data type: {type(embedding_data).__name__}"
            )
            raise TypeError(
                f"Cannot parse embedding_data of type {type(embedding_data).__name__}. "
                f"Expected str, bytes, or memoryview. "
                f"This may indicate a database configuration issue. "
                f"Check that the embedding column is defined as TEXT or BLOB in your database schema. "
                f"If using PostgreSQL, ensure the column type is TEXT or BYTEA, not JSONB."
            )

        similarity = _cosine_similarity(query_vec, vec)
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
        # FAISS backend is recognized but not yet implemented
        logger.warning(
            "FAISS backend is recognized but not yet implemented. "
            "Falling back to JSON vector search."
        )
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

    # Fetch semantic results (overfetch for reranking and deduplication)
    sem_results = semantic(
        db, org_id, query_vec, sources, limit=HYBRID_OVERFETCH_MULTIPLIER * k
    )

    # Fetch BM25 keyword scores (using ts_rank as approximation)
    bm25_scores = _ts_rank_score(
        db, org_id, query, sources, limit=HYBRID_OVERFETCH_MULTIPLIER * k
    )

    # Group results by (source, foreign_id) for deduplication
    buckets: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for similarity, row in sem_results:
        key = (row["source"], row["foreign_id"])
        if key not in buckets:
            buckets[key] = {
                "best_sim": similarity,
                "best_row": row,
                "rows": [(similarity, row)],
            }
        else:
            buckets[key]["rows"].append((similarity, row))
            # Update to best similarity score for this document
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

        # Normalize BM25 using x/(1+x), which produces values in [0, 1) that
        # asymptotically approach 1.0 as x increases to infinity. ts_rank returns
        # non-negative values but can exceed 1.0 for highly relevant matches, so this
        # smooth normalization avoids the hard ceiling of min(1.0, x).
        # Note: This uses PostgreSQL's ts_rank as an approximation of BM25, not true BM25 scoring.
        # While BM25 has built-in length normalization, ts_rank uses a different algorithm and its scores
        # are unbounded and can vary widely. This transformation maps them to [0, 1) for consistent weighting
        # with other normalized components (semantic, recency, authority).
        bm25_score = _normalize_bm25_score(bm25_score)

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
