#!/usr/bin/env python3
# ruff: noqa: E402
"""
Comprehensive database initialization script for NAVI.

Creates ALL database tables defined in the codebase:
- Core tables (projects, team_members, etc.)
- Memory system tables (navi_conversations, user_preferences, etc.)
- Audit tables (audit_log_enhanced, plan_events)
- Analytics tables (llm_metrics, rag_metrics, task_metrics)
- RBAC tables (users, organizations, roles, permissions)

Usage:
    python backend/scripts/init_database.py
"""

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from backend.core.db import Base
from backend.core.settings import settings

# Import all model modules to register them with Base.metadata
# This is CRITICAL - if a model isn't imported, its table won't be created
print("📦 Importing model modules...")

# Core models
try:
    import backend.models  # noqa: F401

    print("   ✓ backend.models")
except Exception as e:
    print(f"   ⚠️  backend.models: {e}")

# Database models (memory system)
try:
    import backend.database.models.memory  # noqa: F401

    print("   ✓ backend.database.models.memory")
except Exception as e:
    print(f"   ⚠️  backend.database.models.memory: {e}")

try:
    import backend.database.models.rbac  # noqa: F401

    print("   ✓ backend.database.models.rbac")
except Exception as e:
    print(f"   ⚠️  backend.database.models.rbac: {e}")

try:
    import backend.database.models.enterprise_project  # noqa: F401

    print("   ✓ backend.database.models.enterprise_project")
except Exception as e:
    print(f"   ⚠️  backend.database.models.enterprise_project: {e}")

try:
    import backend.database.models.memory_graph  # noqa: F401

    print("   ✓ backend.database.models.memory_graph")
except Exception as e:
    print(f"   ⚠️  backend.database.models.memory_graph: {e}")

# Event store models (audit)
try:
    import backend.core.eventstore.models

    print(f"   ✓ {backend.core.eventstore.models.__name__}")
except Exception as e:
    print(f"   ⚠️  backend.core.eventstore.models: {e}")

print()


def main():
    """Run the database initialization."""
    print("=" * 70)
    print("NAVI Database Initialization")
    print("=" * 70)
    print()

    # Safety warning for production environments
    print("⚠️  WARNING: This script will create database tables.")
    print("⚠️  IMPORTANT: Always backup your database before running this script!")
    print("⚠️  CAUTION: Do not run this on production without proper authorization.")
    print()

    # Check if running in production-like environment
    # Require explicit environment variable to proceed in production
    if settings.is_production_like():
        print("🚨 PRODUCTION ENVIRONMENT DETECTED!")
        print("🚨 Running this script in production requires explicit confirmation.")

        # Check for explicit environment variable
        if os.environ.get("ALLOW_DB_INIT") != "1":
            print("❌ ALLOW_DB_INIT=1 environment variable required for production.")
            print("❌ Example: ALLOW_DB_INIT=1 python scripts/init_database.py")
            print("❌ Aborted for safety. No changes made.")
            sys.exit(1)

        # Double confirmation via interactive prompt
        print("⚠️  ALLOW_DB_INIT is set. Requesting final confirmation...")
        response = input(
            "Type 'CREATE TABLES' (all caps) to proceed, or anything else to abort: "
        )
        if response != "CREATE TABLES":
            print("❌ Aborted by user. No changes made.")
            sys.exit(0)
        print("✅ Production confirmation received. Proceeding...")
    print()

    # Get database URL and convert async URL to sync if needed
    raw_url = settings.sqlalchemy_url
    url_obj = make_url(raw_url)

    # Convert async drivers to sync equivalents
    driver_mapping = {
        "postgresql+asyncpg": "postgresql+psycopg",  # Use psycopg3, not legacy psycopg2
        "sqlite+aiosqlite": "sqlite",
        "mysql+aiomysql": "mysql+pymysql",
    }

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

    # Mask password in URL for logging
    safe_url = str(
        effective_url_obj.set(password="****" if effective_url_obj.password else None)
    )
    print(f"Database URL: {safe_url}")
    print()

    # Create engine with sync URL
    engine = create_engine(database_url)
    inspector = inspect(engine)

    # Get all tables currently in database
    existing_tables = set(inspector.get_table_names())
    print(f"📊 Existing tables in database: {len(existing_tables)}")
    if existing_tables:
        for table in sorted(existing_tables):
            print(f"   - {table}")
        print()

    # Get all tables defined in metadata
    metadata_tables = set(Base.metadata.tables.keys())
    print(f"📋 Tables defined in code: {len(metadata_tables)}")
    if metadata_tables:
        for table in sorted(metadata_tables):
            print(f"   - {table}")
        print()

    # Calculate what needs to be created
    tables_to_create = metadata_tables - existing_tables
    tables_up_to_date = metadata_tables & existing_tables

    if tables_up_to_date:
        print(f"✅ {len(tables_up_to_date)} tables already exist (no action needed)")
        print()

    if not tables_to_create:
        print("✅ All tables already exist. Database is up to date!")
        return

    print(f"🔧 Need to create {len(tables_to_create)} tables:")
    for table in sorted(tables_to_create):
        print(f"   - {table}")
    print()

    # Create tables
    try:
        print("🔨 Creating tables...")
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("✅ Table creation completed!")
        print()

        # Verify tables were created
        inspector = inspect(engine)
        created_tables = set(inspector.get_table_names())

        success_count = 0
        failed_count = 0

        print("📊 Verification:")
        for table in sorted(tables_to_create):
            if table in created_tables:
                # Get column info
                columns = inspector.get_columns(table)
                indexes = inspector.get_indexes(table)
                print(f"   ✓ {table} ({len(columns)} columns, {len(indexes)} indexes)")
                success_count += 1
            else:
                print(f"   ✗ {table} - FAILED TO CREATE")
                failed_count += 1

        print()
        print("=" * 70)
        print("Database Initialization Complete!")
        print(f"✅ Created: {success_count} tables")
        if failed_count > 0:
            print(f"❌ Failed: {failed_count} tables")
        print("=" * 70)

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
