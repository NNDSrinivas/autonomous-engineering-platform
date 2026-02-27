#!/usr/bin/env python3
"""
Backfill pgvector embeddings from JSON column

Migrates existing embeddings stored as JSON LOBs in the `embedding` column
to the new `embedding_vec` vector column for ANN search.

Usage:
    python scripts/backfill_pgvector.py

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (default: postgresql://mentor:mentor@localhost:5432/mentor)
    EMBED_DIM: Embedding dimension (default: 1536)
    BATCH_SIZE: Number of rows to process per commit (default: 500)
"""

import json
import os
import sys

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 not installed. Install with: pip install psycopg2-binary")
    sys.exit(1)

# Configuration
EMBED_DIM = int(os.getenv("EMBED_DIM", "1536"))
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://mentor:mentor@localhost:5432/mentor"
)
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "500"))


def backfill_vectors():
    """Backfill vector embeddings from JSON to pgvector format"""
    print("Connecting to database...")
    print(f"Embedding dimension: {EMBED_DIM}")
    print(f"Batch size: {BATCH_SIZE}")

    conn = None  # Initialize to avoid NameError in exception handlers
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Check if embedding_vec column exists
        cur.execute(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='memory_chunk' AND column_name='embedding_vec'
        """
        )
        if not cur.fetchone():
            print("Error: embedding_vec column does not exist. Run migration first.")
            sys.exit(1)

        # Count total rows to backfill
        cur.execute(
            "SELECT COUNT(*) FROM memory_chunk WHERE embedding_vec IS NULL AND embedding IS NOT NULL"
        )
        total = cur.fetchone()[0]
        print(f"\nFound {total} rows to backfill")

        if total == 0:
            print("No rows to backfill. Exiting.")
            return

        # Process in batches
        processed = 0
        errors = 0

        while processed < total:
            # Fetch batch
            cur.execute(
                """
                SELECT id, embedding 
                FROM memory_chunk 
                WHERE embedding_vec IS NULL AND embedding IS NOT NULL
                LIMIT %s
            """,
                (BATCH_SIZE,),
            )
            rows = cur.fetchall()

            if not rows:
                break

            for chunk_id, embedding_blob in rows:
                try:
                    # Handle different data types from psycopg2
                    if isinstance(embedding_blob, str):
                        embedding_str = embedding_blob
                    elif isinstance(embedding_blob, bytes):
                        try:
                            embedding_str = embedding_blob.decode("utf-8")
                        except UnicodeDecodeError as ude:
                            print(
                                f"Error decoding bytes as UTF-8 for row {chunk_id}: {ude}"
                            )
                            errors += 1
                            continue
                    elif isinstance(embedding_blob, memoryview):
                        try:
                            embedding_str = embedding_blob.tobytes().decode("utf-8")
                        except UnicodeDecodeError as ude:
                            print(
                                f"Error decoding memoryview as UTF-8 for row {chunk_id}: {ude}"
                            )
                            errors += 1
                            continue
                    else:
                        raise TypeError(
                            f"Unsupported embedding_blob type: {type(embedding_blob)}"
                        )

                    # Parse JSON embedding
                    vec = json.loads(embedding_str)

                    # Validate and pad/truncate to expected dimension
                    if len(vec) != EMBED_DIM:
                        if len(vec) > EMBED_DIM:
                            action = "Truncating to EMBED_DIM"
                        else:
                            action = "Padding with zeros"
                        print(
                            f"Warning: Row {chunk_id} has dimension {len(vec)}, expected {EMBED_DIM}. {action}."
                        )
                        # Truncate to EMBED_DIM and pad with zeros if needed
                        vec = vec[:EMBED_DIM] + [0.0] * max(0, EMBED_DIM - len(vec))

                    # Format as JSON array for pgvector parameter binding
                    vec_str = json.dumps(vec)

                    # Update row
                    cur.execute(
                        "UPDATE memory_chunk SET embedding_vec = %s WHERE id = %s",
                        (vec_str, chunk_id),
                    )

                except Exception as e:
                    print(f"Error processing row {chunk_id}: {e}")
                    errors += 1
                    continue

            # Commit batch
            conn.commit()
            processed += len(rows)
            print(
                f"Progress: {processed}/{total} rows ({100.0 * processed / total:.1f}%)"
            )

        print("\n✅ Backfill complete!")
        print(f"   Processed: {processed} rows")
        print(f"   Errors: {errors} rows")

        cur.close()
        conn.close()

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)


if __name__ == "__main__":
    backfill_vectors()
