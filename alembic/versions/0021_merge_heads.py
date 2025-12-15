"""Merge heads 0020_chat_history and 4ebeed57d7a3"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0021_merge_heads"
down_revision = ("0020_chat_history", "4ebeed57d7a3")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
