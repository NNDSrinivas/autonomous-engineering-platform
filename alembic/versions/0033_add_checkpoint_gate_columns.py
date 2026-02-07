"""Placeholder for missing checkpoint gate migration.

Revision ID: 0033_add_checkpoint_gate_columns
Revises: 0021_extension_security, 0020_extension_platform, 0030_enterprise_checkpoints,
4bb1ad0958e2, 0010_org_policy_test_coverage
Create Date: 2026-02-06

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0033_add_checkpoint_gate_columns"
down_revision = (
    "0021_extension_security",
    "0020_extension_platform",
    "0030_enterprise_checkpoints",
    "4bb1ad0958e2",
    "0010_org_policy_test_coverage",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Placeholder migration.

    This revision was missing from the repository but exists in the DB.
    Keep it as a no-op to align Alembic history.
    """
    pass


def downgrade() -> None:
    """Downgrade placeholder."""
    pass
