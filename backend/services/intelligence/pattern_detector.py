"""
Pattern Detection Service for NAVI.

Analyzes user behavior and code to detect patterns that can be used
to improve personalization and provide better suggestions.

Features:
- Coding style pattern detection
- Common error pattern recognition
- Workflow pattern analysis
- Language/framework preference detection
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from backend.database.models.memory import (
    UserActivity,
    UserPattern,
    CodeSymbol,
    CodePattern,
)

logger = logging.getLogger(__name__)


class PatternDetector:
    """
    Service for detecting patterns in user behavior and code.

    Analyzes user activities, code samples, and interactions to identify
    recurring patterns that can be used for personalization.
    """

    # Pattern type constants
    CODING_STYLE = "coding_style"
    COMMON_ERRORS = "common_errors"
    WORKFLOW = "workflow"
    LANGUAGE_PREFERENCE = "language_preference"
    FRAMEWORK_PREFERENCE = "framework_preference"
    NAMING_CONVENTION = "naming_convention"
    ERROR_HANDLING = "error_handling"
    TESTING_PATTERN = "testing_pattern"

    # Minimum occurrences before considering a pattern valid
    MIN_OCCURRENCES = 3
    # Confidence threshold for pattern relevance
    CONFIDENCE_THRESHOLD = 0.6

    def __init__(self, db: Session):
        """
        Initialize the pattern detector.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    # =========================================================================
    # User Behavior Pattern Detection
    # =========================================================================

    def detect_user_patterns(
        self,
        user_id: int,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Detect patterns from user's recent activity.

        Args:
            user_id: User ID to analyze
            days: Number of days of history to analyze

        Returns:
            List of detected patterns with confidence scores
        """
        since = datetime.utcnow() - timedelta(days=days)

        # Get user activities
        activities = (
            self.db.query(UserActivity)
            .filter(
                and_(
                    UserActivity.user_id == user_id,
                    UserActivity.created_at >= since,
                )
            )
            .order_by(desc(UserActivity.created_at))
            .all()
        )

        if not activities:
            return []

        detected_patterns = []

        # Detect language preferences
        lang_pattern = self._detect_language_preferences(activities)
        if lang_pattern:
            detected_patterns.append(lang_pattern)

        # Detect workflow patterns
        workflow_patterns = self._detect_workflow_patterns(activities)
        detected_patterns.extend(workflow_patterns)

        # Detect time-based patterns
        time_patterns = self._detect_time_patterns(activities)
        detected_patterns.extend(time_patterns)

        # Detect activity type patterns
        activity_patterns = self._detect_activity_type_patterns(activities)
        detected_patterns.extend(activity_patterns)

        # Store detected patterns
        for pattern in detected_patterns:
            self._store_pattern(user_id, pattern)

        return detected_patterns

    def _detect_language_preferences(
        self,
        activities: List[UserActivity],
    ) -> Optional[Dict[str, Any]]:
        """Detect preferred programming languages from activities."""
        language_counts: Counter = Counter()

        for activity in activities:
            if activity.language:
                language_counts[activity.language] += 1

        if not language_counts:
            return None

        total = sum(language_counts.values())
        top_language, count = language_counts.most_common(1)[0]

        if count < self.MIN_OCCURRENCES:
            return None

        confidence = count / total
        if confidence < self.CONFIDENCE_THRESHOLD:
            return None

        return {
            "pattern_type": self.LANGUAGE_PREFERENCE,
            "pattern_key": f"preferred_language:{top_language}",
            "pattern_data": {
                "language": top_language,
                "usage_count": count,
                "total_activities": total,
                "distribution": dict(language_counts.most_common(5)),
            },
            "confidence": round(confidence, 2),
            "occurrences": count,
        }

    def _detect_workflow_patterns(
        self,
        activities: List[UserActivity],
    ) -> List[Dict[str, Any]]:
        """Detect workflow patterns from activity sequences."""
        patterns = []

        # Group activities by session
        sessions: Dict[str, List[UserActivity]] = defaultdict(list)
        for activity in activities:
            session_key = str(activity.session_id) if activity.session_id else "unknown"
            sessions[session_key].append(activity)

        # Analyze activity sequences within sessions
        sequence_counts: Counter = Counter()
        for session_activities in sessions.values():
            if len(session_activities) < 2:
                continue

            # Sort by time
            sorted_activities = sorted(session_activities, key=lambda a: a.created_at)

            # Create activity type sequences
            for i in range(len(sorted_activities) - 1):
                sequence = f"{sorted_activities[i].activity_type} -> {sorted_activities[i + 1].activity_type}"
                sequence_counts[sequence] += 1

        # Find common sequences
        for sequence, count in sequence_counts.most_common(5):
            if count >= self.MIN_OCCURRENCES:
                total = sum(sequence_counts.values())
                confidence = count / total

                patterns.append(
                    {
                        "pattern_type": self.WORKFLOW,
                        "pattern_key": f"sequence:{sequence}",
                        "pattern_data": {
                            "sequence": sequence,
                            "count": count,
                            "total_sequences": total,
                        },
                        "confidence": round(confidence, 2),
                        "occurrences": count,
                    }
                )

        return patterns

    def _detect_time_patterns(
        self,
        activities: List[UserActivity],
    ) -> List[Dict[str, Any]]:
        """Detect time-based usage patterns."""
        patterns = []

        # Analyze hour of day
        hour_counts: Counter = Counter()
        for activity in activities:
            hour_counts[activity.created_at.hour] += 1

        if hour_counts:
            # Find peak hours
            total = sum(hour_counts.values())
            peak_hour, peak_count = hour_counts.most_common(1)[0]

            if peak_count >= self.MIN_OCCURRENCES:
                patterns.append(
                    {
                        "pattern_type": self.WORKFLOW,
                        "pattern_key": f"peak_hour:{peak_hour}",
                        "pattern_data": {
                            "peak_hour": peak_hour,
                            "count": peak_count,
                            "hourly_distribution": dict(hour_counts),
                        },
                        "confidence": round(peak_count / total, 2),
                        "occurrences": peak_count,
                    }
                )

        return patterns

    def _detect_activity_type_patterns(
        self,
        activities: List[UserActivity],
    ) -> List[Dict[str, Any]]:
        """Detect patterns in activity types."""
        patterns = []

        type_counts: Counter = Counter()
        for activity in activities:
            type_counts[activity.activity_type] += 1

        total = sum(type_counts.values())

        for activity_type, count in type_counts.most_common(3):
            if count >= self.MIN_OCCURRENCES:
                confidence = count / total
                patterns.append(
                    {
                        "pattern_type": self.WORKFLOW,
                        "pattern_key": f"frequent_activity:{activity_type}",
                        "pattern_data": {
                            "activity_type": activity_type,
                            "count": count,
                            "percentage": round(confidence * 100, 1),
                        },
                        "confidence": round(confidence, 2),
                        "occurrences": count,
                    }
                )

        return patterns

    def _store_pattern(self, user_id: int, pattern: Dict[str, Any]) -> UserPattern:
        """Store or update a detected pattern."""
        existing = (
            self.db.query(UserPattern)
            .filter(
                and_(
                    UserPattern.user_id == user_id,
                    UserPattern.pattern_type == pattern["pattern_type"],
                    UserPattern.pattern_key == pattern["pattern_key"],
                )
            )
            .first()
        )

        if existing:
            # Update existing pattern
            existing.pattern_data = pattern["pattern_data"]
            existing.confidence = pattern["confidence"]
            existing.occurrences = pattern["occurrences"]
            existing.last_seen = datetime.utcnow()
            self.db.commit()
            return existing

        # Create new pattern
        new_pattern = UserPattern(
            user_id=user_id,
            pattern_type=pattern["pattern_type"],
            pattern_key=pattern["pattern_key"],
            pattern_data=pattern["pattern_data"],
            confidence=pattern["confidence"],
            occurrences=pattern["occurrences"],
        )
        self.db.add(new_pattern)
        self.db.commit()
        self.db.refresh(new_pattern)
        return new_pattern

    # =========================================================================
    # Code Pattern Detection
    # =========================================================================

    def detect_code_patterns(
        self,
        codebase_id: str,
        symbols: List[CodeSymbol],
    ) -> List[Dict[str, Any]]:
        """
        Detect patterns in code symbols from a codebase.

        Args:
            codebase_id: ID of the codebase
            symbols: List of code symbols to analyze

        Returns:
            List of detected code patterns
        """
        if not symbols:
            return []

        detected_patterns = []

        # Detect naming conventions
        naming_patterns = self._detect_naming_conventions(symbols)
        detected_patterns.extend(naming_patterns)

        # Detect architectural patterns
        arch_patterns = self._detect_architectural_patterns(symbols)
        detected_patterns.extend(arch_patterns)

        # Store detected patterns
        for pattern in detected_patterns:
            self._store_code_pattern(codebase_id, pattern)

        return detected_patterns

    def _detect_naming_conventions(
        self,
        symbols: List[CodeSymbol],
    ) -> List[Dict[str, Any]]:
        """Detect naming convention patterns in code."""
        patterns = []

        # Analyze function naming
        function_symbols = [s for s in symbols if s.symbol_type == "function"]
        if function_symbols:
            naming_style = self._analyze_naming_style(
                [s.symbol_name for s in function_symbols]
            )
            if naming_style:
                patterns.append(
                    {
                        "pattern_type": self.NAMING_CONVENTION,
                        "pattern_name": f"function_naming_{naming_style['style']}",
                        "description": f"Functions use {naming_style['style']} naming convention",
                        "examples": naming_style["examples"][:5],
                        "confidence": naming_style["confidence"],
                        "occurrences": naming_style["count"],
                    }
                )

        # Analyze class naming
        class_symbols = [s for s in symbols if s.symbol_type == "class"]
        if class_symbols:
            naming_style = self._analyze_naming_style(
                [s.symbol_name for s in class_symbols]
            )
            if naming_style:
                patterns.append(
                    {
                        "pattern_type": self.NAMING_CONVENTION,
                        "pattern_name": f"class_naming_{naming_style['style']}",
                        "description": f"Classes use {naming_style['style']} naming convention",
                        "examples": naming_style["examples"][:5],
                        "confidence": naming_style["confidence"],
                        "occurrences": naming_style["count"],
                    }
                )

        return patterns

    def _analyze_naming_style(
        self,
        names: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Analyze naming style from a list of names."""
        if not names:
            return None

        style_counts = {
            "snake_case": 0,
            "camelCase": 0,
            "PascalCase": 0,
            "SCREAMING_SNAKE": 0,
        }

        for name in names:
            if name.isupper() and "_" in name:
                style_counts["SCREAMING_SNAKE"] += 1
            elif "_" in name and name.islower():
                style_counts["snake_case"] += 1
            elif name[0].isupper() and "_" not in name:
                style_counts["PascalCase"] += 1
            elif (
                name[0].islower() and "_" not in name and any(c.isupper() for c in name)
            ):
                style_counts["camelCase"] += 1
            elif "_" in name:
                style_counts["snake_case"] += 1

        total = sum(style_counts.values())
        if total == 0:
            return None

        dominant_style = max(style_counts.items(), key=lambda x: x[1])
        style_name, count = dominant_style

        if count < self.MIN_OCCURRENCES:
            return None

        confidence = count / total

        # Get examples
        examples = []
        for name in names[:10]:
            if self._matches_style(name, style_name):
                examples.append(name)

        return {
            "style": style_name,
            "count": count,
            "total": total,
            "confidence": round(confidence, 2),
            "examples": examples,
        }

    def _matches_style(self, name: str, style: str) -> bool:
        """Check if a name matches a naming style."""
        if style == "snake_case":
            return "_" in name and name.islower()
        elif style == "camelCase":
            return (
                name[0].islower() and "_" not in name and any(c.isupper() for c in name)
            )
        elif style == "PascalCase":
            return name[0].isupper() and "_" not in name
        elif style == "SCREAMING_SNAKE":
            return name.isupper() and "_" in name
        return False

    def _detect_architectural_patterns(
        self,
        symbols: List[CodeSymbol],
    ) -> List[Dict[str, Any]]:
        """Detect architectural patterns in code structure."""
        patterns = []

        # Analyze file organization
        file_paths = list(set(s.file_path for s in symbols))

        # Check for common patterns
        has_services = any("service" in p.lower() for p in file_paths)
        has_controllers = any("controller" in p.lower() for p in file_paths)
        has_models = any("model" in p.lower() for p in file_paths)
        has_repositories = any(
            "repo" in p.lower() or "repository" in p.lower() for p in file_paths
        )

        if has_services and has_controllers and has_models:
            patterns.append(
                {
                    "pattern_type": "architecture",
                    "pattern_name": "mvc_pattern",
                    "description": "Codebase follows MVC/Service pattern",
                    "examples": [
                        {
                            "category": "services",
                            "count": sum(
                                1 for p in file_paths if "service" in p.lower()
                            ),
                        },
                        {
                            "category": "controllers",
                            "count": sum(
                                1 for p in file_paths if "controller" in p.lower()
                            ),
                        },
                        {
                            "category": "models",
                            "count": sum(1 for p in file_paths if "model" in p.lower()),
                        },
                    ],
                    "confidence": 0.8,
                    "occurrences": len(file_paths),
                }
            )

        if has_repositories:
            patterns.append(
                {
                    "pattern_type": "architecture",
                    "pattern_name": "repository_pattern",
                    "description": "Uses Repository pattern for data access",
                    "examples": [
                        p
                        for p in file_paths
                        if "repo" in p.lower() or "repository" in p.lower()
                    ][:5],
                    "confidence": 0.75,
                    "occurrences": sum(
                        1
                        for p in file_paths
                        if "repo" in p.lower() or "repository" in p.lower()
                    ),
                }
            )

        return patterns

    def _store_code_pattern(
        self,
        codebase_id: str,
        pattern: Dict[str, Any],
    ) -> CodePattern:
        """Store or update a detected code pattern."""
        from uuid import UUID

        existing = (
            self.db.query(CodePattern)
            .filter(
                and_(
                    CodePattern.codebase_id == UUID(codebase_id),
                    CodePattern.pattern_type == pattern["pattern_type"],
                    CodePattern.pattern_name == pattern["pattern_name"],
                )
            )
            .first()
        )

        if existing:
            existing.description = pattern.get("description")
            existing.examples = pattern.get("examples", [])
            existing.confidence = pattern.get("confidence", 0.5)
            existing.occurrences = pattern.get("occurrences", 1)
            self.db.commit()
            return existing

        new_pattern = CodePattern(
            codebase_id=UUID(codebase_id),
            pattern_type=pattern["pattern_type"],
            pattern_name=pattern["pattern_name"],
            description=pattern.get("description"),
            examples=pattern.get("examples", []),
            confidence=pattern.get("confidence", 0.5),
            occurrences=pattern.get("occurrences", 1),
        )
        self.db.add(new_pattern)
        self.db.commit()
        self.db.refresh(new_pattern)
        return new_pattern

    # =========================================================================
    # Pattern Retrieval
    # =========================================================================

    def get_user_patterns(
        self,
        user_id: int,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.5,
    ) -> List[UserPattern]:
        """
        Get detected patterns for a user.

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

    def get_code_patterns(
        self,
        codebase_id: str,
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.5,
    ) -> List[CodePattern]:
        """
        Get detected patterns for a codebase.

        Args:
            codebase_id: Codebase ID
            pattern_type: Optional filter by pattern type
            min_confidence: Minimum confidence threshold

        Returns:
            List of CodePattern objects
        """
        from uuid import UUID

        query = self.db.query(CodePattern).filter(
            and_(
                CodePattern.codebase_id == UUID(codebase_id),
                CodePattern.confidence >= min_confidence,
            )
        )

        if pattern_type:
            query = query.filter(CodePattern.pattern_type == pattern_type)

        return query.order_by(desc(CodePattern.confidence)).all()


def get_pattern_detector(db: Session) -> PatternDetector:
    """Factory function to create PatternDetector."""
    return PatternDetector(db)
