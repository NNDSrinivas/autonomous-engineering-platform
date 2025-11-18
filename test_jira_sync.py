"""Quick test script for Jira sync"""
import asyncio
import sys
sys.path.insert(0, "/Users/mounikakapa/Desktop/Personal Projects/autonomous-engineering-platform")

from backend.database.session import db_session
from backend.services.org_ingestor import ingest_jira_for_user

async def test_sync():
    print("🔄 Starting Jira sync test...")
    with db_session() as db:
        try:
            keys = await ingest_jira_for_user(
                db=db,
                user_id="srinivasn7779@gmail.com",
                max_issues=2,
                custom_jql=None,
            )
            print(f"✅ Success! Synced issues: {keys}")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_sync())
