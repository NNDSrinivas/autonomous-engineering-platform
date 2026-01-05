"""Phase 5.1 governance tables

Revision ID: 0025_governance_phase51
Revises: 0024_connectors_ci_runs
Create Date: 2025-12-25

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0025_governance_phase51"
down_revision = "0024_connectors_ci_runs"
branch_labels = None
depends_on = None


def upgrade():
    # Autonomy Policy table - per-user governance settings
    op.create_table(
        "autonomy_policy",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("repo", sa.String(256)),  # NULL for global policy
        sa.Column(
            "autonomy_level", sa.String(16), nullable=False, server_default="standard"
        ),
        sa.Column("max_auto_risk", sa.Float, nullable=False, server_default="0.3"),
        sa.Column("blocked_actions", sa.Text),  # JSON array
        sa.Column("auto_allowed_actions", sa.Text),  # JSON array
        sa.Column("require_approval_for", sa.Text),  # JSON array
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Create unique constraint for user+org+repo combination
    op.create_index(
        "ix_autonomy_policy_user_org_repo",
        "autonomy_policy",
        ["user_id", "org_id", "repo"],
        unique=True,
    )

    # Approval Request table - pending approvals
    op.create_table(
        "approval_request",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("requester_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("repo", sa.String(256)),
        sa.Column("risk_score", sa.Float, nullable=False),
        sa.Column("risk_reasons", sa.Text),  # JSON array
        sa.Column("plan_summary", sa.String(512)),
        sa.Column("context_data", sa.Text),  # JSON object
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("approver_id", sa.String(64)),
        sa.Column("approver_comment", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # Create indexes for approval requests
    op.create_index(
        "ix_approval_request_org_status", "approval_request", ["org_id", "status"]
    )
    op.create_index(
        "ix_approval_request_requester", "approval_request", ["requester_id"]
    )
    op.create_index("ix_approval_request_created", "approval_request", ["created_at"])

    # Governance Audit Log table - comprehensive audit trail
    op.create_table(
        "governance_audit_log",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column(
            "decision", sa.String(32), nullable=False
        ),  # AUTO, APPROVAL_REQUIRED, BLOCKED, APPROVED, REJECTED, EXECUTED
        sa.Column("risk_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("execution_result", sa.String(128)),
        sa.Column("artifacts", sa.Text),  # JSON object
        sa.Column("rollback_available", sa.Boolean, server_default="false"),
    )

    # Create indexes for audit log
    op.create_index(
        "ix_gov_audit_log_org_timestamp",
        "governance_audit_log",
        ["org_id", "timestamp"],
    )
    op.create_index(
        "ix_gov_audit_log_user_timestamp",
        "governance_audit_log",
        ["user_id", "timestamp"],
    )
    op.create_index(
        "ix_gov_audit_log_action_type", "governance_audit_log", ["action_type"]
    )
    op.create_index("ix_gov_audit_log_decision", "governance_audit_log", ["decision"])
    op.create_index(
        "ix_gov_audit_log_risk_score", "governance_audit_log", ["risk_score"]
    )

    # Rollback History table - track rollbacks
    op.create_table(
        "rollback_history",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("original_action_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("message", sa.Text),
        sa.Column("strategy", sa.String(64)),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # Create indexes for rollback history
    op.create_index(
        "ix_rollback_history_org_timestamp", "rollback_history", ["org_id", "timestamp"]
    )
    op.create_index(
        "ix_rollback_history_original_action",
        "rollback_history",
        ["original_action_id"],
    )
    op.create_index("ix_rollback_history_user", "rollback_history", ["user_id"])


def downgrade():
    op.drop_index("ix_rollback_history_user", table_name="rollback_history")
    op.drop_index("ix_rollback_history_original_action", table_name="rollback_history")
    op.drop_index("ix_rollback_history_org_timestamp", table_name="rollback_history")
    op.drop_table("rollback_history")

    op.drop_index("ix_gov_audit_log_risk_score", table_name="governance_audit_log")
    op.drop_index("ix_gov_audit_log_decision", table_name="governance_audit_log")
    op.drop_index("ix_gov_audit_log_action_type", table_name="governance_audit_log")
    op.drop_index("ix_gov_audit_log_user_timestamp", table_name="governance_audit_log")
    op.drop_index("ix_gov_audit_log_org_timestamp", table_name="governance_audit_log")
    op.drop_table("governance_audit_log")

    op.drop_index("ix_approval_request_created", table_name="approval_request")
    op.drop_index("ix_approval_request_requester", table_name="approval_request")
    op.drop_index("ix_approval_request_org_status", table_name="approval_request")
    op.drop_table("approval_request")

    op.drop_index("ix_autonomy_policy_user_org_repo", table_name="autonomy_policy")
    op.drop_table("autonomy_policy")
