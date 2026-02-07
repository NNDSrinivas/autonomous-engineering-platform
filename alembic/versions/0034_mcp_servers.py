"""add mcp servers table

Revision ID: 0034_mcp_servers
Revises: 0ab632cc0bcb
Create Date: 2026-02-07
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0034_mcp_servers"
down_revision = "0ab632cc0bcb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("url", sa.String(length=600), nullable=False),
        sa.Column(
            "transport",
            sa.String(length=40),
            nullable=False,
            server_default="streamable_http",
        ),
        sa.Column(
            "auth_type", sa.String(length=40), nullable=False, server_default="none"
        ),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("secret_json", sa.LargeBinary(), nullable=True),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="unknown"
        ),
        sa.Column("tool_count", sa.Integer(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("user_id", sa.String(length=200), nullable=True),
        sa.Column("org_id", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_mcp_servers_user_id", "mcp_servers", ["user_id"])
    op.create_index("ix_mcp_servers_org_id", "mcp_servers", ["org_id"])
    op.create_index("ix_mcp_servers_name", "mcp_servers", ["name"])


def downgrade() -> None:
    op.drop_index("ix_mcp_servers_name", table_name="mcp_servers")
    op.drop_index("ix_mcp_servers_org_id", table_name="mcp_servers")
    op.drop_index("ix_mcp_servers_user_id", table_name="mcp_servers")
    op.drop_table("mcp_servers")
