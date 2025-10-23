"""Semantic search retrieval with cosine similarity"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from .embeddings import embed_texts
import json
import math
from typing import List, Dict


def cosine(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors"""
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return s / (na * nb)


def search(db: Session, org_id: str, query: str, k: int = 8) -> List[Dict]:
    """Semantic search across memory chunks"""
    qv = embed_texts([query])[0]

    # Fetch all chunks (limit for performance)
    rows = (
        db.execute(
            text(
                """
        SELECT mo.id obj_id, mo.source, mo.foreign_id, mo.title, mo.url, mo.meta_json,
               mc.seq, mc.text, mc.embedding
        FROM memory_chunk mc
        JOIN memory_object mo ON mo.id=mc.object_id
        WHERE mo.org_id=:o
        LIMIT 6000
    """
            ),
            {"o": org_id},
        )
        .mappings()
        .all()
    )

    # Score each chunk
    scored = []
    for r in rows:
        vec = json.loads(bytes(r["embedding"]).decode("utf-8"))
        scored.append((cosine(qv, vec), r))

    # Return top-k
    top = sorted(scored, key=lambda x: x[0], reverse=True)[:k]

    return [
        {
            "score": float(f"{s:.4f}"),
            "source": r["source"],
            "title": r["title"],
            "foreign_id": r["foreign_id"],
            "url": r["url"],
            "meta": json.loads(r["meta_json"] or "{}"),
            "chunk_seq": r["seq"],
            "excerpt": r["text"][:400],
        }
        for s, r in top
    ]
