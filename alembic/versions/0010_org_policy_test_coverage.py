"""org policy test coverage threshold

Revision ID: 0010_org_policy_test_coverage
Revises: 0009_memory_search
Create Date: 2025-11-06

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0010_org_policy_test_coverage"
down_revision = "0009_memory_search"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "org_policy",
        sa.Column("test_coverage_min", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("org_policy", "test_coverage_min")
