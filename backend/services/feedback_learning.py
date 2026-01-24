"""
Feedback Learning System for NAVI

Tracks user interactions to continuously improve NAVI's suggestions:
1. Accept/Reject tracking - what patterns work for each org/team/user
2. Modification tracking - how users modify NAVI's suggestions
3. Quality scoring - rate NAVI's suggestions based on user actions
4. Learning signals - feed insights back into prompt generation

This creates a flywheel where NAVI gets better over time for each
organization based on their specific preferences and patterns.
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)


class FeedbackType(Enum):
    """Types of user feedback on NAVI suggestions."""

    ACCEPTED = "accepted"  # User accepted as-is
    ACCEPTED_MODIFIED = "modified"  # User accepted with changes
    REJECTED = "rejected"  # User rejected completely
    IGNORED = "ignored"  # User didn't respond (timeout)
    PARTIAL = "partial"  # User accepted some parts


class SuggestionCategory(Enum):
    """Categories of NAVI suggestions."""

    FILE_CREATE = "file_create"
    FILE_EDIT = "file_edit"
    FILE_DELETE = "file_delete"
    COMMAND_RUN = "command_run"
    EXPLANATION = "explanation"
    REFACTOR = "refactor"
    FIX = "fix"
    TEST = "test"
    DOCUMENTATION = "documentation"


@dataclass
class Suggestion:
    """A single suggestion made by NAVI."""

    id: str
    category: SuggestionCategory
    content: str  # The suggested code/command/etc.
    context: str  # The user's original request
    language: Optional[str] = None
    framework: Optional[str] = None

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    org_id: Optional[str] = None
    team_id: Optional[str] = None
    user_id: Optional[str] = None


@dataclass
class FeedbackRecord:
    """Record of user feedback on a suggestion."""

    id: str
    suggestion_id: str
    feedback_type: FeedbackType

    # For modified suggestions, track what changed
    original_content: str
    modified_content: Optional[str] = None

    # Diff analysis
    additions: int = 0
    deletions: int = 0

    # User provided reason (optional)
    reason: Optional[str] = None

    # Timing
    response_time_seconds: float = 0.0  # How long user took to respond
    timestamp: datetime = field(default_factory=datetime.now)

    # Context
    org_id: Optional[str] = None
    team_id: Optional[str] = None
    user_id: Optional[str] = None


@dataclass
class LearningInsight:
    """An insight learned from feedback patterns."""

    id: str
    insight_type: (
        str  # "pattern_preferred", "pattern_avoided", "style_preference", etc.
    )
    description: str

    # What triggered this insight
    evidence: List[str] = field(default_factory=list)  # Feedback IDs
    confidence: float = 0.0  # 0-1 confidence score

    # Scope
    org_id: Optional[str] = None
    team_id: Optional[str] = None
    user_id: Optional[str] = None
    language: Optional[str] = None
    framework: Optional[str] = None

    # Lifecycle
    created_at: datetime = field(default_factory=datetime.now)
    last_reinforced: datetime = field(default_factory=datetime.now)
    times_reinforced: int = 1


class FeedbackStore:
    """
    Storage for feedback and learning data.
    In production, this would be backed by a database.
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = Path(
            storage_path
            or os.getenv("NAVI_FEEDBACK_PATH", os.path.expanduser("~/.navi/feedback"))
        )
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # In-memory state
        self.suggestions: Dict[str, Suggestion] = {}
        self.feedback_records: Dict[str, FeedbackRecord] = {}
        self.insights: Dict[str, LearningInsight] = {}

        # Statistics cache
        self._stats_cache: Dict[str, Dict] = {}
        self._stats_cache_time: Optional[datetime] = None

        self._load_from_disk()

    def _load_from_disk(self):
        """Load existing data from disk."""
        feedback_file = self.storage_path / "feedback.json"
        if feedback_file.exists():
            try:
                data = json.loads(feedback_file.read_text())
                # Load suggestions
                for s in data.get("suggestions", []):
                    suggestion = Suggestion(
                        id=s["id"],
                        category=SuggestionCategory(s["category"]),
                        content=s["content"],
                        context=s["context"],
                        language=s.get("language"),
                        framework=s.get("framework"),
                        org_id=s.get("org_id"),
                        team_id=s.get("team_id"),
                        user_id=s.get("user_id"),
                    )
                    self.suggestions[suggestion.id] = suggestion

                # Load feedback
                for f in data.get("feedback", []):
                    record = FeedbackRecord(
                        id=f["id"],
                        suggestion_id=f["suggestion_id"],
                        feedback_type=FeedbackType(f["feedback_type"]),
                        original_content=f["original_content"],
                        modified_content=f.get("modified_content"),
                        additions=f.get("additions", 0),
                        deletions=f.get("deletions", 0),
                        reason=f.get("reason"),
                        response_time_seconds=f.get("response_time_seconds", 0),
                        org_id=f.get("org_id"),
                        team_id=f.get("team_id"),
                        user_id=f.get("user_id"),
                    )
                    self.feedback_records[record.id] = record

                # Load insights
                for i in data.get("insights", []):
                    insight = LearningInsight(
                        id=i["id"],
                        insight_type=i["insight_type"],
                        description=i["description"],
                        evidence=i.get("evidence", []),
                        confidence=i.get("confidence", 0),
                        org_id=i.get("org_id"),
                        team_id=i.get("team_id"),
                        user_id=i.get("user_id"),
                        language=i.get("language"),
                        framework=i.get("framework"),
                        times_reinforced=i.get("times_reinforced", 1),
                    )
                    self.insights[insight.id] = insight

                logger.info(
                    f"Loaded feedback data: {len(self.suggestions)} suggestions, "
                    f"{len(self.feedback_records)} feedback records, "
                    f"{len(self.insights)} insights"
                )
            except Exception as e:
                logger.error(f"Error loading feedback data: {e}")

    def _save_to_disk(self):
        """Persist data to disk."""
        feedback_file = self.storage_path / "feedback.json"
        data = {
            "suggestions": [
                {
                    "id": s.id,
                    "category": s.category.value,
                    "content": s.content,
                    "context": s.context,
                    "language": s.language,
                    "framework": s.framework,
                    "timestamp": s.timestamp.isoformat() if s.timestamp else None,
                    "org_id": s.org_id,
                    "team_id": s.team_id,
                    "user_id": s.user_id,
                }
                for s in self.suggestions.values()
            ],
            "feedback": [
                {
                    "id": f.id,
                    "suggestion_id": f.suggestion_id,
                    "feedback_type": f.feedback_type.value,
                    "original_content": f.original_content,
                    "modified_content": f.modified_content,
                    "additions": f.additions,
                    "deletions": f.deletions,
                    "reason": f.reason,
                    "response_time_seconds": f.response_time_seconds,
                    "timestamp": f.timestamp.isoformat() if f.timestamp else None,
                    "org_id": f.org_id,
                    "team_id": f.team_id,
                    "user_id": f.user_id,
                }
                for f in self.feedback_records.values()
            ],
            "insights": [
                {
                    "id": i.id,
                    "insight_type": i.insight_type,
                    "description": i.description,
                    "evidence": i.evidence,
                    "confidence": i.confidence,
                    "org_id": i.org_id,
                    "team_id": i.team_id,
                    "user_id": i.user_id,
                    "language": i.language,
                    "framework": i.framework,
                    "created_at": i.created_at.isoformat() if i.created_at else None,
                    "last_reinforced": (
                        i.last_reinforced.isoformat() if i.last_reinforced else None
                    ),
                    "times_reinforced": i.times_reinforced,
                }
                for i in self.insights.values()
            ],
        }
        feedback_file.write_text(json.dumps(data, indent=2, default=str))

    def record_suggestion(self, suggestion: Suggestion) -> None:
        """Record a new suggestion made by NAVI."""
        self.suggestions[suggestion.id] = suggestion
        self._save_to_disk()

    def record_feedback(self, feedback: FeedbackRecord) -> None:
        """Record user feedback on a suggestion."""
        self.feedback_records[feedback.id] = feedback
        self._save_to_disk()
        # Invalidate stats cache
        self._stats_cache_time = None

    def add_insight(self, insight: LearningInsight) -> None:
        """Add or update a learning insight."""
        existing = self.insights.get(insight.id)
        if existing:
            # Reinforce existing insight
            existing.times_reinforced += 1
            existing.last_reinforced = datetime.now()
            existing.confidence = min(1.0, existing.confidence + 0.1)
            existing.evidence.extend(insight.evidence)
        else:
            self.insights[insight.id] = insight
        self._save_to_disk()

    def get_insights(
        self,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
        language: Optional[str] = None,
        min_confidence: float = 0.5,
    ) -> List[LearningInsight]:
        """Get relevant insights with filtering."""
        results = []
        for insight in self.insights.values():
            # Skip low-confidence insights
            if insight.confidence < min_confidence:
                continue

            # Filter by scope (more specific scopes override broader ones)
            if user_id and insight.user_id and insight.user_id != user_id:
                continue
            if team_id and insight.team_id and insight.team_id != team_id:
                continue
            if org_id and insight.org_id and insight.org_id != org_id:
                continue
            if language and insight.language and insight.language != language:
                continue

            results.append(insight)

        # Sort by confidence and recency
        results.sort(key=lambda x: (x.confidence, x.times_reinforced), reverse=True)
        return results


