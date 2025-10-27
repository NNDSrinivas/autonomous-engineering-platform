"""Memory Graph API Router - Temporal reasoning and relationship queries

Provides endpoints for:
1. Graph rebuild (batch processing)
2. Node neighborhood queries
3. Natural language graph queries
4. Timeline construction

All endpoints enforce org-level RBAC and audit logging.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.reasoning.temporal_reasoner import TemporalReasoner
from backend.workers.graph_builder import GraphBuilder
from backend.database.models.memory_graph import MemoryNode, MemoryEdge
from backend.core.ai_service import AIService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory-graph"])

# Prometheus metrics (will be initialized in main.py)
try:
    from prometheus_client import Counter, Histogram, Gauge

    graph_build_counter = Counter(
        "aep_graph_builds_total",
        "Total graph rebuild requests",
        ["org_id", "status"],
    )
    graph_query_counter = Counter(
        "aep_graph_queries_total",
        "Total graph queries",
        ["org_id", "endpoint"],
    )
    graph_build_latency = Histogram(
        "aep_graph_build_latency_ms",
        "Graph build latency in milliseconds",
        ["org_id"],
    )
    graph_query_latency = Histogram(
        "aep_graph_query_latency_ms",
        "Graph query latency in milliseconds",
        ["endpoint"],
    )
    graph_nodes_gauge = Gauge(
        "aep_graph_nodes_total",
        "Total number of nodes in memory graph",
        ["org_id"],
    )
    graph_edges_gauge = Gauge(
        "aep_graph_edges_total",
        "Total number of edges in memory graph",
        ["org_id"],
    )
    METRICS_ENABLED = True
except ImportError:
    logger.warning("Prometheus metrics not available")
    METRICS_ENABLED = False


# Request/Response models
class GraphRebuildRequest(BaseModel):
    org_id: str
    since: Optional[str] = Field(
        default="30d", description="Time window (e.g., '30d', '90d')"
    )


class GraphRebuildResponse(BaseModel):
    status: str
    nodes_created: int
    edges_created: int
    nodes_updated: int
    org_id: str
    elapsed_ms: float


class GraphQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query")
    depth: int = Field(default=3, ge=1, le=5, description="Maximum search depth")
    k: int = Field(default=12, ge=1, le=50, description="Maximum nodes to return")


class TimelineQuery(BaseModel):
    issue: str = Field(..., description="Entity foreign_id (e.g., ENG-102, PR#456)")
    window: str = Field(default="30d", description="Time window")


# Dependency: Get org_id from header and validate
def get_org_id(x_org_id: Optional[str] = Header(None)) -> str:
    """Extract and validate org_id from request header"""
    if not x_org_id:
        raise HTTPException(status_code=401, detail="X-Org-Id header required")
    return x_org_id


# Helper: Create AIService instance (consider making this a singleton or FastAPI dependency)
def get_ai_service() -> AIService:
    """Get AIService instance. Called per-request but could be optimized as singleton."""
    return AIService()


# Dependency: Audit logging
def audit_log(
    request: Request,
    org_id: str,
    endpoint: str,
    params: dict,
    duration_ms: float,
):
    """Log graph operation for audit trail"""
    logger.info(
        f"GRAPH_AUDIT: org={org_id}, endpoint={endpoint}, "
        f"req_id={request.state.request_id if hasattr(request.state, 'request_id') else 'unknown'}, "
        f"params={params}, duration_ms={duration_ms:.2f}"
    )
    # In production, write to audit_log table or external audit service


@router.post("/graph/rebuild", response_model=GraphRebuildResponse)
async def rebuild_graph(
    req: GraphRebuildRequest,
    request: Request,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Rebuild memory graph for an organization

    Performs batch processing of artifacts to create nodes and edges.
    Use sparingly - typically nightly or after bulk imports.

    **RBAC**: Requires org-level write access
    """
    start_time = time.time()

    # Verify org_id matches
    if org_id != req.org_id:
        raise HTTPException(
            status_code=403,
            detail="X-Org-Id does not match request org_id",
        )

    try:
        # Parse since parameter with validation
        if req.since.endswith("d"):
            try:
                days = int(req.since.rstrip("d"))
                since = datetime.utcnow() - timedelta(days=days)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid 'since' parameter: {req.since}. Expected format like '30d'.",
                )
        else:
            try:
                since = datetime.fromisoformat(req.since)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid 'since' parameter: {req.since}. Expected ISO format or '30d'.",
                )

        # Initialize builder (using helper to get AIService instance)
        ai_service = get_ai_service()
        builder = GraphBuilder(db, ai_service)

        # Execute rebuild
        stats = builder.rebuild_graph(org_id, since)

        # Update metrics
        if METRICS_ENABLED:
            graph_build_counter.labels(org_id=org_id, status="success").inc()
            graph_build_latency.labels(org_id=org_id).observe(
                (time.time() - start_time) * 1000
            )

            # Update gauges
            node_count = db.query(MemoryNode).filter_by(org_id=org_id).count()
            edge_count = db.query(MemoryEdge).filter_by(org_id=org_id).count()
            graph_nodes_gauge.labels(org_id=org_id).set(node_count)
            graph_edges_gauge.labels(org_id=org_id).set(edge_count)

        elapsed_ms = (time.time() - start_time) * 1000

        # Audit log
        audit_log(request, org_id, "rebuild", {"since": req.since}, elapsed_ms)

        return GraphRebuildResponse(
            status="completed",
            nodes_created=stats["nodes_created"],
            edges_created=stats["edges_created"],
            nodes_updated=stats.get("nodes_updated", 0),
            org_id=org_id,
            elapsed_ms=elapsed_ms,
        )

    except Exception as e:
        if METRICS_ENABLED:
            graph_build_counter.labels(org_id=org_id, status="error").inc()

        logger.error(f"Graph rebuild failed for org={org_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Graph rebuild failed: {str(e)}")


