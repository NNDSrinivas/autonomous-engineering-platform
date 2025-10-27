"""Add memory_node and memory_edge tables for graph relationships

Revision ID: 0013_memory_graph
Revises: 0012_pgvector_bm25
Create Date: 2025-10-27 17:00:00.000000

"""

import os
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0013_memory_graph"
down_revision = "0012_pgvector_bm25"
branch_labels = None
depends_on = None

# Get embedding dimension from environment (must match PR-16 config)
EMBED_DIM = int(os.getenv("EMBED_DIM", "1536"))


def upgrade():
    """Add memory graph tables for temporal reasoning and relationship tracking"""

    # Create memory_node table
    # Represents entities: JIRA issues, Slack threads, meetings, PRs, docs, incidents, etc.
    op.create_table(
        "memory_node",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.String(255), nullable=False, index=True),
        sa.Column(
            "kind",
            sa.String(50),
            nullable=False,
            comment="Entity type: jira_issue|slack_thread|meeting|code_file|pr|doc|wiki|run|incident",
        ),
        sa.Column(
            "foreign_id",
            sa.String(255),
            nullable=False,
            comment="External identifier (e.g., JIRA-123, PR#456)",
        ),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=True,
            comment="AI-generated summary of content",
        ),
        sa.Column(
            "meta_json",
            sa.JSON(),
            nullable=True,
            comment="Metadata: url, assignee, status, etc.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="Updated via trigger or application code",
        ),
    )

    # Try to add pgvector column for semantic search
    try:
        op.add_column(
            "memory_node",
            sa.Column("embedding_vec", sa.types.UserDefinedType(), nullable=True),
        )
    except Exception:
        # Fallback to raw SQL for PostgreSQL
        dialect = op.get_bind().dialect.name
        if dialect == "postgresql":
            op.execute(
                f"ALTER TABLE memory_node ADD COLUMN embedding_vec vector({EMBED_DIM});"
            )

    # Create memory_edge table
    # Represents relationships between nodes with confidence and weight
    op.create_table(
        "memory_edge",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.String(255), nullable=False, index=True),
        sa.Column(
            "src_id",
            sa.Integer(),
            sa.ForeignKey("memory_node.id", ondelete="CASCADE"),
            nullable=False,
            comment="Source node ID",
        ),
        sa.Column(
            "dst_id",
            sa.Integer(),
            sa.ForeignKey("memory_node.id", ondelete="CASCADE"),
            nullable=False,
            comment="Destination node ID",
        ),
        sa.Column(
            "relation",
            sa.String(50),
            nullable=False,
            comment="Edge type: discusses|references|implements|fixes|duplicates|derived_from|caused_by|next|previous",
        ),
        sa.Column(
            "weight",
            sa.Float(),
            nullable=False,
            default=1.0,
            comment="Edge importance weight [0, 1]",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            default=1.0,
            comment="Confidence in relationship [0, 1]",
        ),
        sa.Column(
            "meta_json",
            sa.JSON(),
            nullable=True,
            comment="Edge metadata: source_heuristic, timestamp_diff, etc.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    # Create indexes for efficient queries
    # Index on org_id and kind for filtering by entity type
    op.create_index(
        "idx_memory_node_org_kind", "memory_node", ["org_id", "kind"], unique=False
    )

    # Unique constraint on org + foreign_id to prevent duplicates
    op.create_index(
        "idx_memory_node_org_foreign",
        "memory_node",
        ["org_id", "foreign_id"],
        unique=True,
    )

    # Index on org_id and relation for filtering edges by relationship type
    op.create_index(
        "idx_memory_edge_org_rel", "memory_edge", ["org_id", "relation"], unique=False
    )

    # Index on source node for outbound edge queries
    op.create_index("idx_memory_edge_src", "memory_edge", ["src_id"], unique=False)

    # Index on destination node for inbound edge queries
    op.create_index("idx_memory_edge_dst", "memory_edge", ["dst_id"], unique=False)

    # Create HNSW index on embedding_vec for ANN search (PostgreSQL with pgvector only)
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        # HNSW index with same configuration as PR-16
        # m=16 (connections per layer), ef_construction=64 (build quality)
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_node_embedding_hnsw
            ON memory_node USING hnsw (embedding_vec vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
            """
        )


def downgrade():
    """Remove memory graph tables"""

    # Drop indexes first
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP INDEX IF EXISTS idx_memory_node_embedding_hnsw;")

    op.drop_index("idx_memory_edge_dst", table_name="memory_edge")
    op.drop_index("idx_memory_edge_src", table_name="memory_edge")
    op.drop_index("idx_memory_edge_org_rel", table_name="memory_edge")
    op.drop_index("idx_memory_node_org_foreign", table_name="memory_node")
    op.drop_index("idx_memory_node_org_kind", table_name="memory_node")

    # Drop tables (CASCADE will handle foreign keys)
    op.drop_table("memory_edge")
    op.drop_table("memory_node")
