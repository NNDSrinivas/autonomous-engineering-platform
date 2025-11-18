"""
Memory Retriever - Fetch User & Org Memory (STEP C Enhanced)

Retrieves relevant memories from navi_memory table with semantic vector search:
- User profile (coding style, preferences)
- Workspace memory (project structure, patterns)
- Task memory (Jira issues)
- Interaction memory (past conversations)

Uses pgvector semantic similarity to find most relevant memories.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


async def retrieve_memories(
    user_id: str,
    query: str,
    db=None,
    limit: int = 5,
    min_similarity: float = 0.7
) -> Dict[str, Any]:
    """
    Retrieve relevant memories for the current query.
    
    Args:
        user_id: User identifier
        query: Current user message
        db: Database session
        limit: Max memories to retrieve
    
    Returns:
        {
            "user_profile": [...],     # User preferences, coding style
            "tasks": [...],            # Related Jira tasks
            "interactions": [...],     # Past conversations
            "workspace": [...]         # Project structure, patterns
        }
    """
    
    if not db:
        logger.warning("[MEMORY] No DB session, returning empty memories")
        return _empty_memory_result()
    
    try:
        from backend.services.navi_memory_service import search_memory
        
        logger.info(f"[MEMORY] Searching memories for user={user_id}, query='{query[:50]}...'")
        
        # Search across all categories with semantic vector similarity
        memories = await search_memory(
            db=db,
            user_id=user_id,
            query=query,
            categories=["profile", "workspace", "task", "interaction"],
            limit=limit * 2,  # Retrieve more, then rank
            min_importance=3  # Only retrieve important memories
        )
        
        # Rank by relevance and truncate to limit
        if memories:
            memories = await _rank_by_relevance(memories, query, limit)
        
        # Group by category
        result = {
            "user_profile": [],
            "tasks": [],
            "interactions": [],
            "workspace": []
        }
        
        for mem in memories:
            category = mem.get("category", "interaction")
            if category == "profile":
                result["user_profile"].append(mem)
            elif category == "task":
                result["tasks"].append(mem)
            elif category == "workspace":
                result["workspace"].append(mem)
            else:
                result["interactions"].append(mem)
        
        logger.info(f"[MEMORY] Found {len(memories)} relevant memories")
        return result
    
    except Exception as e:
        logger.error(f"[MEMORY] Error retrieving memories: {e}", exc_info=True)
        return _empty_memory_result()


async def _rank_by_relevance(
    memories: List[Dict[str, Any]], 
    query: str, 
    limit: int
) -> List[Dict[str, Any]]:
    """
    Rank memories by relevance to query.
    
    For now, uses the similarity score from pgvector.
    In future, can use LLM-based reranking.
    """
    # Already ranked by pgvector cosine similarity
    # Just truncate to limit
    return memories[:limit]


def _empty_memory_result() -> Dict[str, Any]:
    """Return empty memory structure."""
    return {
        "user_profile": [],
        "tasks": [],
        "interactions": [],
        "workspace": []
    }


async def retrieve_recent_memories(
    user_id: str,
    db=None,
    category: Optional[str] = None,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Retrieve recent memories by time (not semantic search).
    
    Useful for: "What was I working on?" or "What did we discuss yesterday?"
    """
    
    if not db:
        logger.warning("[MEMORY] No DB session, returning empty")
        return []
    
    try:
        from backend.services.navi_memory_service import get_recent_memories
        
        memories = await get_recent_memories(
            db=db,
            user_id=user_id,
            category=category,
            limit=limit
        )
        
        logger.info(f"[MEMORY] Retrieved {len(memories)} recent memories")
        return memories
    
    except Exception as e:
        logger.error(f"[MEMORY] Error retrieving recent memories: {e}", exc_info=True)
        return []
