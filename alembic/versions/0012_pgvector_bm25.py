"""pgvector + bm25/fts for memory

Revision ID: 0012_pgvector_bm25
Revises: 0011_context_pack_memory_notes
Create Date: 2025-10-24

Adds pgvector extension support for ANN (Approximate Nearest Neighbor) search
and full-text search capabilities for hybrid BM25 ranking (PR-16).

Changes:
- Enable pgvector extension (PostgreSQL only)
- Add embedding_vec column with vector(1536) type for ANN search
- Add text_tsv column for tsvector full-text search (PostgreSQL)
- Create GIN index on tsvector for efficient BM25 queries
- Maintain backwards compatibility with JSON embedding storage

"""

from alembic import op
import sqlalchemy as sa
import os

revision = "0012_pgvector_bm25"
down_revision = "0011_context_pack_memory_notes"
branch_labels = None
depends_on = None

# Get embedding dimension from environment or use default
EMBED_DIM = int(os.getenv("EMBED_DIM", "1536"))


def upgrade():
    # Enable pgvector extension (safe if not PostgreSQL or already exists)
    try:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    except Exception:
        # SQLite or other databases don't support pgvector
        pass

    # Add vector column for ANN search
    # Keep existing JSON embedding column for backwards compatibility
    try:
        # Try using SQLAlchemy UserDefinedType first
        op.add_column(
            "memory_chunk",
            sa.Column("embedding_vec", sa.types.UserDefinedType(), nullable=True),
        )
    except Exception:
        # Fallback to raw SQL for vector type
        # Use EMBED_DIM from configuration for consistency
        try:
            op.execute(
                f"ALTER TABLE memory_chunk ADD COLUMN IF NOT EXISTS embedding_vec vector({EMBED_DIM});"
            )
        except Exception:
            # SQLite fallback - no vector support
            pass

    # Add tsvector column and GIN index for BM25/FTS (PostgreSQL only)
    try:
        # Add text_tsv column for precomputed tsvector
        # Use tsvector type for proper FTS performance
        try:
            from sqlalchemy.dialects import postgresql

            op.add_column(
                "memory_chunk",
                sa.Column("text_tsv", postgresql.TSVECTOR(), nullable=True),
            )
        except ImportError:
            # Fallback to raw SQL if dialect not available
            op.execute(
                "ALTER TABLE memory_chunk ADD COLUMN IF NOT EXISTS text_tsv tsvector;"
            )

        # Populate existing rows with tsvector data
        # Note: For very large tables (millions of rows), consider running this update
        # in batches outside of the migration to avoid long lock times
        op.execute(
            "UPDATE memory_chunk SET text_tsv = to_tsvector('english', coalesce(text, ''));"
        )

        # Create GIN index on precomputed text_tsv column for efficient full-text search
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_chunk_tsv "
            "ON memory_chunk USING GIN (text_tsv);"
        )
    except Exception:
        # SQLite or databases without tsvector support
        pass


def downgrade():
    # Drop GIN index
    try:
        op.execute("DROP INDEX IF EXISTS idx_memory_chunk_tsv;")
    except Exception:
        pass

    # Drop text_tsv column
    try:
        op.execute("ALTER TABLE memory_chunk DROP COLUMN IF EXISTS text_tsv;")
    except Exception:
        pass

    # Drop embedding_vec column
    try:
        op.execute("ALTER TABLE memory_chunk DROP COLUMN IF EXISTS embedding_vec;")
    except Exception:
        pass

    # Note: We don't drop the pgvector extension as it might be used by other tables
    # and dropping it would cascade to all vector columns