class FeedbackAnalyzer:
    """
    Analyzes feedback patterns to generate learning insights.
    """

    def __init__(self, store: FeedbackStore):
        self.store = store

    def analyze_feedback(self, feedback: FeedbackRecord) -> List[LearningInsight]:
        """Analyze a single feedback record for insights."""
        insights = []
        suggestion = self.store.suggestions.get(feedback.suggestion_id)

        if not suggestion:
            return insights

        # Insight 1: Rejection patterns
        if feedback.feedback_type == FeedbackType.REJECTED:
            insight = self._analyze_rejection(feedback, suggestion)
            if insight:
                insights.append(insight)

        # Insight 2: Modification patterns
        elif feedback.feedback_type == FeedbackType.ACCEPTED_MODIFIED:
            insight = self._analyze_modification(feedback, suggestion)
            if insight:
                insights.append(insight)

        # Insight 3: Quick acceptance (high confidence pattern)
        elif feedback.feedback_type == FeedbackType.ACCEPTED:
            if feedback.response_time_seconds < 5.0:  # Very quick acceptance
                insight = self._analyze_quick_acceptance(feedback, suggestion)
                if insight:
                    insights.append(insight)

        return insights

    def _analyze_rejection(
        self, feedback: FeedbackRecord, suggestion: Suggestion
    ) -> Optional[LearningInsight]:
        """Analyze why a suggestion was rejected."""
        insight_id = hashlib.sha256(
            f"rejected:{suggestion.category.value}:{feedback.org_id}".encode()
        ).hexdigest()[:16]

        # Check if this is a pattern
        similar_rejections = self._find_similar_rejections(suggestion)

        if len(similar_rejections) >= 2:
            return LearningInsight(
                id=insight_id,
                insight_type="pattern_rejected",
                description=f"Users frequently reject {suggestion.category.value} suggestions. Consider reviewing this approach.",
                evidence=[feedback.id],
                confidence=min(0.9, 0.3 + len(similar_rejections) * 0.1),
                org_id=feedback.org_id,
                team_id=feedback.team_id,
                language=suggestion.language,
            )

        return None

    def _analyze_modification(
        self, feedback: FeedbackRecord, suggestion: Suggestion
    ) -> Optional[LearningInsight]:
        """Analyze how a suggestion was modified."""
        if not feedback.modified_content:
            return None

        # Calculate modification ratio
        original_len = len(feedback.original_content)
        len(feedback.modified_content)

        if original_len == 0:
            return None

        # Detect what kind of changes were made
        changes = self._diff_content(
            feedback.original_content, feedback.modified_content
        )

        insight_id = hashlib.sha256(
            f"modified:{suggestion.category.value}:{feedback.org_id}:{changes.get('type', 'unknown')}".encode()
        ).hexdigest()[:16]

        if changes.get("type") == "style_change":
            return LearningInsight(
                id=insight_id,
                insight_type="style_preference",
                description=f"Users prefer {changes.get('preference', 'different')} style",
                evidence=[feedback.id],
                confidence=0.4,
                org_id=feedback.org_id,
                team_id=feedback.team_id,
                language=suggestion.language,
            )

        return None

    def _analyze_quick_acceptance(
        self, feedback: FeedbackRecord, suggestion: Suggestion
    ) -> Optional[LearningInsight]:
        """Quick acceptance indicates high-quality suggestion."""
        insight_id = hashlib.sha256(
            f"preferred:{suggestion.category.value}:{suggestion.language}:{feedback.org_id}".encode()
        ).hexdigest()[:16]

        return LearningInsight(
            id=insight_id,
            insight_type="pattern_preferred",
            description=f"This {suggestion.category.value} pattern is quickly accepted",
            evidence=[feedback.id],
            confidence=0.5,
            org_id=feedback.org_id,
            team_id=feedback.team_id,
            language=suggestion.language,
            framework=suggestion.framework,
        )

    def _find_similar_rejections(self, suggestion: Suggestion) -> List[FeedbackRecord]:
        """Find similar rejected suggestions."""
        similar = []
        for feedback in self.store.feedback_records.values():
            if feedback.feedback_type != FeedbackType.REJECTED:
                continue

            orig_suggestion = self.store.suggestions.get(feedback.suggestion_id)
            if not orig_suggestion:
                continue

            # Check similarity
            if (
                orig_suggestion.category == suggestion.category
                and orig_suggestion.language == suggestion.language
                and orig_suggestion.org_id == suggestion.org_id
            ):
                similar.append(feedback)

        return similar

    def _diff_content(self, original: str, modified: str) -> Dict:
        """Analyze differences between original and modified content."""
        changes = {
            "type": "unknown",
            "additions": 0,
            "deletions": 0,
        }

        # Simple line-based diff
        orig_lines = set(original.strip().split("\n"))
        mod_lines = set(modified.strip().split("\n"))

        added = mod_lines - orig_lines
        removed = orig_lines - mod_lines

        changes["additions"] = len(added)
        changes["deletions"] = len(removed)

        # Detect style changes
        if len(added) == len(removed):
            # Might be style change
            if any("'" in line for line in added) and any(
                '"' in line for line in removed
            ):
                changes["type"] = "style_change"
                changes["preference"] = "single_quotes"
            elif any('"' in line for line in added) and any(
                "'" in line for line in removed
            ):
                changes["type"] = "style_change"
                changes["preference"] = "double_quotes"
            elif any("\t" in line for line in added) and any(
                "  " in line for line in removed
            ):
                changes["type"] = "style_change"
                changes["preference"] = "tabs"
            elif any("  " in line for line in added) and any(
                "\t" in line for line in removed
            ):
                changes["type"] = "style_change"
                changes["preference"] = "spaces"

        return changes

    def generate_aggregate_insights(
        self, org_id: str, team_id: Optional[str] = None
    ) -> List[LearningInsight]:
        """Generate aggregate insights from all feedback."""
        insights = []

        # Acceptance rate by category
        category_stats = defaultdict(
            lambda: {"accepted": 0, "rejected": 0, "modified": 0}
        )

        for feedback in self.store.feedback_records.values():
            if feedback.org_id != org_id:
                continue
            if team_id and feedback.team_id != team_id:
                continue

            suggestion = self.store.suggestions.get(feedback.suggestion_id)
            if not suggestion:
                continue

            category = suggestion.category.value
            if feedback.feedback_type == FeedbackType.ACCEPTED:
                category_stats[category]["accepted"] += 1
            elif feedback.feedback_type == FeedbackType.REJECTED:
                category_stats[category]["rejected"] += 1
            elif feedback.feedback_type == FeedbackType.ACCEPTED_MODIFIED:
                category_stats[category]["modified"] += 1

        # Generate insights for each category
        for category, stats in category_stats.items():
            total = sum(stats.values())
            if total < 5:
                continue  # Not enough data

            acceptance_rate = (stats["accepted"] + stats["modified"]) / total

            insight_id = hashlib.sha256(
                f"aggregate:{category}:{org_id}:{team_id or 'all'}".encode()
            ).hexdigest()[:16]

            if acceptance_rate < 0.5:
                insights.append(
                    LearningInsight(
                        id=insight_id,
                        insight_type="low_acceptance",
                        description=f"{category} suggestions have low acceptance ({acceptance_rate:.0%}). Review approach.",
                        confidence=min(0.9, 0.3 + (total / 20)),
                        org_id=org_id,
                        team_id=team_id,
                    )
                )
            elif acceptance_rate > 0.8:
                insights.append(
                    LearningInsight(
                        id=insight_id,
                        insight_type="high_acceptance",
                        description=f"{category} suggestions have high acceptance ({acceptance_rate:.0%}). Good pattern.",
                        confidence=min(0.9, 0.3 + (total / 20)),
                        org_id=org_id,
                        team_id=team_id,
                    )
                )

        return insights


