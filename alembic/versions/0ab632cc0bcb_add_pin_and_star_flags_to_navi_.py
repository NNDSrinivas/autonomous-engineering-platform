"""Add pinned/starred flags to NAVI conversations.

Revision ID: 0ab632cc0bcb
Revises: 0033_add_checkpoint_gate_columns
Create Date: 2026-02-06
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0ab632cc0bcb"
down_revision = "0033_add_checkpoint_gate_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns with server_default to set default for existing rows
    op.add_column(
        "navi_conversations",
        sa.Column(
            "is_pinned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "navi_conversations",
        sa.Column(
            "is_starred",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # Keep server_default to avoid breaking non-ORM insert paths (raw SQL, older services, etc.)
    # The ORM also has Python defaults, but DB defaults provide a safety net for all insert paths


def downgrade() -> None:
    op.drop_column("navi_conversations", "is_starred")
    op.drop_column("navi_conversations", "is_pinned")
