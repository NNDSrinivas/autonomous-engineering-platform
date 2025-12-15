"""Add change_set table"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0023_change_sets"
down_revision = "0022_chat_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clean up any prior partial deployments
    op.execute("DROP INDEX IF EXISTS ix_change_set_org_id")
    op.execute("DROP INDEX IF EXISTS ix_change_set_user_id")
    # Drop table if it exists (SQLite compatible)
    op.execute("DROP TABLE IF EXISTS change_set")

    op.create_table(
        "change_set",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.String(length=255), nullable=True),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("(datetime('now'))"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_change_set_org_id", "change_set", ["org_id"], if_not_exists=True
    )
    op.create_index(
        "ix_change_set_user_id", "change_set", ["user_id"], if_not_exists=True
    )


def downgrade() -> None:
    op.drop_index("ix_change_set_user_id", table_name="change_set")
    op.drop_index("ix_change_set_org_id", table_name="change_set")
    op.drop_table("change_set")
