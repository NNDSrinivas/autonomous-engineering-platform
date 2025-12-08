#!/usr/bin/env python3
"""Quick script to populate test Jira data for testing gating behavior"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from backend.database.session import get_db
from sqlalchemy import text


def populate_test_jira_data():
    """Insert some test Jira issues into navi_memory for testing"""

    db = next(get_db())

    try:
        # Insert test Jira issues directly via SQL
        db.execute(
            text(
                """
            INSERT INTO navi_memory (user_id, category, scope, title, content, meta_json, importance, created_at, updated_at)
            VALUES 
                ('default_user', 'task', 'org_aep_platform_4538597546e6fec6', 
                 'AEP-001: Implement user authentication', 
                 'Task to implement OAuth authentication flow for the AEP platform. Priority: High, Status: In Progress',
                 '{"jira_key": "AEP-001", "status": "In Progress", "priority": "High", "assignee": "default_user"}',
                 5, NOW(), NOW()),
                ('default_user', 'task', 'org_aep_platform_4538597546e6fec6',
                 'AEP-002: Fix database migration',
                 'Fix the database migration issues in the backend. Priority: Medium, Status: To Do', 
                 '{"jira_key": "AEP-002", "status": "To Do", "priority": "Medium", "assignee": "default_user"}',
                 5, NOW(), NOW())
        """
            )
        )

        db.commit()
        print("✅ Successfully populated 2 test Jira issues")

        # Verify
        result = db.execute(
            text(
                """
            SELECT COUNT(*) FROM navi_memory 
            WHERE category = 'task' AND scope = 'org_aep_platform_4538597546e6fec6'
        """
            )
        )
        count = result.scalar()
        print(f"✅ Total Jira tasks in database: {count}")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    populate_test_jira_data()
