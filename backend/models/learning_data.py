"""Database models for learning system data."""

from enum import Enum
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    JSON,
    Boolean,
    func,
    Index,
)
from backend.core.db import Base


class FeedbackTypeEnum(str, Enum):
    """Feedback classification types."""

    ACCEPTED = "accepted"
    ACCEPTED_MODIFIED = "accepted_modified"
    REJECTED = "rejected"


class SuggestionCategoryEnum(str, Enum):
    """Categories of AI suggestions."""

    FILE_CREATE = "file_create"
    FILE_EDIT = "file_edit"
    FILE_DELETE = "file_delete"
    COMMAND_RUN = "command_run"
    EXPLANATION = "explanation"
    REFACTORING = "refactoring"
    BUG_FIX = "bug_fix"
    FEATURE_ADD = "feature_add"
    TEST_CREATE = "test_create"
    DOCUMENTATION = "documentation"


class LearningSuggestion(Base):
    """
    Store learning system suggestions and their outcomes.

    Tracks AI suggestions with user feedback to learn patterns and improve future suggestions.
    This replaces the file-based storage at ~/.navi/feedback/feedback.json
    """

    __tablename__ = "learning_suggestions"

    id = Column(Integer, primary_key=True)

    # Organization and user context
    # Changed from Integer to String to support non-numeric IDs (org_key, OIDC sub, etc.)
    org_id = Column(String(128), nullable=True, index=True)
    user_id = Column(String(128), nullable=True, index=True)

    # Suggestion details
    category = Column(String(64), nullable=False, index=True)  # SuggestionCategoryEnum
    suggestion_text = Column(
        Text, nullable=False, comment="The AI's suggestion content"
    )
    context = Column(
        JSON, nullable=True, comment="Context in which suggestion was made"
    )

    # Feedback
    feedback_type = Column(String(32), nullable=False, index=True)  # FeedbackTypeEnum
    confidence = Column(
        Float, nullable=True, comment="AI's confidence in this suggestion"
    )
    rating = Column(Integer, nullable=True, comment="User rating (1-5)")
    reason = Column(String(256), nullable=True, comment="Reason for feedback")
    comment = Column(Text, nullable=True, comment="Additional user comments")

    # Pattern detection
    pattern_tags = Column(
        JSON, nullable=True, comment="Detected patterns in this suggestion"
    )
    similar_count = Column(Integer, default=0, comment="Count of similar suggestions")

    # Metadata
    session_id = Column(String(128), nullable=True, index=True)
    task_id = Column(String(128), nullable=True)
    model_used = Column(String(128), nullable=True)

    # Link to generation log if available
    gen_id = Column(
        Integer, nullable=True, index=True, comment="Reference to ai_generation_log.id"
    )

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_learning_sug_org_time", "org_id", "created_at"),
        Index("idx_learning_sug_category_feedback", "category", "feedback_type"),
        Index("idx_learning_sug_user_feedback", "user_id", "feedback_type"),
    )


class LearningInsight(Base):
    """
    Store aggregate insights derived from learning suggestions.

    Periodically analyzed patterns and insights from user feedback to guide future AI behavior.
    """

    __tablename__ = "learning_insights"

    id = Column(Integer, primary_key=True)

    # Organization context
    org_id = Column(Integer, nullable=True, index=True)

    # Insight details
    insight_type = Column(
        String(64), nullable=False, index=True
    )  # pattern, preference, anti_pattern, etc.
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    # Pattern data
    pattern_data = Column(
        JSON, nullable=False, comment="Structured data about the pattern"
    )
    examples = Column(
        JSON, nullable=True, comment="Example suggestions demonstrating this insight"
    )

    # Confidence and usage
    confidence = Column(
        Float,
        nullable=False,
        default=0.5,
        comment="Confidence in this insight [0.0, 1.0]",
    )
    sample_size = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of suggestions contributing to insight",
    )
    times_applied = Column(
        Integer,
        default=0,
        comment="Number of times this insight influenced suggestions",
    )

    # Active status
    is_active = Column(
        Boolean, default=True, index=True, comment="Whether to apply this insight"
    )

    # Metadata
    category = Column(
        String(64), nullable=True, index=True, comment="Related suggestion category"
    )
    tags = Column(JSON, nullable=True, comment="Tags for filtering and searching")

    # Timestamps
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_applied = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time this insight was used",
    )

    __table_args__ = (
        Index("idx_learning_ins_org_active", "org_id", "is_active"),
        Index("idx_learning_ins_type_active", "insight_type", "is_active"),
        Index("idx_learning_ins_confidence", "confidence"),
    )


class LearningPattern(Base):
    """
    Store detected behavioral patterns from user interactions.

    Tracks patterns like "user prefers TypeScript over JavaScript" or
    "user always adds tests with new features".
    """

    __tablename__ = "learning_patterns"

    id = Column(Integer, primary_key=True)

    # Organization and user context
    org_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)

    # Pattern details
    pattern_key = Column(
        String(255), nullable=False, comment="Unique identifier for this pattern"
    )
    pattern_type = Column(
        String(64), nullable=False, index=True
    )  # preference, workflow, anti_pattern, etc.
    description = Column(Text, nullable=False)

    # Pattern strength
    confidence = Column(Float, nullable=False, default=0.5)
    occurrences = Column(Integer, nullable=False, default=1)
    positive_feedback = Column(Integer, default=0)
    negative_feedback = Column(Integer, default=0)

    # Context
    context_data = Column(
        JSON, nullable=True, comment="Additional context about when pattern applies"
    )

    # Timestamps
    first_seen = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_learning_pat_org_type", "org_id", "pattern_type"),
        Index("idx_learning_pat_user_type", "user_id", "pattern_type"),
        Index("idx_learning_pat_key", "pattern_key"),
    )
