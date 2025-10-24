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
    # Create session_event table for episodic memory
    op.create_table(
        "session_event",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column(
            "kind", sa.String(32), nullable=False
        ),  # plan|decision|error|qa|exec|meeting
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("meta_json", sa.Text),
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
        sa.Column(
            "scope", sa.String(32), nullable=False
        ),  # repo|service|team|project|personal
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body_md", sa.Text, nullable=False),
        sa.Column("tags", sa.Text),  # JSON array
        sa.Column("importance", sa.Float, server_default="0.5"),
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
        "ix_agent_note_org_scope",
        "agent_note",
        ["org_id", "scope"],
    )


def downgrade():
    op.drop_index("ix_agent_note_org_scope", table_name="agent_note")
    op.drop_table("agent_note")
    op.drop_index("ix_session_event_org_session", table_name="session_event")
    op.drop_table("session_event")
