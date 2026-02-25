#!/usr/bin/env python3
"""
NAVI Complex End-to-End Tests

Tests NAVI's ability to:
1. Develop a complex feature end-to-end
2. Debug and resolve complex bugs
3. Build a complete mini-project
4. Handle multi-step workflows

These tests validate that NAVI can handle real-world engineering tasks.
"""

import asyncio
import aiohttp
import json
import os
import sys
from typing import Dict, Any, List, Tuple
from datetime import datetime

BASE_URL = os.getenv("NAVI_BASE_URL", "http://localhost:8000")
WORKSPACE_ROOT = "/Users/mounikakapa/dev/autonomous-engineering-platform"


async def send_navi_request(
    session: aiohttp.ClientSession,
    message: str,
    attachments: List[Dict] = None,
    mode: str = "agent",
    conversation_history: List[Dict] = None,
) -> Dict[str, Any]:
    """Send request and return full response."""
    payload = {
        "message": message,
        "mode": mode,
        "workspace_root": WORKSPACE_ROOT,
        "attachments": attachments or [],
        "conversationHistory": conversation_history or [],
    }

    start = datetime.now()

    try:
        async with session.post(
            f"{BASE_URL}/api/navi/chat/stream",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=180),  # 3 min for complex tasks
        ) as response:
            result = {
                "status": response.status,
                "content": "",
                "thinking": "",
                "actions": [],
                "activities": [],
                "error": None,
                "duration_ms": 0,
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

            result["duration_ms"] = (datetime.now() - start).total_seconds() * 1000
            return result

    except Exception as e:
        return {
            "status": 0,
            "content": "",
            "thinking": "",
            "actions": [],
            "activities": [],
            "error": str(e),
            "duration_ms": 0,
        }


def analyze_response(result: Dict, requirements: Dict) -> Tuple[bool, List[str]]:
    """
    Analyze response against requirements.

    Requirements dict can contain:
    - min_content_length: minimum content length
    - required_keywords: keywords that must appear
    - required_any_keywords: at least one of these must appear
    - has_actions: whether actions should be proposed
    - has_code: whether code should be generated
    - no_error_patterns: patterns that should NOT appear
    """
    issues = []
    combined = (result.get("content", "") + result.get("thinking", "")).lower()

    if result.get("error"):
        issues.append(f"Error: {result['error'][:100]}")
        return False, issues

    # Check minimum content
    min_len = requirements.get("min_content_length", 50)
    actual_len = len(result.get("content", "")) + len(result.get("thinking", ""))
    if actual_len < min_len:
        issues.append(f"Response too short: {actual_len} chars (min: {min_len})")

    # Check required keywords
    for keyword in requirements.get("required_keywords", []):
        if keyword.lower() not in combined:
            issues.append(f"Missing required keyword: '{keyword}'")

    # Check required_any keywords
    any_keywords = requirements.get("required_any_keywords", [])
    if any_keywords:
        found = [k for k in any_keywords if k.lower() in combined]
        if not found:
            issues.append(f"Missing any of: {any_keywords}")

    # Check for actions
    if requirements.get("has_actions"):
        if not result.get("actions"):
            # Also check if code is in the content
            if "```" not in result.get("content", "") and "def " not in combined:
                issues.append("Expected actions or code generation")

    # Check for code
    if requirements.get("has_code"):
        content = result.get("content", "") + result.get("thinking", "")
        if "```" not in content and "def " not in content and "class " not in content:
            issues.append("Expected code in response")

    # Check for error patterns
    for pattern in requirements.get("no_error_patterns", []):
        if pattern.lower() in combined:
            issues.append(f"Found error pattern: '{pattern}'")

    return len(issues) == 0, issues


async def run_complex_tests():
    """Run complex end-to-end tests."""

    print("=" * 70)
    print("NAVI COMPLEX END-TO-END TESTS")
    print("=" * 70)
    print(f"Testing against: {BASE_URL}")
    print(f"Workspace: {WORKSPACE_ROOT}")
    print()

    results = []

    async with aiohttp.ClientSession() as session:
        # ================================================================
        # TEST 1: COMPLEX FEATURE - Build a complete caching system
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST 1: COMPLEX FEATURE DEVELOPMENT")
        print("Build a complete Redis caching layer for LLM responses")
        print("=" * 70)

        result = await send_navi_request(
            session,
            """Build a complete caching system for LLM responses with these requirements:
            1. Use Redis for distributed caching
            2. Implement cache key generation based on prompt + model
            3. Support TTL (time-to-live) for cache entries
            4. Add cache hit/miss metrics
            5. Handle cache failures gracefully (fallback to LLM)
            6. Support cache invalidation

            Generate the complete implementation with all necessary files.""",
        )

        passed, issues = analyze_response(
            result,
            {
                "min_content_length": 200,
                "required_any_keywords": ["redis", "cache", "ttl", "key"],
                "has_code": True,
                "no_error_patterns": ["i don't understand", "please try again"],
            },
        )

        print(
            f"\n{'✅ PASSED' if passed else '❌ FAILED'} ({result['duration_ms']:.0f}ms)"
        )
        if issues:
            for issue in issues:
                print(f"   ⚠️ {issue}")
        print(f"\nActivities: {len(result['activities'])}")
        print(f"Actions proposed: {len(result['actions'])}")
        if result["actions"]:
            for a in result["actions"][:5]:
                print(
                    f"   - {a.get('type')}: {str(a.get('filePath', a.get('command', '')))[:60]}"
                )
        print(f"\nResponse preview: {result['content'][:300]}...")
        if result["thinking"]:
            print(f"Thinking preview: {result['thinking'][:300]}...")

        results.append(
            ("Complex Feature: Caching System", passed, result["duration_ms"])
        )

        # ================================================================
        # TEST 2: COMPLEX BUG - Debug race condition
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST 2: COMPLEX BUG DEBUGGING")
        print("Debug a race condition in async code")
        print("=" * 70)

        buggy_code = """
import asyncio
from typing import Dict

class UserSessionManager:
    def __init__(self):
        self.sessions: Dict[str, dict] = {}
        self.active_count = 0

    async def create_session(self, user_id: str) -> dict:
        # Check if session exists
        if user_id in self.sessions:
            return self.sessions[user_id]

        # Simulate async operation (e.g., DB lookup)
        await asyncio.sleep(0.1)

        # Create new session
        session = {"user_id": user_id, "created": True}
        self.sessions[user_id] = session
        self.active_count += 1

        return session

    async def delete_session(self, user_id: str):
        if user_id in self.sessions:
            del self.sessions[user_id]
            self.active_count -= 1

# Bug report: When multiple requests come in simultaneously for the same user,
# we sometimes get duplicate sessions or incorrect active_count.
# Example: 10 concurrent requests for user "alice" might create 10 sessions
# instead of 1, and active_count ends up wrong.
"""

        result = await send_navi_request(
            session,
            "Debug this race condition. Users report that concurrent requests cause duplicate sessions and incorrect counts. Find the bug and fix it.",
            attachments=[
                {
                    "kind": "code",
                    "path": "session_manager.py",
                    "content": buggy_code,
                    "language": "python",
                }
            ],
        )

        passed, issues = analyze_response(
            result,
            {
                "min_content_length": 100,
                "required_any_keywords": [
                    "race",
                    "lock",
                    "mutex",
                    "asyncio.lock",
                    "concurrent",
                    "atomic",
                ],
                "no_error_patterns": ["i don't understand"],
            },
        )

        print(
            f"\n{'✅ PASSED' if passed else '❌ FAILED'} ({result['duration_ms']:.0f}ms)"
        )
        if issues:
            for issue in issues:
                print(f"   ⚠️ {issue}")
        print(f"\nResponse preview: {result['content'][:400]}...")
        if result["thinking"]:
            print(f"Thinking preview: {result['thinking'][:400]}...")

        results.append(("Complex Bug: Race Condition", passed, result["duration_ms"]))

        # ================================================================
        # TEST 3: BUILD MINI-PROJECT - REST API for task management
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST 3: BUILD COMPLETE MINI-PROJECT")
        print("Create a task management REST API from scratch")
        print("=" * 70)

        result = await send_navi_request(
            session,
            """Create a complete task management REST API with:

            1. FastAPI endpoints:
               - POST /tasks - Create task
               - GET /tasks - List tasks with filtering
               - GET /tasks/{id} - Get single task
               - PUT /tasks/{id} - Update task
               - DELETE /tasks/{id} - Delete task

            2. Data model:
               - id, title, description, status (pending/in_progress/done), priority, due_date

            3. Features:
               - Input validation with Pydantic
               - In-memory storage (dict) for simplicity
               - Proper error handling
               - Status filtering on list endpoint

            Generate all the code needed to run this API.""",
        )

        passed, issues = analyze_response(
            result,
            {
                "min_content_length": 300,
                "required_any_keywords": [
                    "fastapi",
                    "pydantic",
                    "task",
                    "endpoint",
                    "post",
                    "get",
                ],
                "has_code": True,
                "no_error_patterns": ["i don't understand", "please try again"],
            },
        )

        print(
            f"\n{'✅ PASSED' if passed else '❌ FAILED'} ({result['duration_ms']:.0f}ms)"
        )
        if issues:
            for issue in issues:
                print(f"   ⚠️ {issue}")
        print(f"Actions proposed: {len(result['actions'])}")
        print(f"\nResponse preview: {result['content'][:400]}...")
        if result["thinking"]:
            print(f"Thinking preview: {result['thinking'][:400]}...")

        results.append(("Mini-Project: Task API", passed, result["duration_ms"]))

        # ================================================================
        # TEST 4: COMPLEX DEBUGGING - Memory leak investigation
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST 4: COMPLEX DEBUGGING - Memory Leak")
        print("Investigate and fix a memory leak")
        print("=" * 70)

        leaky_code = """
import asyncio
from typing import Callable, Any

class EventEmitter:
    def __init__(self):
        self.listeners = {}

    def on(self, event: str, callback: Callable):
        if event not in self.listeners:
            self.listeners[event] = []
        self.listeners[event].append(callback)

    def emit(self, event: str, data: Any = None):
        if event in self.listeners:
            for callback in self.listeners[event]:
                callback(data)

class RequestHandler:
    def __init__(self, emitter: EventEmitter):
        self.emitter = emitter
        self.data = [0] * 10000  # Some data

        # Register listener
        self.emitter.on("request", self.handle_request)

    def handle_request(self, data):
        print(f"Handling: {data}")

# Usage pattern that causes memory leak:
emitter = EventEmitter()

async def process_requests():
    for i in range(100000):
        handler = RequestHandler(emitter)  # Created every request
        emitter.emit("request", f"Request {i}")
        # handler goes out of scope but...

# After 100k requests, memory usage is very high. Why?
"""

        result = await send_navi_request(
            session,
            "We have a memory leak. After processing 100k requests, memory usage is extremely high. The RequestHandler objects should be garbage collected but they're not. Find the leak and fix it.",
            attachments=[
                {
                    "kind": "code",
                    "path": "event_emitter.py",
                    "content": leaky_code,
                    "language": "python",
                }
            ],
        )

        passed, issues = analyze_response(
            result,
            {
                "min_content_length": 100,
                "required_any_keywords": [
                    "listener",
                    "reference",
                    "garbage",
                    "remove",
                    "off",
                    "unsubscribe",
                    "cleanup",
                    "weak",
                ],
                "no_error_patterns": ["i don't understand"],
            },
        )

        print(
            f"\n{'✅ PASSED' if passed else '❌ FAILED'} ({result['duration_ms']:.0f}ms)"
        )
        if issues:
            for issue in issues:
                print(f"   ⚠️ {issue}")
        print(f"\nResponse preview: {result['content'][:400]}...")
        if result["thinking"]:
            print(f"Thinking preview: {result['thinking'][:400]}...")

        results.append(("Complex Debug: Memory Leak", passed, result["duration_ms"]))

        # ================================================================
        # TEST 5: MULTI-STEP WORKFLOW - Refactoring with tests
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST 5: MULTI-STEP WORKFLOW")
        print("Refactor code and add tests")
        print("=" * 70)

        legacy_code = """
def process_order(order_data):
    # Validate
    if not order_data.get("items"):
        return {"error": "No items"}
    if not order_data.get("customer_id"):
        return {"error": "No customer"}

    # Calculate totals
    subtotal = 0
    for item in order_data["items"]:
        subtotal += item["price"] * item["quantity"]

    # Apply discount
    discount = 0
    if order_data.get("coupon") == "SAVE10":
        discount = subtotal * 0.1
    elif order_data.get("coupon") == "SAVE20":
        discount = subtotal * 0.2

    # Calculate tax
    tax = (subtotal - discount) * 0.08

    # Total
    total = subtotal - discount + tax

    # Create order record
    order = {
        "customer_id": order_data["customer_id"],
        "items": order_data["items"],
        "subtotal": subtotal,
        "discount": discount,
        "tax": tax,
        "total": total,
        "status": "pending"
    }

    # Would save to database here
    return {"success": True, "order": order}
"""

        result = await send_navi_request(
            session,
            """Refactor this legacy order processing code:

            1. Split into smaller, testable functions
            2. Add proper error handling with custom exceptions
            3. Use dataclasses or Pydantic models
            4. Add type hints
            5. Write unit tests for all functions

            Show me the refactored code with tests.""",
            attachments=[
                {
                    "kind": "code",
                    "path": "order_processor.py",
                    "content": legacy_code,
                    "language": "python",
                }
            ],
        )

        passed, issues = analyze_response(
            result,
            {
                "min_content_length": 200,
                "required_any_keywords": [
                    "class",
                    "def",
                    "test",
                    "dataclass",
                    "pydantic",
                    "typing",
                ],
                "has_code": True,
                "no_error_patterns": ["i don't understand"],
            },
        )

        print(
            f"\n{'✅ PASSED' if passed else '❌ FAILED'} ({result['duration_ms']:.0f}ms)"
        )
        if issues:
            for issue in issues:
                print(f"   ⚠️ {issue}")
        print(f"\nResponse preview: {result['content'][:400]}...")
        if result["thinking"]:
            print(f"Thinking preview: {result['thinking'][:400]}...")

        results.append(("Multi-Step: Refactor + Tests", passed, result["duration_ms"]))

        # ================================================================
        # TEST 6: COMPLEX INTEGRATION - OAuth2 Implementation
        # ================================================================
        print("\n" + "=" * 70)
        print("TEST 6: COMPLEX INTEGRATION")
        print("Implement OAuth2 authentication flow")
        print("=" * 70)

        result = await send_navi_request(
            session,
            """Implement a complete OAuth2 authentication system for a FastAPI app:

            1. JWT token generation and validation
            2. Password hashing with bcrypt
            3. Login endpoint that returns access + refresh tokens
            4. Token refresh endpoint
            5. Protected route decorator
            6. User model with proper security

            Generate production-ready code with security best practices.""",
        )

        passed, issues = analyze_response(
            result,
            {
                "min_content_length": 200,
                "required_any_keywords": [
                    "jwt",
                    "token",
                    "oauth",
                    "bcrypt",
                    "hash",
                    "secret",
                    "bearer",
                ],
                "has_code": True,
                "no_error_patterns": ["i don't understand"],
            },
        )

        print(
            f"\n{'✅ PASSED' if passed else '❌ FAILED'} ({result['duration_ms']:.0f}ms)"
        )
        if issues:
            for issue in issues:
                print(f"   ⚠️ {issue}")
        print(f"Actions proposed: {len(result['actions'])}")
        print(f"\nResponse preview: {result['content'][:400]}...")
        if result["thinking"]:
            print(f"Thinking preview: {result['thinking'][:400]}...")

        results.append(("Complex Integration: OAuth2", passed, result["duration_ms"]))

    # ================================================================
    # FINAL SUMMARY
    # ================================================================
    print("\n" + "=" * 70)
    print("COMPLEX E2E TEST SUMMARY")
    print("=" * 70)

    passed_count = sum(1 for _, p, _ in results if p)
    total_count = len(results)
    total_time = sum(d for _, _, d in results)

    print("\nResults:")
    for name, passed, duration in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"   {status} {name} ({duration:.0f}ms)")

    print(f"\nTotal Tests: {total_count}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {total_count - passed_count}")
    print(f"Success Rate: {passed_count / total_count * 100:.1f}%")
    print(f"Total Time: {total_time / 1000:.1f}s")

    return passed_count == total_count


if __name__ == "__main__":
    success = asyncio.run(run_complex_tests())
    sys.exit(0 if success else 1)
