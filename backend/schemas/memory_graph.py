"""
Memory Graph Schemas - Pydantic models for API requests/responses

Request and response models for the organizational brain API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


# ============================================================================
# Node Schemas
# ============================================================================

class MemoryNodeCreate(BaseModel):
    """Request to create a new memory node"""
    node_type: str = Field(..., description="Type of node: jira_issue, slack_msg, pr, code, etc")
    text: str = Field(..., description="Full text content of the node")
    title: Optional[str] = Field(None, description="Optional title/heading")
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class MemoryNodeResponse(BaseModel):
    """Response with node details"""
    id: int
    org_id: str
    node_type: str
    title: Optional[str]
    text: str
    meta_json: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True


class MemoryNodeWithScore(BaseModel):
    """Node with similarity score (for search results)"""
    id: int
    node_type: str
    title: Optional[str]
    text: str
    score: float
    meta_json: Dict[str, Any]


# ============================================================================
# Edge Schemas
# ============================================================================

class MemoryEdgeCreate(BaseModel):
    """Request to create a new memory edge"""
    from_id: int = Field(..., description="Source node ID")
    to_id: int = Field(..., description="Target node ID")
    edge_type: str = Field(..., description="Type: mentions, documents, implements, relates_to, etc")
    weight: float = Field(1.0, ge=0.0, le=10.0, description="Edge weight (0-10)")
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class MemoryEdgeResponse(BaseModel):
    """Response with edge details"""
    id: int
    org_id: str
    from_id: int
    to_id: int
    edge_type: str
    weight: float
    meta_json: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Query Schemas
# ============================================================================

class OrgBrainQueryRequest(BaseModel):
    """Natural language query to organizational brain"""
    query: str = Field(..., description="Natural language question or search query")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results")
    node_types: Optional[List[str]] = Field(None, description="Filter by node types")
    include_edges: bool = Field(True, description="Include related edges in response")


class OrgBrainQueryResponse(BaseModel):
    """Response to organizational brain query"""
    query: str
    answer: str
    nodes: List[MemoryNodeWithScore]
    edges: Optional[List[MemoryEdgeResponse]] = None
    total_results: int


# ============================================================================
# Graph Navigation Schemas
# ============================================================================

class GraphNavigationRequest(BaseModel):
    """Request to navigate the memory graph"""
    node_id: int = Field(..., description="Starting node ID")
    depth: int = Field(1, ge=1, le=3, description="How many hops to traverse")
    edge_types: Optional[List[str]] = Field(None, description="Filter by edge types")


class GraphNavigationResponse(BaseModel):
    """Response with graph neighborhood"""
    root_node: MemoryNodeResponse
    related_nodes: List[MemoryNodeResponse]
    edges: List[MemoryEdgeResponse]
    total_nodes: int
    total_edges: int


# ============================================================================
# Ingestion Schemas
# ============================================================================

class JiraIssueIngestRequest(BaseModel):
    """Request to ingest Jira issue into memory graph"""
    issue_key: str
    summary: str
    description: Optional[str]
    status: str
    assignee: Optional[str]
    issue_links: Optional[List[Dict[str, Any]]] = None
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict)


class SlackMessageIngestRequest(BaseModel):
    """Request to ingest Slack message into memory graph"""
    channel_id: str
    message_ts: str
    text: str
    user: str
    thread_ts: Optional[str] = None
    mentions: Optional[List[str]] = None
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict)


class GitHubPRIngestRequest(BaseModel):
    """Request to ingest GitHub PR into memory graph"""
    pr_number: int
    title: str
    body: Optional[str]
    state: str
    author: str
    base_branch: str
    head_branch: str
    linked_issues: Optional[List[str]] = None
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ConfluencePageIngestRequest(BaseModel):
    """Request to ingest Confluence page into memory graph"""
    page_id: str
    title: str
    content: str
    space_key: str
    author: str
    parent_page_id: Optional[str] = None
    labels: Optional[List[str]] = None
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    """Response from ingestion operation"""
    node_id: int
    node_type: str
    edges_created: int
    message: str


# ============================================================================
# Batch Operations
# ============================================================================

class BatchIngestRequest(BaseModel):
    """Request to ingest multiple items at once"""
    nodes: List[MemoryNodeCreate]
    edges: Optional[List[MemoryEdgeCreate]] = None


class BatchIngestResponse(BaseModel):
    """Response from batch ingestion"""
    nodes_created: int
    edges_created: int
    node_ids: List[int]
    errors: List[str]
