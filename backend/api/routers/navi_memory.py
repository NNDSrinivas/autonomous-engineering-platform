"""
NAVI Memory API Router.

Provides REST endpoints for managing user memory, organization knowledge,
conversations, codebase indexes, and semantic search.

This is the comprehensive memory system for personalized AI responses.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.auth.deps import get_current_user
from backend.core.auth.models import User
from backend.database.session import get_db
from backend.services.memory.user_memory import get_user_memory_service
from backend.services.memory.org_memory import get_org_memory_service
from backend.services.memory.conversation_memory import get_conversation_memory_service
from backend.services.memory.codebase_memory import get_codebase_memory_service
from backend.services.memory.semantic_search import (
    get_semantic_search_service,
    SearchScope,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/navi-memory", tags=["navi-memory"])


# =============================================================================
# Request/Response Models
# =============================================================================


class UserPreferencesUpdate(BaseModel):
    """Request model for updating user preferences."""

    preferred_language: Optional[str] = None
    preferred_framework: Optional[str] = None
    code_style: Optional[Dict[str, Any]] = None
    response_verbosity: Optional[str] = None
    explanation_level: Optional[str] = None
    theme: Optional[str] = None


class UserPreferencesResponse(BaseModel):
    """Response model for user preferences."""

    user_id: int
    preferred_language: Optional[str]
    preferred_framework: Optional[str]
    code_style: Dict[str, Any]
    response_verbosity: str
    explanation_level: str
    theme: str
    inferred_preferences: Dict[str, Any]


class FeedbackRequest(BaseModel):
    """Request model for submitting feedback."""

    message_id: UUID
    conversation_id: UUID
    feedback_type: str = Field(..., pattern="^(positive|negative|correction)$")
    feedback_data: Optional[Dict[str, Any]] = None
    query_text: Optional[str] = None
    response_text: Optional[str] = None


class KnowledgeCreate(BaseModel):
    """Request model for adding organization knowledge."""

    knowledge_type: str
    title: str
    content: str
    source: Optional[str] = None
    tags: Optional[List[str]] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class KnowledgeResponse(BaseModel):
    """Response model for organization knowledge."""

    id: str
    knowledge_type: str
    title: str
    content: str
    source: Optional[str]
    tags: List[str]
    confidence: float


class StandardCreate(BaseModel):
    """Request model for adding coding standard."""

    standard_type: str
    standard_name: str
    rules: Dict[str, Any]
    description: Optional[str] = None
    good_examples: Optional[List[Dict[str, Any]]] = None
    bad_examples: Optional[List[Dict[str, Any]]] = None
    enforced: bool = False
    severity: str = "warning"


class ConversationCreate(BaseModel):
    """Request model for creating a conversation."""

    title: Optional[str] = None
    workspace_path: Optional[str] = None
    initial_context: Optional[Dict[str, Any]] = None


class ConversationUpdate(BaseModel):
    """Request model for updating a conversation."""

    title: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(active|archived|deleted)$")
    workspace_path: Optional[str] = None
    initial_context: Optional[Dict[str, Any]] = None
    is_pinned: Optional[bool] = None
    is_starred: Optional[bool] = None


class MessageCreate(BaseModel):
    """Request model for adding a message."""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    metadata: Optional[Dict[str, Any]] = None
    tokens_used: Optional[int] = None


class CodebaseIndexCreate(BaseModel):
    """Request model for creating codebase index."""

    workspace_path: str
    workspace_name: Optional[str] = None
    index_config: Optional[Dict[str, Any]] = None


class SearchRequest(BaseModel):
    """Request model for semantic search."""

    query: str
    scope: str = "all"
    codebase_id: Optional[UUID] = None
    limit: int = Field(default=20, le=100)
    min_similarity: float = Field(default=0.5, ge=0.0, le=1.0)


class SearchResultResponse(BaseModel):
    """Response model for search results."""

    id: str
    source: str
    title: str
    content: str
    similarity: float
    metadata: Dict[str, Any]


# =============================================================================
# User Preferences Endpoints
# =============================================================================


@router.get("/preferences")
async def get_preferences(
    user_id: int = Query(..., description="User ID"),
    db: Session = Depends(get_db),
) -> UserPreferencesResponse:
    """Get user preferences."""
    service = get_user_memory_service(db)
    prefs = service.get_or_create_preferences(user_id)

    return UserPreferencesResponse(
        user_id=prefs.user_id,
        preferred_language=prefs.preferred_language,
        preferred_framework=prefs.preferred_framework,
        code_style=prefs.code_style or {},
        response_verbosity=prefs.response_verbosity,
        explanation_level=prefs.explanation_level,
        theme=prefs.theme,
        inferred_preferences=prefs.inferred_preferences or {},
    )


@router.put("/preferences")
async def update_preferences(
    user_id: int,
    update: UserPreferencesUpdate,
    db: Session = Depends(get_db),
) -> UserPreferencesResponse:
    """Update user preferences."""
    service = get_user_memory_service(db)

    # Filter out None values
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    prefs = service.update_preferences(user_id, **update_data)

    return UserPreferencesResponse(
        user_id=prefs.user_id,
        preferred_language=prefs.preferred_language,
        preferred_framework=prefs.preferred_framework,
        code_style=prefs.code_style or {},
        response_verbosity=prefs.response_verbosity,
        explanation_level=prefs.explanation_level,
        theme=prefs.theme,
        inferred_preferences=prefs.inferred_preferences or {},
    )


@router.get("/activity")
async def get_activity(
    user_id: int,
    activity_type: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get user activity history."""
    service = get_user_memory_service(db)
    activities = service.get_recent_activities(
        user_id=user_id,
        activity_type=activity_type,
        limit=limit,
    )

    return [
        {
            "id": str(a.id),
            "activity_type": a.activity_type,
            "activity_data": a.activity_data,
            "workspace_path": a.workspace_path,
            "file_path": a.file_path,
            "language": a.language,
            "created_at": a.created_at.isoformat(),
        }
        for a in activities
    ]


