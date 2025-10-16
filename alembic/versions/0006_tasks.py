"""task system tables

Revision ID: 0006_tasks
Revises: 0005_session_answer
Create Date: 2025-10-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_tasks"
down_revision = "0005_session_answer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "meeting_id",
            sa.Text,
            sa.ForeignKey("meeting.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "action_item_id",
            sa.Text,
            sa.ForeignKey("action_item.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.Text,
            nullable=False,
            server_default="open",
        ),
        sa.Column("assignee", sa.Text, nullable=True),
        sa.Column("priority", sa.Text, nullable=True),
        sa.Column("due_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("org_id", sa.Text, nullable=True),
    )
    op.create_index("ix_task_status", "task", ["status"])
    op.create_index("ix_task_assignee", "task", ["assignee"])
    op.create_index("ix_task_org", "task", ["org_id"])

    op.create_table(
        "task_event",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("task_id", sa.Text, sa.ForeignKey("task.id", ondelete="CASCADE")),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("data", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        ),
    )
    op.create_index("ix_task_event_task", "task_event", ["task_id"])

    op.create_table(
        "task_dependency",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("task_id", sa.Text, sa.ForeignKey("task.id", ondelete="CASCADE")),
        sa.Column(
            "depends_on_task_id",
            sa.Text,
            sa.ForeignKey("task.id", ondelete="CASCADE"),
        ),
    )
    op.create_index("ix_task_dep_task", "task_dependency", ["task_id"])

    op.create_table(
        "task_link",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("task_id", sa.Text, sa.ForeignKey("task.id", ondelete="CASCADE")),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("key", sa.Text, nullable=True),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("meta", sa.JSON, nullable=True),
    )
    op.create_index("ix_task_link_task", "task_link", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_task_link_task", table_name="task_link")
    op.drop_table("task_link")
    op.drop_index("ix_task_dep_task", table_name="task_dependency")
    op.drop_table("task_dependency")
    op.drop_index("ix_task_event_task", table_name="task_event")
    op.drop_table("task_event")
    op.drop_index("ix_task_org", table_name="task")
    op.drop_index("ix_task_assignee", table_name="task")
    op.drop_index("ix_task_status", table_name="task")
    op.drop_table("task")
