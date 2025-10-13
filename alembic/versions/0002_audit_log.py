"""audit log table

Revision ID: 0002_audit_log
Revises: 0001_init
Create Date: 2025-10-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_audit_log"
down_revision = "0001_init"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime, server_default=sa.text("(datetime('now'))")),
        sa.Column("org_id", sa.Text, nullable=True),
        sa.Column("user_email", sa.Text, nullable=True),
        sa.Column("service", sa.Text, nullable=False),
        sa.Column("method", sa.Text, nullable=False),
        sa.Column("path", sa.Text, nullable=False),
        sa.Column("status", sa.Integer, nullable=False),
        sa.Column("req_id", sa.Text, nullable=True),
    )
    op.create_index("ix_audit_log_ts", "audit_log", ["ts"])
    op.create_index("ix_audit_log_org_ts", "audit_log", ["org_id", "ts"])

def downgrade() -> None:
    op.drop_index("ix_audit_log_org_ts", table_name="audit_log")
    op.drop_index("ix_audit_log_ts", table_name="audit_log")
    op.drop_table("audit_log")
