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

# Embedding dimension validation constants
MIN_EMBED_DIM = 128  # Common minimum for semantic models (MiniLM, small BERT)
MAX_EMBED_DIM = 4096  # Prevents excessive memory usage and index bloat

# Get embedding dimension from environment or use default
EMBED_DIM = int(os.getenv("EMBED_DIM", "1536"))


def upgrade():
    # Validate EMBED_DIM is within reasonable bounds to prevent SQL issues
    # Fail fast before attempting any DDL operations
    # Lower bound (128): Common minimum for semantic models (e.g., MiniLM, small BERT)
    # Upper bound (4096): Prevents excessive memory usage and index bloat
    #   - HNSW index memory: ~500-1000 bytes per vector + dimension * 4 bytes
    #   - 4096-dim vectors: ~16KB per vector in index structures
    #   - Most modern embeddings (OpenAI, Cohere, etc.) are ≤ 3072 dimensions
    if not (MIN_EMBED_DIM <= EMBED_DIM <= MAX_EMBED_DIM):
        raise ValueError(
            f"EMBED_DIM must be between {MIN_EMBED_DIM} and {MAX_EMBED_DIM}, got {EMBED_DIM}. "
            "This ensures compatibility with common embedding models and prevents excessive memory usage. "
            "Check your EMBED_DIM environment variable and ensure it matches your embedding model's dimensions."
        )

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
        # Note: For very large tables (millions of rows), this single UPDATE statement
        # may cause extended lock times during migration. Consider alternatives:
        #   1. Run migration during maintenance window with acceptable downtime
        #   2. Use scripts/backfill_pgvector.py for batched, resumable processing
        #   3. Implement batched UPDATE in separate script with row limit checkpoints
        # Current implementation prioritizes migration simplicity for typical datasets
        # (< 1M rows, ~10-30 seconds lock time on modern hardware)
        #
        # Design decision: We provide SKIP_TSVECTOR_UPDATE flag rather than implementing
        # batched updates directly in the migration because:
        # - Alembic migrations should be simple and atomic (all-or-nothing)
        # - Batched updates require complex state tracking and error recovery
        # - Production deployments can plan maintenance windows or skip this step
        # - Post-migration batched backfill provides better observability and control
        #
        # For large tables (>1M rows), we strongly recommend:
        # 1. Set SKIP_TSVECTOR_UPDATE=1 to skip this step entirely
        # 2. Run batched UPDATE post-migration using a script with separate transactions:
        #    #!/bin/bash
        #    # Batched tsvector update script (run outside migration)
        #    while true; do
        #      psql $DATABASE_URL -c "
        #        UPDATE memory_chunk
        #        SET text_tsv = to_tsvector('english', coalesce(text, ''))
        #        WHERE id IN (
        #          SELECT id FROM memory_chunk
        #          WHERE text_tsv IS NULL
        #          LIMIT 1000
        #        );"
        #      updated=\$?
        #      [ \$updated -eq 0 ] && [ \$(psql $DATABASE_URL -t -c "SELECT COUNT(*) FROM memory_chunk WHERE text_tsv IS NULL") -eq 0 ] && break
        #      sleep 0.1  # Brief pause between batches
        #    done
        if os.getenv("SKIP_TSVECTOR_UPDATE", "0") == "1":
            print(
                "[alembic/0012_pgvector_bm25] Skipping tsvector UPDATE due to SKIP_TSVECTOR_UPDATE=1. "
                "You must populate text_tsv for existing rows after migration (e.g., via batched UPDATE)."
            )
        else:
            print(
                "[alembic/0012_pgvector_bm25] WARNING: Running single UPDATE to populate text_tsv. "
                "This may lock memory_chunk table on large datasets. "
                "For >1M rows, consider setting SKIP_TSVECTOR_UPDATE=1 and running batched updates."
            )
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
