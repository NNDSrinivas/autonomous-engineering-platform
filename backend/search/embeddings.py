"""Embeddings provider abstraction with OpenAI and dev fallback"""

import os
from typing import List


def provider() -> str:
    return os.getenv("EMBED_PROVIDER", "openai")


def dim() -> int:
    return int(os.getenv("EMBED_DIM", "1536"))


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a list of texts using configured provider"""
    p = provider()
    if p == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
        r = client.embeddings.create(model=model, input=texts)
        return [d.embedding for d in r.data]
    # Dev fallback without external calls
    out = []
    D = dim()
    for t in texts:
        v = [0.0] * D
        if t:
            v[0] = min(1.0, len(t) / 1000.0)
        out.append(v)
    return out
