"""Add live_plan table for real-time collaboration

Revision ID: 0014_live_plan
Revises: 0013_memory_graph
Create Date: 2025-10-27

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0014_live_plan"
down_revision = "0013_memory_graph"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "live_plan",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("steps", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "participants", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("archived", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_live_plan_org_id", "live_plan", ["org_id"], unique=False)
    op.create_index("ix_live_plan_archived", "live_plan", ["archived"], unique=False)
    op.create_index(
        "ix_live_plan_org_archived", "live_plan", ["org_id", "archived"], unique=False
    )


def downgrade():
    op.drop_index("ix_live_plan_org_archived", table_name="live_plan")
    op.drop_index("ix_live_plan_archived", table_name="live_plan")
    op.drop_index("ix_live_plan_org_id", table_name="live_plan")
    op.drop_table("live_plan")
