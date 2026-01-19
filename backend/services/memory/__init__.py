"""
NAVI Memory Services Package.

Provides comprehensive memory and intelligence services for personalized,
context-aware AI responses.

Services:
- EmbeddingService: Vector embedding generation for semantic search
- UserMemoryService: User preferences, activity tracking, pattern detection
- OrgMemoryService: Organization knowledge, standards, shared context
- ConversationMemoryService: Conversation history and summarization
- CodebaseMemoryService: Code indexing and symbol extraction
- SemanticSearchService: Cross-memory semantic search
"""

# Lazy imports to avoid circular dependencies
__all__ = [
    "EmbeddingService",
    "get_embedding_service",
    "UserMemoryService",
    "get_user_memory_service",
    "OrgMemoryService",
    "get_org_memory_service",
    "ConversationMemoryService",
    "get_conversation_memory_service",
    "CodebaseMemoryService",
    "get_codebase_memory_service",
    "SemanticSearchService",
    "get_semantic_search_service",
]


def __getattr__(name):
    """Lazy import to avoid circular dependencies."""
    if name in ("EmbeddingService", "get_embedding_service"):
        from backend.services.memory.embedding_service import EmbeddingService, get_embedding_service
        return EmbeddingService if name == "EmbeddingService" else get_embedding_service
    elif name in ("UserMemoryService", "get_user_memory_service"):
        from backend.services.memory.user_memory import UserMemoryService, get_user_memory_service
        return UserMemoryService if name == "UserMemoryService" else get_user_memory_service
    elif name in ("OrgMemoryService", "get_org_memory_service"):
        from backend.services.memory.org_memory import OrgMemoryService, get_org_memory_service
        return OrgMemoryService if name == "OrgMemoryService" else get_org_memory_service
    elif name in ("ConversationMemoryService", "get_conversation_memory_service"):
        from backend.services.memory.conversation_memory import ConversationMemoryService, get_conversation_memory_service
        return ConversationMemoryService if name == "ConversationMemoryService" else get_conversation_memory_service
    elif name in ("CodebaseMemoryService", "get_codebase_memory_service"):
        from backend.services.memory.codebase_memory import CodebaseMemoryService, get_codebase_memory_service
        return CodebaseMemoryService if name == "CodebaseMemoryService" else get_codebase_memory_service
    elif name in ("SemanticSearchService", "get_semantic_search_service"):
        from backend.services.memory.semantic_search import SemanticSearchService, get_semantic_search_service
        return SemanticSearchService if name == "SemanticSearchService" else get_semantic_search_service
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
