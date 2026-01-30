"""Enterprise checkpoints for crash recovery

Revision ID: 0030_enterprise_checkpoints
Revises: 0029_enterprise_projects
Create Date: 2026-01-26

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0030_enterprise_checkpoints"
down_revision = "0029_enterprise_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Skip for SQLite (CI uses SQLite for unit tests, this is PostgreSQL-specific)
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        import logging

        logging.getLogger(__name__).info(
            "Skipping enterprise_checkpoints migration for non-PostgreSQL database (%s)",
            bind.dialect.name,
        )
        return

    # Create enterprise_checkpoints table
    op.create_table(
        "enterprise_checkpoints",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "checkpoint_type",
            sa.String(50),
            nullable=False,
            server_default="automatic",
        ),
        sa.Column(
            "iteration_number",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "checkpoint_reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "agent_state",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "conversation_history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "tool_call_history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "files_modified",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "files_created",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "file_snapshots",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "error_history",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "failed_approaches",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "completed_tasks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "pending_tasks",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "current_task_progress",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "context_summary",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "is_context_summarized",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "verification_results",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "is_valid",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "invalidation_reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "restored_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["enterprise_projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["project_task_queue.id"],
            ondelete="SET NULL",
        ),
    )

    # Create indexes
    op.create_index(
        "idx_checkpoint_project_iteration",
        "enterprise_checkpoints",
        ["project_id", "iteration_number"],
    )
    op.create_index(
        "idx_checkpoint_project_valid",
        "enterprise_checkpoints",
        ["project_id", "is_valid"],
    )
    op.create_index(
        "idx_checkpoint_created",
        "enterprise_checkpoints",
        ["created_at"],
    )


def downgrade() -> None:
    # Skip for SQLite
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        import logging

        logging.getLogger(__name__).info(
            "Skipping enterprise_checkpoints downgrade for non-PostgreSQL database (%s)",
            bind.dialect.name,
        )
        return

    # Drop indexes
    op.drop_index("idx_checkpoint_created", table_name="enterprise_checkpoints")
    op.drop_index("idx_checkpoint_project_valid", table_name="enterprise_checkpoints")
    op.drop_index(
        "idx_checkpoint_project_iteration", table_name="enterprise_checkpoints"
    )

    # Drop table
    op.drop_table("enterprise_checkpoints")
