"""Semantic search retrieval with cosine similarity"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from .embeddings import embed_texts
from .indexer import decode_vector_from_bytes
import json
import math
import os
from typing import List, Dict

# Configurable limit for chunk retrieval (can be overridden via env var)
MAX_CHUNKS = int(os.getenv("AEP_SEARCH_MAX_CHUNKS", "6000"))


def cosine(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors - single-pass calculation"""
    dot = mag_a = mag_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        mag_a += x * x
        mag_b += y * y
    na = math.sqrt(mag_a) or 1.0
    nb = math.sqrt(mag_b) or 1.0
    return dot / (na * nb)


def search(db: Session, org_id: str, query: str, k: int = 8) -> List[Dict]:
    """Semantic search across memory chunks

    Note: This implementation loads all chunks into memory and computes similarity in Python.
    For production deployments with >10k chunks, consider:
    - Vector database with native similarity search (pgvector, Pinecone, Weaviate)
    - Pagination and filtering by source type before retrieval
    - Pre-computed index structures (FAISS, Annoy)
    """
    qv = embed_texts([query])[0]

    # Fetch all chunks for this org (limit configurable via env var)[Dict]:
    """Semantic search across memory chunks"""
    qv = embed_texts([query])[0]

    # Fetch all chunks for this org (limit configurable via env var)
    rows = (
        db.execute(
            text(
                """
        SELECT mo.id obj_id, mo.source, mo.foreign_id, mo.title, mo.url, mo.meta_json,
               mc.seq, mc.text, mc.embedding
        FROM memory_chunk mc
        JOIN memory_object mo ON mo.id=mc.object_id
        WHERE mo.org_id=:o
        LIMIT :limit
    """
            ),
            {"o": org_id, "limit": MAX_CHUNKS},
        )
        .mappings()
        .all()
    )

    # Score each chunk
    scored = []
    for r in rows:
        vec = decode_vector_from_bytes(r["embedding"])
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
