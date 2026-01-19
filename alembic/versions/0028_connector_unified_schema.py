"""Unified connector schema for NAVI integration

Adds sync tracking to connectors table and creates connector_items table
for storing synced data from all providers (Linear, GitLab, Notion, Slack, Asana, etc.)

Revision ID: 0028_connector_unified_schema
Revises: 0027_navi_memory_system
Create Date: 2026-01-17

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import logging

logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = "0028_connector_unified_schema"
down_revision = "0027_navi_memory_system"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # Add sync tracking columns to connectors table
    # Check if columns already exist first
    inspector = sa.inspect(bind)
    existing_columns = [col["name"] for col in inspector.get_columns("connectors")]

    if "last_synced_at" not in existing_columns:
        op.add_column(
            "connectors",
            sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "sync_status" not in existing_columns:
        op.add_column(
            "connectors",
            sa.Column(
                "sync_status",
                sa.String(length=20),
                nullable=True,
                server_default="pending",
            ),
        )

    if "sync_error" not in existing_columns:
        op.add_column(
            "connectors",
            sa.Column("sync_error", sa.Text(), nullable=True),
        )

    if "org_id" not in existing_columns:
        op.add_column(
            "connectors",
            sa.Column("org_id", sa.String(length=200), nullable=True),
        )

    # Create connector_items table for storing synced data
    # Use UUID for PostgreSQL, String for SQLite
    if is_postgres:
        op.create_table(
            "connector_items",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("connector_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("item_type", sa.String(length=50), nullable=False),
            sa.Column("external_id", sa.String(length=255), nullable=False),
            # Common fields
            sa.Column("title", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=100), nullable=True),
            sa.Column("url", sa.Text(), nullable=True),
            # Flexible data storage
            sa.Column("data", JSONB(), nullable=False, server_default="{}"),
            # Metadata
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.Column("external_created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("external_updated_at", sa.DateTime(timezone=True), nullable=True),
            # User association
            sa.Column("user_id", sa.String(length=200), nullable=True),
            sa.Column("org_id", sa.String(length=200), nullable=True),
            sa.Column("assignee", sa.String(length=255), nullable=True),
            # Unique constraint
            sa.UniqueConstraint(
                "connector_id",
                "provider",
                "item_type",
                "external_id",
                name="uq_connector_item",
            ),
            sa.ForeignKeyConstraint(
                ["connector_id"],
                ["connectors.id"],
                name="fk_connector_items_connector",
                ondelete="CASCADE",
            ),
        )
    else:
        # SQLite version
        op.create_table(
            "connector_items",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("connector_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=50), nullable=False),
            sa.Column("item_type", sa.String(length=50), nullable=False),
            sa.Column("external_id", sa.String(length=255), nullable=False),
            # Common fields
            sa.Column("title", sa.Text(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=100), nullable=True),
            sa.Column("url", sa.Text(), nullable=True),
            # Flexible data storage (JSON for SQLite)
            sa.Column("data", sa.JSON(), nullable=False, server_default="{}"),
            # Metadata
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.Column("external_created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("external_updated_at", sa.DateTime(timezone=True), nullable=True),
            # User association
            sa.Column("user_id", sa.String(length=200), nullable=True),
            sa.Column("org_id", sa.String(length=200), nullable=True),
            sa.Column("assignee", sa.String(length=255), nullable=True),
            # Unique constraint
            sa.UniqueConstraint(
                "connector_id",
                "provider",
                "item_type",
                "external_id",
                name="uq_connector_item",
            ),
            sa.ForeignKeyConstraint(
                ["connector_id"],
                ["connectors.id"],
                name="fk_connector_items_connector",
                ondelete="CASCADE",
            ),
        )

    # Create indexes for common queries
    op.create_index(
        "idx_connector_items_provider",
        "connector_items",
        ["provider", "item_type"],
    )
    op.create_index(
        "idx_connector_items_connector",
        "connector_items",
        ["connector_id"],
    )
    op.create_index(
        "idx_connector_items_user",
        "connector_items",
        ["user_id"],
    )
    op.create_index(
        "idx_connector_items_org",
        "connector_items",
        ["org_id"],
    )
    op.create_index(
        "idx_connector_items_assignee",
        "connector_items",
        ["assignee"],
    )
    op.create_index(
        "idx_connector_items_status",
        "connector_items",
        ["status"],
    )
    op.create_index(
        "idx_connector_items_external_updated",
        "connector_items",
        ["external_updated_at"],
    )


def downgrade():
    # Drop indexes
    op.drop_index("idx_connector_items_external_updated", table_name="connector_items")
    op.drop_index("idx_connector_items_status", table_name="connector_items")
    op.drop_index("idx_connector_items_assignee", table_name="connector_items")
    op.drop_index("idx_connector_items_org", table_name="connector_items")
    op.drop_index("idx_connector_items_user", table_name="connector_items")
    op.drop_index("idx_connector_items_connector", table_name="connector_items")
    op.drop_index("idx_connector_items_provider", table_name="connector_items")

    # Drop table
    op.drop_table("connector_items")

    # Remove added columns from connectors table
    op.drop_column("connectors", "org_id")
    op.drop_column("connectors", "sync_error")
    op.drop_column("connectors", "sync_status")
    op.drop_column("connectors", "last_synced_at")
