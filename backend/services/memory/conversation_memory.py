"""
Conversation Memory Service for NAVI.

Manages conversation history, message storage, and summarization
for maintaining context across sessions.

Features:
- Conversation lifecycle management
- Message storage with embeddings
- Automatic conversation summarization
- Semantic search across conversation history
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from backend.database.models.memory import (
    Conversation,
    ConversationSummary,
    Message,
)
from backend.services.memory.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class ConversationMemoryService:
    """
    Service for managing conversation memory.

    Provides methods to store, retrieve, and search conversation
    history with automatic summarization for efficient context loading.
    """

    def __init__(self, db: Session):
        """
        Initialize the conversation memory service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.embedding_service = get_embedding_service()

    # =========================================================================
    # Conversation Management
    # =========================================================================

    def create_conversation(
        self,
        user_id: int,
        org_id: Optional[int] = None,
        title: Optional[str] = None,
        workspace_path: Optional[str] = None,
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> Conversation:
        """
        Create a new conversation.

        Args:
            user_id: User ID
            org_id: Optional organization ID
            title: Optional conversation title
            workspace_path: Optional workspace path
            initial_context: Optional initial context

        Returns:
            Created Conversation
        """
        conversation = Conversation(
            user_id=user_id,
            org_id=org_id,
            title=title,
            workspace_path=workspace_path,
            initial_context=initial_context,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        logger.info(f"Created conversation {conversation.id} for user {user_id}")
        return conversation

    def get_conversation(self, conversation_id: UUID) -> Optional[Conversation]:
        """
        Get a conversation by ID.

        Args:
            conversation_id: Conversation ID

        Returns:
            Conversation or None if not found
        """
        return (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )

    def get_user_conversations(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Conversation]:
        """
        Get conversations for a user.

        Args:
            user_id: User ID
            status: Optional filter by status
            limit: Maximum conversations to return
            offset: Offset for pagination

        Returns:
            List of Conversation objects
        """
        query = self.db.query(Conversation).filter(Conversation.user_id == user_id)

        if status:
            query = query.filter(Conversation.status == status)
        else:
            # By default, exclude deleted
            query = query.filter(Conversation.status != "deleted")

        return (
            query.order_by(desc(Conversation.updated_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def update_conversation(
        self,
        conversation_id: UUID,
        **kwargs: Any,
    ) -> Optional[Conversation]:
        """
        Update a conversation.

        Args:
            conversation_id: Conversation ID
            **kwargs: Fields to update

        Returns:
            Updated Conversation or None if not found
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None

        allowed_fields = {"title", "status", "workspace_path", "initial_context"}
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(conversation, key, value)

        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def archive_conversation(self, conversation_id: UUID) -> bool:
        """
        Archive a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            True if archived, False if not found
        """
        result = self.update_conversation(conversation_id, status="archived")
        return result is not None

    def delete_conversation(self, conversation_id: UUID) -> bool:
        """
        Soft delete a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            True if deleted, False if not found
        """
        result = self.update_conversation(conversation_id, status="deleted")
        return result is not None

    # =========================================================================
    # Message Management
    # =========================================================================

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        tokens_used: Optional[int] = None,
        generate_embedding: bool = True,
    ) -> Message:
        """
        Add a message to a conversation.

        Args:
            conversation_id: Conversation ID
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata
            tokens_used: Optional token count
            generate_embedding: Whether to generate embedding

        Returns:
            Created Message
        """
        embedding_text = None
        if generate_embedding and content:
            embedding_text = await self.embedding_service.embed_text(content)

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            message_metadata=metadata or {},
            tokens_used=tokens_used,
            embedding_text=embedding_text,
        )
        self.db.add(message)

        # Update conversation timestamp
        conversation = self.get_conversation(conversation_id)
        if conversation:
            conversation.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(message)

        # Auto-generate title if this is the first user message and no title exists
        if role == "user" and conversation and not conversation.title:
            self._auto_generate_title(conversation, content)

        return message

    def _auto_generate_title(
        self, conversation: Conversation, first_message: str
    ) -> None:
        """Generate conversation title from first message."""
        # Simple title generation: first 50 chars of first message
        title = first_message[:50].strip()
        if len(first_message) > 50:
            title += "..."
        conversation.title = title
        self.db.commit()

    def get_messages(
        self,
        conversation_id: UUID,
        limit: Optional[int] = None,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None,
    ) -> List[Message]:
        """
        Get messages for a conversation.

        Args:
            conversation_id: Conversation ID
            limit: Maximum messages to return
            before: Get messages before this time
            after: Get messages after this time

        Returns:
            List of Message objects
        """
        query = self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        )

        if before:
            query = query.filter(Message.created_at < before)

        if after:
            query = query.filter(Message.created_at > after)

        query = query.order_by(Message.created_at)

        if limit:
            query = query.limit(limit)

        return query.all()

    def get_recent_messages(
        self,
        conversation_id: UUID,
        limit: int = 20,
    ) -> List[Message]:
        """
        Get most recent messages for a conversation.

        Args:
            conversation_id: Conversation ID
            limit: Maximum messages to return

        Returns:
            List of Message objects (oldest first)
        """
        messages = (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .limit(limit)
            .all()
        )
        # Return in chronological order
        return list(reversed(messages))

    def get_message_count(self, conversation_id: UUID) -> int:
        """
        Get message count for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            Number of messages
        """
        return (
            self.db.query(func.count(Message.id))
            .filter(Message.conversation_id == conversation_id)
            .scalar()
        ) or 0

    # =========================================================================
    # Conversation Summarization
    # =========================================================================

    async def create_summary(
        self,
        conversation_id: UUID,
        summary_text: str,
        key_points: Optional[List[str]] = None,
        from_message_id: Optional[UUID] = None,
        to_message_id: Optional[UUID] = None,
        message_count: Optional[int] = None,
    ) -> ConversationSummary:
        """
        Create a conversation summary.

        Args:
            conversation_id: Conversation ID
            summary_text: Summary content
            key_points: Extracted key points
            from_message_id: First message in summary range
            to_message_id: Last message in summary range
            message_count: Number of messages summarized

        Returns:
            Created ConversationSummary
        """
        # Generate embedding for semantic search
        embedding_text = await self.embedding_service.embed_text(summary_text)

        summary = ConversationSummary(
            conversation_id=conversation_id,
            summary=summary_text,
            key_points=key_points or [],
            message_count=message_count or 0,
            from_message_id=from_message_id,
            to_message_id=to_message_id,
            embedding_text=embedding_text,
        )
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)

        logger.info(f"Created summary for conversation {conversation_id}")
        return summary

    def get_summaries(
        self,
        conversation_id: UUID,
    ) -> List[ConversationSummary]:
        """
        Get all summaries for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            List of ConversationSummary objects
        """
        return (
            self.db.query(ConversationSummary)
            .filter(ConversationSummary.conversation_id == conversation_id)
            .order_by(ConversationSummary.created_at)
            .all()
        )

    def get_latest_summary(
        self,
        conversation_id: UUID,
    ) -> Optional[ConversationSummary]:
        """
        Get the most recent summary for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            ConversationSummary or None
        """
        return (
            self.db.query(ConversationSummary)
            .filter(ConversationSummary.conversation_id == conversation_id)
            .order_by(desc(ConversationSummary.created_at))
            .first()
        )

    # =========================================================================
    # Semantic Search
    # =========================================================================

    async def search_conversations(
        self,
        user_id: int,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Search across user's conversations.

        Args:
            user_id: User ID
            query: Search query
            limit: Maximum results
            min_similarity: Minimum similarity threshold

        Returns:
            List of matching conversations with scores
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.embed_text(query)

        # Get user's conversations
        conversations = self.get_user_conversations(user_id, limit=100)

        results = []
        for conv in conversations:
            # Search in messages
            messages = (
                self.db.query(Message)
                .filter(
                    and_(
                        Message.conversation_id == conv.id,
                        Message.embedding_text.isnot(None),
                    )
                )
                .all()
            )

            best_similarity = 0.0
            best_message = None

            for msg in messages:
                if msg.embedding_text is None:
                    continue

                msg_embedding = list(msg.embedding_text)
                similarity = self.embedding_service.cosine_similarity(
                    query_embedding, msg_embedding
                )

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_message = msg

            if best_similarity >= min_similarity:
                results.append(
                    {
                        "conversation_id": str(conv.id),
                        "title": conv.title,
                        "similarity": best_similarity,
                        "matching_message": (
                            {
                                "id": str(best_message.id),
                                "role": best_message.role,
                                "content": (
                                    best_message.content[:200] + "..."
                                    if len(best_message.content) > 200
                                    else best_message.content
                                ),
                            }
                            if best_message
                            else None
                        ),
                        "updated_at": conv.updated_at.isoformat(),
                    }
                )

        # Sort by similarity
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    async def search_messages(
        self,
        conversation_id: UUID,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Search messages within a conversation.

        Args:
            conversation_id: Conversation ID
            query: Search query
            limit: Maximum results
            min_similarity: Minimum similarity threshold

        Returns:
            List of matching messages with scores
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.embed_text(query)

        # Get messages with embeddings
        messages = (
            self.db.query(Message)
            .filter(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.embedding_text.isnot(None),
                )
            )
            .all()
        )

        results = []
        for msg in messages:
            if msg.embedding_text is None:
                continue

            msg_embedding = list(msg.embedding_text)
            similarity = self.embedding_service.cosine_similarity(
                query_embedding, msg_embedding
            )

            if similarity >= min_similarity:
                results.append(
                    {
                        "id": str(msg.id),
                        "role": msg.role,
                        "content": msg.content,
                        "similarity": similarity,
                        "created_at": msg.created_at.isoformat(),
                    }
                )

        # Sort by similarity
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    # =========================================================================
    # Context Building
    # =========================================================================

    def build_conversation_context(
        self,
        conversation_id: UUID,
        max_messages: int = 20,
        include_summary: bool = True,
    ) -> Dict[str, Any]:
        """
        Build context from a conversation for NAVI.

        Args:
            conversation_id: Conversation ID
            max_messages: Maximum recent messages to include
            include_summary: Whether to include conversation summary

        Returns:
            Dictionary with conversation context
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return {}

        context = {
            "conversation_id": str(conversation.id),
            "title": conversation.title,
            "workspace_path": conversation.workspace_path,
            "initial_context": conversation.initial_context,
            "messages": [],
            "summary": None,
        }

        # Get recent messages
        messages = self.get_recent_messages(conversation_id, limit=max_messages)
        context["messages"] = [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ]

        # Include summary if available
        if include_summary:
            summary = self.get_latest_summary(conversation_id)
            if summary:
                context["summary"] = {
                    "text": summary.summary,
                    "key_points": summary.key_points,
                    "message_count": summary.message_count,
                }

        return context

    def get_conversation_stats(
        self,
        user_id: int,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get conversation statistics for a user.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dictionary with conversation statistics
        """
        since = datetime.utcnow() - timedelta(days=days)

        # Count conversations
        total_conversations = (
            self.db.query(func.count(Conversation.id))
            .filter(
                and_(
                    Conversation.user_id == user_id,
                    Conversation.created_at >= since,
                )
            )
            .scalar()
        ) or 0

        # Count messages
        total_messages = (
            self.db.query(func.count(Message.id))
            .join(Conversation)
            .filter(
                and_(
                    Conversation.user_id == user_id,
                    Message.created_at >= since,
                )
            )
            .scalar()
        ) or 0

        # Average messages per conversation
        avg_messages = (
            total_messages / total_conversations if total_conversations > 0 else 0
        )

        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "avg_messages_per_conversation": round(avg_messages, 1),
            "period_days": days,
        }


def get_conversation_memory_service(db: Session) -> ConversationMemoryService:
    """Factory function to create ConversationMemoryService."""
    return ConversationMemoryService(db)
