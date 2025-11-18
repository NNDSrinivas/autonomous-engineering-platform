"""
Organizational Brain API Endpoints

REST API for interacting with the organizational memory graph:
- Natural language queries
- Node creation and management
- Edge creation and graph navigation
- Batch ingestion from various platforms
- Statistics and analytics

All endpoints require authentication and organization context.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database.session import get_db
from backend.core.auth.deps import get_current_user
from backend.core.auth.models import User
from backend.schemas.memory_graph import (
    MemoryNodeCreate,
    MemoryNodeResponse,
    MemoryEdgeCreate,
    MemoryEdgeResponse,
    OrgBrainQueryRequest,
    OrgBrainQueryResponse,
    GraphNavigationRequest,
    GraphNavigationResponse,
    JiraIssueIngestRequest,
    SlackMessageIngestRequest,
    GitHubPRIngestRequest,
    ConfluencePageIngestRequest,
    IngestResponse,
    MemoryNodeWithScore
)
from backend.services.memory_graph_service import MemoryGraphService
from backend.services.org_brain_query import OrgBrainQuery
from backend.services.ingestors.jira_ingestor import JiraIngestor
from backend.services.ingestors.slack_ingestor import SlackIngestor
from backend.services.ingestors.github_ingestor import GitHubIngestor
from backend.services.ingestors.confluence_ingestor import ConfluenceIngestor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/org-brain", tags=["Organizational Brain"])


def get_memory_service(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
) -> MemoryGraphService:
    """Dependency to get memory graph service."""
    org_id = user.org_id or 'default-org'
    return MemoryGraphService(db=db, org_id=org_id, user_id=user.user_id)


# ============================================================================
# Query Endpoints
# ============================================================================

@router.post("/query", response_model=OrgBrainQueryResponse)
async def query_organizational_brain(
    request: OrgBrainQueryRequest,
    mg: MemoryGraphService = Depends(get_memory_service)
):
    """
    Natural language query across organizational memory.
    
    Examples:
    - "Show everything related to SCRUM-123"
    - "Summarize discussions about authentication redesign"
    - "What PRs were merged last week?"
    - "Find all mentions of the deploy pipeline"
    """
    try:
        query_engine = OrgBrainQuery(mg)
        result = await query_engine.query(
            question=request.query,
            limit=request.limit,
            node_types=request.node_types,
            include_edges=request.include_edges
        )
        
        # Convert to response model
        nodes = [
            MemoryNodeWithScore(
                id=n["id"],
                node_type=n["node_type"],
                title=n.get("title"),
                text=n["text"],
                score=n["score"],
                meta_json=n.get("meta_json", {})
            )
            for n in result["nodes"]
        ]
        
        return OrgBrainQueryResponse(
            query=request.query,
            answer=result["answer"],
            nodes=nodes,
            edges=result.get("edges"),
            total_results=result["total_nodes"]
        )
        
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}"
        )


@router.get("/search")
async def semantic_search(
    query: str,
    limit: int = 10,
    node_types: Optional[str] = None,
    mg: MemoryGraphService = Depends(get_memory_service)
):
    """
    Direct semantic search without LLM reasoning.
    Returns raw similarity search results.
    """
    try:
        types_list = node_types.split(",") if node_types else None
        results = await mg.search(query=query, limit=limit, node_types=types_list)
        return {"results": results, "total": len(results)}
        
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


# ============================================================================
# Node Management
# ============================================================================

@router.post("/nodes", response_model=MemoryNodeResponse, status_code=status.HTTP_201_CREATED)
async def create_node(
    node: MemoryNodeCreate,
    mg: MemoryGraphService = Depends(get_memory_service)
):
    """Create a new memory node."""
    try:
        node_id = await mg.add_node(
            node_type=node.node_type,
            text=node.text,
            title=node.title,
            meta=node.meta
        )
        
        created_node = mg.get_node(node_id)
        if not created_node:
            raise HTTPException(status_code=404, detail="Node creation failed")
        
        return MemoryNodeResponse.from_orm(created_node)
        
    except Exception as e:
        logger.error(f"Node creation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Node creation failed: {str(e)}"
        )


@router.get("/nodes/{node_id}", response_model=MemoryNodeResponse)
async def get_node(
    node_id: int,
    mg: MemoryGraphService = Depends(get_memory_service)
):
    """Get a specific node by ID."""
    node = mg.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    return MemoryNodeResponse.from_orm(node)


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    node_id: int,
    mg: MemoryGraphService = Depends(get_memory_service)
):
    """Delete a node and all its relationships."""
    success = mg.delete_node(node_id)
    if not success:
        raise HTTPException(status_code=404, detail="Node not found")


# ============================================================================
# Edge Management
# ============================================================================

@router.post("/edges", response_model=MemoryEdgeResponse, status_code=status.HTTP_201_CREATED)
async def create_edge(
    edge: MemoryEdgeCreate,
    mg: MemoryGraphService = Depends(get_memory_service)
):
    """Create a new edge between two nodes."""
    try:
        edge_id = mg.add_edge(
            from_id=edge.from_id,
            to_id=edge.to_id,
            edge_type=edge.edge_type,
            weight=edge.weight,
            meta=edge.meta
        )
        
        # Get the created edge
        from backend.models.memory_graph import MemoryEdge
        created_edge = mg.db.query(MemoryEdge).filter(MemoryEdge.id == edge_id).first()
        
        if not created_edge:
            raise HTTPException(status_code=404, detail="Edge creation failed")
        
        return MemoryEdgeResponse.from_orm(created_edge)
        
    except Exception as e:
        logger.error(f"Edge creation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Edge creation failed: {str(e)}"
        )


# ============================================================================
# Graph Navigation
# ============================================================================

@router.post("/navigate", response_model=GraphNavigationResponse)
async def navigate_graph(
    request: GraphNavigationRequest,
    mg: MemoryGraphService = Depends(get_memory_service)
):
    """Navigate the graph starting from a specific node."""
    try:
        # Get root node
        root_node = mg.get_node(request.node_id)
        if not root_node:
            raise HTTPException(status_code=404, detail="Root node not found")
        
        # Get related nodes
        related_nodes, edges = mg.get_related_nodes(
            node_id=request.node_id,
            edge_types=request.edge_types,
            depth=request.depth
        )
        
        return GraphNavigationResponse(
            root_node=MemoryNodeResponse.from_orm(root_node),
            related_nodes=[MemoryNodeResponse.from_orm(n) for n in related_nodes],
            edges=[MemoryEdgeResponse.from_orm(e) for e in edges],
            total_nodes=len(related_nodes),
            total_edges=len(edges)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Graph navigation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Navigation failed: {str(e)}"
        )


# ============================================================================
# Platform-Specific Ingestion
# ============================================================================

@router.post("/ingest/jira", response_model=IngestResponse)
async def ingest_jira_issue(
    request: JiraIssueIngestRequest,
    mg: MemoryGraphService = Depends(get_memory_service)
):
    """Ingest a Jira issue into the memory graph."""
    try:
        ingestor = JiraIngestor(mg)
        
        # Convert request to issue dict
        issue_dict = {
            "key": request.issue_key,
            "fields": {
                "summary": request.summary,
                "description": request.description,
                "status": {"name": request.status},
                "assignee": {"displayName": request.assignee} if request.assignee else None,
                "issuelinks": request.issue_links or []
            }
        }
        
        node_id = await ingestor.ingest_issue(issue_dict)
        
        return IngestResponse(
            node_id=node_id,
            node_type="jira_issue",
            edges_created=0,
            message=f"Successfully ingested Jira issue {request.issue_key}"
        )
        
    except Exception as e:
        logger.error(f"Jira ingestion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )


@router.post("/ingest/slack", response_model=IngestResponse)
async def ingest_slack_message(
    request: SlackMessageIngestRequest,
    mg: MemoryGraphService = Depends(get_memory_service)
):
    """Ingest a Slack message into the memory graph."""
    try:
        ingestor = SlackIngestor(mg)
        
        message_dict = {
            "text": request.text,
            "user": request.user,
            "ts": request.message_ts,
            "thread_ts": request.thread_ts
        }
        
        node_id = await ingestor.ingest_message(
            channel_id=request.channel_id,
            message=message_dict
        )
        
        return IngestResponse(
            node_id=node_id,
            node_type="slack_message",
            edges_created=0,
            message="Successfully ingested Slack message"
        )
        
    except Exception as e:
        logger.error(f"Slack ingestion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )


@router.post("/ingest/github/pr", response_model=IngestResponse)
async def ingest_github_pr(
    request: GitHubPRIngestRequest,
    mg: MemoryGraphService = Depends(get_memory_service)
):
    """Ingest a GitHub pull request into the memory graph."""
    try:
        ingestor = GitHubIngestor(mg)
        
        pr_dict = {
            "number": request.pr_number,
            "title": request.title,
            "body": request.body,
            "state": request.state,
            "user": {"login": request.author},
            "base": {"ref": request.base_branch},
            "head": {"ref": request.head_branch}
        }
        
        node_id = await ingestor.ingest_pr(pr_dict, repo_name="default-repo")
        
        return IngestResponse(
            node_id=node_id,
            node_type="github_pr",
            edges_created=0,
            message=f"Successfully ingested GitHub PR #{request.pr_number}"
        )
        
    except Exception as e:
        logger.error(f"GitHub PR ingestion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )


@router.post("/ingest/confluence", response_model=IngestResponse)
async def ingest_confluence_page(
    request: ConfluencePageIngestRequest,
    mg: MemoryGraphService = Depends(get_memory_service)
):
    """Ingest a Confluence page into the memory graph."""
    try:
        ingestor = ConfluenceIngestor(mg)
        
        page_dict = {
            "id": request.page_id,
            "title": request.title,
            "body": {"storage": {"value": request.content}},
            "space": {"key": request.space_key},
            "history": {"createdBy": {"displayName": request.author}}
        }
        
        node_id = await ingestor.ingest_page(page_dict)
        
        return IngestResponse(
            node_id=node_id,
            node_type="confluence_page",
            edges_created=0,
            message=f"Successfully ingested Confluence page '{request.title}'"
        )
        
    except Exception as e:
        logger.error(f"Confluence ingestion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )


# ============================================================================
# Statistics and Analytics
# ============================================================================

@router.get("/stats")
async def get_stats(mg: MemoryGraphService = Depends(get_memory_service)):
    """Get statistics about the memory graph."""
    try:
        stats = mg.get_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )
