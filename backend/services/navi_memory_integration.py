"""
NAVI Memory Integration Service.

Integrates the comprehensive memory system into NAVI's response pipeline,
enabling personalized, context-aware, and intelligent responses.

Features:
- Retrieve relevant memory context for queries
- Store conversation history automatically
- Apply user preferences to responses
- Learn from user feedback
- Provide organization-aware responses
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from backend.services.memory.user_memory import get_user_memory_service
from backend.services.memory.org_memory import get_org_memory_service
from backend.services.memory.conversation_memory import get_conversation_memory_service
from backend.services.memory.codebase_memory import get_codebase_memory_service
from backend.services.memory.semantic_search import get_semantic_search_service
from backend.services.intelligence.pattern_detector import get_pattern_detector
from backend.services.intelligence.preference_learner import get_preference_learner
from backend.services.intelligence.context_predictor import get_context_predictor
from backend.services.intelligence.response_personalizer import (
    get_response_personalizer,
)

logger = logging.getLogger(__name__)


class NaviMemoryIntegration:
    """
    Integration service connecting NAVI with the memory system.

    Provides a unified interface for:
    - Retrieving relevant context from memory
    - Storing interactions for future learning
    - Personalizing responses based on history
    """

    def __init__(self, db: Session):
        """
        Initialize the memory integration service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

        # Initialize memory services
        self.user_memory = get_user_memory_service(db)
        self.org_memory = get_org_memory_service(db)
        self.conversation_memory = get_conversation_memory_service(db)
        self.codebase_memory = get_codebase_memory_service(db)
        self.semantic_search = get_semantic_search_service(db)

        # Initialize intelligence services
        self.pattern_detector = get_pattern_detector(db)
        self.preference_learner = get_preference_learner(db)
        self.context_predictor = get_context_predictor(db)
        self.response_personalizer = get_response_personalizer(db)

    # =========================================================================
    # Context Retrieval for NAVI Requests
    # =========================================================================

    async def get_memory_context(
        self,
        query: str,
        user_id: int,
        org_id: Optional[int] = None,
        workspace_path: Optional[str] = None,
        conversation_id: Optional[UUID] = None,
        current_file: Optional[str] = None,
        max_items: int = 10,
    ) -> Dict[str, Any]:
        """
        Get comprehensive memory context for a NAVI request.

        Retrieves relevant context from all memory sources to inform
        NAVI's response.

        Args:
            query: User's query
            user_id: User ID
            org_id: Optional organization ID
            workspace_path: Optional workspace path
            conversation_id: Optional conversation ID
            current_file: Optional current file being edited
            max_items: Maximum context items per category

        Returns:
            Dictionary containing memory context for NAVI
        """
        context = {
            "retrieved_at": datetime.utcnow().isoformat(),
            "user_context": {},
            "org_context": {},
            "conversation_context": {},
            "code_context": [],
            "semantic_matches": [],
            "personalization": {},
            "predictions": [],
        }

        try:
            # 1. Get user context (preferences, patterns)
            context["user_context"] = self.user_memory.build_user_context(user_id)

            # 2. Get organization context if available
            if org_id:
                context["org_context"] = await self._get_org_context(org_id, query)

            # 3. Get conversation context if in a conversation
            if conversation_id:
                context["conversation_context"] = (
                    self.conversation_memory.build_conversation_context(
                        conversation_id,
                        max_messages=20,
                        include_summary=True,
                    )
                )

            # 4. Search for relevant code context
            context["code_context"] = await self._get_code_context(
                query, user_id, workspace_path, current_file
            )

            # 5. Semantic search across all memory
            context["semantic_matches"] = await self._semantic_search(
                query, user_id, org_id, max_items
            )

            # 6. Get personalization context
            context["personalization"] = (
                self.response_personalizer.build_personalization_context(
                    user_id, org_id
                )
            )

            # 7. Predict additional relevant context
            predictions = await self.context_predictor.predict_context(
                query, user_id, org_id, workspace_path, current_file
            )
            context["predictions"] = predictions.get("predictions", [])

        except Exception as e:
            logger.error(f"Error retrieving memory context: {e}")

        return context

    async def _get_org_context(
        self,
        org_id: int,
        query: str,
    ) -> Dict[str, Any]:
        """Get organization-specific context."""
        org_context = {}

        try:
            # Get relevant knowledge
            knowledge = await self.org_memory.search_knowledge(org_id, query, limit=5)
            org_context["knowledge"] = knowledge

            # Get coding standards
            standards = self.org_memory.get_enforced_standards(org_id)
            org_context["standards"] = [
                {
                    "type": s.standard_type,
                    "name": s.standard_name,
                    "rules": s.rules,
                }
                for s in standards
            ]

            # Get relevant context hierarchy
            global_context = self.org_memory.get_context(org_id, "global", "default")
            if global_context:
                org_context["global_context"] = global_context.context_value

        except Exception as e:
            logger.warning(f"Error getting org context: {e}")

        return org_context

    async def _get_code_context(
        self,
        query: str,
        user_id: int,
        workspace_path: Optional[str],
        current_file: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Get relevant code context."""
        code_context = []

        if not workspace_path:
            return code_context

        try:
            # Find codebase index for workspace
            index = self.codebase_memory.get_index_by_path(user_id, workspace_path)
            if not index:
                return code_context

            # Search for relevant symbols
            results = await self.codebase_memory.search_symbols(
                str(index.id), query, limit=10
            )
            code_context = results

            # Prioritize current file if available
            if current_file:
                for item in code_context:
                    if item.get("file_path") == current_file:
                        item["relevance"] = min(1.0, item.get("relevance", 0.5) + 0.2)

                # Sort by relevance
                code_context.sort(key=lambda x: x.get("relevance", 0), reverse=True)

        except Exception as e:
            logger.warning(f"Error getting code context: {e}")

        return code_context

    async def _semantic_search(
        self,
        query: str,
        user_id: int,
        org_id: Optional[int],
        max_items: int,
    ) -> List[Dict[str, Any]]:
        """Perform semantic search across memory."""
        try:
            from backend.services.memory.semantic_search import SearchScope

            scope = SearchScope(
                search_conversations=True,
                search_knowledge=bool(org_id),
                search_code=True,
            )

            results = await self.semantic_search.search(
                query=query,
                user_id=user_id,
                org_id=org_id,
                scope=scope,
            )

            return [r.to_dict() for r in results[:max_items]]

        except Exception as e:
            logger.warning(f"Error in semantic search: {e}")
            return []

    # =========================================================================
    # Storing Interactions
    # =========================================================================

    async def store_interaction(
        self,
        user_id: int,
        conversation_id: UUID,
        user_message: str,
        assistant_response: str,
        metadata: Optional[Dict[str, Any]] = None,
        org_id: Optional[int] = None,
        workspace_path: Optional[str] = None,
        file_path: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Store an interaction in memory for future learning.

        Args:
            user_id: User ID
            conversation_id: Conversation ID
            user_message: User's message
            assistant_response: NAVI's response
            metadata: Optional metadata
            org_id: Optional organization ID
            workspace_path: Optional workspace path
            file_path: Optional file path
            language: Optional programming language

        Returns:
            Dictionary with stored message IDs
        """
        result = {
            "user_message_id": None,
            "assistant_message_id": None,
            "activity_tracked": False,
        }

        try:
            # Store user message
            user_msg = await self.conversation_memory.add_message(
                conversation_id=conversation_id,
                role="user",
                content=user_message,
                metadata=metadata,
            )
            result["user_message_id"] = str(user_msg.id)

            # Store assistant response
            assistant_msg = await self.conversation_memory.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=assistant_response,
                metadata=metadata,
            )
            result["assistant_message_id"] = str(assistant_msg.id)

            # Track activity for pattern detection
            self.user_memory.track_activity(
                user_id=user_id,
                activity_type="query",
                activity_data={
                    "query": user_message[:500],  # Truncate for storage
                    "response_length": len(assistant_response),
                    "conversation_id": str(conversation_id),
                },
                org_id=org_id,
                workspace_path=workspace_path,
                file_path=file_path,
                language=language,
            )
            result["activity_tracked"] = True

        except Exception as e:
            logger.error(f"Error storing interaction: {e}")

        return result

    async def create_conversation(
        self,
        user_id: int,
        title: Optional[str] = None,
        org_id: Optional[int] = None,
        workspace_path: Optional[str] = None,
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> UUID:
        """
        Create a new conversation.

        Args:
            user_id: User ID
            title: Optional title
            org_id: Optional organization ID
            workspace_path: Optional workspace path
            initial_context: Optional initial context

        Returns:
            Conversation ID
        """
        conversation = self.conversation_memory.create_conversation(
            user_id=user_id,
            org_id=org_id,
            title=title,
            workspace_path=workspace_path,
            initial_context=initial_context,
        )
        return conversation.id

    # =========================================================================
    # Feedback and Learning
    # =========================================================================

    async def record_feedback(
        self,
        user_id: int,
        message_id: UUID,
        conversation_id: UUID,
        feedback_type: str,
        feedback_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record user feedback on a NAVI response.

        Args:
            user_id: User ID
            message_id: Message ID
            conversation_id: Conversation ID
            feedback_type: Feedback type (positive, negative, correction)
            feedback_data: Optional feedback details

        Returns:
            Dictionary with feedback ID and learning status
        """
        result = {
            "feedback_id": None,
            "learning_triggered": False,
        }

        try:
            # Get message content for context
            messages = self.conversation_memory.get_messages(conversation_id, limit=10)
            query_text = None
            response_text = None

            for i, msg in enumerate(messages):
                if str(msg.id) == str(message_id):
                    response_text = msg.content
                    if i > 0 and messages[i - 1].role == "user":
                        query_text = messages[i - 1].content
                    break

            # Record feedback
            feedback = self.user_memory.record_feedback(
                user_id=user_id,
                message_id=message_id,
                conversation_id=conversation_id,
                feedback_type=feedback_type,
                feedback_data=feedback_data,
                query_text=query_text,
                response_text=response_text,
            )
            result["feedback_id"] = str(feedback.id)

            # Trigger learning if enough feedback collected
            feedback_count = len(
                self.db.query(type(feedback)).filter_by(user_id=user_id).limit(10).all()
            )

            if feedback_count >= 5:
                learning_result = self.preference_learner.learn_from_feedback(user_id)
                result["learning_triggered"] = True
                result["learning_result"] = learning_result

        except Exception as e:
            logger.error(f"Error recording feedback: {e}")

        return result

    # =========================================================================
    # System Prompt Enhancement
    # =========================================================================

    def enhance_system_prompt(
        self,
        base_prompt: str,
        user_id: int,
        org_id: Optional[int] = None,
    ) -> str:
        """
        Enhance the base system prompt with personalization.

        Args:
            base_prompt: The base NAVI system prompt
            user_id: User ID
            org_id: Optional organization ID

        Returns:
            Enhanced system prompt
        """
        context = self.response_personalizer.build_personalization_context(
            user_id, org_id
        )
        return self.response_personalizer.create_personalized_system_prompt(
            base_prompt, context
        )

    # =========================================================================
    # Pattern Detection and Analysis
    # =========================================================================

    async def analyze_user_patterns(
        self,
        user_id: int,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Analyze and detect user behavior patterns.

        Args:
            user_id: User ID
            days: Days of history to analyze

        Returns:
            Dictionary of detected patterns
        """
        patterns = self.pattern_detector.detect_user_patterns(user_id, days)
        return {
            "patterns_detected": len(patterns),
            "patterns": patterns,
            "analyzed_days": days,
        }

    # =========================================================================
    # Format Context for LLM Prompt
    # =========================================================================

    def format_context_for_prompt(
        self,
        context: Dict[str, Any],
        max_tokens: int = 2000,
    ) -> str:
        """
        Format memory context for inclusion in LLM prompt.

        Args:
            context: Memory context from get_memory_context
            max_tokens: Maximum approximate tokens

        Returns:
            Formatted context string
        """
        parts = []
        char_limit = max_tokens * 4  # Approximate chars per token

        # User preferences
        user_ctx = context.get("user_context", {})
        prefs = user_ctx.get("preferences", {})
        if prefs:
            pref_text = "\n=== USER PREFERENCES ===\n"
            if prefs.get("preferred_language"):
                pref_text += f"- Preferred language: {prefs['preferred_language']}\n"
            if prefs.get("preferred_framework"):
                pref_text += f"- Preferred framework: {prefs['preferred_framework']}\n"
            if prefs.get("response_verbosity"):
                pref_text += f"- Response style: {prefs['response_verbosity']}\n"
            parts.append(pref_text)

        # Organization standards
        org_ctx = context.get("org_context", {})
        standards = org_ctx.get("standards", [])
        if standards:
            std_text = "\n=== ORGANIZATION STANDARDS ===\n"
            for std in standards[:5]:
                std_text += f"- {std['name']}: {std.get('rules', {})}\n"
            parts.append(std_text)

        # Relevant code context
        code_ctx = context.get("code_context", [])
        if code_ctx:
            code_text = "\n=== RELEVANT CODE ===\n"
            for item in code_ctx[:5]:
                code_text += f"- {item.get('symbol_type', 'code')}: {item.get('name', 'unknown')} in {item.get('file_path', 'unknown')}\n"
            parts.append(code_text)

        # Semantic matches
        matches = context.get("semantic_matches", [])
        if matches:
            match_text = "\n=== RELATED CONTEXT ===\n"
            for match in matches[:5]:
                match_text += f"- [{match.get('source', 'unknown')}] {match.get('content', '')[:100]}...\n"
            parts.append(match_text)

        # Combine and truncate
        result = "".join(parts)
        if len(result) > char_limit:
            result = result[:char_limit] + "\n[Context truncated...]"

        return result


def get_navi_memory_integration(db: Session) -> NaviMemoryIntegration:
    """Factory function to create NaviMemoryIntegration."""
    return NaviMemoryIntegration(db)
