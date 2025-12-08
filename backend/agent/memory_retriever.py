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


class OrgSnippet:
    """
    Standard format for organizational memory snippets across all sources.

    This creates a unified interface so NAVI treats Jira, Slack, meetings,
    wiki, code, builds, and conversations uniformly.
    """

    def __init__(
        self,
        snippet_id: str,
        source: str,  # "jira", "slack", "meeting", "wiki", "code", "build", "navi"
        title: str,
        content: str,
        metadata: Dict[str, Any],
        url: Optional[str] = None,
        timestamp: Optional[str] = None,
        relevance: float = 0.0,
    ):
        self.snippet_id = snippet_id
        self.source = source
        self.title = title
        self.content = content
        self.metadata = metadata
        self.url = url
        self.timestamp = timestamp
        self.relevance = relevance

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "snippet_id": self.snippet_id,
            "source": self.source,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
            "url": self.url,
            "timestamp": self.timestamp,
            "relevance": self.relevance,
        }


class MemoryContext:
    """
    Complete memory context combining traditional NAVI memories + org snippets.

    This is what gets passed to the agent for decision-making.
    """

    def __init__(
        self,
        user_profile: Optional[List[Dict[str, Any]]] = None,
        tasks: Optional[List[Dict[str, Any]]] = None,
        interactions: Optional[List[Dict[str, Any]]] = None,
        workspace: Optional[List[Dict[str, Any]]] = None,
        org_snippets: Optional[List[OrgSnippet]] = None,
    ):
        self.user_profile = user_profile or []
        self.tasks = tasks or []
        self.interactions = interactions or []
        self.workspace = workspace or []
        self.org_snippets = org_snippets or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for agent consumption."""
        return {
            "user_profile": self.user_profile,
            "tasks": self.tasks,
            "interactions": self.interactions,
            "workspace": self.workspace,
            "org_snippets": [snippet.to_dict() for snippet in self.org_snippets],
        }

    def get_total_count(self) -> int:
        """Get total number of memory items."""
        return (
            len(self.user_profile)
            + len(self.tasks)
            + len(self.interactions)
            + len(self.workspace)
            + len(self.org_snippets)
        )


async def retrieve_memories(
    user_id: str, query: str, db=None, limit: int = 5, min_similarity: float = 0.7
) -> MemoryContext:
    """
    Retrieve relevant memories for the current query.

    Returns both traditional NAVI memories AND org snippets from unified sources.

    Args:
        user_id: User identifier
        query: Current user message
        db: Database session
        limit: Max memories to retrieve per category

    Returns:
        MemoryContext with user_profile, tasks, interactions, workspace, org_snippets
    """

    if not db:
        logger.warning("[MEMORY] No DB session, returning empty memories")
        return _empty_memory_context()

    try:
        # Get traditional NAVI memories
        from backend.services.navi_memory_service import search_memory

        logger.info(
            f"[MEMORY] Searching memories for user={user_id}, query='{query[:50]}...'"
        )

        # Search across all categories with semantic vector similarity
        memories = await search_memory(
            db=db,
            user_id=user_id,
            query=query,
            categories=["profile", "workspace", "task", "interaction"],
            limit=limit * 2,  # Retrieve more, then rank
            min_importance=3,  # Only retrieve important memories
        )

        # Rank by relevance and truncate to limit
        if memories:
            memories = await _rank_by_relevance(memories, query, limit)

        # Group traditional memories by category
        user_profile = []
        tasks = []
        interactions = []
        workspace = []

        for mem in memories:
            category = mem.get("category", "interaction")
            if category == "profile":
                user_profile.append(mem)
            elif category == "task":
                tasks.append(mem)
            elif category == "workspace":
                workspace.append(mem)
            else:
                interactions.append(mem)

        # Get unified org snippets from all sources
        org_snippets = []
        try:
            unified_memories = await retrieve_unified_memories_raw(user_id, query, db)
            # Convert unified memories to OrgSnippet format
            org_snippets = _convert_unified_to_snippets(unified_memories)
        except Exception as e:
            logger.warning(f"[MEMORY] Could not fetch unified memories: {e}")

        # Create complete memory context
        context = MemoryContext(
            user_profile=user_profile,
            tasks=tasks,
            interactions=interactions,
            workspace=workspace,
            org_snippets=org_snippets,
        )

        logger.info(
            f"[MEMORY] Found {context.get_total_count()} total memories ({len(memories)} traditional + {len(org_snippets)} org snippets)"
        )
        return context

    except Exception as e:
        logger.error(f"[MEMORY] Error retrieving memories: {e}", exc_info=True)
        return _empty_memory_context()


async def _rank_by_relevance(
    memories: List[Dict[str, Any]], query: str, limit: int
) -> List[Dict[str, Any]]:
    """
    Rank memories by relevance to query.

    For now, uses the similarity score from pgvector.
    In future, can use LLM-based reranking.
    """
    # Already ranked by pgvector cosine similarity
    # Just truncate to limit
    return memories[:limit]


def _empty_memory_context() -> MemoryContext:
    """Return empty memory context."""
    return MemoryContext()


def _convert_unified_to_snippets(unified_memories: Dict[str, Any]) -> List[OrgSnippet]:
    """
    Convert unified memory results to OrgSnippet format.

    Takes the output from unified_memory_retriever and converts each
    source's results into standardized OrgSnippet objects.
    """
    snippets = []

    # Process each source in the unified memories
    source_mapping = {
        "jira": "jira_memories",
        "slack": "slack_memories",
        "meetings": "meeting_memories",
        "wiki": "wiki_memories",
        "code": "code_memories",
        "builds": "build_memories",
        "navi": "navi_memories",
    }

    for source, key in source_mapping.items():
        items = unified_memories.get(key, [])

        for i, item in enumerate(items):
            snippet = OrgSnippet(
                snippet_id=f"{source}_{i}_{item.get('id', 'unknown')}",
                source=source,
                title=item.get("title")
                or item.get("summary")
                or f"{source.title()} Item",
                content=item.get("content")
                or item.get("text")
                or item.get("description")
                or "",
                metadata=item.get("metadata", {}),
                url=item.get("url") or item.get("permalink"),
                timestamp=item.get("timestamp")
                or item.get("ts")
                or item.get("created_at"),
                relevance=item.get("relevance", 0.0),
            )
            snippets.append(snippet)

    return snippets


async def retrieve_recent_memories(
    user_id: str, db=None, category: Optional[str] = None, limit: int = 5
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
            db=db, user_id=user_id, category=category, limit=limit
        )

        logger.info(f"[MEMORY] Retrieved {len(memories)} recent memories")
        return memories

    except Exception as e:
        logger.error(f"[MEMORY] Error retrieving recent memories: {e}", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# UNIFIED MEMORY RETRIEVAL (B1 + B2 + B3)
# ---------------------------------------------------------------------------


async def retrieve_unified_memories_raw(
    user_id: str,
    query: str,
    db=None,
) -> Dict[str, Any]:
    """
    Enhanced memory retrieval that pulls from multiple sources:
    - Jira tasks/issues
    - Slack/Teams messages
    - Meeting summaries
    - Wiki/Confluence docs
    - Code search results
    - Build/CI status
    - Prior NAVI conversations

    Falls back gracefully if sources aren't available.

    This returns raw unified memories, not MemoryContext.
    """
    try:
        from backend.agent.unified_memory_retriever import retrieve_unified_memories

        return await retrieve_unified_memories(user_id, query, db)
    except ImportError:
        logger.warning(
            "[MEMORY] Unified memory retriever not available, using fallback"
        )
        # Return empty unified memories structure
        return {
            "jira_memories": [],
            "slack_memories": [],
            "meeting_memories": [],
            "wiki_memories": [],
            "code_memories": [],
            "build_memories": [],
            "navi_memories": [],
        }
