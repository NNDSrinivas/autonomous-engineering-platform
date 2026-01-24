"""
Context Prediction Service for NAVI.

Predicts relevant context before user needs it, enabling faster
and more informed responses.

Features:
- Predict relevant code context based on query
- Suggest related past conversations
- Pre-load relevant organization knowledge
- Anticipate follow-up questions
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from backend.database.models.memory import (
    Conversation,
    Message,
    OrgKnowledge,
    CodeSymbol,
    UserActivity,
    UserPattern,
)
from backend.services.memory.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class ContextPredictor:
    """
    Service for predicting relevant context for NAVI queries.

    Uses historical data, patterns, and semantic similarity to
    anticipate what context will be useful for responding to queries.
    """

    # Maximum number of context items to include
    MAX_CONTEXT_ITEMS = 10
    # Minimum similarity for context relevance
    MIN_SIMILARITY = 0.5
    # Time window for recent context (hours)
    RECENT_WINDOW_HOURS = 4

    def __init__(self, db: Session):
        """
        Initialize the context predictor.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.embedding_service = get_embedding_service()

    # =========================================================================
    # Context Prediction
    # =========================================================================

    async def predict_context(
        self,
        query: str,
        user_id: int,
        org_id: Optional[int] = None,
        workspace_path: Optional[str] = None,
        current_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Predict relevant context for a query.

        Args:
            query: The user's query
            user_id: User ID
            org_id: Optional organization ID
            workspace_path: Optional workspace path
            current_file: Optional current file being edited

        Returns:
            Dictionary containing predicted context
        """
        context = {
            "predicted_at": datetime.utcnow().isoformat(),
            "query": query,
            "code_context": [],
            "conversation_context": [],
            "knowledge_context": [],
            "user_context": {},
            "predictions": [],
        }

        # Predict based on query type
        query_type = self._classify_query_type(query)
        context["query_type"] = query_type

        # Get user context (preferences, patterns)
        context["user_context"] = self._get_user_context(user_id)

        # Predict code context if relevant
        if query_type in ["code", "debug", "explain", "implement"]:
            code_context = await self._predict_code_context(
                query, user_id, workspace_path, current_file
            )
            context["code_context"] = code_context

        # Get relevant past conversations
        conversation_context = await self._predict_conversation_context(query, user_id)
        context["conversation_context"] = conversation_context

        # Get relevant organization knowledge
        if org_id:
            knowledge_context = await self._predict_knowledge_context(query, org_id)
            context["knowledge_context"] = knowledge_context

        # Predict follow-up needs
        predictions = self._predict_followups(query, query_type, context)
        context["predictions"] = predictions

        return context

    def _classify_query_type(self, query: str) -> str:
        """Classify the type of query for context prediction."""
        query_lower = query.lower()

        # Code-related queries
        if any(
            kw in query_lower for kw in ["implement", "write", "create", "add", "code"]
        ):
            return "implement"

        if any(kw in query_lower for kw in ["bug", "error", "fix", "debug", "issue"]):
            return "debug"

        if any(kw in query_lower for kw in ["explain", "what does", "how does", "why"]):
            return "explain"

        if any(kw in query_lower for kw in ["refactor", "improve", "optimize"]):
            return "refactor"

        if any(kw in query_lower for kw in ["test", "spec", "coverage"]):
            return "test"

        # Documentation queries
        if any(kw in query_lower for kw in ["document", "docs", "readme", "comment"]):
            return "document"

        # Architecture queries
        if any(
            kw in query_lower
            for kw in ["architecture", "design", "pattern", "structure"]
        ):
            return "architecture"

        return "general"

    def _get_user_context(self, user_id: int) -> Dict[str, Any]:
        """Get user-specific context for personalization."""
        # Get user patterns
        patterns = (
            self.db.query(UserPattern)
            .filter(
                and_(
                    UserPattern.user_id == user_id,
                    UserPattern.confidence >= 0.6,
                )
            )
            .order_by(desc(UserPattern.confidence))
            .limit(5)
            .all()
        )

        # Get recent activity
        recent_since = datetime.utcnow() - timedelta(hours=self.RECENT_WINDOW_HOURS)
        recent_activity = (
            self.db.query(UserActivity)
            .filter(
                and_(
                    UserActivity.user_id == user_id,
                    UserActivity.created_at >= recent_since,
                )
            )
            .order_by(desc(UserActivity.created_at))
            .limit(10)
            .all()
        )

        return {
            "patterns": [
                {
                    "type": p.pattern_type,
                    "key": p.pattern_key,
                    "confidence": p.confidence,
                }
                for p in patterns
            ],
            "recent_files": list(
                set(a.file_path for a in recent_activity if a.file_path)
            )[:5],
            "recent_languages": list(
                set(a.language for a in recent_activity if a.language)
            )[:3],
            "session_activity_count": len(recent_activity),
        }

    async def _predict_code_context(
        self,
        query: str,
        user_id: int,
        workspace_path: Optional[str],
        current_file: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Predict relevant code context for the query."""
        context = []

        # If we have a current file, prioritize it
        if current_file:
            context.append(
                {
                    "type": "current_file",
                    "file": current_file,
                    "relevance": 1.0,
                }
            )

        # Search for relevant symbols using query embedding
        try:
            query_embedding = await self.embedding_service.embed_text(query)

            # Get symbols with embeddings
            symbols = (
                self.db.query(CodeSymbol)
                .filter(CodeSymbol.embedding_text.isnot(None))
                .limit(100)  # Limit for performance
                .all()
            )

            # Calculate similarities
            ranked_symbols = []
            for symbol in symbols:
                if not symbol.embedding_text:
                    continue

                symbol_embedding = self.embedding_service.deserialize_embedding(
                    symbol.embedding_text
                )
                similarity = self.embedding_service.cosine_similarity(
                    query_embedding, symbol_embedding
                )

                if similarity >= self.MIN_SIMILARITY:
                    ranked_symbols.append(
                        {
                            "type": "code_symbol",
                            "symbol_type": symbol.symbol_type,
                            "name": symbol.symbol_name,
                            "file": symbol.file_path,
                            "line": symbol.line_start,
                            "relevance": round(similarity, 2),
                        }
                    )

            # Sort by relevance
            ranked_symbols.sort(key=lambda x: x["relevance"], reverse=True)
            context.extend(ranked_symbols[: self.MAX_CONTEXT_ITEMS])

        except Exception as e:
            logger.warning(f"Error predicting code context: {e}")

        return context

    async def _predict_conversation_context(
        self,
        query: str,
        user_id: int,
    ) -> List[Dict[str, Any]]:
        """Predict relevant past conversations."""
        context = []

        try:
            query_embedding = await self.embedding_service.embed_text(query)

            # Get recent conversations
            recent_conversations = (
                self.db.query(Conversation)
                .filter(
                    and_(
                        Conversation.user_id == user_id,
                        Conversation.status != "deleted",
                    )
                )
                .order_by(desc(Conversation.updated_at))
                .limit(20)
                .all()
            )

            for conv in recent_conversations:
                # Get messages with embeddings
                messages = (
                    self.db.query(Message)
                    .filter(
                        and_(
                            Message.conversation_id == conv.id,
                            Message.embedding_text.isnot(None),
                        )
                    )
                    .limit(10)
                    .all()
                )

                best_similarity = 0.0
                best_message = None

                for msg in messages:
                    if not msg.embedding_text:
                        continue

                    msg_embedding = self.embedding_service.deserialize_embedding(
                        msg.embedding_text
                    )
                    similarity = self.embedding_service.cosine_similarity(
                        query_embedding, msg_embedding
                    )

                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_message = msg

                if best_similarity >= self.MIN_SIMILARITY:
                    context.append(
                        {
                            "type": "past_conversation",
                            "conversation_id": str(conv.id),
                            "title": conv.title,
                            "relevance": round(best_similarity, 2),
                            "matching_content": (
                                best_message.content[:100] + "..."
                                if best_message and len(best_message.content) > 100
                                else best_message.content if best_message else None
                            ),
                        }
                    )

            # Sort by relevance
            context.sort(key=lambda x: x["relevance"], reverse=True)

        except Exception as e:
            logger.warning(f"Error predicting conversation context: {e}")

        return context[: self.MAX_CONTEXT_ITEMS]

    async def _predict_knowledge_context(
        self,
        query: str,
        org_id: int,
    ) -> List[Dict[str, Any]]:
        """Predict relevant organization knowledge."""
        context = []

        try:
            query_embedding = await self.embedding_service.embed_text(query)

            # Get org knowledge with embeddings
            knowledge_items = (
                self.db.query(OrgKnowledge)
                .filter(
                    and_(
                        OrgKnowledge.org_id == org_id,
                        OrgKnowledge.embedding_text.isnot(None),
                    )
                )
                .all()
            )

            for item in knowledge_items:
                if not item.embedding_text:
                    continue

                item_embedding = self.embedding_service.deserialize_embedding(
                    item.embedding_text
                )
                similarity = self.embedding_service.cosine_similarity(
                    query_embedding, item_embedding
                )

                if similarity >= self.MIN_SIMILARITY:
                    context.append(
                        {
                            "type": "org_knowledge",
                            "knowledge_type": item.knowledge_type,
                            "title": item.title,
                            "content_preview": (
                                item.content[:150] + "..."
                                if len(item.content) > 150
                                else item.content
                            ),
                            "relevance": round(similarity, 2),
                        }
                    )

            # Sort by relevance
            context.sort(key=lambda x: x["relevance"], reverse=True)

        except Exception as e:
            logger.warning(f"Error predicting knowledge context: {e}")

        return context[: self.MAX_CONTEXT_ITEMS]

    def _predict_followups(
        self,
        query: str,
        query_type: str,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Predict likely follow-up questions or needs."""
        predictions = []

        # Based on query type, predict common follow-ups
        if query_type == "implement":
            predictions.extend(
                [
                    {"type": "likely_followup", "content": "User may ask about tests"},
                    {
                        "type": "likely_followup",
                        "content": "User may ask about error handling",
                    },
                ]
            )

        elif query_type == "debug":
            predictions.extend(
                [
                    {
                        "type": "likely_followup",
                        "content": "User may want to see related code",
                    },
                    {
                        "type": "likely_followup",
                        "content": "User may need help with fix implementation",
                    },
                ]
            )

        elif query_type == "explain":
            predictions.extend(
                [
                    {"type": "likely_followup", "content": "User may ask for examples"},
                    {
                        "type": "likely_followup",
                        "content": "User may want deeper explanation",
                    },
                ]
            )

        # Based on user patterns
        user_patterns = context.get("user_context", {}).get("patterns", [])
        for pattern in user_patterns:
            if pattern["type"] == "workflow":
                predictions.append(
                    {
                        "type": "pattern_based",
                        "content": f"User typically follows pattern: {pattern['key']}",
                        "confidence": pattern["confidence"],
                    }
                )

        return predictions[:5]

    # =========================================================================
    # Proactive Context
    # =========================================================================

    def get_proactive_suggestions(
        self,
        user_id: int,
        workspace_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get proactive suggestions based on user's current context.

        Args:
            user_id: User ID
            workspace_path: Optional workspace path

        Returns:
            List of proactive suggestions
        """
        suggestions = []

        # Get recent activity
        recent_since = datetime.utcnow() - timedelta(hours=1)
        recent_activity = (
            self.db.query(UserActivity)
            .filter(
                and_(
                    UserActivity.user_id == user_id,
                    UserActivity.created_at >= recent_since,
                )
            )
            .order_by(desc(UserActivity.created_at))
            .limit(10)
            .all()
        )

        # Analyze recent activity for suggestions
        error_activities = [
            a for a in recent_activity if "error" in a.activity_type.lower()
        ]
        if len(error_activities) >= 3:
            suggestions.append(
                {
                    "type": "proactive",
                    "category": "debugging",
                    "content": "I noticed you've encountered several errors. Would you like help debugging?",
                    "confidence": 0.8,
                }
            )

        # Check for repetitive activities
        activity_types = [a.activity_type for a in recent_activity]
        from collections import Counter

        type_counts = Counter(activity_types)
        most_common = type_counts.most_common(1)

        if most_common and most_common[0][1] >= 5:
            suggestions.append(
                {
                    "type": "proactive",
                    "category": "automation",
                    "content": f"You've been doing a lot of '{most_common[0][0]}'. Would you like me to help automate this?",
                    "confidence": 0.7,
                }
            )

        return suggestions


def get_context_predictor(db: Session) -> ContextPredictor:
    """Factory function to create ContextPredictor."""
    return ContextPredictor(db)
