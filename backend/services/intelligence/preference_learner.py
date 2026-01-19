"""
Preference Learning Service for NAVI.

Learns user preferences from feedback, interactions, and behavior
to improve personalization over time.

Features:
- Learn from explicit feedback (thumbs up/down)
- Learn from implicit signals (acceptance/rejection of suggestions)
- Update preferences based on patterns
- Decay old preferences over time
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from backend.database.models.memory import (
    UserFeedback,
    UserPreferences,
    UserPattern,
)

logger = logging.getLogger(__name__)


class PreferenceLearner:
    """
    Service for learning and updating user preferences.

    Analyzes feedback, interactions, and behavioral patterns to
    continuously improve understanding of user preferences.
    """

    # Learning rate for preference updates
    LEARNING_RATE = 0.1
    # Decay rate for old preferences (per day)
    DECAY_RATE = 0.01
    # Minimum confidence to apply learned preference
    MIN_CONFIDENCE = 0.6
    # Number of feedback items to trigger preference update
    FEEDBACK_THRESHOLD = 5

    def __init__(self, db: Session):
        """
        Initialize the preference learner.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    # =========================================================================
    # Learning from Feedback
    # =========================================================================

    def learn_from_feedback(self, user_id: int) -> Dict[str, Any]:
        """
        Analyze user feedback to learn preferences.

        Args:
            user_id: User ID to analyze

        Returns:
            Dictionary of learned preferences
        """
        # Get recent feedback
        recent_feedback = (
            self.db.query(UserFeedback)
            .filter(UserFeedback.user_id == user_id)
            .order_by(desc(UserFeedback.created_at))
            .limit(100)
            .all()
        )

        if len(recent_feedback) < self.FEEDBACK_THRESHOLD:
            return {"message": "Not enough feedback to learn from"}

        learned = {
            "response_preferences": self._analyze_response_feedback(recent_feedback),
            "content_preferences": self._analyze_content_feedback(recent_feedback),
            "corrections": self._analyze_corrections(recent_feedback),
        }

        # Apply learned preferences
        self._apply_learned_preferences(user_id, learned)

        return learned

    def _analyze_response_feedback(
        self,
        feedback: List[UserFeedback],
    ) -> Dict[str, Any]:
        """Analyze feedback to learn response style preferences."""
        positive = [f for f in feedback if f.feedback_type == "positive"]
        negative = [f for f in feedback if f.feedback_type == "negative"]

        analysis = {
            "positive_count": len(positive),
            "negative_count": len(negative),
            "signals": [],
        }

        # Analyze response length preferences
        pos_lengths = []
        neg_lengths = []

        for f in positive:
            if f.response_text:
                pos_lengths.append(len(f.response_text))

        for f in negative:
            if f.response_text:
                neg_lengths.append(len(f.response_text))

        if pos_lengths and neg_lengths:
            avg_pos_length = sum(pos_lengths) / len(pos_lengths)
            avg_neg_length = sum(neg_lengths) / len(neg_lengths)

            if avg_pos_length < avg_neg_length * 0.7:
                analysis["signals"].append({
                    "type": "verbosity_preference",
                    "value": "brief",
                    "confidence": 0.7,
                })
            elif avg_pos_length > avg_neg_length * 1.3:
                analysis["signals"].append({
                    "type": "verbosity_preference",
                    "value": "detailed",
                    "confidence": 0.7,
                })

        return analysis

    def _analyze_content_feedback(
        self,
        feedback: List[UserFeedback],
    ) -> Dict[str, Any]:
        """Analyze feedback to learn content preferences."""
        # Analyze query patterns in positive vs negative feedback
        positive_queries = [f.query_text for f in feedback if f.feedback_type == "positive" and f.query_text]
        negative_queries = [f.query_text for f in feedback if f.feedback_type == "negative" and f.query_text]

        analysis = {
            "preferred_topics": [],
            "avoided_topics": [],
        }

        # Simple keyword extraction (can be enhanced with NLP)
        positive_keywords = self._extract_keywords(positive_queries)
        negative_keywords = self._extract_keywords(negative_queries)

        # Find keywords more common in positive feedback
        for keyword, count in positive_keywords.items():
            neg_count = negative_keywords.get(keyword, 0)
            if count > neg_count * 2 and count >= 3:
                analysis["preferred_topics"].append({
                    "topic": keyword,
                    "positive_count": count,
                    "negative_count": neg_count,
                })

        return analysis

    def _extract_keywords(self, texts: List[str]) -> Dict[str, int]:
        """Extract keyword frequencies from texts."""
        from collections import Counter

        # Common words to ignore
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "can",
            "to", "of", "in", "for", "on", "with", "at", "by", "from",
            "this", "that", "these", "those", "it", "its", "they", "them",
            "their", "what", "which", "who", "how", "when", "where", "why",
            "i", "me", "my", "you", "your", "we", "our", "and", "or", "but",
        }

        words = []
        for text in texts:
            if not text:
                continue
            # Simple tokenization
            text_words = text.lower().split()
            words.extend([w.strip(".,!?;:") for w in text_words if len(w) > 3 and w.lower() not in stop_words])

        return dict(Counter(words).most_common(20))

    def _analyze_corrections(
        self,
        feedback: List[UserFeedback],
    ) -> Dict[str, Any]:
        """Analyze correction feedback to learn specific preferences."""
        corrections = [f for f in feedback if f.feedback_type == "correction"]

        analysis = {
            "correction_count": len(corrections),
            "patterns": [],
        }

        for correction in corrections:
            if correction.feedback_data:
                correction_type = correction.feedback_data.get("correction_type")
                if correction_type:
                    analysis["patterns"].append({
                        "type": correction_type,
                        "details": correction.feedback_data.get("details"),
                    })

        return analysis

    def _apply_learned_preferences(
        self,
        user_id: int,
        learned: Dict[str, Any],
    ) -> None:
        """Apply learned preferences to user profile."""
        preferences = (
            self.db.query(UserPreferences)
            .filter(UserPreferences.user_id == user_id)
            .first()
        )

        if not preferences:
            preferences = UserPreferences(user_id=user_id)
            self.db.add(preferences)

        # Update inferred preferences
        inferred = preferences.inferred_preferences or {}

        # Apply response preferences
        response_prefs = learned.get("response_preferences", {})
        for signal in response_prefs.get("signals", []):
            if signal["type"] == "verbosity_preference" and signal["confidence"] >= self.MIN_CONFIDENCE:
                inferred["learned_verbosity"] = signal["value"]
                inferred["verbosity_confidence"] = signal["confidence"]

        # Apply content preferences
        content_prefs = learned.get("content_preferences", {})
        if content_prefs.get("preferred_topics"):
            inferred["preferred_topics"] = [t["topic"] for t in content_prefs["preferred_topics"][:5]]

        # Store learning timestamp
        inferred["last_learned"] = datetime.utcnow().isoformat()
        inferred["feedback_analyzed"] = response_prefs.get("positive_count", 0) + response_prefs.get("negative_count", 0)

        preferences.inferred_preferences = inferred
        self.db.commit()

    # =========================================================================
    # Learning from Activity Patterns
    # =========================================================================

    def learn_from_patterns(self, user_id: int) -> Dict[str, Any]:
        """
        Update preferences based on detected user patterns.

        Args:
            user_id: User ID

        Returns:
            Dictionary of preference updates
        """
        # Get user patterns
        patterns = (
            self.db.query(UserPattern)
            .filter(
                and_(
                    UserPattern.user_id == user_id,
                    UserPattern.confidence >= self.MIN_CONFIDENCE,
                )
            )
            .all()
        )

        if not patterns:
            return {"message": "No patterns to learn from"}

        updates = []

        for pattern in patterns:
            update = self._pattern_to_preference(pattern)
            if update:
                updates.append(update)

        # Apply updates
        if updates:
            self._apply_pattern_preferences(user_id, updates)

        return {"updates": updates}

    def _pattern_to_preference(
        self,
        pattern: UserPattern,
    ) -> Optional[Dict[str, Any]]:
        """Convert a detected pattern to a preference update."""
        if pattern.pattern_type == "language_preference":
            return {
                "preference": "preferred_language",
                "value": pattern.pattern_data.get("language"),
                "confidence": pattern.confidence,
                "source": "activity_pattern",
            }

        if pattern.pattern_type == "framework_preference":
            return {
                "preference": "preferred_framework",
                "value": pattern.pattern_data.get("framework"),
                "confidence": pattern.confidence,
                "source": "activity_pattern",
            }

        return None

    def _apply_pattern_preferences(
        self,
        user_id: int,
        updates: List[Dict[str, Any]],
    ) -> None:
        """Apply pattern-based preference updates."""
        preferences = (
            self.db.query(UserPreferences)
            .filter(UserPreferences.user_id == user_id)
            .first()
        )

        if not preferences:
            preferences = UserPreferences(user_id=user_id)
            self.db.add(preferences)

        for update in updates:
            pref_name = update["preference"]
            value = update["value"]
            confidence = update["confidence"]

            # Only update if confidence is high enough
            if confidence < self.MIN_CONFIDENCE:
                continue

            # Check if we should override existing preference
            current_value = getattr(preferences, pref_name, None)

            if current_value is None:
                # No existing preference, apply learned one
                setattr(preferences, pref_name, value)

                # Track in inferred preferences
                inferred = preferences.inferred_preferences or {}
                inferred[f"{pref_name}_learned"] = True
                inferred[f"{pref_name}_confidence"] = confidence
                preferences.inferred_preferences = inferred

        self.db.commit()

    # =========================================================================
    # Preference Decay
    # =========================================================================

    def decay_old_preferences(self, user_id: int, days_inactive: int = 30) -> Dict[str, Any]:
        """
        Decay confidence in old learned preferences.

        Args:
            user_id: User ID
            days_inactive: Days of inactivity before decay applies

        Returns:
            Dictionary of decayed preferences
        """
        preferences = (
            self.db.query(UserPreferences)
            .filter(UserPreferences.user_id == user_id)
            .first()
        )

        if not preferences or not preferences.inferred_preferences:
            return {"message": "No inferred preferences to decay"}

        inferred = preferences.inferred_preferences
        last_learned = inferred.get("last_learned")

        if not last_learned:
            return {"message": "No learning timestamp found"}

        last_learned_dt = datetime.fromisoformat(last_learned)
        days_since = (datetime.utcnow() - last_learned_dt).days

        if days_since < days_inactive:
            return {"message": f"Preferences still fresh ({days_since} days old)"}

        # Apply decay
        decay_factor = 1 - (self.DECAY_RATE * (days_since - days_inactive))
        decay_factor = max(0.5, decay_factor)  # Don't decay below 50%

        decayed = []

        for key in list(inferred.keys()):
            if key.endswith("_confidence"):
                original = inferred[key]
                inferred[key] = round(original * decay_factor, 2)
                decayed.append({
                    "preference": key.replace("_confidence", ""),
                    "original_confidence": original,
                    "new_confidence": inferred[key],
                })

        preferences.inferred_preferences = inferred
        self.db.commit()

        return {
            "decay_factor": decay_factor,
            "days_since_learning": days_since,
            "decayed_preferences": decayed,
        }

    # =========================================================================
    # Preference Retrieval
    # =========================================================================

    def get_effective_preferences(self, user_id: int) -> Dict[str, Any]:
        """
        Get effective preferences combining explicit and learned preferences.

        Args:
            user_id: User ID

        Returns:
            Dictionary of effective preferences
        """
        preferences = (
            self.db.query(UserPreferences)
            .filter(UserPreferences.user_id == user_id)
            .first()
        )

        if not preferences:
            return self._default_preferences()

        effective = {
            # Explicit preferences take priority
            "preferred_language": preferences.preferred_language,
            "preferred_framework": preferences.preferred_framework,
            "response_verbosity": preferences.response_verbosity,
            "explanation_level": preferences.explanation_level,
            "theme": preferences.theme,
            "code_style": preferences.code_style or {},
        }

        # Add inferred preferences where explicit ones are missing
        inferred = preferences.inferred_preferences or {}

        if not effective["preferred_language"] and inferred.get("preferred_language_learned"):
            effective["preferred_language"] = inferred.get("learned_language")
            effective["language_is_inferred"] = True

        if not effective["preferred_framework"] and inferred.get("preferred_framework_learned"):
            effective["preferred_framework"] = inferred.get("learned_framework")
            effective["framework_is_inferred"] = True

        # Apply learned verbosity if confidence is high
        learned_verbosity = inferred.get("learned_verbosity")
        verbosity_confidence = inferred.get("verbosity_confidence", 0)
        if learned_verbosity and verbosity_confidence >= self.MIN_CONFIDENCE:
            effective["learned_verbosity"] = learned_verbosity
            effective["verbosity_confidence"] = verbosity_confidence

        # Add preferred topics
        if inferred.get("preferred_topics"):
            effective["preferred_topics"] = inferred["preferred_topics"]

        return effective

    def _default_preferences(self) -> Dict[str, Any]:
        """Return default preferences for new users."""
        return {
            "preferred_language": None,
            "preferred_framework": None,
            "response_verbosity": "balanced",
            "explanation_level": "intermediate",
            "theme": "dark",
            "code_style": {},
        }


def get_preference_learner(db: Session) -> PreferenceLearner:
    """Factory function to create PreferenceLearner."""
    return PreferenceLearner(db)