@router.post("/feedback")
async def submit_feedback(
    user_id: int,
    feedback: FeedbackRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Submit feedback on a NAVI response."""
    service = get_user_memory_service(db)

    result = service.record_feedback(
        user_id=user_id,
        message_id=feedback.message_id,
        conversation_id=feedback.conversation_id,
        feedback_type=feedback.feedback_type,
        feedback_data=feedback.feedback_data,
        query_text=feedback.query_text,
        response_text=feedback.response_text,
    )

    return {
        "id": str(result.id),
        "feedback_type": result.feedback_type,
        "created_at": result.created_at.isoformat(),
        "message": "Feedback recorded successfully",
    }


@router.get("/user-context")
async def get_user_context(
    user_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get comprehensive user context for NAVI responses."""
    service = get_user_memory_service(db)
    return service.build_user_context(user_id)


# =============================================================================
# Organization Knowledge Endpoints
# =============================================================================


@router.get("/org/knowledge")
async def get_org_knowledge(
    org_id: int,
    knowledge_type: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> List[KnowledgeResponse]:
    """Get organization knowledge base entries."""
    service = get_org_memory_service(db)

    tag_list = tags.split(",") if tags else None
    entries = service.get_knowledge(
        org_id=org_id,
        knowledge_type=knowledge_type,
        tags=tag_list,
        limit=limit,
    )

    return [
        KnowledgeResponse(
            id=str(e.id),
            knowledge_type=e.knowledge_type,
            title=e.title,
            content=e.content,
            source=e.source,
            tags=e.tags or [],
            confidence=e.confidence,
        )
        for e in entries
    ]


@router.post("/org/knowledge")
async def add_org_knowledge(
    org_id: int,
    knowledge: KnowledgeCreate,
    created_by: Optional[int] = None,
    db: Session = Depends(get_db),
) -> KnowledgeResponse:
    """Add knowledge to organization knowledge base."""
    service = get_org_memory_service(db)

    entry = await service.add_knowledge(
        org_id=org_id,
        knowledge_type=knowledge.knowledge_type,
        title=knowledge.title,
        content=knowledge.content,
        source=knowledge.source,
        tags=knowledge.tags,
        confidence=knowledge.confidence,
        created_by=created_by,
    )

    return KnowledgeResponse(
        id=str(entry.id),
        knowledge_type=entry.knowledge_type,
        title=entry.title,
        content=entry.content,
        source=entry.source,
        tags=entry.tags or [],
        confidence=entry.confidence,
    )


@router.get("/org/standards")
async def get_org_standards(
    org_id: int,
    standard_type: Optional[str] = None,
    enforced_only: bool = False,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get organization coding standards."""
    service = get_org_memory_service(db)

    standards = service.get_standards(
        org_id=org_id,
        standard_type=standard_type,
        enforced_only=enforced_only,
    )

    return [
        {
            "id": str(s.id),
            "standard_type": s.standard_type,
            "standard_name": s.standard_name,
            "description": s.description,
            "rules": s.rules,
            "enforced": s.enforced,
            "severity": s.severity,
            "good_examples": s.good_examples or [],
            "bad_examples": s.bad_examples or [],
        }
        for s in standards
    ]


@router.post("/org/standards")
async def add_org_standard(
    org_id: int,
    standard: StandardCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a coding standard to the organization."""
    service = get_org_memory_service(db)

    result = service.add_standard(
        org_id=org_id,
        standard_type=standard.standard_type,
        standard_name=standard.standard_name,
        rules=standard.rules,
        description=standard.description,
        good_examples=standard.good_examples,
        bad_examples=standard.bad_examples,
        enforced=standard.enforced,
        severity=standard.severity,
    )

    return {
        "id": str(result.id),
        "standard_type": result.standard_type,
        "standard_name": result.standard_name,
        "message": "Standard added successfully",
    }


@router.get("/org/context")
async def get_org_context(
    org_id: int,
    project: Optional[str] = None,
    team: Optional[str] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get comprehensive organization context for NAVI responses."""
    service = get_org_memory_service(db)
    return service.build_org_context(org_id, project=project, team=team)


# =============================================================================
# Conversation Endpoints
# =============================================================================


@router.get("/conversations")
async def list_conversations(
    user_id: int,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List user's conversations."""
    service = get_conversation_memory_service(db)

    conversations = service.get_user_conversations(
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset,
    )

    return [
        {
            "id": str(c.id),
            "title": c.title,
            "status": c.status,
            "is_pinned": c.is_pinned,
            "is_starred": c.is_starred,
            "workspace_path": c.workspace_path,
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in conversations
    ]


@router.post("/conversations")
async def create_conversation(
    user_id: int,
    org_id: Optional[int] = None,
    conversation: ConversationCreate = ConversationCreate(),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new conversation."""
    service = get_conversation_memory_service(db)

    result = service.create_conversation(
        user_id=user_id,
        org_id=org_id,
        title=conversation.title,
        workspace_path=conversation.workspace_path,
        initial_context=conversation.initial_context,
    )

    return {
        "id": str(result.id),
        "title": result.title,
        "status": result.status,
        "is_pinned": result.is_pinned,
        "is_starred": result.is_starred,
        "created_at": result.created_at.isoformat(),
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: UUID,
    include_messages: bool = True,
    message_limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get a conversation with optional messages."""
    service = get_conversation_memory_service(db)

    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = {
        "id": str(conversation.id),
        "title": conversation.title,
        "status": conversation.status,
        "is_pinned": conversation.is_pinned,
        "is_starred": conversation.is_starred,
        "workspace_path": conversation.workspace_path,
        "initial_context": conversation.initial_context,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }

    if include_messages:
        messages = service.get_recent_messages(conversation_id, limit=message_limit)
        result["messages"] = [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "metadata": m.message_metadata,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]

    return result


@router.patch("/conversations/{conversation_id}")
async def update_conversation(
    conversation_id: UUID,
    update: ConversationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Update conversation metadata.

    Security: Uses authenticated user from JWT/session, not user-controlled params.
    """
    service = get_conversation_memory_service(db)

    # Fetch conversation first to verify ownership
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Verify ownership: conversation belongs to the authenticated user
    # Get user_id from authenticated user (not from request params)
    user_id = (
        current_user.user_id if hasattr(current_user, "user_id") else current_user.id
    )
    org_id = getattr(current_user, "org_id", None) or getattr(
        current_user, "org_key", None
    )

    # Normalize both user IDs to strings to avoid type mismatch (UUID/int vs string) causing false 403s
    if str(conversation.user_id) != str(user_id):
        raise HTTPException(
            status_code=403, detail="Not authorized to modify this conversation"
        )
    # Normalize org IDs to strings for same reason (mixed auth backends can have different types)
    if (
        org_id
        and hasattr(conversation, "org_id")
        and conversation.org_id
        and str(conversation.org_id) != str(org_id)
    ):
        raise HTTPException(
            status_code=403, detail="Not authorized to modify this conversation"
        )

    # Apply updates
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    conversation = service.update_conversation(conversation_id, **update_data)
    if not conversation:
        raise HTTPException(status_code=500, detail="Update failed")

    return {
        "id": str(conversation.id),
        "title": conversation.title,
        "status": conversation.status,
        "is_pinned": conversation.is_pinned,
        "is_starred": conversation.is_starred,
        "workspace_path": conversation.workspace_path,
        "initial_context": conversation.initial_context,
        "created_at": conversation.created_at.isoformat(),
        "updated_at": conversation.updated_at.isoformat(),
    }


@router.post("/conversations/{conversation_id}/messages")
async def add_message(
    conversation_id: UUID,
    message: MessageCreate,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add a message to a conversation."""
    service = get_conversation_memory_service(db)

    # Verify conversation exists
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await service.add_message(
        conversation_id=conversation_id,
        role=message.role,
        content=message.content,
        metadata=message.metadata,
        tokens_used=message.tokens_used,
    )

    return {
        "id": str(result.id),
        "role": result.role,
        "content": result.content,
        "created_at": result.created_at.isoformat(),
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Delete (soft) a conversation."""
    service = get_conversation_memory_service(db)

    success = service.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"message": "Conversation deleted successfully"}


# =============================================================================
# Codebase Index Endpoints
# =============================================================================


@router.post("/codebase/index")
async def create_codebase_index(
    user_id: int,
    index_data: CodebaseIndexCreate,
    org_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a new codebase index."""
    service = get_codebase_memory_service(db)

    result = service.create_index(
        workspace_path=index_data.workspace_path,
        user_id=user_id,
        org_id=org_id,
        workspace_name=index_data.workspace_name,
        index_config=index_data.index_config,
    )

    return {
        "id": str(result.id),
        "workspace_path": result.workspace_path,
        "workspace_name": result.workspace_name,
        "status": result.index_status,
        "created_at": result.created_at.isoformat(),
    }


@router.get("/codebase/status")
async def get_codebase_status(
    index_id: UUID,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get codebase index status."""
    service = get_codebase_memory_service(db)

    index = service.get_index(index_id)
    if not index:
        raise HTTPException(status_code=404, detail="Codebase index not found")

    return {
        "id": str(index.id),
        "workspace_path": index.workspace_path,
        "workspace_name": index.workspace_name,
        "status": index.index_status,
        "last_indexed": index.last_indexed.isoformat() if index.last_indexed else None,
        "last_error": index.last_error,
        "stats": {
            "file_count": index.file_count,
            "symbol_count": index.symbol_count,
            "total_lines": index.total_lines,
        },
    }


@router.get("/codebase/search")
async def search_codebase(
    codebase_id: UUID,
    query: str,
    symbol_type: Optional[str] = None,
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Search code symbols in a codebase."""
    service = get_codebase_memory_service(db)

    results = await service.search_symbols(
        codebase_id=codebase_id,
        query=query,
        symbol_type=symbol_type,
        limit=limit,
    )

    return results


@router.delete("/codebase/{index_id}")
async def delete_codebase_index(
    index_id: UUID,
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    """Delete a codebase index."""
    service = get_codebase_memory_service(db)

    success = service.delete_index(index_id)
    if not success:
        raise HTTPException(status_code=404, detail="Codebase index not found")

    return {"message": "Codebase index deleted successfully"}


# =============================================================================
# Semantic Search Endpoints
# =============================================================================


@router.post("/search")
async def semantic_search(
    user_id: int,
    search: SearchRequest,
    org_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> List[SearchResultResponse]:
    """Semantic search across all memory types."""
    service = get_semantic_search_service(db)

    # Parse scope
    try:
        scope = SearchScope(search.scope)
    except ValueError:
        scope = SearchScope.ALL

    results = await service.search(
        query=search.query,
        user_id=user_id,
        org_id=org_id,
        codebase_id=search.codebase_id,
        scope=scope,
        limit=search.limit,
        min_similarity=search.min_similarity,
    )

    return [
        SearchResultResponse(
            id=r.id,
            source=r.source,
            title=r.title,
            content=r.content,
            similarity=r.similarity,
            metadata=r.metadata,
        )
        for r in results
    ]


@router.get("/context")
async def get_query_context(
    query: str,
    user_id: int,
    org_id: Optional[int] = None,
    codebase_id: Optional[UUID] = None,
    max_items: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Get relevant context for a user query."""
    service = get_semantic_search_service(db)

    context = await service.get_context_for_query(
        query=query,
        user_id=user_id,
        org_id=org_id,
        codebase_id=codebase_id,
        max_context_items=max_items,
    )

    return context
