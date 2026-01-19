"""
Semantic Search Service for NAVI Memory System.

Provides unified semantic search across all memory types:
- Conversations and messages
- Organization knowledge
- Code symbols
- User patterns

Features:
- Cross-memory search with relevance ranking
- Contextual filtering (user, org, workspace)
- Result aggregation and deduplication
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from backend.services.memory.embedding_service import get_embedding_service
from backend.services.memory.conversation_memory import ConversationMemoryService
from backend.services.memory.org_memory import OrgMemoryService
from backend.services.memory.codebase_memory import CodebaseMemoryService

logger = logging.getLogger(__name__)


class SearchScope(str, Enum):
    """Search scope options."""
    ALL = "all"
    CONVERSATIONS = "conversations"
    KNOWLEDGE = "knowledge"
    CODE = "code"


@dataclass
class SearchResult:
    """Unified search result."""
    id: str
    source: str  # conversations, knowledge, code
    title: str
    content: str
    similarity: float
    metadata: Dict[str, Any]


class SemanticSearchService:
    """
    Unified semantic search across all NAVI memory.

    Aggregates search results from conversations, organization knowledge,
    and codebase indexes with relevance ranking.
    """

    def __init__(self, db: Session):
        """
        Initialize the semantic search service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.embedding_service = get_embedding_service()
        self.conversation_service = ConversationMemoryService(db)
        self.org_service = OrgMemoryService(db)
        self.codebase_service = CodebaseMemoryService(db)

    async def search(
        self,
        query: str,
        user_id: Optional[int] = None,
        org_id: Optional[int] = None,
        codebase_id: Optional[UUID] = None,
        scope: SearchScope = SearchScope.ALL,
        limit: int = 20,
        min_similarity: float = 0.5,
    ) -> List[SearchResult]:
        """
        Search across all memory with contextual filtering.

        Args:
            query: Search query
            user_id: Optional user ID for filtering
            org_id: Optional organization ID for filtering
            codebase_id: Optional codebase ID for code search
            scope: Search scope (all, conversations, knowledge, code)
            limit: Maximum results
            min_similarity: Minimum similarity threshold

        Returns:
            List of SearchResult objects sorted by relevance
        """
        results: List[SearchResult] = []

        # Search conversations
        if scope in (SearchScope.ALL, SearchScope.CONVERSATIONS) and user_id:
            conversation_results = await self._search_conversations(
                query, user_id, limit, min_similarity
            )
            results.extend(conversation_results)

        # Search organization knowledge
        if scope in (SearchScope.ALL, SearchScope.KNOWLEDGE) and org_id:
            knowledge_results = await self._search_knowledge(
                query, org_id, limit, min_similarity
            )
            results.extend(knowledge_results)

        # Search code symbols
        if scope in (SearchScope.ALL, SearchScope.CODE) and codebase_id:
            code_results = await self._search_code(
                query, codebase_id, limit, min_similarity
            )
            results.extend(code_results)

        # Sort all results by similarity
        results.sort(key=lambda x: x.similarity, reverse=True)

        # Apply limit
        return results[:limit]

    async def _search_conversations(
        self,
        query: str,
        user_id: int,
        limit: int,
        min_similarity: float,
    ) -> List[SearchResult]:
        """Search in user's conversations."""
        results = []

        try:
            conv_results = await self.conversation_service.search_conversations(
                user_id=user_id,
                query=query,
                limit=limit,
                min_similarity=min_similarity,
            )

            for r in conv_results:
                results.append(SearchResult(
                    id=r["conversation_id"],
                    source="conversations",
                    title=r["title"] or "Untitled Conversation",
                    content=r["matching_message"]["content"] if r.get("matching_message") else "",
                    similarity=r["similarity"],
                    metadata={
                        "conversation_id": r["conversation_id"],
                        "matching_message": r.get("matching_message"),
                        "updated_at": r.get("updated_at"),
                    },
                ))
        except Exception as e:
            logger.error(f"Error searching conversations: {e}")

        return results

    async def _search_knowledge(
        self,
        query: str,
        org_id: int,
        limit: int,
        min_similarity: float,
    ) -> List[SearchResult]:
        """Search in organization knowledge base."""
        results = []

        try:
            knowledge_results = await self.org_service.search_knowledge(
                org_id=org_id,
                query=query,
                limit=limit,
                min_similarity=min_similarity,
            )

            for r in knowledge_results:
                results.append(SearchResult(
                    id=r["id"],
                    source="knowledge",
                    title=r["title"],
                    content=r["content"][:500] + "..." if len(r["content"]) > 500 else r["content"],
                    similarity=r["similarity"],
                    metadata={
                        "knowledge_type": r["knowledge_type"],
                        "tags": r.get("tags", []),
                        "confidence": r.get("confidence", 1.0),
                    },
                ))
        except Exception as e:
            logger.error(f"Error searching knowledge: {e}")

        return results

    async def _search_code(
        self,
        query: str,
        codebase_id: UUID,
        limit: int,
        min_similarity: float,
    ) -> List[SearchResult]:
        """Search in codebase symbols."""
        results = []

        try:
            code_results = await self.codebase_service.search_symbols(
                codebase_id=codebase_id,
                query=query,
                limit=limit,
                min_similarity=min_similarity,
            )

            for r in code_results:
                content_parts = []
                if r.get("signature"):
                    content_parts.append(r["signature"])
                if r.get("documentation"):
                    content_parts.append(r["documentation"][:200])

                results.append(SearchResult(
                    id=r["id"],
                    source="code",
                    title=f"{r['type']}: {r['name']}",
                    content="\n".join(content_parts) if content_parts else r["qualified_name"] or r["name"],
                    similarity=r["similarity"],
                    metadata={
                        "symbol_type": r["type"],
                        "file_path": r["file_path"],
                        "line_start": r["line_start"],
                        "line_end": r["line_end"],
                        "qualified_name": r.get("qualified_name"),
                    },
                ))
        except Exception as e:
            logger.error(f"Error searching code: {e}")

        return results

    async def find_related(
        self,
        content: str,
        user_id: Optional[int] = None,
        org_id: Optional[int] = None,
        codebase_id: Optional[UUID] = None,
        limit: int = 5,
    ) -> Dict[str, List[SearchResult]]:
        """
        Find related content across all memory types.

        Args:
            content: Content to find relations for
            user_id: Optional user ID
            org_id: Optional organization ID
            codebase_id: Optional codebase ID
            limit: Maximum results per category

        Returns:
            Dictionary with results grouped by source
        """
        results = {
            "conversations": [],
            "knowledge": [],
            "code": [],
        }

        # Search each category separately
        if user_id:
            results["conversations"] = await self._search_conversations(
                content, user_id, limit, min_similarity=0.6
            )

        if org_id:
            results["knowledge"] = await self._search_knowledge(
                content, org_id, limit, min_similarity=0.6
            )

        if codebase_id:
            results["code"] = await self._search_code(
                content, codebase_id, limit, min_similarity=0.6
            )

        return results

    async def get_context_for_query(
        self,
        query: str,
        user_id: int,
        org_id: Optional[int] = None,
        codebase_id: Optional[UUID] = None,
        max_context_items: int = 10,
    ) -> Dict[str, Any]:
        """
        Get relevant context for a user query.

        Searches across all memory types and builds a context dictionary
        suitable for including in LLM prompts.

        Args:
            query: User query
            user_id: User ID
            org_id: Optional organization ID
            codebase_id: Optional codebase ID for code context
            max_context_items: Maximum context items to include

        Returns:
            Dictionary with relevant context
        """
        context = {
            "relevant_conversations": [],
            "relevant_knowledge": [],
            "relevant_code": [],
            "has_context": False,
        }

        # Search for relevant items
        results = await self.search(
            query=query,
            user_id=user_id,
            org_id=org_id,
            codebase_id=codebase_id,
            limit=max_context_items,
            min_similarity=0.6,
        )

        # Group results by source
        for result in results:
            if result.source == "conversations":
                context["relevant_conversations"].append({
                    "title": result.title,
                    "excerpt": result.content[:300],
                    "similarity": round(result.similarity, 3),
                })
            elif result.source == "knowledge":
                context["relevant_knowledge"].append({
                    "title": result.title,
                    "content": result.content,
                    "type": result.metadata.get("knowledge_type"),
                    "similarity": round(result.similarity, 3),
                })
            elif result.source == "code":
                context["relevant_code"].append({
                    "symbol": result.title,
                    "file": result.metadata.get("file_path"),
                    "line": result.metadata.get("line_start"),
                    "content": result.content,
                    "similarity": round(result.similarity, 3),
                })

        context["has_context"] = bool(
            context["relevant_conversations"]
            or context["relevant_knowledge"]
            or context["relevant_code"]
        )

        return context

    def format_context_for_prompt(
        self,
        context: Dict[str, Any],
        max_tokens: int = 2000,
    ) -> str:
        """
        Format search context for inclusion in LLM prompts.

        Args:
            context: Context dictionary from get_context_for_query
            max_tokens: Approximate maximum tokens for context

        Returns:
            Formatted context string
        """
        if not context.get("has_context"):
            return ""

        parts = []

        # Add relevant knowledge
        if context.get("relevant_knowledge"):
            parts.append("## Relevant Organization Knowledge\n")
            for item in context["relevant_knowledge"][:3]:
                parts.append(f"**{item['title']}** ({item.get('type', 'general')})")
                parts.append(item["content"][:500])
                parts.append("")

        # Add relevant code
        if context.get("relevant_code"):
            parts.append("## Relevant Code\n")
            for item in context["relevant_code"][:3]:
                parts.append(f"**{item['symbol']}** in `{item['file']}:{item.get('line', 0)}`")
                if item.get("content"):
                    parts.append(f"```\n{item['content'][:300]}\n```")
                parts.append("")

        # Add relevant conversations
        if context.get("relevant_conversations"):
            parts.append("## Related Past Conversations\n")
            for item in context["relevant_conversations"][:2]:
                parts.append(f"**{item['title']}**")
                parts.append(f"_{item['excerpt']}..._")
                parts.append("")

        result = "\n".join(parts)

        # Rough token estimation (4 chars per token)
        estimated_tokens = len(result) // 4
        if estimated_tokens > max_tokens:
            # Truncate to fit
            max_chars = max_tokens * 4
            result = result[:max_chars] + "\n...(truncated)"

        return result


def get_semantic_search_service(db: Session) -> SemanticSearchService:
    """Factory function to create SemanticSearchService."""
    return SemanticSearchService(db)
