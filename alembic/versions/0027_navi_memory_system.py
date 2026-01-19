"""NAVI Comprehensive Memory System

Creates all tables for the NAVI memory and intelligence system:
- User Memory: preferences, activity, patterns, feedback
- Organization Memory: knowledge, standards, context
- Conversation Memory: conversations, messages, summaries
- Codebase Memory: index, symbols, patterns

Revision ID: 0027_navi_memory_system
Revises: aced98884720
Create Date: 2026-01-16

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from typing import Any

try:
    from pgvector.sqlalchemy import Vector  # type: ignore

    HAS_PGVECTOR = True
except ImportError:
    Vector = None  # type: ignore
    HAS_PGVECTOR = False

# revision identifiers, used by Alembic.
revision = "0027_navi_memory_system"
down_revision = "aced98884720"
branch_labels = None
depends_on = None


def upgrade():
    """Create comprehensive NAVI memory system tables"""
    conn = op.get_bind()
    is_postgres = conn.dialect.name == "postgresql"

    # Ensure pgvector extension is enabled
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Use Vector type for PostgreSQL, TEXT for SQLite/others
    if is_postgres and HAS_PGVECTOR and Vector is not None:
        embedding_type: Any = Vector(1536)
    else:
        embedding_type = sa.Text()

    # Use appropriate timestamp defaults per dialect
    timestamp_default = (
        sa.text("now()") if is_postgres else sa.text("CURRENT_TIMESTAMP")
    )
    uuid_default = sa.text("gen_random_uuid()") if is_postgres else None

    # =========================================================================
    # USER MEMORY TABLES
    # =========================================================================

    # User Preferences
    op.create_table(
        "user_preferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=uuid_default),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("preferred_language", sa.String(50), nullable=True),
        sa.Column("preferred_framework", sa.String(100), nullable=True),
        sa.Column("code_style", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("response_verbosity", sa.String(20), server_default=sa.text("'balanced'"), nullable=False),
        sa.Column("explanation_level", sa.String(20), server_default=sa.text("'intermediate'"), nullable=False),
        sa.Column("theme", sa.String(20), server_default=sa.text("'dark'")),
        sa.Column("keyboard_shortcuts", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("inferred_preferences", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )

    # User Activity
    op.create_table(
        "user_activity",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=uuid_default),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("activity_type", sa.String(50), nullable=False),
        sa.Column("activity_data", JSONB, nullable=False),
        sa.Column("workspace_path", sa.Text(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index("idx_user_activity_user", "user_activity", ["user_id", "created_at"])
    op.create_index("idx_user_activity_type", "user_activity", ["activity_type"])

    # User Patterns
    op.create_table(
        "user_patterns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=uuid_default),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pattern_type", sa.String(50), nullable=False),
        sa.Column("pattern_key", sa.String(255), nullable=False),
        sa.Column("pattern_data", JSONB, nullable=False),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.5")),
        sa.Column("occurrences", sa.Integer(), server_default=sa.text("1")),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index("idx_user_patterns_user", "user_patterns", ["user_id"])
    op.create_index("idx_user_patterns_type", "user_patterns", ["pattern_type"])

    # User Feedback
    op.create_table(
        "user_feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=uuid_default),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("feedback_type", sa.String(20), nullable=False),
        sa.Column("feedback_data", JSONB, nullable=True),
        sa.Column("query_text", sa.Text(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index("idx_user_feedback_user", "user_feedback", ["user_id"])

    # =========================================================================
    # ORGANIZATION MEMORY TABLES
    # =========================================================================

    # Org Knowledge
    op.create_table(
        "org_knowledge",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=uuid_default),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("knowledge_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_text", embedding_type, nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("confidence", sa.Float(), server_default=sa.text("1.0")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index("idx_org_knowledge_org", "org_knowledge", ["org_id"])
    op.create_index("idx_org_knowledge_type", "org_knowledge", ["knowledge_type"])
    if is_postgres and HAS_PGVECTOR:
        op.execute("""
            CREATE INDEX idx_org_knowledge_embedding
            ON org_knowledge
            USING hnsw (embedding_text vector_cosine_ops)
        """)

    # Org Standards
    op.create_table(
        "org_standards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=uuid_default),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("standard_type", sa.String(50), nullable=False),
        sa.Column("standard_name", sa.String(255), nullable=False),
        sa.Column("rules", JSONB, nullable=False),
        sa.Column("good_examples", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("bad_examples", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("enforced", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index("idx_org_standards_org", "org_standards", ["org_id"])
    op.create_index("idx_org_standards_type", "org_standards", ["standard_type"])

    # Org Context
    op.create_table(
        "org_context",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=uuid_default),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("context_type", sa.String(50), nullable=False),
        sa.Column("context_key", sa.String(255), nullable=False),
        sa.Column("context_value", JSONB, nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("org_context.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index("idx_org_context_org", "org_context", ["org_id"])
    op.create_unique_constraint("uq_org_context", "org_context", ["org_id", "context_type", "context_key"])

    # =========================================================================
    # CONVERSATION MEMORY TABLES
    # =========================================================================

    # Conversations
    op.create_table(
        "navi_conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=uuid_default),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("workspace_path", sa.Text(), nullable=True),
        sa.Column("initial_context", JSONB, nullable=True),
        sa.Column("status", sa.String(20), server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index("idx_navi_conversations_user", "navi_conversations", ["user_id", "created_at"])

    # Messages
    op.create_table(
        "navi_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=uuid_default),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("navi_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding_text", embedding_type, nullable=True),
        sa.Column("message_metadata", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index("idx_navi_messages_conversation", "navi_messages", ["conversation_id", "created_at"])
    if is_postgres and HAS_PGVECTOR:
        op.execute("""
            CREATE INDEX idx_navi_messages_embedding
            ON navi_messages
            USING hnsw (embedding_text vector_cosine_ops)
        """)

    # Conversation Summaries
    op.create_table(
        "navi_conversation_summaries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=uuid_default),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("navi_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("key_points", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("message_count", sa.Integer(), nullable=True),
        sa.Column("from_message_id", UUID(as_uuid=True), nullable=True),
        sa.Column("to_message_id", UUID(as_uuid=True), nullable=True),
        sa.Column("embedding_text", embedding_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index("idx_navi_conversation_summaries_conv", "navi_conversation_summaries", ["conversation_id"])

    # =========================================================================
    # CODEBASE MEMORY TABLES
    # =========================================================================

    # Codebase Index
    op.create_table(
        "codebase_index",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=uuid_default),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("workspace_path", sa.Text(), nullable=False),
        sa.Column("workspace_name", sa.String(255), nullable=True),
        sa.Column("last_indexed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("index_status", sa.String(20), server_default=sa.text("'pending'")),
        sa.Column("file_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("index_config", JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index("idx_codebase_index_user", "codebase_index", ["user_id"])
    op.create_unique_constraint("uq_codebase_index_user_path", "codebase_index", ["user_id", "workspace_path"])

    # Code Symbols
    op.create_table(
        "code_symbols",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=uuid_default),
        sa.Column("codebase_id", UUID(as_uuid=True), sa.ForeignKey("codebase_index.id", ondelete="CASCADE"), nullable=False),
        sa.Column("symbol_type", sa.String(50), nullable=False),
        sa.Column("symbol_name", sa.String(255), nullable=False),
        sa.Column("qualified_name", sa.Text(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=True),
        sa.Column("line_end", sa.Integer(), nullable=True),
        sa.Column("code_snippet", sa.Text(), nullable=True),
        sa.Column("documentation", sa.Text(), nullable=True),
        sa.Column("embedding_text", embedding_type, nullable=True),
        sa.Column("parent_symbol_id", UUID(as_uuid=True), sa.ForeignKey("code_symbols.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index("idx_code_symbols_codebase", "code_symbols", ["codebase_id"])
    op.create_index("idx_code_symbols_name", "code_symbols", ["symbol_name"])
    op.create_index("idx_code_symbols_type", "code_symbols", ["symbol_type"])
    if is_postgres and HAS_PGVECTOR:
        op.execute("""
            CREATE INDEX idx_code_symbols_embedding
            ON code_symbols
            USING hnsw (embedding_text vector_cosine_ops)
        """)

    # Code Patterns
    op.create_table(
        "code_patterns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=uuid_default),
        sa.Column("codebase_id", UUID(as_uuid=True), sa.ForeignKey("codebase_index.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pattern_type", sa.String(50), nullable=False),
        sa.Column("pattern_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("examples", JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.5")),
        sa.Column("occurrences", sa.Integer(), server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=timestamp_default, nullable=False),
    )
    op.create_index("idx_code_patterns_codebase", "code_patterns", ["codebase_id"])
    op.create_index("idx_code_patterns_type", "code_patterns", ["pattern_type"])


def downgrade():
    """Drop all NAVI memory system tables"""
    conn = op.get_bind()
    is_postgres = conn.dialect.name == "postgresql"

    # Drop in reverse order due to foreign keys

    # Code Patterns
    op.drop_index("idx_code_patterns_type", "code_patterns")
    op.drop_index("idx_code_patterns_codebase", "code_patterns")
    op.drop_table("code_patterns")

    # Code Symbols
    if is_postgres and HAS_PGVECTOR:
        op.execute("DROP INDEX IF EXISTS idx_code_symbols_embedding")
    op.drop_index("idx_code_symbols_type", "code_symbols")
    op.drop_index("idx_code_symbols_name", "code_symbols")
    op.drop_index("idx_code_symbols_codebase", "code_symbols")
    op.drop_table("code_symbols")

    # Codebase Index
    op.drop_constraint("uq_codebase_index_user_path", "codebase_index", type_="unique")
    op.drop_index("idx_codebase_index_user", "codebase_index")
    op.drop_table("codebase_index")

    # Conversation Summaries
    op.drop_index("idx_navi_conversation_summaries_conv", "navi_conversation_summaries")
    op.drop_table("navi_conversation_summaries")

    # Messages
    if is_postgres and HAS_PGVECTOR:
        op.execute("DROP INDEX IF EXISTS idx_navi_messages_embedding")
    op.drop_index("idx_navi_messages_conversation", "navi_messages")
    op.drop_table("navi_messages")

    # Conversations
    op.drop_index("idx_navi_conversations_user", "navi_conversations")
    op.drop_table("navi_conversations")

    # Org Context
    op.drop_constraint("uq_org_context", "org_context", type_="unique")
    op.drop_index("idx_org_context_org", "org_context")
    op.drop_table("org_context")

    # Org Standards
    op.drop_index("idx_org_standards_type", "org_standards")
    op.drop_index("idx_org_standards_org", "org_standards")
    op.drop_table("org_standards")

    # Org Knowledge
    if is_postgres and HAS_PGVECTOR:
        op.execute("DROP INDEX IF EXISTS idx_org_knowledge_embedding")
    op.drop_index("idx_org_knowledge_type", "org_knowledge")
    op.drop_index("idx_org_knowledge_org", "org_knowledge")
    op.drop_table("org_knowledge")

    # User Feedback
    op.drop_index("idx_user_feedback_user", "user_feedback")
    op.drop_table("user_feedback")

    # User Patterns
    op.drop_index("idx_user_patterns_type", "user_patterns")
    op.drop_index("idx_user_patterns_user", "user_patterns")
    op.drop_table("user_patterns")

    # User Activity
    op.drop_index("idx_user_activity_type", "user_activity")
    op.drop_index("idx_user_activity_user", "user_activity")
    op.drop_table("user_activity")

    # User Preferences
    op.drop_table("user_preferences")
