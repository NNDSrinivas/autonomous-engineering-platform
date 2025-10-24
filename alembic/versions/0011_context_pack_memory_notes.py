"""episodic events + agent notes for RACP

Revision ID: 0011_context_pack_memory_notes
Revises: 0010_ext_connectors
Create Date: 2025-10-24 12:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0011_context_pack_memory_notes"
down_revision = "0010_ext_connectors"
branch_labels = None
depends_on = None


def upgrade():
    # Drop tables if they exist (handles re-running migration)
    op.drop_table("session_event", if_exists=True)
    op.drop_table("agent_note", if_exists=True)

    # Create session_event table for episodic memory
    op.create_table(
        "session_event",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column(
            "event_type", sa.String(32), nullable=False
        ),  # plan|decision|error|qa|exec|meeting
        sa.Column("task_key", sa.String(64), nullable=True),  # Optional task reference
        sa.Column("context", sa.Text, nullable=False),
        sa.Column("metadata", sa.Text),  # JSON metadata
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_session_event_org_session",
        "session_event",
        ["org_id", "session_id"],
    )

    # Create agent_note table for long-term consolidated memory
    op.create_table(
        "agent_note",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("task_key", sa.String(64), nullable=False),  # Task identifier
        sa.Column("context", sa.Text, nullable=False),  # Full context/details
        sa.Column("summary", sa.Text, nullable=False),  # Consolidated summary
        sa.Column("importance", sa.Integer, server_default="5"),  # 1-10 scale
        # NOTE: Using Text for tags instead of JSONB for cross-database compatibility (SQLite/PostgreSQL)
        # Application layer handles JSON parsing via parse_tags_field() helper in context/service.py
        sa.Column("tags", sa.Text),  # JSON array of tags
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_agent_note_org_task",
        "agent_note",
        ["org_id", "task_key"],
    )


def downgrade():
    # Drop tables (indices are automatically dropped with tables)
    op.drop_table("agent_note")
    op.drop_table("session_event")
