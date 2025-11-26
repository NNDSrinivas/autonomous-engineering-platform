#!/usr/bin/env python3
"""
Slack Channel Manager

This utility helps you:
1. See which channels your bot can access
2. Join public channels automatically  
3. Get instructions for private channel invites
4. Test message fetching after joining

Usage:
    python manage_slack_channels.py
"""

import os
import sys
import asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def manage_channels():
    """Interactive channel management."""
    print("🔗 Slack Channel Manager")
    print("=" * 40)
    
    # Check if bot token is configured
    token = os.getenv("AEP_SLACK_BOT_TOKEN", "")
    if not token:
        print("❌ AEP_SLACK_BOT_TOKEN not set")
        print("Set it first: export AEP_SLACK_BOT_TOKEN=xoxb-your-token")
        return
    
    try:
        from backend.integrations.slack_client import SlackClient
        client = SlackClient()
        print(f"✅ Connected to Slack")
        
        # List all channels
        channels = client.list_channels()
        print(f"\n📋 Found {len(channels)} channels:")
        
        accessible_count = 0
        
        for i, ch in enumerate(channels, 1):
            ch_id = ch.get("id")
            ch_name = ch.get("name", "unknown")
            ch_type = "🔒 Private" if ch.get("is_private") else "🌐 Public"
            member_count = ch.get("num_members", 0)
            
            print(f"\n{i}. #{ch_name} ({ch_id})")
            print(f"   Type: {ch_type} | Members: {member_count}")
            
            # Try to fetch a few messages to see if bot has access
            try:
                messages = client.fetch_channel_messages(ch_id, limit=2)
                accessible_count += 1
                print(f"   ✅ Bot has access ({len(messages)} recent messages)")
                
                if messages:
                    latest = messages[0]
                    msg_text = latest.get("text", "")[:60]
                    if len(msg_text) > 60:
                        msg_text += "..."
                    user = latest.get("user", "unknown")
                    print(f"   💬 Latest: @{user}: {msg_text}")
                
            except Exception as e:
                if "not_in_channel" in str(e):
                    print(f"   ❌ Bot not in channel")
                    
                    if not ch.get("is_private"):
                        print(f"   🔧 Attempting to join...")
                        if client.join_channel(ch_id):
                            try:
                                messages = client.fetch_channel_messages(ch_id, limit=2)
                                accessible_count += 1
                                print(f"   ✅ Joined successfully! ({len(messages)} recent messages)")
                            except:
                                print(f"   ⚠️ Joined but still cannot read messages")
                        else:
                            print(f"   ❌ Failed to join")
                    else:
                        print(f"   ℹ️ Private channel - manual invite required")
                        print(f"   💡 Invite @your-bot-name to #{ch_name} in Slack")
                else:
                    print(f"   ❌ Error: {e}")
        
        print(f"\n📊 Summary:")
        print(f"  Total channels: {len(channels)}")
        print(f"  Bot has access: {accessible_count}")
        print(f"  Need invites: {len(channels) - accessible_count}")
        
        # Test unified memory
        print(f"\n🧠 Testing Unified Memory Integration...")
        from backend.services.slack_service import search_messages_for_user
        
        messages = search_messages_for_user(
            db=None,
            user_id="test_user", 
            limit=10
        )
        
        print(f"✅ Unified memory can fetch {len(messages)} messages total")
        
        if messages:
            print(f"\n💬 Sample messages from unified memory:")
            for msg in messages[:3]:
                channel = msg.get("channel_name", msg.get("channel", "unknown"))
                text = msg.get("text", "")[:80]
                if len(text) > 80:
                    text += "..."
                user = msg.get("user", "unknown")
                print(f"   #{channel} - @{user}: {text}")
        
        if accessible_count > 0:
            print(f"\n🎉 SUCCESS! Bot can access Slack messages!")
            print(f"NAVI will now include these messages in organizational memory.")
        else:
            print(f"\n⚠️ Bot needs channel access to fetch messages.")
            print(f"Invite the bot to channels or join public ones.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(manage_channels())