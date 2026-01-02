"""Add chat sessions and link chat history to sessions"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0022_chat_sessions"
down_revision = "0020_chat_history"
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
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
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
    # Skip foreign key constraint for SQLite compatibility
    # SQLite doesn't support adding foreign key constraints after table creation
    # The relationship will be maintained at the application level


def downgrade() -> None:
    # Skip foreign key constraint drop for SQLite compatibility
    op.drop_index("ix_chat_history_session_id", table_name="chat_history")
    op.drop_column("chat_history", "session_id")
    op.drop_index("ix_chat_session_user_id", table_name="chat_session")
    op.drop_index("ix_chat_session_org_id", table_name="chat_session")
    op.drop_table("chat_session")
