"""Session Facts Tables for Persistent Memory

Creates tables for NAVI's persistent session memory:
- navi_workspace_sessions: Links sessions to workspace paths
- navi_session_facts: Stores extracted facts that persist across restarts
- navi_error_resolutions: Tracks errors and their solutions
- navi_installed_dependencies: Records installed packages

Revision ID: 0028b_session_facts
Revises: 0028_connector_unified_schema
Create Date: 2026-01-26

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = "0028b_session_facts"
down_revision = "0028_connector_unified_schema"
branch_labels = None
depends_on = None


def upgrade():
    # Create navi_workspace_sessions table
    op.create_table(
        "navi_workspace_sessions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_path",
            sa.Text(),
            nullable=False,
            comment="Absolute path to the workspace/project",
        ),
        sa.Column(
            "workspace_name",
            sa.String(255),
            nullable=True,
            comment="Project name (from package.json, etc.)",
        ),
        sa.Column(
            "current_session_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="Active conversation session ID",
        ),
        sa.Column(
            "last_known_state",
            JSONB,
            nullable=True,
            server_default="{}",
            comment="Last known project state (servers, ports, etc.)",
        ),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_active",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "workspace_path", name="uq_user_workspace"),
    )
    op.create_index(
        "idx_workspace_session_user",
        "navi_workspace_sessions",
        ["user_id"],
    )
    op.create_index(
        "idx_workspace_session_path",
        "navi_workspace_sessions",
        ["workspace_path"],
    )

    # Create navi_session_facts table
    op.create_table(
        "navi_session_facts",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "workspace_session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("navi_workspace_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.String(50),
            nullable=False,
            comment="Category: server, file, decision, error, task, discovery, dependency",
        ),
        sa.Column(
            "fact_key",
            sa.String(255),
            nullable=False,
            comment="Unique key within category",
        ),
        sa.Column(
            "fact_value",
            sa.Text(),
            nullable=False,
            comment="The fact value",
        ),
        sa.Column(
            "source_message_id",
            UUID(as_uuid=True),
            nullable=True,
            comment="Message ID where fact was extracted",
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default="1.0",
            comment="Confidence score [0.0, 1.0]",
        ),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Whether this fact is still valid/current",
        ),
        sa.Column(
            "superseded_by_id",
            UUID(as_uuid=True),
            sa.ForeignKey("navi_session_facts.id", ondelete="SET NULL"),
            nullable=True,
            comment="Newer fact that supersedes this one",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_verified",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="When this fact was last confirmed true",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_session_fact_category",
        "navi_session_facts",
        ["category"],
    )
    op.create_index(
        "idx_session_fact_current",
        "navi_session_facts",
        ["is_current"],
    )

    # Create navi_error_resolutions table
    op.create_table(
        "navi_error_resolutions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "workspace_session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("navi_workspace_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "error_type",
            sa.String(100),
            nullable=False,
            comment="Error type: build_error, runtime_error, command_failed, dependency_error",
        ),
        sa.Column(
            "error_signature",
            sa.Text(),
            nullable=False,
            comment="Normalized error signature for matching",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=False,
            comment="Original error message",
        ),
        sa.Column(
            "resolution_steps",
            JSONB,
            nullable=False,
            comment="Steps taken to resolve the error",
        ),
        sa.Column(
            "resolution_summary",
            sa.Text(),
            nullable=False,
            comment="Human-readable summary of the fix",
        ),
        sa.Column(
            "times_applied",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="Number of times this resolution was applied",
        ),
        sa.Column(
            "times_successful",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="Number of times it successfully resolved the error",
        ),
        sa.Column(
            "context_data",
            JSONB,
            nullable=True,
            server_default="{}",
            comment="Additional context (file paths, versions, etc.)",
        ),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_applied",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_error_resolution_type",
        "navi_error_resolutions",
        ["error_type"],
    )
    op.create_index(
        "idx_error_resolution_workspace",
        "navi_error_resolutions",
        ["workspace_session_id"],
    )

    # Create navi_installed_dependencies table
    op.create_table(
        "navi_installed_dependencies",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "workspace_session_id",
            UUID(as_uuid=True),
            sa.ForeignKey("navi_workspace_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "package_manager",
            sa.String(50),
            nullable=False,
            comment="Package manager: npm, pip, cargo, etc.",
        ),
        sa.Column(
            "package_name",
            sa.String(255),
            nullable=False,
        ),
        sa.Column(
            "package_version",
            sa.String(100),
            nullable=True,
            comment="Installed version",
        ),
        sa.Column(
            "is_dev_dependency",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "install_command",
            sa.Text(),
            nullable=True,
            comment="Command used to install",
        ),
        sa.Column(
            "installed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_verified",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_session_id",
            "package_manager",
            "package_name",
            name="uq_workspace_package",
        ),
    )
    op.create_index(
        "idx_installed_dep_workspace",
        "navi_installed_dependencies",
        ["workspace_session_id"],
    )


def downgrade():
    # Drop tables in reverse order
    op.drop_index("idx_installed_dep_workspace", table_name="navi_installed_dependencies")
    op.drop_table("navi_installed_dependencies")

    op.drop_index("idx_error_resolution_workspace", table_name="navi_error_resolutions")
    op.drop_index("idx_error_resolution_type", table_name="navi_error_resolutions")
    op.drop_table("navi_error_resolutions")

    op.drop_index("idx_session_fact_current", table_name="navi_session_facts")
    op.drop_index("idx_session_fact_category", table_name="navi_session_facts")
    op.drop_table("navi_session_facts")

    op.drop_index("idx_workspace_session_path", table_name="navi_workspace_sessions")
    op.drop_index("idx_workspace_session_user", table_name="navi_workspace_sessions")
    op.drop_table("navi_workspace_sessions")
