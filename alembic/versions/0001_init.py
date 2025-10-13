"""initial baseline

Revision ID: 0001_init
Revises:
Create Date: 2025-10-13
"""

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Baseline only; feature tables land in later revisions.
    pass


def downgrade() -> None:
    pass
