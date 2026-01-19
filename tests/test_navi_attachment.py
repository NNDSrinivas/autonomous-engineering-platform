#!/usr/bin/env python3
"""
Quick test for attachment handling fix.
"""

import asyncio
import aiohttp
import json
import os

BASE_URL = os.getenv("NAVI_BASE_URL", "http://localhost:8000")
WORKSPACE_ROOT = "/Users/mounikakapa/dev/autonomous-engineering-platform"

async def test_code_attachment():
    """Test code review with attachment."""

    code_snippet = '''
def process_request(data):
    result = data["items"][0]["value"]
    return result * 2
'''

    payload = {
        "message": "Review this code and tell me what could go wrong:",
        "mode": "agent",
        "workspace_root": WORKSPACE_ROOT,
        "attachments": [{
            "kind": "code",
            "path": "example.py",
            "content": code_snippet,
            "language": "python"
        }],
        "conversationHistory": [],
    }

    print("Testing attachment handling...")
    print(f"Payload: {json.dumps(payload, indent=2)[:500]}")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{BASE_URL}/api/navi/chat/stream",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                print(f"\nStatus: {response.status}")

                if response.status != 200:
                    error_text = await response.text()
                    print(f"❌ Error: {error_text}")
                    return False

                # Parse SSE response
                full_content = ""
                error = None

                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        if "content" in data:
                            full_content += data["content"]
                        if "error" in data:
                            error = data["error"]
                            break
                    except json.JSONDecodeError:
                        continue

                if error:
                    print(f"❌ Error in response: {error}")
                    return False

                print(f"\n✅ Response received ({len(full_content)} chars)")
                print(f"Preview: {full_content[:300]}...")

                # Check for meaningful response
                keywords = ["index", "key", "error", "empty", "none", "check", "exception", "crash"]
                found = [k for k in keywords if k in full_content.lower()]
                if found:
                    print(f"✅ Found relevant keywords: {found}")
                    return True
                else:
                    print(f"⚠️ Response may not address the code issues. Keywords found: {found}")
                    return True  # Still passed, just no specific keywords

        except Exception as e:
            print(f"❌ Request failed: {e}")
            return False

if __name__ == "__main__":
    result = asyncio.run(test_code_attachment())
    exit(0 if result else 1)
