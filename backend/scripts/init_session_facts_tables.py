#!/usr/bin/env python3
"""
Initialize Session Facts Tables

This script creates the new persistent session memory tables:
- navi_workspace_sessions: Links sessions to workspace paths
- navi_session_facts: Stores extracted facts that persist across restarts
- navi_error_resolutions: Tracks errors and their solutions
- navi_installed_dependencies: Records installed packages

Run this script once to create the tables:
    python -m backend.scripts.init_session_facts_tables
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text  # noqa: E402
from backend.core.db import get_engine  # noqa: E402

# Import models to register them with Base.metadata
from backend.database.models.session_facts import (  # noqa: E402
    WorkspaceSession,
    SessionFact,
    ErrorResolution,
    InstalledDependency,
)


def create_tables():
    """Create the session facts tables."""
    engine = get_engine()

    # Get list of tables to create
    tables_to_create = [
        WorkspaceSession.__table__,
        SessionFact.__table__,
        ErrorResolution.__table__,
        InstalledDependency.__table__,
    ]

    print("Creating session facts tables...")

    # Create tables
    for table in tables_to_create:
        try:
            table.create(engine, checkfirst=True)
            print(f"  ✓ Created table: {table.name}")
        except Exception as e:
            print(f"  ✗ Error creating {table.name}: {e}")

    print("\nDone! Session facts tables are ready.")

    # Print table info
    print("\nCreated tables:")
    print("  - navi_workspace_sessions: Links sessions to workspace paths")
    print("  - navi_session_facts: Stores extracted facts")
    print("  - navi_error_resolutions: Tracks errors and solutions")
    print("  - navi_installed_dependencies: Records installed packages")


def verify_tables():
    """Verify that tables were created."""
    engine = get_engine()

    print("\nVerifying tables...")

    with engine.connect() as conn:
        # Check each table
        tables = [
            "navi_workspace_sessions",
            "navi_session_facts",
            "navi_error_resolutions",
            "navi_installed_dependencies",
        ]

        for table_name in tables:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                count = result.scalar()
                print(f"  ✓ {table_name}: {count} rows")
            except Exception as e:
                print(f"  ✗ {table_name}: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("NAVI Persistent Session Memory - Table Initialization")
    print("=" * 60)
    print()

    create_tables()
    verify_tables()

    print()
    print("=" * 60)
    print("Setup complete! NAVI will now remember context across restarts.")
    print("=" * 60)
