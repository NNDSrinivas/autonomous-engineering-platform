"""Add Slack and Confluence connections with encrypted tokens

Revision ID: 0010_slack_confluence_encrypted
Revises: 0009_memory_search
Create Date: 2025-10-23

Security:
- Slack bot tokens stored encrypted (bot_token_encrypted column)
- Confluence access tokens stored encrypted (access_token_encrypted column)
- Encryption uses Fernet (AES-128-CBC + HMAC-SHA256)
- Encryption key must be set via TOKEN_ENCRYPTION_KEY environment variable
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_slack_confluence_encrypted"
down_revision = "0009_memory_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create Slack and Confluence connection tables with encrypted token storage"""
    
    # Slack connection table
    op.create_table(
        "slack_connection",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("org_id", sa.Text, nullable=True),
        sa.Column("user_id", sa.Text, nullable=True),
        sa.Column("workspace_id", sa.Text, nullable=True),
        sa.Column("workspace_name", sa.Text, nullable=True),
        sa.Column("team_id", sa.Text, nullable=True),
        # Encrypted token column - stores encrypted bot token
        sa.Column("bot_token_encrypted", sa.Text, nullable=True),
        sa.Column("scopes", sa.JSON, nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
        ),
    )
    
    # Create index for faster org lookups
    op.create_index(
        "ix_slack_connection_org_id",
        "slack_connection",
        ["org_id"]
    )
    
    # Confluence connection table
    op.create_table(
        "confluence_connection",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("org_id", sa.Text, nullable=True),
        sa.Column("user_id", sa.Text, nullable=True),
        sa.Column("cloud_base_url", sa.Text, nullable=False),
        # Encrypted token column - stores encrypted access token
        sa.Column("access_token_encrypted", sa.Text, nullable=True),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("scopes", sa.JSON, nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
        ),
    )
    
    # Create index for faster org lookups
    op.create_index(
        "ix_confluence_connection_org_id",
        "confluence_connection",
        ["org_id"]
    )


def downgrade() -> None:
    """Remove Slack and Confluence connection tables"""
    op.drop_index("ix_confluence_connection_org_id", table_name="confluence_connection")
    op.drop_table("confluence_connection")
    op.drop_index("ix_slack_connection_org_id", table_name="slack_connection")
    op.drop_table("slack_connection")
