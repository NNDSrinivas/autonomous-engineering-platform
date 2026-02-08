#!/usr/bin/env python3
"""
Database migration script for NAVI v1 tables.

Creates the following tables:
- llm_metrics: LLM call metrics (tokens, cost, latency)
- rag_metrics: RAG retrieval metrics
- task_metrics: Task execution metrics
- learning_suggestions: AI suggestions tracked for learning
- learning_feedback: User feedback on suggestions
- learning_insights: Generated insights from feedback analysis
- telemetry_events: Frontend and backend telemetry events

Usage:
    python backend/migrations/create_v1_tables.py
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, inspect  # noqa: E402
from backend.core.db import Base  # noqa: E402
from backend.core.config import settings  # noqa: E402

# Import all models to register them with Base.metadata
import backend.models  # noqa: E402, F401


def main():
    """Run the migration."""
    print("=" * 60)
    print("NAVI v1 Database Migration")
    print("=" * 60)
    print()

    # Get database URL (redact credentials for security)
    database_url = settings.sqlalchemy_url
    # Mask password in URL for logging
    safe_url = database_url
    if "://" in database_url and "@" in database_url:
        # Extract scheme and rest
        scheme, rest = database_url.split("://", 1)
        # If auth is present, mask it
        if "@" in rest:
            auth_and_rest = rest.split("@", 1)
            # Keep only the username, mask password
            if ":" in auth_and_rest[0]:
                user = auth_and_rest[0].split(":")[0]
                safe_url = f"{scheme}://{user}:****@{auth_and_rest[1]}"
            else:
                safe_url = f"{scheme}://****@{auth_and_rest[1]}"
    print(f"Database URL: {safe_url}")
    print()

    # Create engine
    engine = create_engine(database_url)
    inspector = inspect(engine)

    # Explicitly whitelist v1 analytics tables to create
    # This ensures we only create the intended tables, not all registered models
    v1_tables = [
        "llm_metrics",
        "rag_metrics",
        "task_metrics",
    ]

    # Check which tables already exist
    existing_tables = inspector.get_table_names()
    tables_to_create = [t for t in v1_tables if t not in existing_tables]
    tables_already_exist = [t for t in v1_tables if t in existing_tables]

    if tables_already_exist:
        print("⚠️  Tables already exist:")
        for table in tables_already_exist:
            print(f"   - {table}")
        print()

    if not tables_to_create:
        print("✅ All v1 tables already exist. Nothing to do.")
        return

    print("📋 Tables to create:")
    for table in tables_to_create:
        print(f"   - {table}")
    print()

    # Create tables
    try:
        print("🔧 Creating tables...")
        # Only create the explicitly whitelisted v1 tables
        metadata_tables_to_create = [
            Base.metadata.tables[name]
            for name in tables_to_create
            if name in Base.metadata.tables
        ]
        if not metadata_tables_to_create:
            print(
                "⚠️  No matching table definitions found in metadata for requested tables."
            )
            return
        Base.metadata.create_all(
            bind=engine,
            tables=metadata_tables_to_create,
            checkfirst=True,
        )
        print("✅ Tables created successfully!")
        print()

        # Verify tables were created
        inspector = inspect(engine)
        created_tables = inspector.get_table_names()

        for table in tables_to_create:
            if table in created_tables:
                # Get column info
                columns = inspector.get_columns(table)
                print(f"✓ {table} ({len(columns)} columns)")
            else:
                print(f"✗ {table} - FAILED TO CREATE")

        print()
        print("=" * 60)
        print("Migration complete!")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
