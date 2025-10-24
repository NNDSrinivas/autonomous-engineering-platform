"""Hybrid retrieval engine for Context Pack

Combines semantic search with keyword matching, recency, and authority scoring.
"""

from sqlalchemy.orm import Session
from sqlalchemy import text
import json
import math
import time
import re
from typing import List, Dict, Any
from ..search.embeddings import embed_texts


# Simple keyword tokenizer
KW_SPLIT = re.compile(r"[A-Za-z0-9_]+")


def _kw_score(q: str, txt: str) -> float:
    """Calculate keyword overlap score between query and text"""
    if not q or not txt:
        return 0.0
    qset = set(w.lower() for w in KW_SPLIT.findall(q) if len(w) > 2)
    tset = set(w.lower() for w in KW_SPLIT.findall(txt))
    if not qset:
        return 0.0
    inter = len(qset & tset)
    return min(1.0, inter / max(3, len(qset)))


def _recency_score(ts: float, now: float) -> float:
    """Calculate recency score with 30-day half-life"""
    days = max(0.0, (now - ts) / 86400.0)
    return 1.0 / (1.0 + days / 30.0)


def _authority_score(meta: Dict[str, Any]) -> float:
    """Calculate authority score based on engagement metrics"""
    s = 0.0
    if meta.get("ticket_status") in ("Done", "Merged", "Closed"):
        s += 0.3
    if meta.get("replies", 0) > 5:
        s += 0.2
    if meta.get("views", 0) > 50:
        s += 0.1
    return min(0.5, s)


def build_context_pack(
    db: Session, org_id: str, query: str, k: int, sources: List[str]
) -> List[Dict[str, Any]]:
    """Build context pack using hybrid retrieval

    Args:
        db: Database session
        org_id: Organization ID
        query: Search query
        k: Number of results to return
        sources: Optional list of sources to filter by

    Returns:
        List of context hits with scores and metadata
    """
    # 1) Get query embedding for semantic search
    qv = embed_texts([query])[0]

    # 2) Fetch memory chunks with optional source filtering
    source_filter = "AND mo.source = ANY(:src)" if sources else ""
    rows = (
        db.execute(
            text(
                f"""
      SELECT mo.source, mo.foreign_id, mo.title, mo.url, mo.meta_json, mc.text, mc.seq,
             EXTRACT(EPOCH FROM mc.created_at) as cts, mc.embedding
      FROM memory_chunk mc
      JOIN memory_object mo ON mo.id = mc.object_id
      WHERE mo.org_id = :o {source_filter}
      LIMIT 8000
    """
            ),
            {"o": org_id, "src": sources} if sources else {"o": org_id},
        )
        .mappings()
        .all()
    )

    def cosine(a, b):
        """Calculate cosine similarity between two vectors"""
        s = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(x * x for x in b)) or 1.0
        return s / (na * nb)

    # 3) Score each chunk with hybrid ranking
    now = time.time()
    scored = []
    for r in rows:
        vec = json.loads(bytes(r["embedding"]).decode("utf-8"))
        sem = cosine(qv, vec)
        kw = _kw_score(query, r["text"] or "")
        rec = _recency_score(r["cts"] or now, now)
        meta = json.loads(r["meta_json"] or "{}")
        auth = _authority_score(meta)

        # Hybrid score: semantic (55%), keyword (25%), recency (12%), authority (8%)
        final = 0.55 * sem + 0.25 * kw + 0.12 * rec + 0.08 * auth
        scored.append((final, r, {"sem": sem, "kw": kw, "rec": rec, "auth": auth}))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 4) Deduplicate by (source, foreign_id), keep best excerpt
    seen = set()
    out = []
    for s, r, parts in scored:
        key = (r["source"], r["foreign_id"])
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "source": r["source"],
                "title": r["title"],
                "foreign_id": r["foreign_id"],
                "url": r["url"],
                "excerpt": (r["text"] or "")[:700],
                "score": float(f"{s:.4f}"),
                "meta": json.loads(r["meta_json"] or "{}"),
            }
        )
        if len(out) >= k:
            break

    return out
