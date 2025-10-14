"""meetings mvp tables

Revision ID: ba72f0e6da5f
Revises: fix_audit_log_autoincrement
Create Date: 2025-10-13

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "ba72f0e6da5f"
down_revision = "fix_audit_log_autoincrement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Note: pgcrypto extension only needed for PostgreSQL, skip for SQLite
    # op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    op.create_table(
        "meeting",
        sa.Column("id", sa.Text, primary_key=True),  # UUID string
        sa.Column("session_id", sa.Text, unique=True, nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("provider", sa.Text, nullable=True),  # zoom|teams|meet|manual
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "participants", sa.JSON, nullable=True
        ),  # [{"name":..., "email":...}]
        sa.Column("org_id", sa.Text, nullable=True),
    )
    op.create_index("ix_meeting_started", "meeting", ["started_at"])

    op.create_table(
        "transcript_segment",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "meeting_id", sa.Text, sa.ForeignKey("meeting.id", ondelete="CASCADE")
        ),
        sa.Column("ts_start_ms", sa.Integer, nullable=True),
        sa.Column("ts_end_ms", sa.Integer, nullable=True),
        sa.Column("speaker", sa.Text, nullable=True),
        sa.Column("text", sa.Text, nullable=False),
    )
    op.create_index("ix_transcript_meeting", "transcript_segment", ["meeting_id"])

    op.create_table(
        "meeting_summary",
        sa.Column(
            "meeting_id",
            sa.Text,
            sa.ForeignKey("meeting.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("bullets", sa.JSON, nullable=True),
        sa.Column("decisions", sa.JSON, nullable=True),
        sa.Column("risks", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("(datetime('now'))"),
        ),  # SQLite compatible
    )

    op.create_table(
        "action_item",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "meeting_id", sa.Text, sa.ForeignKey("meeting.id", ondelete="CASCADE")
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("assignee", sa.Text, nullable=True),
        sa.Column("due_hint", sa.Text, nullable=True),
        sa.Column("confidence", sa.Numeric, nullable=True),
        sa.Column(
            "source_segment",
            sa.Text,
            sa.ForeignKey("transcript_segment.id", ondelete="SET NULL"),
        ),
    )
    op.create_index("ix_action_meeting", "action_item", ["meeting_id"])


def downgrade() -> None:
    op.drop_index("ix_action_meeting", table_name="action_item")
    op.drop_table("action_item")
    op.drop_table("meeting_summary")
    op.drop_index("ix_transcript_meeting", table_name="transcript_segment")
    op.drop_table("transcript_segment")
    op.drop_index("ix_meeting_started", table_name="meeting")
    op.drop_table("meeting")
