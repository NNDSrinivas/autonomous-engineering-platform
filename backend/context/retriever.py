"""Hybrid retrieval engine for Context Pack

Combines semantic search with keyword matching, recency, and authority scoring.

NOTE (PR-16): This module now serves as a thin wrapper around the new
search.backends module which provides pgvector ANN, FAISS, and hybrid BM25 support.
The legacy constants and scoring functions below are kept for backwards compatibility
but are no longer actively used in the main retrieval path.
"""

from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from ..search.backends import hybrid_search as backends_hybrid_search


def build_context_pack(
    db: Session,
    org_id: str,
    query: str,
    k: int,
    sources: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Build context pack using hybrid retrieval

    Delegates to search.backends.hybrid_search which provides:
    - Semantic search via pgvector ANN or JSON fallback
    - BM25 keyword matching via PostgreSQL FTS
    - Recency and authority scoring
    - Hybrid ranking with configurable weights

    Args:
        db: Database session
        org_id: Organization ID for tenant isolation
        query: Search query string
        k: Number of results to return
        sources: Optional list of sources to filter (e.g., ["github", "jira"])

    Returns:
        List of context hits with scores and metadata
    """
    return backends_hybrid_search(db, org_id, query, sources, k)