class FeedbackLearningManager:
    """
    Main manager for the feedback learning system.
    Integrates storage, analysis, and prompt enhancement.
    """

    def __init__(self, store: FeedbackStore = None):
        self.store = store or FeedbackStore()
        self.analyzer = FeedbackAnalyzer(self.store)

    def track_suggestion(
        self,
        suggestion_id: str,
        category: SuggestionCategory,
        content: str,
        context: str,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
        language: Optional[str] = None,
        framework: Optional[str] = None,
    ) -> Suggestion:
        """Track a new suggestion made by NAVI."""
        suggestion = Suggestion(
            id=suggestion_id,
            category=category,
            content=content,
            context=context,
            language=language,
            framework=framework,
            org_id=org_id,
            team_id=team_id,
            user_id=user_id,
        )
        self.store.record_suggestion(suggestion)
        return suggestion

    def record_user_feedback(
        self,
        suggestion_id: str,
        feedback_type: FeedbackType,
        original_content: str,
        modified_content: Optional[str] = None,
        reason: Optional[str] = None,
        response_time: float = 0.0,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Record user feedback on a suggestion."""
        feedback_id = hashlib.sha256(
            f"{suggestion_id}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        # Calculate diff stats if modified
        additions = 0
        deletions = 0
        if modified_content and original_content:
            orig_lines = original_content.strip().split("\n")
            mod_lines = modified_content.strip().split("\n")
            additions = max(0, len(mod_lines) - len(orig_lines))
            deletions = max(0, len(orig_lines) - len(mod_lines))

        feedback = FeedbackRecord(
            id=feedback_id,
            suggestion_id=suggestion_id,
            feedback_type=feedback_type,
            original_content=original_content,
            modified_content=modified_content,
            additions=additions,
            deletions=deletions,
            reason=reason,
            response_time_seconds=response_time,
            org_id=org_id,
            team_id=team_id,
            user_id=user_id,
        )

        self.store.record_feedback(feedback)

        # Analyze for insights
        insights = self.analyzer.analyze_feedback(feedback)
        for insight in insights:
            self.store.add_insight(insight)

        logger.info(
            f"Recorded {feedback_type.value} feedback for suggestion {suggestion_id}"
        )

    def get_learning_context(
        self,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> str:
        """
        Get learning-based context for prompt enhancement.
        Returns insights that should guide NAVI's responses.
        """
        insights = self.store.get_insights(
            org_id=org_id,
            team_id=team_id,
            user_id=user_id,
            language=language,
            min_confidence=0.5,
        )

        if not insights:
            return ""

        lines = ["=== LEARNED PREFERENCES ===\n"]

        for insight in insights[:10]:  # Top 10 insights
            if insight.insight_type == "pattern_preferred":
                lines.append(f"✓ {insight.description}")
            elif insight.insight_type == "pattern_rejected":
                lines.append(f"✗ Avoid: {insight.description}")
            elif insight.insight_type == "style_preference":
                lines.append(f"• Style: {insight.description}")
            else:
                lines.append(f"• {insight.description}")

        return "\n".join(lines)

    def get_acceptance_stats(
        self,
        org_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
        days: int = 30,
    ) -> Dict:
        """Get acceptance statistics for the specified scope."""
        cutoff = datetime.now() - timedelta(days=days)

        stats = {
            "total": 0,
            "accepted": 0,
            "modified": 0,
            "rejected": 0,
            "ignored": 0,
            "acceptance_rate": 0.0,
            "by_category": defaultdict(lambda: {"total": 0, "accepted": 0}),
        }

        for feedback in self.store.feedback_records.values():
            # Filter by scope
            if org_id and feedback.org_id != org_id:
                continue
            if team_id and feedback.team_id != team_id:
                continue
            if user_id and feedback.user_id != user_id:
                continue

            # Filter by time
            if feedback.timestamp and feedback.timestamp < cutoff:
                continue

            stats["total"] += 1

            suggestion = self.store.suggestions.get(feedback.suggestion_id)
            category = suggestion.category.value if suggestion else "unknown"

            if feedback.feedback_type == FeedbackType.ACCEPTED:
                stats["accepted"] += 1
                stats["by_category"][category]["accepted"] += 1
            elif feedback.feedback_type == FeedbackType.ACCEPTED_MODIFIED:
                stats["modified"] += 1
                stats["by_category"][category]["accepted"] += 1
            elif feedback.feedback_type == FeedbackType.REJECTED:
                stats["rejected"] += 1
            elif feedback.feedback_type == FeedbackType.IGNORED:
                stats["ignored"] += 1

            stats["by_category"][category]["total"] += 1

        if stats["total"] > 0:
            stats["acceptance_rate"] = (stats["accepted"] + stats["modified"]) / stats[
                "total"
            ]

        return stats


# ============================================================
# GLOBAL INSTANCE
# ============================================================

_feedback_manager: Optional[FeedbackLearningManager] = None


def get_feedback_manager() -> FeedbackLearningManager:
    """Get the global feedback learning manager."""
    global _feedback_manager
    if _feedback_manager is None:
        _feedback_manager = FeedbackLearningManager()
    return _feedback_manager


def track_suggestion(
    suggestion_id: str,
    category: SuggestionCategory,
    content: str,
    context: str,
    **kwargs,
) -> Suggestion:
    """Convenience function to track a suggestion."""
    return get_feedback_manager().track_suggestion(
        suggestion_id=suggestion_id,
        category=category,
        content=content,
        context=context,
        **kwargs,
    )


def record_feedback(
    suggestion_id: str,
    feedback_type: FeedbackType,
    original_content: str,
    **kwargs,
) -> None:
    """Convenience function to record feedback."""
    get_feedback_manager().record_user_feedback(
        suggestion_id=suggestion_id,
        feedback_type=feedback_type,
        original_content=original_content,
        **kwargs,
    )


def get_learning_context(
    org_id: Optional[str] = None,
    team_id: Optional[str] = None,
    user_id: Optional[str] = None,
    language: Optional[str] = None,
) -> str:
    """Convenience function to get learning context."""
    return get_feedback_manager().get_learning_context(
        org_id=org_id,
        team_id=team_id,
        user_id=user_id,
        language=language,
    )
