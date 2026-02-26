"""Enterprise Projects for Long-Running Development

Creates tables for enterprise-level project management:
- enterprise_projects: Main project entity with goals, milestones, ADRs
- human_checkpoint_gates: Human approval gates for critical decisions
- project_task_queue: Task queue with dependencies and verification

These tables enable building full enterprise applications (e-commerce, microservices)
that span weeks/months of development.

Revision ID: 0029_enterprise_projects
Revises: 0028_connector_unified_schema
Create Date: 2026-01-25

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from typing import Any

# revision identifiers, used by Alembic.
revision = "0029_enterprise_projects"
down_revision = "0028b_session_facts"
branch_labels = None
depends_on = None


def upgrade():
    """Create enterprise project tables"""
    conn = op.get_bind()
    is_postgres = conn.dialect.name == "postgresql"

    # Use appropriate types per dialect
    uuid_type: Any = PG_UUID(as_uuid=True) if is_postgres else sa.String(36)
    json_type: Any = JSONB if is_postgres else sa.JSON

    # Use appropriate defaults per dialect
    timestamp_default = (
        sa.text("now()") if is_postgres else sa.text("CURRENT_TIMESTAMP")
    )
    uuid_default = sa.text("gen_random_uuid()") if is_postgres else None
    json_empty_obj = sa.text("'{}'::jsonb") if is_postgres else sa.text("'{}'")
    json_empty_arr = sa.text("'[]'::jsonb") if is_postgres else sa.text("'[]'")

    # =========================================================================
    # ENTERPRISE PROJECTS TABLE
    # =========================================================================

    op.create_table(
        "enterprise_projects",
        sa.Column("id", uuid_type, primary_key=True, server_default=uuid_default),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_session_id",
            uuid_type,
            sa.ForeignKey("navi_workspace_sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Project metadata
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "project_type",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'general'"),
        ),
        # Goals and progress (stored as JSONB arrays)
        sa.Column("goals", json_type, server_default=json_empty_arr),
        sa.Column("milestones", json_type, server_default=json_empty_arr),
        sa.Column("completed_components", json_type, server_default=json_empty_arr),
        sa.Column("pending_components", json_type, server_default=json_empty_arr),
        # Architecture Decision Records
        sa.Column("architecture_decisions", json_type, server_default=json_empty_arr),
        # Blockers and human decisions
        sa.Column("blockers", json_type, server_default=json_empty_arr),
        sa.Column("human_decisions", json_type, server_default=json_empty_arr),
        # Project configuration
        sa.Column("config", json_type, server_default=json_empty_obj),
        # Status and progress
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'planning'"),
        ),
        sa.Column("progress_percentage", sa.Integer(), nullable=False, default=0),
        # Iteration tracking
        sa.Column("total_iterations", sa.Integer(), nullable=False, default=0),
        sa.Column("last_checkpoint_iteration", sa.Integer(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=timestamp_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=timestamp_default,
            nullable=False,
        ),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes for enterprise_projects
    op.create_index(
        "idx_enterprise_projects_user",
        "enterprise_projects",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_enterprise_projects_status",
        "enterprise_projects",
        ["status"],
    )
    op.create_index(
        "idx_enterprise_projects_workspace",
        "enterprise_projects",
        ["workspace_session_id"],
    )

    # =========================================================================
    # PROJECT TASK QUEUE TABLE
    # =========================================================================

    op.create_table(
        "project_task_queue",
        sa.Column("id", uuid_type, primary_key=True, server_default=uuid_default),
        sa.Column(
            "project_id",
            uuid_type,
            sa.ForeignKey("enterprise_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Task identification
        sa.Column("task_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "task_type",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'development'"),
        ),
        # Priority and dependencies
        sa.Column("priority", sa.Integer(), nullable=False, default=50),
        sa.Column("dependencies", json_type, server_default=json_empty_arr),
        sa.Column("can_parallelize", sa.Boolean(), default=False),
        # Verification
        sa.Column("verification_criteria", json_type, server_default=json_empty_arr),
        sa.Column("verification_result", json_type, nullable=True),
        sa.Column("verification_passed", sa.Boolean(), default=False),
        # Task outputs
        sa.Column("outputs", json_type, server_default=json_empty_arr),
        sa.Column("modified_files", json_type, server_default=json_empty_arr),
        # Milestone association
        sa.Column("milestone_id", sa.String(100), nullable=True),
        # Parent task for sub-tasks
        sa.Column(
            "parent_task_id",
            uuid_type,
            sa.ForeignKey("project_task_queue.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Status and progress
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("progress_percentage", sa.Integer(), nullable=False, default=0),
        # Error tracking
        sa.Column("error_count", sa.Integer(), nullable=False, default=0),
        sa.Column("last_error", sa.Text(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=timestamp_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=timestamp_default,
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create indexes for project_task_queue
    op.create_index(
        "idx_project_task_queue_project",
        "project_task_queue",
        ["project_id", "priority"],
    )
    op.create_index(
        "idx_project_task_queue_status",
        "project_task_queue",
        ["project_id", "status"],
    )
    op.create_index(
        "idx_project_task_queue_milestone",
        "project_task_queue",
        ["milestone_id"],
    )

    # Unique constraint for task_key within project
    if is_postgres:
        op.create_unique_constraint(
            "uq_project_task_key",
            "project_task_queue",
            ["project_id", "task_key"],
        )

    # =========================================================================
    # HUMAN CHECKPOINT GATES TABLE
    # =========================================================================

    op.create_table(
        "human_checkpoint_gates",
        sa.Column("id", uuid_type, primary_key=True, server_default=uuid_default),
        sa.Column(
            "project_id",
            uuid_type,
            sa.ForeignKey("enterprise_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Gate type and details
        sa.Column("gate_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Decision options
        sa.Column("options", json_type, server_default=json_empty_arr),
        # Context that triggered this gate
        sa.Column("trigger_context", json_type, server_default=json_empty_obj),
        # Associated task (if any)
        sa.Column(
            "task_id",
            uuid_type,
            sa.ForeignKey("project_task_queue.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Status and decision
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("chosen_option_id", sa.String(100), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.String(255), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        # Priority and blocking
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'normal'"),
        ),
        sa.Column("blocks_progress", sa.Boolean(), default=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=timestamp_default,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=timestamp_default,
            nullable=False,
        ),
    )

    # Create indexes for human_checkpoint_gates
    op.create_index(
        "idx_human_checkpoint_gates_project",
        "human_checkpoint_gates",
        ["project_id", "created_at"],
    )
    op.create_index(
        "idx_human_checkpoint_gates_status",
        "human_checkpoint_gates",
        ["status"],
    )
    op.create_index(
        "idx_human_checkpoint_gates_type",
        "human_checkpoint_gates",
        ["gate_type"],
    )


def downgrade():
    """Drop enterprise project tables"""
    conn = op.get_bind()
    is_postgres = conn.dialect.name == "postgresql"

    # Drop in reverse order due to foreign keys

    # Human Checkpoint Gates
    op.drop_index("idx_human_checkpoint_gates_type", "human_checkpoint_gates")
    op.drop_index("idx_human_checkpoint_gates_status", "human_checkpoint_gates")
    op.drop_index("idx_human_checkpoint_gates_project", "human_checkpoint_gates")
    op.drop_table("human_checkpoint_gates")

    # Project Task Queue
    if is_postgres:
        op.drop_constraint("uq_project_task_key", "project_task_queue", type_="unique")
    op.drop_index("idx_project_task_queue_milestone", "project_task_queue")
    op.drop_index("idx_project_task_queue_status", "project_task_queue")
    op.drop_index("idx_project_task_queue_project", "project_task_queue")
    op.drop_table("project_task_queue")

    # Enterprise Projects
    op.drop_index("idx_enterprise_projects_workspace", "enterprise_projects")
    op.drop_index("idx_enterprise_projects_status", "enterprise_projects")
    op.drop_index("idx_enterprise_projects_user", "enterprise_projects")
    op.drop_table("enterprise_projects")
