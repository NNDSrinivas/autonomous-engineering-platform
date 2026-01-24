#!/usr/bin/env python3
"""
NAVI Final Comprehensive Test - Focus on core capabilities
"""

import asyncio
import aiohttp
import json
import os
import sys

BASE_URL = os.getenv("NAVI_BASE_URL", "http://localhost:8000")
WORKSPACE_ROOT = "/Users/mounikakapa/dev/autonomous-engineering-platform"


async def send_request(session, message, attachments=None, mode="agent"):
    """Send request and return full response data."""
    payload = {
        "message": message,
        "mode": mode,
        "workspace_root": WORKSPACE_ROOT,
        "attachments": attachments or [],
        "conversationHistory": [],
    }

    try:
        async with session.post(
            f"{BASE_URL}/api/navi/chat/stream",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=120),
        ) as response:
            result = {
                "status": response.status,
                "content": "",
                "thinking": "",
                "actions": [],
                "activities": [],
                "error": None,
            }

            if response.status != 200:
                result["error"] = await response.text()
                return result

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
                        result["content"] += data["content"]
                    if "thinking" in data:
                        result["thinking"] += data["thinking"]
                    if "actions" in data:
                        result["actions"].extend(data["actions"])
                    if "activity" in data:
                        result["activities"].append(data["activity"])
                    if "error" in data:
                        result["error"] = data["error"]
                except json.JSONDecodeError:
                    continue

            return result
    except Exception as e:
        return {
            "error": str(e),
            "status": 0,
            "content": "",
            "thinking": "",
            "actions": [],
            "activities": [],
        }


def is_meaningful_response(result, min_content=50, check_not_error=True):
    """Check if response is meaningful and not a hardcoded fallback."""
    if result.get("error"):
        return False, f"Error: {result['error']}"

    content = result.get("content", "")
    thinking = result.get("thinking", "")
    combined = content + thinking

    if len(combined) < min_content:
        return False, f"Response too short: {len(combined)} chars"

    # Check for hardcoded error messages
    error_patterns = [
        "i couldn't generate",
        "i encountered an error",
        "please try again",
        "i don't understand",
        "could you rephrase",
    ]

    for pattern in error_patterns:
        if pattern in combined.lower():
            return False, f"Found error pattern: '{pattern}'"

    return True, f"Response length: {len(content)} content + {len(thinking)} thinking"


