"""LLM telemetry audit table

Revision ID: 0007_llm_telemetry
Revises: 0006_tasks
Create Date: 2024-06-10

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0007_llm_telemetry"
down_revision = "0006_tasks"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "llm_call",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("phase", sa.String(32), nullable=False),  # e.g., plan|code|review
        sa.Column("model", sa.String(64), nullable=False),  # e.g., gpt-4.1|claude-3-5
        sa.Column("status", sa.String(16), nullable=False),  # ok|error
        # sha256 of prompt+context (64 chars for hex representation)
        sa.Column("prompt_hash", sa.String(64), nullable=True),
        sa.Column("tokens", sa.Integer, nullable=True),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("org_id", sa.String(64), nullable=True),  # future: multi-tenant
        sa.Column("user_id", sa.String(64), nullable=True),  # optional: from auth
    )
    op.create_index("ix_llm_call_created_at", "llm_call", ["created_at"])
    op.create_index("ix_llm_call_phase", "llm_call", ["phase"])
    op.create_index("ix_llm_call_model", "llm_call", ["model"])
    op.create_index("ix_llm_call_status", "llm_call", ["status"])


def downgrade():
    op.drop_index("ix_llm_call_status", table_name="llm_call")
    op.drop_index("ix_llm_call_model", table_name="llm_call")
    op.drop_index("ix_llm_call_phase", table_name="llm_call")
    op.drop_index("ix_llm_call_created_at", table_name="llm_call")
    op.drop_table("llm_call")
