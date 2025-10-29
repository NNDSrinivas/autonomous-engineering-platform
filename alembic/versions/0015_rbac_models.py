"""RBAC models for organizations, users, and roles.

Revision ID: 0015_rbac_models
Revises: ba72f0e6da5f
Create Date: 2025-10-29

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0015_rbac_models"
down_revision = "0014_live_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create RBAC tables: organizations, roles, users, user_roles."""
    
    # Organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("org_key", sa.String(length=64), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
    )
    op.create_index("ix_organizations_org_key", "organizations", ["org_key"])

    # Roles table (with seed data)
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=32), nullable=False, unique=True),
    )
    # Seed standard roles
    op.execute("INSERT INTO roles(name) VALUES ('viewer'), ('planner'), ('admin')")

    # Users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("sub", sa.String(length=128), nullable=False, unique=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False),
    )
    op.create_index("ix_users_sub", "users", ["sub"])
    op.create_index("ix_users_email", "users", ["email"])

    # UserRoles table (many-to-many with optional project scoping)
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("project_key", sa.String(length=128), nullable=True),
        sa.UniqueConstraint("user_id", "role_id", "project_key", name="uq_user_role_scope"),
    )


def downgrade() -> None:
    """Drop RBAC tables in reverse order."""
    op.drop_table("user_roles")
    
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_sub", table_name="users")
    op.drop_table("users")
    
    op.drop_table("roles")
    
    op.drop_index("ix_organizations_org_key", table_name="organizations")
    op.drop_table("organizations")
