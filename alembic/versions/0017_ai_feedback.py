"""Add AI feedback and generation logging tables

Revision ID: 0017_ai_feedback
Revises: 0016_audit_and_events
Create Date: 2025-11-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_ai_feedback"
down_revision = "0016_audit_and_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_generation_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_key", sa.String(64), index=True),
        sa.Column("user_sub", sa.String(128), index=True),
        sa.Column("task_type", sa.String(48), nullable=False),  # e.g., codegen, summarize
        sa.Column("input_fingerprint", sa.String(64), nullable=True),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("temperature", sa.Float, nullable=False),
        sa.Column("params", sa.JSON, nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("result_ref", sa.String(128), nullable=True),  # e.g., diff sha
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )

    op.create_table(
        "ai_feedback",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("gen_id", sa.Integer, sa.ForeignKey("ai_generation_log.id", ondelete="CASCADE"), index=True),
        sa.Column("org_key", sa.String(64), index=True),
        sa.Column("user_sub", sa.String(128), index=True),
        sa.Column("rating", sa.SmallInteger, nullable=False),  # +1 thumbs-up, 0 neutral, -1 thumbs-down
        sa.Column("reason", sa.String(64), nullable=True),     # correctness, style, performance, security, other
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("ai_feedback")
    op.drop_table("ai_generation_log")