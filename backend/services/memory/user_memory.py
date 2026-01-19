"""
User Memory Service for NAVI.

Manages user preferences, activity tracking, and pattern detection
to enable personalized AI responses.

Features:
- User preferences storage and retrieval
- Activity tracking for learning
- Pattern detection from user behavior
- Feedback processing for improvement
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from backend.database.models.memory import (
    UserActivity,
    UserFeedback,
    UserPattern,
    UserPreferences,
)

logger = logging.getLogger(__name__)


class UserMemoryService:
    """
    Service for managing user-level memory and preferences.

    Provides methods to store and retrieve user preferences,
    track activities, detect patterns, and process feedback.
    """

    def __init__(self, db: Session):
        """
        Initialize the user memory service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    # =========================================================================
    # User Preferences
    # =========================================================================

    def get_preferences(self, user_id: int) -> Optional[UserPreferences]:
        """
        Get user preferences.

        Args:
            user_id: User ID

        Returns:
            UserPreferences or None if not found
        """
        return (
            self.db.query(UserPreferences)
            .filter(UserPreferences.user_id == user_id)
            .first()
        )

    def get_or_create_preferences(self, user_id: int) -> UserPreferences:
        """
        Get existing preferences or create default ones.

        Args:
            user_id: User ID

        Returns:
            UserPreferences (existing or newly created)
        """
        prefs = self.get_preferences(user_id)
        if prefs is None:
            prefs = UserPreferences(user_id=user_id)
            self.db.add(prefs)
            self.db.commit()
            self.db.refresh(prefs)
            logger.info(f"Created default preferences for user {user_id}")
        return prefs

    def update_preferences(
        self,
        user_id: int,
        **kwargs: Any,
    ) -> UserPreferences:
        """
        Update user preferences.

        Args:
            user_id: User ID
            **kwargs: Preference fields to update

        Returns:
            Updated UserPreferences
        """
        prefs = self.get_or_create_preferences(user_id)

        # Update allowed fields
        allowed_fields = {
            "preferred_language",
            "preferred_framework",
            "code_style",
            "response_verbosity",
            "explanation_level",
            "theme",
            "keyboard_shortcuts",
        }

        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(prefs, key, value)

        self.db.commit()
        self.db.refresh(prefs)
        logger.info(f"Updated preferences for user {user_id}: {list(kwargs.keys())}")
        return prefs

    def update_inferred_preferences(
        self,
        user_id: int,
        inferred: Dict[str, Any],
        merge: bool = True,
    ) -> UserPreferences:
        """
        Update inferred (learned) preferences.

        Args:
            user_id: User ID
            inferred: Inferred preferences dict
            merge: Whether to merge with existing (True) or replace (False)

        Returns:
            Updated UserPreferences
        """
        prefs = self.get_or_create_preferences(user_id)

        if merge and prefs.inferred_preferences:
            # Merge with existing
            current = dict(prefs.inferred_preferences)
            current.update(inferred)
            prefs.inferred_preferences = current
        else:
            prefs.inferred_preferences = inferred

        self.db.commit()
        self.db.refresh(prefs)
        return prefs

    # =========================================================================
    # Activity Tracking
    # =========================================================================

    def track_activity(
        self,
        user_id: int,
        activity_type: str,
        activity_data: Dict[str, Any],
        org_id: Optional[int] = None,
        workspace_path: Optional[str] = None,
        file_path: Optional[str] = None,
        language: Optional[str] = None,
        session_id: Optional[UUID] = None,
    ) -> UserActivity:
        """
        Record a user activity.

        Args:
            user_id: User ID
            activity_type: Type of activity (query, code_edit, approval, etc.)
            activity_data: Structured activity data
            org_id: Optional organization ID
            workspace_path: Optional workspace path
            file_path: Optional file path
            language: Optional programming language
            session_id: Optional session ID for grouping

        Returns:
            Created UserActivity
        """
        activity = UserActivity(
            user_id=user_id,
            org_id=org_id,
            activity_type=activity_type,
            activity_data=activity_data,
            workspace_path=workspace_path,
            file_path=file_path,
            language=language,
            session_id=session_id,
        )
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        return activity

    def get_recent_activities(
        self,
        user_id: int,
        activity_type: Optional[str] = None,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[UserActivity]:
        """
        Get recent user activities.

        Args:
            user_id: User ID
            activity_type: Optional filter by activity type
            limit: Maximum activities to return
            since: Optional filter for activities after this time

        Returns:
            List of UserActivity objects
        """
        query = self.db.query(UserActivity).filter(UserActivity.user_id == user_id)

        if activity_type:
            query = query.filter(UserActivity.activity_type == activity_type)

        if since:
            query = query.filter(UserActivity.created_at >= since)

        return query.order_by(desc(UserActivity.created_at)).limit(limit).all()

    def get_activity_stats(
        self,
        user_id: int,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get activity statistics for a user.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dictionary with activity statistics
        """
        since = datetime.utcnow() - timedelta(days=days)

        # Count by activity type
        type_counts = (
            self.db.query(
                UserActivity.activity_type,
                func.count(UserActivity.id).label("count"),
            )
            .filter(
                and_(
                    UserActivity.user_id == user_id,
                    UserActivity.created_at >= since,
                )
            )
            .group_by(UserActivity.activity_type)
            .all()
        )

        # Count by language
        language_counts = (
            self.db.query(
                UserActivity.language,
                func.count(UserActivity.id).label("count"),
            )
            .filter(
                and_(
                    UserActivity.user_id == user_id,
                    UserActivity.created_at >= since,
                    UserActivity.language.isnot(None),
                )
            )
            .group_by(UserActivity.language)
            .all()
        )

        # Total count
        total = (
            self.db.query(func.count(UserActivity.id))
            .filter(
                and_(
                    UserActivity.user_id == user_id,
                    UserActivity.created_at >= since,
                )
            )
            .scalar()
        )

        return {
            "total_activities": total or 0,
            "by_type": {t: c for t, c in type_counts},
            "by_language": {l: c for l, c in language_counts if l},
            "period_days": days,
        }

    # =========================================================================
    # Pattern Detection
    # =========================================================================

    def record_pattern(
        self,
        user_id: int,
        pattern_type: str,
        pattern_key: str,
        pattern_data: Dict[str, Any],
        confidence: float = 0.5,
    ) -> UserPattern:
        """
        Record or update a detected pattern.

        Args:
            user_id: User ID
            pattern_type: Type of pattern
            pattern_key: Unique key for the pattern
            pattern_data: Pattern details
            confidence: Confidence level [0.0, 1.0]

        Returns:
            Created or updated UserPattern
        """
        # Check if pattern exists
        existing = (
            self.db.query(UserPattern)
            .filter(
                and_(
                    UserPattern.user_id == user_id,
                    UserPattern.pattern_type == pattern_type,
                    UserPattern.pattern_key == pattern_key,
                )
            )
            .first()
        )

        if existing:
            # Update existing pattern
            existing.pattern_data = pattern_data
            existing.occurrences += 1
            # Increase confidence with more occurrences (max 0.95)
            existing.confidence = min(0.95, existing.confidence + 0.05)
            existing.last_seen = datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing

        # Create new pattern
        pattern = UserPattern(
            user_id=user_id,
            pattern_type=pattern_type,
            pattern_key=pattern_key,
            pattern_data=pattern_data,
            confidence=confidence,
        )
        self.db.add(pattern)
        self.db.commit()
        self.db.refresh(pattern)
        return pattern

    def get_patterns(
        self,
        user_id: int,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[UserPattern]:
        """
        Get user patterns.

        Args:
            user_id: User ID
            pattern_type: Optional filter by pattern type
            min_confidence: Minimum confidence threshold

        Returns:
            List of UserPattern objects
        """
        query = self.db.query(UserPattern).filter(
            and_(
                UserPattern.user_id == user_id,
                UserPattern.confidence >= min_confidence,
            )
        )

        if pattern_type:
            query = query.filter(UserPattern.pattern_type == pattern_type)

        return query.order_by(desc(UserPattern.confidence)).all()

    def get_coding_style_patterns(self, user_id: int) -> Dict[str, Any]:
        """
        Get detected coding style patterns for a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary of coding style patterns
        """
        patterns = self.get_patterns(user_id, pattern_type="coding_style", min_confidence=0.5)

        style = {}
        for p in patterns:
            style[p.pattern_key] = {
                "value": p.pattern_data,
                "confidence": p.confidence,
                "occurrences": p.occurrences,
            }
        return style

    # =========================================================================
    # Feedback Processing
    # =========================================================================

    def record_feedback(
        self,
        user_id: int,
        message_id: UUID,
        conversation_id: UUID,
        feedback_type: str,
        feedback_data: Optional[Dict[str, Any]] = None,
        query_text: Optional[str] = None,
        response_text: Optional[str] = None,
    ) -> UserFeedback:
        """
        Record user feedback on a NAVI response.

        Args:
            user_id: User ID
            message_id: ID of the message being rated
            conversation_id: ID of the conversation
            feedback_type: Type (positive, negative, correction)
            feedback_data: Additional feedback details
            query_text: Original user query
            response_text: NAVI's response

        Returns:
            Created UserFeedback
        """
        feedback = UserFeedback(
            user_id=user_id,
            message_id=message_id,
            conversation_id=conversation_id,
            feedback_type=feedback_type,
            feedback_data=feedback_data,
            query_text=query_text,
            response_text=response_text,
        )
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)

        logger.info(f"Recorded {feedback_type} feedback from user {user_id}")
        return feedback

    def get_feedback_stats(
        self,
        user_id: int,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get feedback statistics for a user.

        Args:
            user_id: User ID
            days: Number of days to analyze

        Returns:
            Dictionary with feedback statistics
        """
        since = datetime.utcnow() - timedelta(days=days)

        # Count by feedback type
        type_counts = (
            self.db.query(
                UserFeedback.feedback_type,
                func.count(UserFeedback.id).label("count"),
            )
            .filter(
                and_(
                    UserFeedback.user_id == user_id,
                    UserFeedback.created_at >= since,
                )
            )
            .group_by(UserFeedback.feedback_type)
            .all()
        )

        counts = {t: c for t, c in type_counts}
        positive = counts.get("positive", 0)
        negative = counts.get("negative", 0)
        total = sum(counts.values())

        return {
            "total_feedback": total,
            "positive": positive,
            "negative": negative,
            "corrections": counts.get("correction", 0),
            "satisfaction_rate": positive / total if total > 0 else 0.0,
            "period_days": days,
        }

    # =========================================================================
    # Context Building
    # =========================================================================

    def build_user_context(self, user_id: int) -> Dict[str, Any]:
        """
        Build comprehensive user context for NAVI responses.

        Aggregates preferences, patterns, and recent activity
        to provide personalized context.

        Args:
            user_id: User ID

        Returns:
            Dictionary with user context
        """
        # Get preferences
        prefs = self.get_preferences(user_id)

        # Get high-confidence patterns
        patterns = self.get_patterns(user_id, min_confidence=0.6)

        # Get recent activity summary
        activity_stats = self.get_activity_stats(user_id, days=7)

        context = {
            "preferences": {},
            "patterns": {},
            "recent_activity": activity_stats,
        }

        if prefs:
            context["preferences"] = {
                "language": prefs.preferred_language,
                "framework": prefs.preferred_framework,
                "code_style": prefs.code_style or {},
                "verbosity": prefs.response_verbosity,
                "explanation_level": prefs.explanation_level,
                "inferred": prefs.inferred_preferences or {},
            }

        for pattern in patterns:
            if pattern.pattern_type not in context["patterns"]:
                context["patterns"][pattern.pattern_type] = {}
            context["patterns"][pattern.pattern_type][pattern.pattern_key] = pattern.pattern_data

        return context


def get_user_memory_service(db: Session) -> UserMemoryService:
    """Factory function to create UserMemoryService."""
    return UserMemoryService(db)
