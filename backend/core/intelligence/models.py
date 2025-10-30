"""
Data models for the Intelligent Context Agent system.
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer, Boolean
from sqlalchemy.sql import func
from backend.core.db import Base


class SourceType(str, Enum):
    """Types of integrated data sources."""
    JIRA = "jira"
    SLACK = "slack"
    CONFLUENCE = "confluence"
    TEAMS = "teams"
    ZOOM = "zoom"
    GITHUB = "github"
    MEETINGS = "meetings"
    DOCUMENTATION = "documentation"


class ContextSource(Base):
    """Database model for context sources and their metadata."""
    __tablename__ = "context_sources"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    source_id = Column(String(255), nullable=False, index=True)  # External ID
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=True)
    url = Column(String(1000), nullable=True)
    author = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    source_metadata = Column(JSON, nullable=True)  # Source-specific metadata
    org_key = Column(String(100), nullable=False, index=True)  # Organization scope
    indexed_at = Column(DateTime, nullable=True)  # When last indexed for search
    embedding_vector = Column(Text, nullable=True)  # For semantic search


class ContextQuery(BaseModel):
    """Model for user queries to the context agent."""
    query: str = Field(..., description="The user's question or request")
    source_types: Optional[List[SourceType]] = Field(
        default=None, 
        description="Limit search to specific source types"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context like current task, project, etc."
    )
    org_key: str = Field(..., description="Organization key for scoping")
    user_id: Optional[str] = Field(default=None, description="User making the query")
    limit: int = Field(default=10, description="Maximum number of results")


class ContextResult(BaseModel):
    """Individual result from context search."""
    source_type: SourceType
    source_id: str
    title: str
    snippet: str = Field(..., description="Relevant snippet from the content")
    url: Optional[str] = None
    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    relevance_score: float = Field(..., description="Relevance score 0-1")
    source_metadata: Optional[Dict[str, Any]] = None


class ContextResponse(BaseModel):
    """Response from the intelligent context agent."""
    query: str
    results: List[ContextResult]
    total_found: int
    processing_time_ms: int
    suggested_questions: List[str] = Field(
        default_factory=list,
        description="Follow-up questions the user might ask"
    )
    answer_summary: Optional[str] = Field(
        default=None,
        description="AI-generated summary of the answer"
    )


class TaskContext(BaseModel):
    """Context information for a specific task/ticket."""
    task_id: str
    task_type: SourceType  # JIRA, GitHub issue, etc.
    title: str
    description: Optional[str] = None
    assignee: Optional[str] = None
    status: Optional[str] = None
    related_context: List[ContextResult] = Field(
        default_factory=list,
        description="Automatically gathered related information"
    )


class UserQuestion(Base):
    """Database model to track user questions for learning and improvement."""
    __tablename__ = "user_questions"

    id = Column(Integer, primary_key=True, index=True)
    org_key = Column(String(100), nullable=False, index=True)
    user_id = Column(String(255), nullable=True, index=True)
    question = Column(Text, nullable=False)
    context_provided = Column(JSON, nullable=True)  # Context when question was asked
    results_found = Column(Integer, nullable=False, default=0)
    user_satisfied = Column(Boolean, nullable=True)  # User feedback
    created_at = Column(DateTime, server_default=func.now())
    response_data = Column(JSON, nullable=True)  # The full response we provided