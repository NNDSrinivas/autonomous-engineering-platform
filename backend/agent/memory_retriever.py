"""
Memory Retriever - Fetch User & Org Memory

Retrieves relevant memories from navi_memory table:
- User profile (coding style, preferences)
- Workspace memory (project structure, patterns)
- Task memory (Jira issues)
- Interaction memory (past conversations)

Uses semantic search to find most relevant memories for current query.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


async def retrieve_memories(
    user_id: str,
    query: str,
    db=None,
    limit: int = 5
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
        
        # Search across all categories
        memories = search_memory(
            db=db,
            user_id=user_id,
            query=query,
            categories=["profile", "workspace", "task", "interaction"],
            limit=limit,
            min_importance=3  # Only retrieve important memories
        )
        
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


def _empty_memory_result() -> Dict[str, Any]:
    """Return empty memory structure."""
    return {
        "user_profile": [],
        "tasks": [],
        "interactions": [],
        "workspace": []
    }
