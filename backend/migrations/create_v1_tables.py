#!/usr/bin/env python3
"""
Database migration script for NAVI v1 analytics tables.

Creates the following tables:
- llm_metrics: LLM call metrics (tokens, cost, latency)
- rag_metrics: RAG retrieval metrics
- task_metrics: Task execution metrics

Usage:
    python backend/migrations/create_v1_tables.py
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, inspect  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
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

    # Get database URL and convert async URL to sync if needed
    raw_url = settings.sqlalchemy_url
    url_obj = make_url(raw_url)

    # Convert async drivers to sync equivalents
    driver_mapping = {
        "postgresql+asyncpg": "postgresql+psycopg2",
        "sqlite+aiosqlite": "sqlite",
        "mysql+aiomysql": "mysql+pymysql",
    }

    # Track the effective URL object used to build the engine
    effective_url_obj = url_obj

    # Check if URL uses an async driver
    original_drivername = url_obj.drivername
    if original_drivername in driver_mapping:
        sync_driver = driver_mapping[original_drivername]
        effective_url_obj = url_obj.set(drivername=sync_driver)
        database_url = str(effective_url_obj)
        print(
            f"⚠️  Converted async driver '{original_drivername}' to sync driver '{sync_driver}'"
        )
    else:
        database_url = raw_url

    # Mask password in URL for logging, using the effective URL (with any driver swap)
    safe_url = str(
        effective_url_obj.set(password="****" if effective_url_obj.password else None)
    )
    print(f"Database URL: {safe_url}")
    print()

    # Create engine with sync URL
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
