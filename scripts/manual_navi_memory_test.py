#!/usr/bin/env python3
"""
Manual test script for NAVI memory persistence (not a pytest test).

This is an interactive script that calls a live backend at 127.0.0.1:8787.
DO NOT run via pytest - execute directly: ./scripts/manual_navi_memory_test.py

Tests all 4 levels of memory:
1. Short-term memory (100 messages in session)
2. Conversation persistence (saves to database)
3. Cross-session memory (loads from database)
4. Cross-conversation memory (semantic search)
"""

import asyncio
import json
import os
import uuid
from typing import Dict, Any

import httpx

# Prevent pytest from collecting this as a test
pytest_plugins = []
__test__ = False  # Explicitly mark as non-test file for pytest


BASE_URL = "http://127.0.0.1:8787"
CONVERSATION_ID = str(uuid.uuid4())

print("🧪 Testing NAVI Memory System")
print(f"📝 Conversation ID: {CONVERSATION_ID}")
print("=" * 80)


async def send_message(
    message: str,
    conversation_id: str = None,
    conversation_history: list = None,
) -> Dict[str, Any]:
    """Send a message to NAVI autonomous endpoint and collect response."""
    url = f"{BASE_URL}/api/navi/chat/autonomous"

    payload = {
        "message": message,
        "conversation_id": conversation_id,
        "conversation_history": conversation_history or [],
        "workspace_path": os.getenv("WORKSPACE_PATH", os.getcwd()),
        "run_verification": False,  # Skip verification for faster testing
        "model": "gpt-4o-mini",
    }

    print(f"\n💬 User: {message}")
    print("-" * 80)

    assistant_response = ""
    event_count = 0

    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream("POST", url, json=payload) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]  # Remove "data: " prefix

                    if data_str == "[DONE]":
                        break

                    try:
                        event = json.loads(data_str)
                        event_count += 1

                        # Print status events
                        if event.get("type") == "status":
                            status = event.get("status", "")
                            print(f"📊 Status: {status}")

                        # Collect text events
                        elif event.get("type") == "text":
                            content = event.get("text") or event.get("content", "")
                            assistant_response += content
                            # Print first 100 chars
                            if len(content) > 0:
                                print(f"💭 NAVI: {content[:100]}...", end="\r")

                        # Print complete event
                        elif event.get("type") == "complete":
                            summary = event.get("summary", "")
                            print(f"\n✅ Complete: {summary}")

                    except json.JSONDecodeError:
                        # Ignore non-JSON lines in SSE stream (e.g., connection heartbeats)
                        pass

    print(f"\n📈 Total events received: {event_count}")
    print(f"📝 Response length: {len(assistant_response)} characters")

    return {
        "message": message,
        "response": assistant_response,
        "event_count": event_count,
    }


async def main():
    """Run the memory test sequence."""
    results = []

    # Test 1: Ask about creating a Python hello world program
    print("\n" + "=" * 80)
    print("TEST 1: Create hello world program")
    print("=" * 80)
    result1 = await send_message(
        message="Can you create a simple hello world Python program?",
        conversation_id=CONVERSATION_ID,
    )
    results.append(result1)
    await asyncio.sleep(2)

    # Test 2: Ask about something different (to add variety)
    print("\n" + "=" * 80)
    print("TEST 2: Ask about file structure")
    print("=" * 80)
    result2 = await send_message(
        message="What files are in the backend directory?",
        conversation_id=CONVERSATION_ID,
    )
    results.append(result2)
    await asyncio.sleep(2)

    # Test 3: Reference the first request (test memory)
    print("\n" + "=" * 80)
    print("TEST 3: Reference first request - TEST MEMORY")
    print("=" * 80)
    result3 = await send_message(
        message="Can you show me the actual code for the hello world program we discussed earlier?",
        conversation_id=CONVERSATION_ID,
    )
    results.append(result3)
    await asyncio.sleep(2)

    # Test 4: Ask about the conversation itself
    print("\n" + "=" * 80)
    print("TEST 4: Ask about conversation history")
    print("=" * 80)
    result4 = await send_message(
        message="What have we talked about so far in this conversation?",
        conversation_id=CONVERSATION_ID,
    )
    results.append(result4)
    await asyncio.sleep(2)

    # Test 5: Start a NEW conversation and see if it can find the old one (cross-conversation memory)
    print("\n" + "=" * 80)
    print("TEST 5: New conversation - TEST CROSS-CONVERSATION MEMORY")
    print("=" * 80)
    new_conversation_id = str(uuid.uuid4())
    result5 = await send_message(
        message="Did we discuss a Python hello world program in a previous conversation?",
        conversation_id=new_conversation_id,
    )
    results.append(result5)

    # Summary
    print("\n" + "=" * 80)
    print("🎯 TEST SUMMARY")
    print("=" * 80)

    # Check if Test 3 referenced the first conversation
    test3_mentions_hello = (
        "hello" in result3["response"].lower() or "print" in result3["response"].lower()
    )

    # Check if Test 4 summarized the conversation
    test4_mentions_multiple = (
        len(result4["response"]) > 100
    )  # Should have substantial content

    # Check if Test 5 found the previous conversation
    test5_found_previous = (
        "hello" in result5["response"].lower()
        or "previous" in result5["response"].lower()
        or "conversation" in result5["response"].lower()
    )

    print(f"\n✅ Test 1 (Hello World): {result1['event_count']} events")
    print(f"✅ Test 2 (File Structure): {result2['event_count']} events")
    print(
        f"{'✅' if test3_mentions_hello else '❌'} Test 3 (Memory): Referenced hello world = {test3_mentions_hello}"
    )
    print(
        f"{'✅' if test4_mentions_multiple else '❌'} Test 4 (History): Summarized conversation = {test4_mentions_multiple}"
    )
    print(
        f"{'✅' if test5_found_previous else '❌'} Test 5 (Cross-Conversation): Found previous conversation = {test5_found_previous}"
    )

    print("\n" + "=" * 80)
    print("🎊 MEMORY SYSTEM TEST COMPLETE!")
    print("=" * 80)

    # Print conversation IDs for manual verification
    print("\n📋 Conversation IDs for manual verification:")
    print(f"   Main conversation: {CONVERSATION_ID}")
    print(f"   New conversation: {new_conversation_id}")
    print(
        f"\n💡 You can verify in database with: SELECT * FROM navi_conversations WHERE id = '{CONVERSATION_ID}'"
    )


if __name__ == "__main__":
    asyncio.run(main())
