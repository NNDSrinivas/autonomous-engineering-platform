"""Add chat sessions and link chat history to sessions"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0022_chat_sessions"
down_revision = "0021_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chat_session",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("org_id", sa.String(length=255), nullable=True, index=True),
        sa.Column("user_id", sa.String(length=255), nullable=False, index=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("(datetime('now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("(datetime('now'))"),
            nullable=False,
        ),
    )
    op.execute("DROP INDEX IF EXISTS ix_chat_session_org_id")
    op.execute("DROP INDEX IF EXISTS ix_chat_session_user_id")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chat_session_org_id ON chat_session (org_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chat_session_user_id ON chat_session (user_id)"
    )

    # Link chat_history to chat_session
    op.add_column(
        "chat_history", sa.Column("session_id", sa.BigInteger(), nullable=True)
    )
    op.execute("DROP INDEX IF EXISTS ix_chat_history_session_id")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chat_history_session_id ON chat_history (session_id)"
    )
    op.create_foreign_key(
        "fk_chat_history_session",
        source_table="chat_history",
        referent_table="chat_session",
        local_cols=["session_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chat_history_session", "chat_history", type_="foreignkey")
    op.drop_index("ix_chat_history_session_id", table_name="chat_history")
    op.drop_column("chat_history", "session_id")
    op.drop_index("ix_chat_session_user_id", table_name="chat_session")
    op.drop_index("ix_chat_session_org_id", table_name="chat_session")
    op.drop_table("chat_session")
