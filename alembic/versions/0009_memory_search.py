"""memory search tables

Revision ID: 0009_memory_search
Revises: 0008_org_policy_rbac_approvals
Create Date: 2025-10-23

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0009_memory_search"
down_revision = "0008_org_policy_rbac_approvals"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "memory_object",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),  # jira|meeting|action|code
        sa.Column("foreign_id", sa.String(128), nullable=False),
        sa.Column("title", sa.Text),
        sa.Column("url", sa.Text),
        sa.Column("lang", sa.String(12)),
        sa.Column("meta_json", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "memory_chunk",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "object_id",
            sa.Integer,
            sa.ForeignKey("memory_object.id", ondelete="CASCADE"),
        ),
        sa.Column("seq", sa.Integer, nullable=False, server_default="0"),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("embedding", sa.LargeBinary),  # JSON-encoded vector bytes
        sa.Column("vec_dim", sa.Integer),
        sa.Column("hash", sa.String(64)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_memory_object_org_source", "memory_object", ["org_id", "source"]
    )
    op.create_index("ix_memory_chunk_object_seq", "memory_chunk", ["object_id", "seq"])


def downgrade():
    op.drop_index("ix_memory_chunk_object_seq", table_name="memory_chunk")
    op.drop_index("ix_memory_object_org_source", table_name="memory_object")
    op.drop_table("memory_chunk")
    op.drop_table("memory_object")