async def run_tests():
    """Run comprehensive tests."""

    tests = []

    async with aiohttp.ClientSession() as session:
        # TEST 1: Project Understanding
        print("\n" + "=" * 60)
        print("TEST 1: Project Understanding")
        print("=" * 60)
        result = await send_request(
            session, "What kind of project is this? What technologies does it use?"
        )
        meaningful, reason = is_meaningful_response(result)
        tests.append(("Project Understanding", meaningful, reason, result))
        print(f"{'✅' if meaningful else '❌'} {reason}")
        if result["content"]:
            print(f"   Preview: {result['content'][:150]}...")

        # TEST 2: Code Analysis with Attachment
        print("\n" + "=" * 60)
        print("TEST 2: Code Analysis with Attachment")
        print("=" * 60)
        result = await send_request(
            session,
            "What potential issues do you see in this code?",
            attachments=[
                {
                    "kind": "code",
                    "path": "test.py",
                    "content": """
def get_user(user_id):
    users = load_users()
    return users[user_id]
""",
                    "language": "python",
                }
            ],
        )
        meaningful, reason = is_meaningful_response(result, min_content=30)
        # Also check if it actually analyzed the code
        combined = (result["content"] + result["thinking"]).lower()
        code_analyzed = any(
            k in combined
            for k in ["keyerror", "index", "exist", "none", "missing", "valid", "check"]
        )
        if meaningful and not code_analyzed:
            meaningful = False
            reason = "Response doesn't analyze code issues"
        tests.append(("Code Analysis", meaningful, reason, result))
        print(f"{'✅' if meaningful else '❌'} {reason}")
        if result["thinking"]:
            print(f"   Thinking: {result['thinking'][:150]}...")
        if result["content"]:
            print(f"   Content: {result['content'][:150]}...")

        # TEST 3: Error Stack Trace Analysis
        print("\n" + "=" * 60)
        print("TEST 3: Error Stack Trace Analysis")
        print("=" * 60)
        result = await send_request(
            session,
            """I'm getting this error:
TypeError: 'NoneType' object is not subscriptable
  File "api.py", line 42, in handler
    return data["result"]["value"]
What's wrong and how do I fix it?""",
        )
        meaningful, reason = is_meaningful_response(result)
        combined = (result["content"] + result["thinking"]).lower()
        error_understood = any(
            k in combined for k in ["none", "null", "subscript", "check", "if ", "get("]
        )
        if meaningful and not error_understood:
            meaningful = False
            reason = "Response doesn't address the error"
        tests.append(("Error Analysis", meaningful, reason, result))
        print(f"{'✅' if meaningful else '❌'} {reason}")
        if result["content"]:
            print(f"   Preview: {result['content'][:200]}...")

        # TEST 4: Implementation Request
        print("\n" + "=" * 60)
        print("TEST 4: Implementation Request")
        print("=" * 60)
        result = await send_request(
            session,
            "Add a simple rate limiter to the API that limits each IP to 100 requests per minute.",
        )
        meaningful, reason = is_meaningful_response(result, min_content=100)
        # Check if it proposes implementation
        has_impl = (
            len(result["actions"]) > 0
            or "def " in result["content"]
            or "class " in result["content"]
            or "```" in result["content"]
        )
        if meaningful and not has_impl:
            # Also check thinking for implementation details
            has_impl = (
                "def " in result["thinking"]
                or "class " in result["thinking"]
                or "```" in result["thinking"]
            )
        tests.append(("Implementation", meaningful, reason, result))
        print(f"{'✅' if meaningful else '❌'} {reason}")
        if result["actions"]:
            print(f"   Actions: {len(result['actions'])} proposed")
        if result["content"]:
            print(f"   Preview: {result['content'][:200]}...")

        # TEST 5: Run Project Request
        print("\n" + "=" * 60)
        print("TEST 5: Run Project Request")
        print("=" * 60)
        result = await send_request(session, "How do I run this project locally?")
        meaningful, reason = is_meaningful_response(result)
        combined = (result["content"] + result["thinking"]).lower()
        has_commands = any(
            k in combined
            for k in [
                "npm",
                "pip",
                "python",
                "node",
                "install",
                "run",
                "start",
                "uvicorn",
            ]
        )
        if meaningful and not has_commands:
            meaningful = False
            reason = "Response doesn't include run commands"
        tests.append(("Run Instructions", meaningful, reason, result))
        print(f"{'✅' if meaningful else '❌'} {reason}")
        if result["content"]:
            print(f"   Preview: {result['content'][:200]}...")

        # TEST 6: Debugging Strategy
        print("\n" + "=" * 60)
        print("TEST 6: Debugging Strategy")
        print("=" * 60)
        result = await send_request(
            session,
            "The LLM responses are very slow, taking 15+ seconds. How can I optimize this?",
        )
        meaningful, reason = is_meaningful_response(result)
        combined = (result["content"] + result["thinking"]).lower()
        has_suggestions = any(
            k in combined
            for k in [
                "cache",
                "stream",
                "async",
                "timeout",
                "parallel",
                "batch",
                "model",
            ]
        )
        if meaningful and not has_suggestions:
            meaningful = False
            reason = "Response doesn't suggest optimizations"
        tests.append(("Performance Debug", meaningful, reason, result))
        print(f"{'✅' if meaningful else '❌'} {reason}")
        if result["content"]:
            print(f"   Preview: {result['content'][:200]}...")

        # TEST 7: Security Review
        print("\n" + "=" * 60)
        print("TEST 7: Security Review")
        print("=" * 60)
        result = await send_request(
            session,
            "Review this for security issues",
            attachments=[
                {
                    "kind": "code",
                    "path": "auth.py",
                    "content": """
import os
API_KEY = "sk-abc123secret"

def authenticate(request):
    key = request.headers.get("X-API-Key")
    return key == API_KEY
""",
                    "language": "python",
                }
            ],
        )
        meaningful, reason = is_meaningful_response(result, min_content=30)
        combined = (result["content"] + result["thinking"]).lower()
        found_issue = any(
            k in combined
            for k in [
                "hardcoded",
                "secret",
                "environment",
                "env",
                "expose",
                "leak",
                "commit",
            ]
        )
        if meaningful and not found_issue:
            meaningful = False
            reason = "Didn't identify hardcoded secret"
        tests.append(("Security Review", meaningful, reason, result))
        print(f"{'✅' if meaningful else '❌'} {reason}")
        if result["thinking"]:
            print(f"   Thinking: {result['thinking'][:150]}...")
        if result["content"]:
            print(f"   Content: {result['content'][:150]}...")

        # TEST 8: Clarification Needed
        print("\n" + "=" * 60)
        print("TEST 8: Handling Ambiguous Request")
        print("=" * 60)
        result = await send_request(session, "Make it better")
        # For ambiguous requests, NAVI should either ask for clarification or try to help
        meaningful, reason = is_meaningful_response(result, min_content=30)
        combined = (result["content"] + result["thinking"]).lower()
        # Either asks for clarification or tries to help with something
        handled = any(
            k in combined
            for k in [
                "what",
                "which",
                "specify",
                "clarify",
                "help",
                "improve",
                "better",
            ]
        )
        if meaningful and not handled:
            meaningful = False
            reason = "Didn't handle ambiguous request appropriately"
        tests.append(("Ambiguous Handling", meaningful, reason, result))
        print(f"{'✅' if meaningful else '❌'} {reason}")
        if result["content"]:
            print(f"   Preview: {result['content'][:200]}...")

    # SUMMARY
    print("\n" + "=" * 60)
    print("FINAL TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for t in tests if t[1])
    failed = len(tests) - passed

    for name, success, reason, _ in tests:
        print(f"{'✅' if success else '❌'} {name}: {reason}")

    print(f"\nTotal: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {passed/len(tests)*100:.1f}%")

    # Detailed failure analysis
    if failed > 0:
        print("\n--- Failed Test Details ---")
        for name, success, reason, result in tests:
            if not success:
                print(f"\n{name}:")
                print(f"  Reason: {reason}")
                if result.get("error"):
                    print(f"  Error: {result['error'][:200]}")
                if result.get("content"):
                    print(f"  Content: {result['content'][:300]}")
                if result.get("thinking"):
                    print(f"  Thinking: {result['thinking'][:300]}")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
