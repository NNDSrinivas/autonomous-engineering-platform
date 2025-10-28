"""Pydantic schemas for Context Pack API"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ContextPackRequest(BaseModel):
    """Request schema for building a context pack"""

    query: str = Field(..., description="Search query for context retrieval")
    task_key: Optional[str] = Field(None, description="Associated task key (e.g., JIRA issue)")
    active_path: Optional[str] = Field(None, description="Currently active file path for context")
    k: int = Field(8, description="Number of results to return", ge=1, le=100)
    sources: Optional[List[str]] = Field(
        None,
        description="Filter by sources: jira, meeting, code, confluence, slack, wiki",
    )
    policy: Optional[str] = Field(
        None, description="Policy name for filtering: public_only, internal_only"
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
    """Agent note output schema - matches database columns"""

    id: int
    task_key: str = Field(..., description="Associated task key")
    context: str = Field(..., description="Full context/details")
    summary: str = Field(..., description="Consolidated summary")
    importance: int = Field(..., description="Importance score 1-10", ge=1, le=10)
    tags: List[str] = Field(default_factory=list, description="Categorization tags")
    created_at: Optional[str] = Field(None, description="Creation timestamp (ISO)")
    updated_at: Optional[str] = Field(None, description="Last update timestamp (ISO)")


class ContextPackResponse(BaseModel):
    """Response schema for context pack"""

    query: str = Field(..., description="Original query")
    hits: List[ContextHit] = Field(
        default_factory=list, description="Context hits from memory search"
    )
    notes: List[AgentNoteOut] = Field(default_factory=list, description="Relevant agent notes")
    latency_ms: int = Field(..., description="Retrieval latency in milliseconds")
    total: int = Field(..., description="Total number of hits returned")
