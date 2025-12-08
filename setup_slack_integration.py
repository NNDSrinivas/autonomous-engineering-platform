#!/usr/bin/env python3
"""
Slack Bot Token Setup Helper

This script helps you:
1. Get your Slack bot token
2. Test the Slack API connection
3. Verify NAVI can access your Slack workspace

App Details:
- App ID: A09TM9MG95J
- Client ID: 9932030018053.9939327553188
- Created: November 17, 2025

Steps to get your bot token:
1. Go to https://api.slack.com/apps/A09TM9MG95J/oauth
2. Click "Install to Workspace" or "Reinstall App"
3. Authorize the app in your workspace
4. Copy the "Bot User OAuth Token" (starts with xoxb-)
5. Set it as AEP_SLACK_BOT_TOKEN environment variable
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_bot_token():
    """Check if bot token is configured."""
    token = os.getenv("AEP_SLACK_BOT_TOKEN", "")

    if not token:
        print("❌ AEP_SLACK_BOT_TOKEN not set")
        print("\n📋 To get your bot token:")
        print("1. Visit: https://api.slack.com/apps/A09TM9MG95J/oauth")
        print("2. Click 'Install to Workspace' or 'Reinstall App'")
        print("3. Authorize the app in your Slack workspace")
        print("4. Copy the 'Bot User OAuth Token' (starts with xoxb-)")
        print("5. Set it: export AEP_SLACK_BOT_TOKEN=xoxb-your-token-here")
        print("6. Run this script again to test the connection")
        return False

    if not token.startswith("xoxb-"):
        print(f"⚠️ Bot token doesn't look right: {token[:20]}...")
        print("Bot tokens should start with 'xoxb-'")
        return False

    print(f"✅ Bot token configured: {token[:20]}...")
    return True


def test_slack_client():
    """Test SlackClient initialization and basic API calls."""
    print("\n=== Testing SlackClient ===")

    try:
        from backend.integrations.slack_client import SlackClient

        print("✅ SlackClient imported successfully")

        # Test client creation
        client = SlackClient()
        print("✅ SlackClient initialized with bot token")

        # Test API call - list channels
        channels = client.list_channels()
        print(f"✅ Connected to Slack! Found {len(channels)} channels")

        # Show sample channels
        if channels:
            print("📋 Sample channels:")
            for ch in channels[:3]:  # Show first 3 channels
                ch_name = ch.get("name", "unknown")
                ch_id = ch.get("id", "unknown")
                print(f"   - #{ch_name} ({ch_id})")

        return True, channels

    except Exception as e:
        print(f"❌ SlackClient test failed: {e}")
        return False, []


async def test_slack_service():
    """Test the slack_service integration."""
    print("\n=== Testing Slack Service Integration ===")

    try:
        from backend.services.slack_service import search_messages_for_user, _get_client

        print("✅ Slack service imported successfully")

        # Test client creation through service
        client = _get_client()
        if client is None:
            print("❌ Slack service could not create client")
            return False

        print("✅ Slack service can create SlackClient")

        # Test message search (with mock DB)
        messages = search_messages_for_user(
            db=None, user_id="test_user", limit=5  # No DB for testing
        )

        print(f"✅ Message search works: {len(messages)} messages retrieved")
        return True

    except Exception as e:
        print(f"❌ Slack service test failed: {e}")
        return False


async def test_unified_memory_with_slack():
    """Test that unified memory includes real Slack data."""
    print("\n=== Testing Unified Memory with Slack ===")

    try:
        from backend.agent.unified_memory_retriever import retrieve_unified_memories

        print("✅ Unified memory retriever imported")

        # Test unified memory retrieval
        memories = await retrieve_unified_memories(
            user_id="test_user", query="recent messages", db=None
        )

        slack_memories = memories.get("slack_memories", [])
        print("✅ Unified memory retrieval completed")
        print(f"   - Total sources: {len(memories)} ")
        print(f"   - Slack messages: {len(slack_memories)}")

        if slack_memories:
            print("📋 Sample Slack messages in memory:")
            for msg in slack_memories[:2]:  # Show first 2 messages
                channel = msg.get("channel_name", msg.get("channel", "unknown"))
                text = (
                    msg.get("text", "")[:100] + "..."
                    if len(msg.get("text", "")) > 100
                    else msg.get("text", "")
                )
                print(f"   - #{channel}: {text}")

        return len(slack_memories) > 0

    except Exception as e:
        print(f"❌ Unified memory test failed: {e}")
        return False


async def main():
    """Run all Slack integration tests."""
    print("🔗 Slack Integration Setup & Test")
    print("=" * 50)

    # Step 1: Check token configuration
    if not check_bot_token():
        return False

    # Step 2: Test SlackClient
    client_works, channels = test_slack_client()
    if not client_works:
        return False

    # Step 3: Test slack service
    service_works = await test_slack_service()
    if not service_works:
        return False

    # Step 4: Test unified memory integration
    memory_works = await test_unified_memory_with_slack()

    print("\n" + "=" * 50)
    print("📊 Integration Test Results:")
    print("  ✅ Bot Token: Configured")
    print(f"  ✅ SlackClient: Connected ({len(channels)} channels)")
    print("  ✅ Slack Service: Working")
    print(
        f"  {'✅' if memory_works else '⚠️'} Unified Memory: {'Working' if memory_works else 'No messages yet'}"
    )

    if memory_works:
        print("\n🎉 SUCCESS! Slack is fully integrated with NAVI!")
        print("NAVI can now access your Slack messages as organizational memory.")
    else:
        print("\n✅ Integration is working, but no messages retrieved yet.")
        print("This is normal for new setups. Try sending some messages in Slack.")

    return True


if __name__ == "__main__":
    asyncio.run(main())
