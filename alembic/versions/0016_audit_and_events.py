"""Add plan events and enhanced audit log tables

Revision ID: 0016_audit_and_events
Revises: 0015_rbac_models
Create Date: 2025-10-30
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_audit_and_events"
down_revision = "0015_rbac_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create plan_events table for event replay
    op.create_table(
        "plan_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("plan_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("seq", sa.Integer, nullable=False, index=True),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("user_sub", sa.String(length=128), nullable=True),
        sa.Column("org_key", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_events_plan_seq", "plan_events", ["plan_id", "seq"], unique=True
    )
    op.create_index("ix_plan_events_created_at", "plan_events", ["created_at"])

    # Create enhanced audit log table (separate from existing audit_log)
    op.create_table(
        "audit_log_enhanced",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_key", sa.String(length=64), nullable=True, index=True),
        sa.Column("actor_sub", sa.String(length=128), nullable=True, index=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("route", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("status_code", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_audit_enhanced_org_created", "audit_log_enhanced", ["org_key", "created_at"]
    )
    op.create_index(
        "ix_audit_enhanced_actor_created",
        "audit_log_enhanced",
        ["actor_sub", "created_at"],
    )
    op.create_index(
        "ix_audit_enhanced_created_at", "audit_log_enhanced", ["created_at"]
    )


def downgrade() -> None:
    # Drop enhanced audit log table
    op.drop_index("ix_audit_enhanced_created_at", table_name="audit_log_enhanced")
    op.drop_index("ix_audit_enhanced_actor_created", table_name="audit_log_enhanced")
    op.drop_index("ix_audit_enhanced_org_created", table_name="audit_log_enhanced")
    op.drop_table("audit_log_enhanced")

    # Drop plan events table
    op.drop_index("ix_plan_events_created_at", table_name="plan_events")
    op.drop_index("ix_events_plan_seq", table_name="plan_events")
    op.drop_table("plan_events")
