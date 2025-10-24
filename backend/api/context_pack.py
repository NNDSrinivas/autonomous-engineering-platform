"""Context Pack API endpoint

Provides retrieval-augmented context for LLM prompts
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..context.schemas import ContextPackRequest, ContextPackResponse
from ..context.retriever import build_context_pack
from ..context.service import filter_by_policy, fetch_relevant_notes
from ..telemetry.context_metrics import CTX_LAT_MS, CTX_HITS
import time

router = APIRouter(prefix="/context", tags=["context"])


@router.post("/pack", response_model=ContextPackResponse)
def get_context_pack(req: ContextPackRequest, db: Session = Depends(get_db)):
    """Build retrieval-augmented context pack for LLM prompts

    Combines:
    - Semantic search over memory chunks
    - Keyword matching for precision
    - Recency scoring for relevance
    - Authority scoring for quality
    - Agent notes for task-specific context

    Returns:
    - Top K context hits with scores
    - Relevant agent notes
    - Latency metrics
    """
    t0 = time.time()

    # Default org_id for MVP (should come from auth in production)
    org_id = "default_org"

    # Build hybrid context pack
    hits = build_context_pack(
        db=db,
        org_id=org_id,
        query=req.query,
        k=req.k,
        sources=req.sources or [],
    )

    # Apply policy filtering if specified
    if req.policy:
        hits = filter_by_policy(db, org_id, hits, req.policy)

    # Fetch relevant agent notes if task_key provided
    notes = []
    if req.task_key:
        notes = fetch_relevant_notes(db, org_id, req.task_key, limit=5)

    # Record metrics
    lat = int((time.time() - t0) * 1000)
    CTX_LAT_MS.observe(lat)
    CTX_HITS.observe(len(hits))

    return ContextPackResponse(
        hits=hits,
        notes=notes,
        latency_ms=lat,
        total=len(hits),
    )
