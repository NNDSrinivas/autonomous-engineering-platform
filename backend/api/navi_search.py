"""NAVI Unified RAG Search API

This endpoint provides semantic search across all NAVI memory categories:
- Jira tasks (category=task)
- Confluence documentation (category=workspace)
- User preferences (category=profile)
- Chat history (category=interaction)

Enables NAVI to answer questions like:
- "What's the dev environment URL?"
- "Any Confluence pages for LAB-158?"
- "Where did we discuss barcode overrides?"
"""

from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import structlog

from backend.database.session import get_db
from backend.services.navi_memory_service import search_memory

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/navi", tags=["navi-search"])


# ============================================================================
# Request/Response Models
# ============================================================================


class SearchRequest(BaseModel):
    """Request for semantic search across NAVI memory"""

    query: str = Field(..., description="Natural language search query")
    user_id: str = Field(..., description="User identifier")
    categories: List[str] = Field(
        default=["profile", "workspace", "task", "interaction"],
        description="Memory categories to search",
    )
    limit: int = Field(
        default=8, ge=1, le=50, description="Maximum number of results to return"
    )
    min_importance: int = Field(
        default=1, ge=1, le=5, description="Minimum importance score to include"
    )


class SearchResultItem(BaseModel):
    """A single search result with metadata"""

    id: int = Field(..., description="Memory ID")
    category: str = Field(..., description="Memory category")
    scope: Optional[str] = Field(None, description="Scope identifier (e.g., task ID)")
    title: Optional[str] = Field(None, description="Memory title")
    content: str = Field(..., description="Memory content")
    similarity: float = Field(..., description="Cosine similarity score (0-1)")
    importance: int = Field(..., description="Importance score (1-5)")
    meta: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    created_at: Optional[str] = Field(None, description="Creation timestamp")


class SearchResponse(BaseModel):
    """Response containing search results"""

    query: str = Field(..., description="Original search query")
    results: List[SearchResultItem] = Field(..., description="Ranked search results")
    total: int = Field(..., description="Number of results returned")
    user_id: str = Field(..., description="User identifier")


class SearchStatsResponse(BaseModel):
    """Statistics about NAVI memory for a user"""

    user_id: str
    total_memories: int
    by_category: Dict[str, int]


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/search", response_model=SearchResponse)
async def unified_search(req: SearchRequest, db: Session = Depends(get_db)):
    """
    Unified semantic search across all NAVI memory.

    This is NAVI's RAG (Retrieval Augmented Generation) engine.
    It searches across Jira tasks, Confluence docs, user preferences,
    and chat history to provide context-aware responses.

    **Example Request:**
    ```json
    {
        "query": "What's the dev environment URL?",
        "user_id": "srinivas@example.com",
        "categories": ["workspace", "task"],
        "limit": 5
    }
    ```

    **What it does:**
    1. Generates embedding for the query
    2. Searches navi_memory using pgvector cosine similarity
    3. Ranks results by similarity + importance
    4. Returns top N results with citations

    **Use cases:**
    - "What's the dev environment URL?" → finds Confluence pages
    - "Any docs for LAB-158?" → finds Jira + Confluence
    - "Where did we discuss this?" → finds meeting notes
    - "What's my current task?" → finds assigned Jira issues
    """
    if not req.user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")

    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query is required")

    logger.info(
        "NAVI search requested",
        user_id=req.user_id,
        query=req.query,
        categories=req.categories,
        limit=req.limit,
    )

    try:
        # Perform semantic search
        memories = await search_memory(
            db=db,
            user_id=req.user_id,
            query=req.query,
            categories=req.categories,
            limit=req.limit,
            min_importance=req.min_importance,
        )

        # Convert to API format
        results = [
            SearchResultItem(
                id=mem["id"],
                category=mem["category"],
                scope=mem.get("scope"),
                title=mem.get("title"),
                content=mem["content"],
                similarity=mem["similarity"],
                importance=mem["importance"],
                meta=mem.get("meta"),
                created_at=mem.get("created_at"),
            )
            for mem in memories
        ]

        logger.info(
            "NAVI search complete",
            user_id=req.user_id,
            query=req.query,
            results_count=len(results),
        )

        return SearchResponse(
            query=req.query,
            results=results,
            total=len(results),
            user_id=req.user_id,
        )

    except Exception as e:
        logger.error("NAVI search failed", error=str(e), user_id=req.user_id)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/search/stats", response_model=SearchStatsResponse)
async def get_search_stats(user_id: str, db: Session = Depends(get_db)):
    """
    Get statistics about NAVI memory for a user.

    Returns total memory count and breakdown by category.
    Useful for debugging and understanding memory coverage.
    """
    if not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id is required")

    try:
        from sqlalchemy import text

        # Get total count
        total_result = db.execute(
            text("SELECT COUNT(*) FROM navi_memory WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
        total = total_result.scalar() or 0

        # Get count by category
        category_result = db.execute(
            text(
                """
                SELECT category, COUNT(*) as count
                FROM navi_memory
                WHERE user_id = :user_id
                GROUP BY category
            """
            ),
            {"user_id": user_id},
        )

        by_category = {row[0]: row[1] for row in category_result}

        logger.info(
            "Retrieved memory stats",
            user_id=user_id,
            total=total,
            by_category=by_category,
        )

        return SearchStatsResponse(
            user_id=user_id, total_memories=total, by_category=by_category
        )

    except Exception as e:
        logger.error("Failed to get memory stats", error=str(e), user_id=user_id)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/search/health")
async def search_health():
    """
    Check NAVI search service health.
    """
    return {
        "status": "ok",
        "service": "navi-search",
        "message": "Unified RAG search engine is running",
        "endpoints": ["/search", "/search/stats", "/search/health"],
    }
