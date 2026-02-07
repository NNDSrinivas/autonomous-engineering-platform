"""
Memory System Database Models.

Comprehensive models for NAVI's memory and intelligence system including:
- User preferences, activity tracking, patterns, and feedback
- Organization knowledge base, coding standards, and shared context
- Conversation history with message embeddings
- Codebase indexing with symbol extraction and pattern detection

All models support multi-tenancy via org_id and use pgvector for semantic search.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, relationship

from backend.core.db import Base

# pgvector support
try:
    from pgvector.sqlalchemy import Vector

    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False
    Vector = None

# Use Vector type if available, otherwise fall back to Text
EMBEDDING_DIMENSION = 1536
EmbeddingType = Vector(EMBEDDING_DIMENSION) if HAS_PGVECTOR else Text


# =============================================================================
# User Memory Tables
# =============================================================================


class UserPreferences(Base):
    """
    User preferences and settings for personalized NAVI responses.

    Stores both explicit preferences (set by user) and inferred preferences
    (learned from behavior patterns).
    """

    __tablename__ = "user_preferences"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[int] = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Coding preferences
    preferred_language: Mapped[Optional[str]] = Column(
        String(50),
        nullable=True,
        comment="Primary programming language (e.g., python, typescript)",
    )
    preferred_framework: Mapped[Optional[str]] = Column(
        String(100),
        nullable=True,
        comment="Preferred framework (e.g., fastapi, react, django)",
    )
    code_style: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        default={},
        comment="Code style preferences: indentation, naming conventions, etc.",
    )

    # Communication preferences
    response_verbosity: Mapped[str] = Column(
        String(20),
        default="balanced",
        nullable=False,
        comment="Response length preference: brief, balanced, detailed",
    )
    explanation_level: Mapped[str] = Column(
        String(20),
        default="intermediate",
        nullable=False,
        comment="Technical depth: beginner, intermediate, expert",
    )

    # UI preferences
    theme: Mapped[str] = Column(
        String(20),
        default="dark",
        nullable=False,
    )
    keyboard_shortcuts: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        default={},
    )

    # Learned preferences (auto-detected from behavior)
    inferred_preferences: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        default={},
        comment="Preferences learned from user behavior patterns",
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship
    user = relationship("DBUser", backref="preferences", uselist=False)

    def __repr__(self) -> str:
        return (
            f"<UserPreferences(user_id={self.user_id}, lang={self.preferred_language})>"
        )


class UserActivity(Base):
    """
    Track user activities for learning patterns and providing context.

    Records queries, code edits, approvals, rejections, and other interactions
    to build a comprehensive understanding of user behavior.
    """

    __tablename__ = "user_activity"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[int] = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Activity type
    activity_type: Mapped[str] = Column(
        String(50),
        nullable=False,
        comment="Type: query, code_edit, approval, rejection, search, feedback",
    )
    activity_data: Mapped[Dict[str, Any]] = Column(
        JSONB,
        nullable=False,
        comment="Structured data about the activity",
    )

    # Context
    workspace_path: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Path to the workspace where activity occurred",
    )
    file_path: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Specific file being worked on",
    )
    language: Mapped[Optional[str]] = Column(
        String(50),
        nullable=True,
        comment="Programming language context",
    )

    # Session tracking
    session_id: Mapped[Optional[str]] = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Group activities by session",
    )

    # Timestamp
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    __table_args__ = (
        Index("idx_user_activity_user_time", "user_id", "created_at"),
        Index("idx_user_activity_type", "activity_type"),
        Index("idx_user_activity_session", "session_id"),
    )

    def __repr__(self) -> str:
        return f"<UserActivity(id={self.id}, type={self.activity_type})>"


class UserPattern(Base):
    """
    Detected patterns in user behavior.

    Stores coding styles, common errors, workflow patterns, and other
    behavioral patterns learned from user activity.
    """

    __tablename__ = "user_patterns"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[int] = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Pattern details
    pattern_type: Mapped[str] = Column(
        String(50),
        nullable=False,
        comment="Type: coding_style, common_errors, workflow, naming, testing",
    )
    pattern_key: Mapped[str] = Column(
        String(255),
        nullable=False,
        comment="Unique key identifying the specific pattern",
    )
    pattern_data: Mapped[Dict[str, Any]] = Column(
        JSONB,
        nullable=False,
        comment="Detailed pattern information",
    )

    # Confidence tracking
    confidence: Mapped[float] = Column(
        Float,
        default=0.5,
        nullable=False,
        comment="Confidence in pattern accuracy [0.0, 1.0]",
    )
    occurrences: Mapped[int] = Column(
        Integer,
        default=1,
        nullable=False,
        comment="Number of times pattern was observed",
    )

    # Timestamps
    first_seen: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "pattern_type", "pattern_key", name="uq_user_pattern"
        ),
        Index("idx_user_pattern_type", "user_id", "pattern_type"),
    )

    def __repr__(self) -> str:
        return f"<UserPattern(user_id={self.user_id}, type={self.pattern_type})>"


class UserFeedback(Base):
    """
    User feedback on NAVI responses for continuous improvement.

    Captures positive/negative feedback and corrections to learn
    from user preferences and improve response quality.
    """

    __tablename__ = "user_feedback"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[int] = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Reference to conversation
    message_id: Mapped[str] = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="ID of the message being rated",
    )
    conversation_id: Mapped[str] = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="ID of the conversation",
    )

    # Feedback
    feedback_type: Mapped[str] = Column(
        String(20),
        nullable=False,
        comment="Type: positive, negative, correction",
    )
    feedback_data: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        nullable=True,
        comment="Additional feedback details or corrections",
    )

    # Context preservation
    query_text: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Original user query",
    )
    response_text: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="NAVI's response that received feedback",
    )

    # Timestamp
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("idx_user_feedback_user", "user_id"),
        Index("idx_user_feedback_conversation", "conversation_id"),
    )

    def __repr__(self) -> str:
        return f"<UserFeedback(id={self.id}, type={self.feedback_type})>"


# =============================================================================
# Organization Memory Tables
# =============================================================================


class OrgKnowledge(Base):
    """
    Organization knowledge base for shared context.

    Stores organizational patterns, conventions, architecture decisions,
    and other knowledge that applies across the entire organization.
    Supports semantic search via embedding vectors.
    """

    __tablename__ = "org_knowledge"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    org_id: Mapped[int] = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Knowledge content
    knowledge_type: Mapped[str] = Column(
        String(50),
        nullable=False,
        comment="Type: pattern, convention, architecture, decision, documentation",
    )
    title: Mapped[str] = Column(
        String(255),
        nullable=False,
    )
    content: Mapped[str] = Column(
        Text,
        nullable=False,
    )

    # Semantic search - embedding vector stored as text, converted by pgvector
    # In migration: ALTER TABLE org_knowledge ADD COLUMN embedding vector(1536);
    embedding_text = Column(
        EmbeddingType,
        nullable=True,
        comment="Embedding vector for semantic search",
    )

    # Metadata
    source: Mapped[Optional[str]] = Column(
        String(100),
        nullable=True,
        comment="Source: manual, inferred, documentation, code_analysis",
    )
    confidence: Mapped[float] = Column(
        Float,
        default=1.0,
        nullable=False,
        comment="Confidence in knowledge accuracy [0.0, 1.0]",
    )

    # Ownership
    created_by: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (Index("idx_org_knowledge_org_type", "org_id", "knowledge_type"),)

    def __repr__(self) -> str:
        return f"<OrgKnowledge(id={self.id}, title={self.title[:30]}...)>"


class OrgStandard(Base):
    """
    Organization coding standards and conventions.

    Defines rules for naming conventions, code structure, testing requirements,
    security practices, and other standards that NAVI should enforce.
    """

    __tablename__ = "org_standards"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    org_id: Mapped[int] = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Standard definition
    standard_type: Mapped[str] = Column(
        String(50),
        nullable=False,
        comment="Type: naming, structure, testing, security, documentation, api",
    )
    standard_name: Mapped[str] = Column(
        String(255),
        nullable=False,
    )
    rules: Mapped[Dict[str, Any]] = Column(
        JSONB,
        nullable=False,
        comment="Machine-readable rules for the standard",
    )

    # Examples
    good_examples: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=[],
        comment="Examples of code following the standard",
    )
    bad_examples: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=[],
        comment="Examples of code violating the standard",
    )

    # Enforcement
    enforced: Mapped[bool] = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether NAVI should actively enforce this standard",
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "org_id", "standard_type", "standard_name", name="uq_org_standard"
        ),
        Index("idx_org_standard_type", "org_id", "standard_type"),
    )

    def __repr__(self) -> str:
        return f"<OrgStandard(id={self.id}, name={self.standard_name})>"


class OrgContext(Base):
    """
    Organization shared context with hierarchical inheritance.

    Stores project, team, and domain-specific context that can be
    inherited and overridden at different levels.
    """

    __tablename__ = "org_context"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    org_id: Mapped[int] = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Context definition
    context_type: Mapped[str] = Column(
        String(50),
        nullable=False,
        comment="Type: global, project, team, domain, workspace",
    )
    context_key: Mapped[str] = Column(
        String(255),
        nullable=False,
        comment="Unique key within type (e.g., project name)",
    )
    context_value: Mapped[Dict[str, Any]] = Column(
        JSONB,
        nullable=False,
        comment="Context data",
    )

    # Hierarchy
    parent_id: Mapped[Optional[str]] = Column(
        UUID(as_uuid=True),
        ForeignKey("org_context.id", ondelete="CASCADE"),
        nullable=True,
        comment="Parent context for inheritance",
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Self-referential relationship for hierarchy
    parent = relationship("OrgContext", remote_side=[id], backref="children")

    __table_args__ = (
        UniqueConstraint(
            "org_id", "context_type", "context_key", name="uq_org_context"
        ),
        Index("idx_org_context_type", "org_id", "context_type"),
    )

    def __repr__(self) -> str:
        return f"<OrgContext(id={self.id}, type={self.context_type}, key={self.context_key})>"


# =============================================================================
# Conversation Memory Tables
# =============================================================================


class Conversation(Base):
    """
    Conversation sessions with NAVI.

    Groups related messages together with workspace context
    for conversation history and retrieval.
    """

    __tablename__ = "navi_conversations"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[int] = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Conversation metadata
    title: Mapped[Optional[str]] = Column(
        String(255),
        nullable=True,
        comment="Auto-generated or user-set title",
    )

    # Context
    workspace_path: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Workspace where conversation started",
    )
    initial_context: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        nullable=True,
        comment="Initial context provided at conversation start",
    )

    # Status
    status: Mapped[str] = Column(
        String(20),
        default="active",
        nullable=False,
        comment="Status: active, archived, deleted",
    )

    # UI metadata
    is_pinned: Mapped[bool] = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Pinned in history",
    )
    is_starred: Mapped[bool] = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Starred in history",
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    messages: Mapped[List["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    summaries: Mapped[List["ConversationSummary"]] = relationship(
        "ConversationSummary",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_conversation_user_time", "user_id", "created_at"),
        Index("idx_conversation_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, title={self.title})>"


class Message(Base):
    """
    Individual messages within a conversation.

    Stores message content with embeddings for semantic search
    and metadata for context retrieval.
    """

    __tablename__ = "navi_messages"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    conversation_id: Mapped[str] = Column(
        UUID(as_uuid=True),
        ForeignKey("navi_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Message content
    role: Mapped[str] = Column(
        String(20),
        nullable=False,
        comment="Role: user, assistant, system",
    )
    content: Mapped[str] = Column(
        Text,
        nullable=False,
    )

    # Semantic search - embedding stored as text, converted by pgvector
    embedding_text = Column(
        EmbeddingType,
        nullable=True,
        comment="Embedding vector for semantic search",
    )

    # Message metadata (not using 'metadata' as it's reserved in SQLAlchemy)
    message_metadata: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        default={},
        comment="Additional metadata: attachments, tool_calls, etc.",
    )
    tokens_used: Mapped[Optional[int]] = Column(
        Integer,
        nullable=True,
        comment="Token count for this message",
    )

    # Timestamp
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationship
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )

    __table_args__ = (
        Index("idx_message_conversation_time", "conversation_id", "created_at"),
        Index("idx_message_role", "role"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role})>"


class ConversationSummary(Base):
    """
    Summarized conversation segments for fast context loading.

    Stores periodic summaries of conversation history to enable
    efficient context retrieval without loading all messages.
    """

    __tablename__ = "navi_conversation_summaries"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    conversation_id: Mapped[str] = Column(
        UUID(as_uuid=True),
        ForeignKey("navi_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Summary content
    summary: Mapped[str] = Column(
        Text,
        nullable=False,
    )
    key_points: Mapped[Optional[List[str]]] = Column(
        JSONB,
        default=[],
        comment="Extracted key points from the conversation",
    )

    # Coverage
    message_count: Mapped[int] = Column(
        Integer,
        nullable=False,
        comment="Number of messages summarized",
    )
    from_message_id: Mapped[Optional[str]] = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="First message in summary range",
    )
    to_message_id: Mapped[Optional[str]] = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Last message in summary range",
    )

    # Semantic search
    embedding_text = Column(
        EmbeddingType,
        nullable=True,
        comment="Embedding vector for semantic search",
    )

    # Timestamp
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationship
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="summaries",
    )

    __table_args__ = (Index("idx_summary_conversation", "conversation_id"),)

    def __repr__(self) -> str:
        return f"<ConversationSummary(id={self.id}, messages={self.message_count})>"


# =============================================================================
# Codebase Memory Tables
# =============================================================================


class CodebaseIndex(Base):
    """
    Indexed codebase metadata and status.

    Tracks workspace indexing status, configuration, and statistics
    for each user's or organization's codebase.
    """

    __tablename__ = "codebase_index"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        comment="Owner user (nullable for org-level indexes)",
    )
    org_id: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        comment="Owner organization",
    )

    # Workspace info
    workspace_path: Mapped[str] = Column(
        Text,
        nullable=False,
    )
    workspace_name: Mapped[Optional[str]] = Column(
        String(255),
        nullable=True,
    )

    # Index status
    index_status: Mapped[str] = Column(
        String(20),
        default="pending",
        nullable=False,
        comment="Status: pending, indexing, ready, error, stale",
    )
    last_indexed: Mapped[Optional[datetime]] = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Statistics
    file_count: Mapped[int] = Column(
        Integer,
        default=0,
        nullable=False,
    )

    # Configuration
    index_config: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        default={},
        comment="Indexing configuration: include/exclude patterns, etc.",
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    symbols: Mapped[List["CodeSymbol"]] = relationship(
        "CodeSymbol",
        back_populates="codebase",
        cascade="all, delete-orphan",
    )
    patterns: Mapped[List["CodePattern"]] = relationship(
        "CodePattern",
        back_populates="codebase",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "workspace_path", name="uq_codebase_user_workspace"
        ),
        Index("idx_codebase_status", "index_status"),
        Index("idx_codebase_org", "org_id"),
    )

    def __repr__(self) -> str:
        return f"<CodebaseIndex(id={self.id}, path={self.workspace_path})>"


class CodeSymbol(Base):
    """
    Indexed code symbols from a codebase.

    Stores functions, classes, variables, and other symbols
    with their locations and embeddings for semantic search.
    """

    __tablename__ = "code_symbols"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    codebase_id: Mapped[str] = Column(
        UUID(as_uuid=True),
        ForeignKey("codebase_index.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Symbol identification
    symbol_type: Mapped[str] = Column(
        String(50),
        nullable=False,
        comment="Type: function, class, method, variable, import, interface, type",
    )
    symbol_name: Mapped[str] = Column(
        String(255),
        nullable=False,
    )
    qualified_name: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Fully qualified name (e.g., module.Class.method)",
    )

    # Location
    file_path: Mapped[str] = Column(
        Text,
        nullable=False,
    )
    line_start: Mapped[Optional[int]] = Column(
        Integer,
        nullable=True,
    )
    line_end: Mapped[Optional[int]] = Column(
        Integer,
        nullable=True,
    )

    # Code content
    code_snippet: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Extracted code for the symbol",
    )
    documentation: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Docstring or inline documentation",
    )

    # Semantic search
    embedding_text = Column(
        EmbeddingType,
        nullable=True,
        comment="Embedding vector for semantic search",
    )

    # Hierarchy
    parent_symbol_id: Mapped[Optional[str]] = Column(
        UUID(as_uuid=True),
        ForeignKey("code_symbols.id", ondelete="CASCADE"),
        nullable=True,
        comment="Parent symbol (e.g., class for a method)",
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship
    codebase: Mapped["CodebaseIndex"] = relationship(
        "CodebaseIndex",
        back_populates="symbols",
    )
    parent = relationship("CodeSymbol", remote_side=[id], backref="children")

    __table_args__ = (
        Index("idx_symbol_codebase", "codebase_id"),
        Index("idx_symbol_name", "symbol_name"),
        Index("idx_symbol_type", "symbol_type"),
        Index("idx_symbol_file", "file_path"),
    )

    def __repr__(self) -> str:
        return f"<CodeSymbol(id={self.id}, name={self.symbol_name}, type={self.symbol_type})>"


class CodePattern(Base):
    """
    Detected patterns in a codebase.

    Stores architectural patterns, naming conventions, error handling
    patterns, and other detected patterns from code analysis.
    """

    __tablename__ = "code_patterns"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    codebase_id: Mapped[str] = Column(
        UUID(as_uuid=True),
        ForeignKey("codebase_index.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Pattern details
    pattern_type: Mapped[str] = Column(
        String(50),
        nullable=False,
        comment="Type: architecture, naming, error_handling, testing, api_design",
    )
    pattern_name: Mapped[str] = Column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
    )

    # Examples from codebase
    examples: Mapped[Optional[List[Dict[str, Any]]]] = Column(
        JSONB,
        default=[],
        comment="Code examples demonstrating the pattern",
    )

    # Confidence
    confidence: Mapped[float] = Column(
        Float,
        default=0.5,
        nullable=False,
        comment="Confidence in pattern detection [0.0, 1.0]",
    )
    occurrences: Mapped[int] = Column(
        Integer,
        default=1,
        nullable=False,
        comment="Number of times pattern was found",
    )

    # Timestamp
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Relationship
    codebase: Mapped["CodebaseIndex"] = relationship(
        "CodebaseIndex",
        back_populates="patterns",
    )

    __table_args__ = (
        Index("idx_pattern_codebase", "codebase_id"),
        Index("idx_pattern_type", "pattern_type"),
    )

    def __repr__(self) -> str:
        return f"<CodePattern(id={self.id}, name={self.pattern_name})>"