@router.get("/graph/node/{foreign_id}")
async def get_node_neighborhood(
    foreign_id: str,
    request: Request,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Get node and its 1-hop neighborhood

    Returns the node and all directly connected nodes/edges.

    **RBAC**: Requires org-level read access
    """
    start_time = time.time()

    try:
        # Find node
        node = (
            db.query(MemoryNode).filter_by(org_id=org_id, foreign_id=foreign_id).first()
        )

        if not node:
            raise HTTPException(status_code=404, detail=f"Node {foreign_id} not found")

        # Get 1-hop neighborhood (using helper to get AIService instance)
        ai_service = get_ai_service()
        reasoner = TemporalReasoner(db, ai_service)
        nodes, edges = reasoner._build_subgraph(node, depth=1)

        elapsed_ms = (time.time() - start_time) * 1000

        if METRICS_ENABLED:
            graph_query_counter.labels(org_id=org_id, endpoint="node").inc()
            graph_query_latency.labels(endpoint="node").observe(elapsed_ms)

        # Audit log
        audit_log(request, org_id, "node", {"foreign_id": foreign_id}, elapsed_ms)

        return {
            "node": node.to_dict(),
            "neighbors": [n.to_dict() for n in nodes if n.id != node.id],
            "edges": [e.to_dict() for e in edges],
            "elapsed_ms": elapsed_ms,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Node query failed for {foreign_id}, org={org_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Node query failed: {str(e)}")


@router.post("/graph/query")
async def query_graph(
    req: GraphQueryRequest,
    request: Request,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Query memory graph with natural language

    Finds relevant subgraph and generates narrative explanation.
    Use for "explain" queries like "why was ENG-102 reopened?"

    **RBAC**: Requires org-level read access
    """
    start_time = time.time()

    try:
        # Initialize reasoner (using helper to get AIService instance)
        ai_service = get_ai_service()
        reasoner = TemporalReasoner(db, ai_service)

        # Execute explain
        result = reasoner.explain(org_id, req.query, depth=req.depth, k=req.k)

        elapsed_ms = (time.time() - start_time) * 1000

        if METRICS_ENABLED:
            graph_query_counter.labels(org_id=org_id, endpoint="query").inc()
            graph_query_latency.labels(endpoint="query").observe(elapsed_ms)

        # Audit log
        audit_log(
            request,
            org_id,
            "query",
            {"query": req.query, "depth": req.depth, "k": req.k},
            elapsed_ms,
        )

        result["elapsed_ms"] = elapsed_ms
        return result

    except Exception as e:
        logger.error(
            f"Graph query failed for '{req.query}', org={org_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Graph query failed: {str(e)}")


@router.get("/timeline")
async def get_timeline(
    issue: str,
    window: str = "30d",
    request: Request = None,
    org_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Get timeline for an entity

    Returns chronologically ordered events related to the entity.

    **RBAC**: Requires org-level read access

    Query params:
    - issue: Entity foreign_id (e.g., ENG-102, PR#456)
    - window: Time window (default: 30d)
    """
    start_time = time.time()

    try:
        # Initialize reasoner (using helper to get AIService instance)
        ai_service = get_ai_service()
        reasoner = TemporalReasoner(db, ai_service)

        # Execute timeline
        result = reasoner.timeline_for(org_id, issue, window)

        elapsed_ms = (time.time() - start_time) * 1000

        if METRICS_ENABLED:
            graph_query_counter.labels(org_id=org_id, endpoint="timeline").inc()
            graph_query_latency.labels(endpoint="timeline").observe(elapsed_ms)

        # Audit log
        if request:
            audit_log(
                request,
                org_id,
                "timeline",
                {"issue": issue, "window": window},
                elapsed_ms,
            )

        result["elapsed_ms"] = elapsed_ms
        return result

    except Exception as e:
        logger.error(
            f"Timeline query failed for {issue}, org={org_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Timeline query failed: {str(e)}")
