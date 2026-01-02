"""add connectors and ci_runs tables

Revision ID: 0024_connectors_ci_runs
Revises: 0023_change_sets
Create Date: 2025-03-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0024_connectors_ci_runs"
down_revision = "0023_change_sets"
branch_labels = None
depends_on = None


def upgrade():
    # Drop existing tables and indexes if they exist
    op.execute("DROP TABLE IF EXISTS connectors")
    op.execute("DROP TABLE IF EXISTS ci_runs")
    op.execute("DROP INDEX IF EXISTS ix_connectors_provider")
    op.execute("DROP INDEX IF EXISTS ix_connectors_workspace_user")
    op.execute("DROP INDEX IF EXISTS ix_connectors_workspace_root")
    op.execute("DROP INDEX IF EXISTS ix_connectors_user_id")
    
    op.create_table(
        "connectors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("secret_json", sa.LargeBinary(), nullable=True),
        sa.Column("workspace_root", sa.String(length=500), nullable=True),
        sa.Column("user_id", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_connectors_provider", "connectors", ["provider"])
    op.create_index("ix_connectors_workspace_user", "connectors", ["workspace_root", "user_id"])

    op.create_table(
        "ci_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("repo", sa.String(length=300), nullable=True),
        sa.Column("workflow", sa.String(length=200), nullable=True),
        sa.Column("run_id", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("conclusion", sa.String(length=50), nullable=True),
        sa.Column("url", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta_json", sa.Text(), nullable=True),
        sa.Column("workspace_root", sa.String(length=500), nullable=True),
        sa.Column("user_id", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_ci_runs_provider", "ci_runs", ["provider"])
    op.create_index("ix_ci_runs_repo", "ci_runs", ["repo"])
    op.create_index("ix_ci_runs_run_id_provider", "ci_runs", ["run_id", "provider"])


def downgrade():
    op.drop_index("ix_ci_runs_run_id_provider", table_name="ci_runs")
    op.drop_index("ix_ci_runs_repo", table_name="ci_runs")
    op.drop_index("ix_ci_runs_provider", table_name="ci_runs")
    op.drop_table("ci_runs")
    op.drop_index("ix_connectors_workspace_user", table_name="connectors")
    op.drop_index("ix_connectors_provider", table_name="connectors")
    op.drop_table("connectors")
