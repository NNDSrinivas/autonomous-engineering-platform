"""session answers table

Revision ID: 0005_session_answer
Revises: 0004_integrations_ro
Create Date: 2025-10-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_session_answer"
down_revision = "0004_integrations_ro"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_answer",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("session_id", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column(
            "citations", sa.JSON, nullable=True
        ),  # [{"type":"meeting|jira|code|pr", ...}]
        sa.Column("confidence", sa.Numeric, nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
    )
    op.create_index(
        "ix_session_answer_session_created",
        "session_answer",
        ["session_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_session_answer_session_created", table_name="session_answer")
    op.drop_table("session_answer")
