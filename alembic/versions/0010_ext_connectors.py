"""ext connectors for slack/confluence/wiki/zoom/teams (read)

Revision ID: 0010_ext_connectors
Revises: 0009_memory_search
Create Date: 2025-10-23

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0010_ext_connectors"
down_revision = "0009_memory_search"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "slack_connection",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("bot_token", sa.Text, nullable=False),
        sa.Column("team_id", sa.String(64)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "confluence_connection",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("base_url", sa.Text, nullable=False),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("email", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "sync_cursor",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column(
            "source", sa.String(32), nullable=False
        ),  # slack|confluence|wiki|zoom|teams
        sa.Column("cursor", sa.Text),  # timestamp/etag/id
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "wiki_page",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("url", sa.Text),
        sa.Column("content", sa.Text),
        sa.Column("updated", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_sync_cursor_org_src", "sync_cursor", ["org_id", "source"])


def downgrade():
    op.drop_index("ix_sync_cursor_org_src", table_name="sync_cursor")
    op.drop_table("wiki_page")
    op.drop_table("sync_cursor")
    op.drop_table("confluence_connection")
    op.drop_table("slack_connection")
