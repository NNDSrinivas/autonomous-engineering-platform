"""Memory indexing - chunk and embed content from various sources"""

from sqlalchemy.orm import Session
from sqlalchemy import text
from .embeddings import embed_texts
import hashlib
import json
from typing import Dict, List

CHUNK = 1200
OVERLAP = 150


def encode_vector_as_bytes(vec: List[float]) -> memoryview:
    """Encode a vector as bytes for storage in LargeBinary column.
    Uses JSON encoding for SQLite compatibility and easy migration to pgvector."""
    return memoryview(bytearray(json.dumps(vec), "utf-8"))


def decode_vector_from_bytes(data: bytes) -> List[float]:
    """Decode a vector from bytes stored in LargeBinary column."""
    return json.loads(bytes(data).decode("utf-8"))


def _chunks(s: str, n: int = CHUNK, overlap: int = OVERLAP):
    """Split text into overlapping chunks"""
    s = s or ""
    out = []
    i = 0
    while i < len(s):
        out.append(s[i : i + n])
        i += n - overlap
    return out or [""]


def upsert_memory_object(
    db: Session,
    org_id: str,
    source: str,
    foreign_id: str,
    title: str,
    url: str,
    lang: str,
    meta: Dict,
    content: str,
):
    """Index a content object into memory with embeddings"""
    # Insert or get existing object
    row = (
        db.execute(
            text(
                """
        INSERT INTO memory_object (org_id,source,foreign_id,title,url,lang,meta_json)
        VALUES (:o,:s,:f,:t,:u,:l,:m)
        ON CONFLICT (org_id, source, foreign_id) DO NOTHING
        RETURNING id
    """
            ),
            {
                "o": org_id,
                "s": source,
                "f": foreign_id,
                "t": title,
                "u": url,
                "l": lang,
                "m": json.dumps(meta),
            },
        )
        .mappings()
        .first()
    )

    if row is None:
        row = (
            db.execute(
                text(
                    "SELECT id FROM memory_object WHERE org_id=:o AND source=:s AND foreign_id=:f"
                ),
                {"o": org_id, "s": source, "f": foreign_id},
            )
            .mappings()
            .first()
        )

    obj_id = row["id"]

    # Chunk and embed
    parts = _chunks(content)
    vecs = embed_texts(parts)

    for i, (chunk, vec) in enumerate(zip(parts, vecs)):
        # Use blake2b for faster hashing (deduplication purposes only)
        h = hashlib.blake2b(chunk.encode()).hexdigest()
        # Skip if chunk already indexed
        if db.execute(
            text("SELECT 1 FROM memory_chunk WHERE object_id=:id AND hash=:h"),
            {"id": obj_id, "h": h},
        ).fetchone():
            continue

        db.execute(
            text(
                """
            INSERT INTO memory_chunk (object_id,seq,text,embedding,vec_dim,hash)
            VALUES (:id,:seq,:text,:emb,:dim,:h)
        """
            ),
            {
                "id": obj_id,
                "seq": i,
                "text": chunk,
                "emb": encode_vector_as_bytes(vec),
                "dim": len(vec),
                "h": h,
            },
        )

    db.commit()
    return obj_id
