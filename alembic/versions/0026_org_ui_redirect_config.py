"""Add org UI redirect settings

Revision ID: 0026_org_ui_redirect_config
Revises: 0025_governance_phase51
Create Date: 2025-02-14

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0026_org_ui_redirect_config"
down_revision = "0025_governance_phase51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("ui_base_url", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("ui_allowed_domains", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column("ui_redirect_path", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("organizations", "ui_redirect_path")
    op.drop_column("organizations", "ui_allowed_domains")
    op.drop_column("organizations", "ui_base_url")
