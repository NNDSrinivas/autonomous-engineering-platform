"""org policy, rbac, approvals

Revision ID: 0008_org_policy_rbac_approvals
Revises: 0007_llm_telemetry
Create Date: 2025-10-22

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0008_org_policy_rbac_approvals"
down_revision = "0007_llm_telemetry"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "org",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
    )

    op.create_table(
        "org_user",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column(
            "role", sa.String(16), nullable=False
        ),  # admin|maintainer|developer|viewer
    )

    op.create_table(
        "org_policy",
        sa.Column("org_id", sa.String(64), sa.ForeignKey("org.id"), primary_key=True),
        sa.Column("models_allow", sa.Text),  # JSON array
        sa.Column(
            "phase_budgets", sa.Text
        ),  # JSON {plan,code,review:{tokens,usd_per_day}}
        sa.Column("commands_allow", sa.Text),  # JSON array
        sa.Column("commands_deny", sa.Text),  # JSON array
        sa.Column("paths_allow", sa.Text),  # JSON array of globs
        sa.Column("repos_allow", sa.Text),  # JSON array org/repo
        sa.Column("branches_protected", sa.Text),  # JSON array
        sa.Column("required_reviewers", sa.Integer, server_default="1"),
        sa.Column(
            "require_review_for", sa.Text
        ),  # JSON array of action kinds [edit,cmd,git,pr,jira]
    )

    op.create_table(
        "change_request",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.String(64), sa.ForeignKey("org.id"), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("ticket_key", sa.String(64)),
        sa.Column("title", sa.String(256)),
        sa.Column("plan_json", sa.Text, nullable=False),  # proposed steps
        sa.Column("patch_summary", sa.Text),  # optional unified diff summary text
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="pending"
        ),  # pending|approved|rejected
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "change_review",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "change_id",
            sa.Integer,
            sa.ForeignKey("change_request.id", ondelete="CASCADE"),
        ),
        sa.Column("reviewer_id", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),  # approve|reject
        sa.Column("comment", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_index("ix_org_user_org", "org_user", ["org_id"])
    op.create_index("ix_change_status", "change_request", ["status"])
    op.create_index("ix_change_org", "change_request", ["org_id"])


def downgrade():
    op.drop_index("ix_change_org", table_name="change_request")
    op.drop_index("ix_change_status", table_name="change_request")
    op.drop_index("ix_org_user_org", table_name="org_user")
    op.drop_table("change_review")
    op.drop_table("change_request")
    op.drop_table("org_policy")
    op.drop_table("org_user")
    op.drop_table("org")
