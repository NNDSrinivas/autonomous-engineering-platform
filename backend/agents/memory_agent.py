from typing import List, Dict, Any, Optional
import asyncio
import json
from datetime import datetime, timedelta

try:
    from ..models.plan import MemoryEvent
    from ..services.database_service import DatabaseService
    from ..core.config import get_settings
except ImportError:
    from backend.models.plan import MemoryEvent
    from backend.services.database_service import DatabaseService
    from backend.core.config import get_settings


class MemoryAgent:
    """
    The Memory Agent provides persistent long-term and short-term memory for Navi.
    This enables context continuity, personalization, and learning from past interactions.

    Unlike simple conversation history, this is structured, searchable, and intelligent.
    """

    def __init__(self):
        self.db = DatabaseService()
        self.settings = get_settings()

        # Memory retention policies
        self.retention_policies = {
            "instruction": timedelta(days=30),
            "execution_result": timedelta(days=14),
            "error": timedelta(days=7),
            "feedback": timedelta(days=60),
            "context_update": timedelta(days=7),
            "user_preference": timedelta(days=365),  # Long-term
        }

    async def load_context(self, user_id: str, limit: int = 20) -> Dict[str, Any]:
        """
        Load comprehensive context for a user session
        """

        # Get recent events
        recent_events = await self._get_recent_events(user_id, limit)

        # Get user preferences
        preferences = await self._get_user_preferences(user_id)

        # Get execution patterns
        patterns = await self._analyze_execution_patterns(user_id)

        # Get current project context
        project_context = await self._get_project_context(user_id)

        return {
            "recent_events": [event.dict() for event in recent_events],
            "user_preferences": preferences,
            "execution_patterns": patterns,
            "project_context": project_context,
            "loaded_at": datetime.now().isoformat(),
        }

    async def save_event(
        self,
        user_id: str,
        event_type: str,
        content: Dict[str, Any],
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
    ) -> MemoryEvent:
        """
        Save an event to the user's memory with intelligent importance scoring
        """

        # Auto-calculate importance if not provided
        if importance == 0.5:  # Default value
            importance = await self._calculate_importance(event_type, content)

        # Generate event ID
        event_id = (
            f"{user_id}_{event_type}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        )

        # Create memory event
        event = MemoryEvent(
            id=event_id,
            user_id=user_id,
            event_type=event_type,
            content=content,
            timestamp=datetime.now(),
            importance=importance,
            tags=tags or [],
        )

        # Save to database
        await self._store_event(event)

        # Trigger background processing
        asyncio.create_task(self._process_new_event(event))

        return event

    async def retrieve(self, intent: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve relevant memory context for an intent and context
        Phase 4.1.2 compatibility method
        """
        # Simple implementation for now - just return recent context
        user_id = context.get("user_id", "default")
        return await self.load_context(user_id, limit=10)

    async def search_memory(
        self,
        user_id: str,
        query: str,
        event_types: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[MemoryEvent]:
        """
        Semantic search through user's memory
        """

        # For now, implement keyword-based search
        # In production, this would use vector embeddings
        events = await self._search_events_by_keywords(
            user_id, query, event_types or [], limit
        )

        # Sort by relevance and importance
        events.sort(key=lambda e: (e.importance, e.timestamp), reverse=True)

        return events[:limit]

    async def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]):
        """
        Update user preferences with learning from behavior
        """

        # Load existing preferences
        current_prefs = await self._get_user_preferences(user_id)

        # Merge with new preferences
        updated_prefs = {**current_prefs, **preferences}

        # Save as memory event
        await self.save_event(
            user_id=user_id,
            event_type="user_preference",
            content={
                "preferences": updated_prefs,
                "updated_fields": list(preferences.keys()),
            },
            importance=0.8,
            tags=["preferences", "personalization"],
        )

    async def get_contextual_suggestions(
        self, user_id: str, current_instruction: str, repo_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get intelligent suggestions based on user history and context
        """

        # Find similar past instructions
        similar_events = await self.search_memory(
            user_id=user_id,
            query=current_instruction,
            event_types=["instruction", "execution_result"],
            limit=5,
        )

        suggestions = []

        for event in similar_events:
            if event.event_type == "instruction":
                # Suggest based on successful past executions
                suggestions.append(
                    {
                        "type": "past_success",
                        "suggestion": f"Similar to: {event.content.get('instruction', '')[:100]}...",
                        "confidence": event.importance,
                        "timestamp": event.timestamp.isoformat(),
                    }
                )

        # Analyze current repo for context-specific suggestions
        repo_suggestions = await self._generate_repo_suggestions(repo_context)
        suggestions.extend(repo_suggestions)

        return suggestions[:10]  # Return top 10 suggestions

    async def learn_from_feedback(
        self, user_id: str, execution_id: str, feedback: Dict[str, Any]
    ):
        """
        Learn from user feedback to improve future suggestions
        """

        await self.save_event(
            user_id=user_id,
            event_type="feedback",
            content={
                "execution_id": execution_id,
                "feedback": feedback,
                "learning_signal": True,
            },
            importance=0.9,  # Feedback is very important for learning
            tags=["feedback", "learning", "improvement"],
        )

        # Trigger background learning process
        asyncio.create_task(self._process_feedback(user_id, execution_id, feedback))

    async def cleanup_old_memories(self, user_id: Optional[str] = None):
        """
        Clean up old memories based on retention policies
        """

        cutoff_date = datetime.now()

        for event_type, retention_period in self.retention_policies.items():
            event_cutoff = cutoff_date - retention_period

            # Archive or delete old events
            await self._cleanup_events_before_date(
                user_id or "system", event_type, event_cutoff
            )

    # Private helper methods

    async def _get_recent_events(self, user_id: str, limit: int) -> List[MemoryEvent]:
        """
        Get recent events for user context
        """
        query = """
        SELECT * FROM memory_events 
        WHERE user_id = ? 
        ORDER BY timestamp DESC 
        LIMIT ?
        """

        rows = await self.db.fetch_all(query, [user_id, limit])
        return [self._row_to_event(row) for row in rows]

    async def _get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get user preferences from memory
        """
        query = """
        SELECT content FROM memory_events 
        WHERE user_id = ? AND event_type = 'user_preference'
        ORDER BY timestamp DESC 
        LIMIT 1
        """

        row = await self.db.fetch_one(query, [user_id])
        if row:
            return json.loads(row["content"]).get("preferences", {})

        # Return default preferences
        return {
            "preferred_languages": [],
            "complexity_tolerance": "medium",
            "auto_apply_safe_fixes": True,
            "explanation_detail": "balanced",
            "backup_before_changes": True,
        }

    async def _analyze_execution_patterns(self, user_id: str) -> Dict[str, Any]:
        """
        Analyze user's execution patterns for insights
        """
        query = """
        SELECT content FROM memory_events 
        WHERE user_id = ? AND event_type = 'execution_result'
        ORDER BY timestamp DESC 
        LIMIT 50
        """

        rows = await self.db.fetch_all(query, [user_id])

        if not rows:
            return {"total_executions": 0, "success_rate": 0.0, "common_actions": []}

        # Analyze patterns
        executions = [json.loads(row["content"]) for row in rows]

        success_count = sum(1 for exec in executions if exec.get("success", False))
        success_rate = success_count / len(executions)

        # Find common action types
        action_counts = {}
        for exec in executions:
            plan = exec.get("plan", {})
            steps = plan.get("steps", [])
            for step in steps:
                action_type = step.get("action_type", "unknown")
                action_counts[action_type] = action_counts.get(action_type, 0) + 1

        common_actions = sorted(
            action_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "total_executions": len(executions),
            "success_rate": success_rate,
            "common_actions": [
                {"action": action, "count": count} for action, count in common_actions
            ],
            "average_plan_size": sum(
                len(e.get("plan", {}).get("steps", [])) for e in executions
            )
            / len(executions),
        }

    async def _get_project_context(self, user_id: str) -> Dict[str, Any]:
        """
        Get current project context from recent activity
        """
        query = """
        SELECT content FROM memory_events 
        WHERE user_id = ? AND event_type = 'context_update'
        ORDER BY timestamp DESC 
        LIMIT 1
        """

        row = await self.db.fetch_one(query, [user_id])
        if row:
            return json.loads(row["content"])

        return {}

    async def _calculate_importance(
        self, event_type: str, content: Dict[str, Any]
    ) -> float:
        """
        Calculate importance score for an event
        """

        base_importance = {
            "instruction": 0.7,
            "execution_result": 0.6,
            "error": 0.8,
            "feedback": 0.9,
            "context_update": 0.4,
            "user_preference": 0.8,
        }.get(event_type, 0.5)

        # Adjust based on content
        if event_type == "execution_result":
            if not content.get("success", True):
                base_importance += 0.2  # Failures are more important to remember

            complexity = content.get("complexity_score", 0.5)
            base_importance += complexity * 0.1

        elif event_type == "error":
            # Critical errors are very important
            if "critical" in content.get("error_type", "").lower():
                base_importance = 1.0

        return min(1.0, base_importance)

    async def _store_event(self, event: MemoryEvent):
        """
        Store event in database
        """
        query = """
        INSERT INTO memory_events (id, user_id, event_type, content, timestamp, importance, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """

        await self.db.execute(
            query,
            [
                event.id,
                event.user_id,
                event.event_type,
                json.dumps(event.content),
                event.timestamp,
                event.importance,
                json.dumps(event.tags),
            ],
        )

    async def _process_new_event(self, event: MemoryEvent):
        """
        Background processing for new events
        """

        # Update user model
        await self._update_user_model(event)

        # Extract insights
        await self._extract_insights(event)

        # Update preferences based on behavior
        if event.event_type in ["instruction", "execution_result"]:
            await self._infer_preferences(event)

    async def _search_events_by_keywords(
        self, user_id: str, query: str, event_types: List[str], limit: int
    ) -> List[MemoryEvent]:
        """
        Search events using keyword matching
        """

        # Build SQL query
        sql_query = "SELECT * FROM memory_events WHERE user_id = ?"
        params = [user_id]

        if event_types:
            placeholders = ",".join(["?" for _ in event_types])
            sql_query += f" AND event_type IN ({placeholders})"
            params.extend(event_types)

        # Add keyword search (simplified)
        keywords = query.lower().split()
        if keywords:
            keyword_conditions = []
            for keyword in keywords:
                keyword_conditions.append("LOWER(content) LIKE ?")
                params.append(f"%{keyword}%")

            if keyword_conditions:
                sql_query += f" AND ({' OR '.join(keyword_conditions)})"

        sql_query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(str(limit))

        rows = await self.db.fetch_all(sql_query, params)
        return [self._row_to_event(row) for row in rows]

    async def _generate_repo_suggestions(
        self, repo_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate suggestions based on repository context
        """
        suggestions = []

        # Analyze repo structure
        languages = repo_context.get("languages", {})
        hotspots = repo_context.get("hotspots", [])

        if "javascript" in languages or "typescript" in languages:
            suggestions.append(
                {
                    "type": "repo_insight",
                    "suggestion": "JavaScript/TypeScript project detected. Consider adding ESLint or Prettier configuration.",
                    "confidence": 0.7,
                    "category": "tooling",
                }
            )

        if "python" in languages:
            suggestions.append(
                {
                    "type": "repo_insight",
                    "suggestion": "Python project detected. Consider adding type hints or updating dependencies.",
                    "confidence": 0.7,
                    "category": "code_quality",
                }
            )

        # Check for common patterns
        if any("test" in file.lower() for file in hotspots):
            suggestions.append(
                {
                    "type": "repo_insight",
                    "suggestion": "Test files detected. Consider running test coverage analysis.",
                    "confidence": 0.6,
                    "category": "testing",
                }
            )

        return suggestions

    def _row_to_event(self, row: Dict[str, Any]) -> MemoryEvent:
        """
        Convert database row to MemoryEvent object
        """
        return MemoryEvent(
            id=row["id"],
            user_id=row["user_id"],
            event_type=row["event_type"],
            content=(
                json.loads(row["content"])
                if isinstance(row["content"], str)
                else row["content"]
            ),
            timestamp=(
                row["timestamp"]
                if isinstance(row["timestamp"], datetime)
                else datetime.fromisoformat(row["timestamp"])
            ),
            importance=row["importance"],
            tags=(
                json.loads(row["tags"])
                if isinstance(row["tags"], str)
                else (row["tags"] or [])
            ),
        )

    async def _update_user_model(self, event: MemoryEvent):
        """
        Update internal user model based on new event
        """
        # This would update user preferences, skill level estimates, etc.
        # Implementation depends on the specific user modeling approach
        pass

    async def _extract_insights(self, event: MemoryEvent):
        """
        Extract actionable insights from events
        """
        # This would analyze patterns, detect issues, suggest improvements, etc.
        pass

    async def _infer_preferences(self, event: MemoryEvent):
        """
        Infer user preferences from behavior
        """
        # This would analyze user choices to infer preferences automatically
        pass

    async def _process_feedback(
        self, user_id: str, execution_id: str, feedback: Dict[str, Any]
    ):
        """
        Process user feedback for learning
        """
        # This would update models based on user feedback
        pass

    async def _cleanup_events_before_date(
        self, user_id: str, event_type: str, cutoff_date: datetime
    ):
        """
        Clean up events before a certain date
        """
        query = """
        DELETE FROM memory_events 
        WHERE user_id = ? AND event_type = ? AND timestamp < ?
        """

        params = [event_type, cutoff_date]
        if user_id:
            query = query.replace("user_id = ? AND", "user_id = ? AND")
            params.insert(0, user_id)
        else:
            query = query.replace("WHERE user_id = ? AND", "WHERE")

        await self.db.execute(query, params)
