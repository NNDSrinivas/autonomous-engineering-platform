"""Add conversation message/reply tables for Slack/Teams"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0019_conversation_tables"
down_revision = "0018_navi_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_message",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("channel", sa.String(length=255), nullable=True),
        sa.Column("thread_ts", sa.String(length=255), nullable=True),
        sa.Column("message_ts", sa.String(length=255), nullable=True),
        sa.Column("user", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "meta_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_message_org_id", "conversation_message", ["org_id"]
    )
    op.create_index(
        "ix_conversation_message_message_ts", "conversation_message", ["message_ts"]
    )

    op.create_table(
        "conversation_reply",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(length=255), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=False),
        sa.Column("message_ts", sa.String(length=255), nullable=True),
        sa.Column("user", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "meta_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["conversation_message.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversation_reply_org_id", "conversation_reply", ["org_id"])
    op.create_index(
        "ix_conversation_reply_message_ts", "conversation_reply", ["message_ts"]
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_reply_message_ts", table_name="conversation_reply")
    op.drop_index("ix_conversation_reply_org_id", table_name="conversation_reply")
    op.drop_table("conversation_reply")

    op.drop_index(
        "ix_conversation_message_message_ts", table_name="conversation_message"
    )
    op.drop_index("ix_conversation_message_org_id", table_name="conversation_message")
    op.drop_table("conversation_message")
