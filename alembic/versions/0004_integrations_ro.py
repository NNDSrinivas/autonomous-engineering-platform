"""jira + github read-only

Revision ID: 0004_integrations_ro
Revises: ba72f0e6da5f
Create Date: 2025-10-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_integrations_ro"
down_revision = "ba72f0e6da5f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jira_connection",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("org_id", sa.Text, nullable=True),
        sa.Column("user_id", sa.Text, nullable=True),
        sa.Column("cloud_base_url", sa.Text, nullable=False),
        sa.Column("token_type", sa.Text, nullable=True),
        sa.Column("access_token", sa.Text, nullable=True),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("scopes", sa.JSON, nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_table(
        "jira_project_config",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("org_id", sa.Text, nullable=True),
        sa.Column(
            "connection_id",
            sa.Text,
            sa.ForeignKey("jira_connection.id", ondelete="CASCADE"),
        ),
        sa.Column("project_keys", sa.JSON, nullable=False),
        sa.Column("default_jql", sa.Text, nullable=True),
        sa.Column("last_sync_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_table(
        "jira_issue",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "connection_id",
            sa.Text,
            sa.ForeignKey("jira_connection.id", ondelete="CASCADE"),
        ),
        sa.Column("project_key", sa.Text, nullable=False),
        sa.Column("issue_key", sa.Text, unique=True, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=True),
        sa.Column("priority", sa.Text, nullable=True),
        sa.Column("assignee", sa.Text, nullable=True),
        sa.Column("reporter", sa.Text, nullable=True),
        sa.Column("labels", sa.JSON, nullable=True),
        sa.Column("epic_key", sa.Text, nullable=True),
        sa.Column("sprint", sa.Text, nullable=True),
        sa.Column("updated", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("raw", sa.JSON, nullable=True),
        sa.Column("indexed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_jira_issue_project", "jira_issue", ["project_key"])
    op.create_index("ix_jira_issue_updated", "jira_issue", ["updated"])

    op.create_table(
        "gh_connection",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("org_id", sa.Text, nullable=True),
        sa.Column("user_id", sa.Text, nullable=True),
        sa.Column("token_type", sa.Text, nullable=True),  # app|oauth
        sa.Column("installation_id", sa.Text, nullable=True),
        sa.Column("access_token", sa.Text, nullable=True),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("scopes", sa.JSON, nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_table(
        "gh_repo",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "connection_id",
            sa.Text,
            sa.ForeignKey("gh_connection.id", ondelete="CASCADE"),
        ),
        sa.Column("repo_full_name", sa.Text, nullable=False),  # org/repo
        sa.Column("default_branch", sa.Text, nullable=True),
        sa.Column("is_private", sa.Boolean, nullable=True),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("last_index_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("index_mode", sa.Text, nullable=True),  # api|git (placeholder)
    )
    op.create_table(
        "gh_file",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("repo_id", sa.Text, sa.ForeignKey("gh_repo.id", ondelete="CASCADE")),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=True),
        sa.Column("lang", sa.Text, nullable=True),
        sa.Column("sha", sa.Text, nullable=True),
        sa.Column("updated", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_gh_file_repo_path", "gh_file", ["repo_id", "path"])

    op.create_table(
        "gh_issue_pr",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("repo_id", sa.Text, sa.ForeignKey("gh_repo.id", ondelete="CASCADE")),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("type", sa.Text, nullable=False),  # issue|pr
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("state", sa.Text, nullable=True),
        sa.Column("author", sa.Text, nullable=True),
        sa.Column("updated", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("url", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_gh_issue_pr_repo_updated", "gh_issue_pr", ["repo_id", "updated"]
    )


def downgrade() -> None:
    op.drop_index("ix_gh_issue_pr_repo_updated", table_name="gh_issue_pr")
    op.drop_table("gh_issue_pr")
    op.drop_index("ix_gh_file_repo_path", table_name="gh_file")
    op.drop_table("gh_file")
    op.drop_table("gh_repo")
    op.drop_table("gh_connection")
    op.drop_index("ix_jira_issue_updated", table_name="jira_issue")
    op.drop_index("ix_jira_issue_project", table_name="jira_issue")
    op.drop_table("jira_issue")
    op.drop_table("jira_project_config")
    op.drop_table("jira_connection")
