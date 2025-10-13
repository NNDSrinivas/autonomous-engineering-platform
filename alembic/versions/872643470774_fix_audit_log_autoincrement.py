"""
Migration to fix autoincrement issues in the audit_log table.

Problem encountered:
The original audit_log table used a BigInteger primary key with autoincrement enabled.
In SQLite, autoincrement only works correctly when the primary key column is defined as
INTEGER PRIMARY KEY (not BigInteger or other types). Using BigInteger or other types can
result in SQLite not auto-generating unique IDs as expected, leading to integrity errors
or duplicate key issues.

Why this fix:
To ensure proper autoincrement behavior across all supported databases (especially SQLite),
this migration drops and recreates the audit_log table with the id column defined as
sa.Integer, primary_key=True, autoincrement=True. This matches SQLite's requirements for
autoincrement and avoids issues seen with the previous schema.

The migration also recreates the necessary indexes after the table is redefined.
"""

from alembic import op
import sqlalchemy as sa

revision = "fix_audit_log_autoincrement"
down_revision = "0002_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop and recreate the table with proper INTEGER PRIMARY KEY for SQLite autoincrement
    op.drop_index("ix_audit_log_org_ts", table_name="audit_log")
    op.drop_index("ix_audit_log_ts", table_name="audit_log")
    op.drop_table("audit_log")

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime, server_default=sa.func.now()),
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

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime, server_default=sa.func.now()),
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
