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
from ..deps import get_current_user
from backend.core.auth_org import require_org
import time
from backend.agent.context_packet import build_context_packet  # Agent-facing packet builder

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

    # Resolve org_id from caller; require it to avoid cross-tenant leakage.
    if not req.org_id:
        raise HTTPException(status_code=400, detail="org_id is required for context retrieval")
    org_id = req.org_id

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
        query=req.query,
        hits=hits,
        notes=notes,
        latency_ms=lat,
        total=len(hits),
    )


@router.get("/packet/{task_key}")
async def get_context_packet(
    task_key: str,
    db: Session = Depends(get_db),
    include_related: bool = True,
    current_user: dict = Depends(get_current_user),
    org_ctx: dict = Depends(require_org),
):
    """
    Build a unified context packet for a task/PR keyed by `task_key`.

    This is the live, source-linked payload the NAVI agent will consume for
    planning and approvals. For now it hydrates Jira facts from the ingested
    cache and leaves hooks for Slack/Teams/Docs/PR/CI hydration.
    """
    org_id = org_ctx["org_id"]

    try:
        packet = await build_context_packet(
            task_key=task_key,
            db=db,
            user_id=current_user.get("user_id"),
            org_id=org_id,
            include_related=include_related,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build context packet: {exc}")

    return packet.to_dict()
