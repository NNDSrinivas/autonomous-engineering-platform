#!/usr/bin/env python3
"""
Debug test to trace attachment handling through NAVI.
"""

import asyncio
import aiohttp
import json
import os

BASE_URL = os.getenv("NAVI_BASE_URL", "http://localhost:8000")
WORKSPACE_ROOT = "/Users/mounikakapa/dev/autonomous-engineering-platform"


async def test_with_detailed_logging():
    """Test with detailed response capture."""

    code_snippet = """
def process_request(data):
    result = data["items"][0]["value"]
    return result * 2
"""

    # Test 1: Regular agent mode with attachment
    payload = {
        "message": "This Python code has potential bugs. What are the issues with this code and how can I fix them?",
        "mode": "agent",
        "workspace_root": WORKSPACE_ROOT,
        "attachments": [
            {
                "kind": "code",
                "path": "example.py",
                "content": code_snippet,
                "language": "python",
            }
        ],
        "conversationHistory": [],
    }

    print("=" * 60)
    print("TEST: Code review with attachment")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{BASE_URL}/api/navi/chat/stream",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                print(f"Status: {response.status}")

                all_events = []
                full_content = ""
                actions = []
                activity_events = []
                thinking = []

                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        all_events.append(data)

                        if "content" in data:
                            full_content += data["content"]
                        if "actions" in data:
                            actions.extend(data["actions"])
                        if "activity" in data:
                            activity_events.append(data["activity"])
                        if "thinking" in data:
                            thinking.append(data["thinking"])
                        if "error" in data:
                            print(f"❌ Error: {data['error']}")
                            return False
                    except json.JSONDecodeError:
                        continue

                print("\n📊 Event Summary:")
                print(f"   Activity events: {len(activity_events)}")
                print(f"   Thinking chunks: {len(thinking)}")
                print(f"   Actions: {len(actions)}")
                print(f"   Content length: {len(full_content)} chars")

                if activity_events:
                    print("\n📋 Activity Events:")
                    for evt in activity_events[:10]:
                        print(
                            f"   - {evt.get('kind', '?')}: {evt.get('label', '?')} - {evt.get('detail', '')[:50]}"
                        )

                if thinking:
                    print("\n💭 Thinking (first 500 chars):")
                    all_thinking = "".join(thinking)
                    print(f"   {all_thinking[:500]}...")

                print("\n📝 Full Response:")
                print("-" * 40)
                print(full_content)
                print("-" * 40)

                # Analyze response quality
                response_lower = full_content.lower()
                quality_checks = [
                    (
                        "Mentions index/key access",
                        any(
                            k in response_lower
                            for k in ["index", "keyerror", "key error", "out of range"]
                        ),
                    ),
                    (
                        "Mentions empty/none check",
                        any(
                            k in response_lower
                            for k in ["empty", "none", "null", "undefined"]
                        ),
                    ),
                    (
                        "Mentions error handling",
                        any(
                            k in response_lower
                            for k in ["try", "except", "error", "exception", "catch"]
                        ),
                    ),
                    (
                        "Mentions the specific code",
                        "items" in response_lower
                        or "value" in response_lower
                        or "process_request" in response_lower,
                    ),
                    (
                        "Not just echoing code",
                        len(full_content) > len(code_snippet) * 2,
                    ),
                ]

                print("\n✅ Quality Checks:")
                all_passed = True
                for check_name, passed in quality_checks:
                    status = "✅" if passed else "❌"
                    print(f"   {status} {check_name}")
                    if not passed:
                        all_passed = False

                return all_passed

        except Exception as e:
            print(f"❌ Request failed: {e}")
            import traceback

            traceback.print_exc()
            return False


if __name__ == "__main__":
    result = asyncio.run(test_with_detailed_logging())
    print(f"\n{'='*60}")
    print(f"RESULT: {'✅ PASSED' if result else '❌ FAILED'}")
    print(f"{'='*60}")
    exit(0 if result else 1)
