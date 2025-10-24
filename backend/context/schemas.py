"""Pydantic schemas for Context Pack API"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class ContextPackRequest(BaseModel):
    """Request schema for building a context pack"""

    query: Optional[str] = None
    task_key: Optional[str] = None
    active_path: Optional[str] = None
    k: int = 8
    sources: Optional[List[str]] = (
        None  # ["jira","meeting","code","confluence","slack","wiki"]
    )


class ContextHit(BaseModel):
    """A single context hit from memory search"""

    source: str
    title: Optional[str]
    foreign_id: str
    url: Optional[str]
    excerpt: str
    score: float
    meta: Dict[str, Any] = {}


class AgentNoteOut(BaseModel):
    """Agent note output schema"""

    id: int
    title: str
    body_md: str
    scope: str
    importance: float
    tags: List[str] = []


class ContextPackResponse(BaseModel):
    """Response schema for context pack"""

    query: str
    hits: List[ContextHit]
    notes: List[AgentNoteOut]
    budget_tokens: int
