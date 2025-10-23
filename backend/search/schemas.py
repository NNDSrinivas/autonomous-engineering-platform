"""Pydantic schemas for search API"""

from pydantic import BaseModel
from typing import List, Optional, Dict


class SearchRequest(BaseModel):
    q: str
    k: int = 8


class SearchHit(BaseModel):
    score: float
    source: str
    title: Optional[str]
    foreign_id: str
    url: Optional[str]
    meta: Dict[str, str] = {}
    chunk_seq: int
    excerpt: str


class SearchResponse(BaseModel):
    hits: List[SearchHit]
