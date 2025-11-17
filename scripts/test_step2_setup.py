#!/usr/bin/env python3
"""
Test script for Step 2: Org Integrations

This script verifies the basic setup without requiring actual Jira/Confluence credentials.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")

    try:
        from backend.integrations.jira_client import JiraClient

        print("✓ JiraClient imported")
    except Exception as e:
        print(f"✗ JiraClient import failed: {e}")
        return False

    try:
        from backend.integrations.confluence_client import ConfluenceClient

        print("✓ ConfluenceClient imported")
    except Exception as e:
        print(f"✗ ConfluenceClient import failed: {e}")
        return False

    try:
        from backend.services.navi_memory_service import (
            store_memory,
            search_memory,
            generate_embedding,
        )

        print("✓ navi_memory_service imported")
    except Exception as e:
        print(f"✗ navi_memory_service import failed: {e}")
        return False

    try:
        from backend.services.org_ingestor import (
            ingest_jira_for_user,
            ingest_confluence_space,
        )

        print("✓ org_ingestor imported")
    except Exception as e:
        print(f"✗ org_ingestor import failed: {e}")
        return False

    try:
        from backend.api.org_sync import router

        print("✓ org_sync router imported")
    except Exception as e:
        print(f"✗ org_sync router import failed: {e}")
        return False

    return True


def test_migration_file():
    """Check migration file exists and has correct revision"""
    print("\nTesting migration...")

    migration_path = "alembic/versions/0018_navi_memory.py"

    if not os.path.exists(migration_path):
        print(f"✗ Migration file not found: {migration_path}")
        return False

    with open(migration_path, "r") as f:
        content = f.read()

        # Use regex for flexible whitespace matching
        import re

        if not re.search(r"revision\s*=\s*['\"]0018_navi_memory['\"]", content):
            print("✗ Migration revision ID incorrect")
            return False

        if not re.search(r"down_revision\s*=\s*['\"]0017_ai_feedback['\"]", content):
            print("✗ Migration down_revision incorrect")
            return False

        if "CREATE TABLE navi_memory" not in content and "create_table(" not in content:
            print("✗ Migration doesn't create navi_memory table")
            return False

    print("✓ Migration file is valid")
    return True


def test_env_example():
    """Check .env.example has required variables"""
    print("\nTesting .env.example...")

    if not os.path.exists(".env.example"):
        print("✗ .env.example not found")
        return False

    with open(".env.example", "r") as f:
        content = f.read()

        required_vars = [
            "AEP_JIRA_BASE_URL",
            "AEP_JIRA_EMAIL",
            "AEP_JIRA_API_TOKEN",
            "AEP_CONFLUENCE_BASE_URL",
            "AEP_CONFLUENCE_EMAIL",
            "AEP_CONFLUENCE_API_TOKEN",
        ]

        for var in required_vars:
            if var not in content:
                print(f"✗ Missing env var: {var}")
                return False

    print("✓ .env.example has all required variables")
    return True


def test_main_router_registration():
    """Check that org_sync router is registered in main.py"""
    print("\nTesting main.py router registration...")

    main_path = "backend/api/main.py"

    if not os.path.exists(main_path):
        print(f"✗ main.py not found: {main_path}")
        return False

    with open(main_path, "r") as f:
        content = f.read()

        if "from .org_sync import router as org_sync_router" not in content:
            print("✗ org_sync router not imported in main.py")
            return False

        if "app.include_router(org_sync_router)" not in content:
            print("✗ org_sync router not registered in main.py")
            return False

    print("✓ org_sync router is registered in main.py")
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("Step 2: Org Integrations - Setup Verification")
    print("=" * 60)
    print()

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Migration", test_migration_file()))
    results.append((".env.example", test_env_example()))
    results.append(("Router Registration", test_main_router_registration()))

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")

    all_passed = all(result[1] for result in results)

    print()
    if all_passed:
        print("🎉 All tests passed! Step 2 setup is complete.")
        print()
        print("Next steps:")
        print("1. Run migration: alembic upgrade head")
        print("2. Configure .env with Jira/Confluence credentials")
        print("3. Start backend: uvicorn backend.api.main:app --reload --port 8787")
        print("4. Test sync: curl -X POST http://localhost:8787/api/org/sync/jira \\")
        print('             -H "Content-Type: application/json" \\')
        print(
            '             -d \'{"user_id": "your-email@example.com", "max_issues": 5}\''
        )
        return 0
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
