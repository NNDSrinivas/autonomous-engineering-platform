#!/usr/bin/env python3
"""
NAVI End-to-End Capability Tests

Tests NAVI's ability to handle real-world scenarios without hardcoded hints.
Each test sends a natural language request and validates the response quality.
"""

import asyncio
import aiohttp
import json
import os
import sys
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

# Configuration
BASE_URL = os.getenv("NAVI_BASE_URL", "http://localhost:8000")
WORKSPACE_ROOT = os.getenv(
    "WORKSPACE_ROOT", "/Users/mounikakapa/dev/autonomous-engineering-platform"
)


@dataclass
class TestResult:
    name: str
    passed: bool
    response: Dict[str, Any]
    error: Optional[str] = None
    duration_ms: float = 0
    notes: List[str] = None


class NaviTester:
    def __init__(self):
        self.results: List[TestResult] = []
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def send_navi_request(
        self,
        message: str,
        attachments: List[Dict] = None,
        mode: str = "agent",
        workspace_root: str = None,
    ) -> Dict[str, Any]:
        """Send a request to NAVI chat stream endpoint."""
        payload = {
            "message": message,
            "mode": mode,
            "workspace_root": workspace_root or WORKSPACE_ROOT,
            "attachments": attachments or [],
            "conversationHistory": [],
        }

        start = datetime.now()

        try:
            async with self.session.post(
                f"{BASE_URL}/api/navi/chat/stream",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return {"error": f"HTTP {response.status}: {error_text}"}

                # Parse SSE response
                full_content = ""
                actions = []
                activity_events = []
                router_info = {}
                metrics = {}

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
                        if "actions" in data:
                            actions.extend(data["actions"])
                        if "activity" in data:
                            activity_events.append(data["activity"])
                        if "router_info" in data:
                            router_info = data["router_info"]
                        if "metrics" in data:
                            metrics = data["metrics"]
                        if "error" in data:
                            return {"error": data["error"]}
                    except json.JSONDecodeError:
                        continue

                duration = (datetime.now() - start).total_seconds() * 1000

                return {
                    "content": full_content,
                    "actions": actions,
                    "activity_events": activity_events,
                    "router_info": router_info,
                    "metrics": metrics,
                    "duration_ms": duration,
                }

        except Exception as e:
            return {"error": str(e)}

    async def run_test(
        self,
        name: str,
        message: str,
        validators: List[callable],
        attachments: List[Dict] = None,
        mode: str = "agent",
    ) -> TestResult:
        """Run a single test and validate results."""
        print(f"\n{'='*60}")
        print(f"TEST: {name}")
        print(f"{'='*60}")
        print(f"Message: {message[:100]}{'...' if len(message) > 100 else ''}")

        response = await self.send_navi_request(message, attachments, mode)

        if "error" in response:
            result = TestResult(
                name=name,
                passed=False,
                response=response,
                error=response["error"],
                notes=["Request failed with error"],
            )
            print(f"❌ FAILED: {response['error']}")
            self.results.append(result)
            return result

        # Run validators
        notes = []
        passed = True
        for validator in validators:
            try:
                valid, note = validator(response)
                notes.append(note)
                if not valid:
                    passed = False
            except Exception as e:
                notes.append(f"Validator error: {e}")
                passed = False

        result = TestResult(
            name=name,
            passed=passed,
            response=response,
            duration_ms=response.get("duration_ms", 0),
            notes=notes,
        )

        if passed:
            print(f"✅ PASSED ({result.duration_ms:.0f}ms)")
        else:
            print("❌ FAILED")

        for note in notes:
            print(f"   - {note}")

        # Show response preview
        content = response.get("content", "")
        if content:
            preview = content[:300].replace("\n", " ")
            print(f"   Response: {preview}{'...' if len(content) > 300 else ''}")

        if response.get("actions"):
            print(f"   Actions: {len(response['actions'])} proposed")
            for action in response["actions"][:3]:
                print(
                    f"      - {action.get('type', 'unknown')}: {action.get('filePath', action.get('command', ''))[:50]}"
                )

        self.results.append(result)
        return result


# ============================================================================
# VALIDATORS
# ============================================================================


def has_content(min_length: int = 50):
    """Validate that response has meaningful content."""

    def validator(response: Dict) -> tuple:
        content = response.get("content", "")
        if len(content) >= min_length:
            return True, f"Content length: {len(content)} chars"
        return False, f"Content too short: {len(content)} chars (min: {min_length})"

    return validator


def no_hardcoded_response():
    """Validate response is not a generic hardcoded fallback."""
    hardcoded_patterns = [
        "I couldn't generate a response",
        "I encountered an error",
        "Please try again",
        "I'm not sure what you mean",
        "Could you rephrase",
        "I don't understand",
        "Error:",
        "Sorry, I can't",
    ]

    def validator(response: Dict) -> tuple:
        content = response.get("content", "").lower()
        for pattern in hardcoded_patterns:
            if pattern.lower() in content:
                return False, f"Found hardcoded fallback: '{pattern}'"
        return True, "No hardcoded fallback detected"

    return validator


def contains_keywords(keywords: List[str], min_matches: int = 1):
    """Validate response contains expected keywords."""

    def validator(response: Dict) -> tuple:
        content = response.get("content", "").lower()
        matches = [k for k in keywords if k.lower() in content]
        if len(matches) >= min_matches:
            return True, f"Found keywords: {matches}"
        return False, f"Missing keywords. Found {len(matches)}/{min_matches}: {matches}"

    return validator


def has_actions(action_types: List[str] = None):
    """Validate response includes proposed actions."""

    def validator(response: Dict) -> tuple:
        actions = response.get("actions", [])
        if not actions:
            return False, "No actions proposed"
        if action_types:
            found_types = [a.get("type") for a in actions]
            matches = [t for t in action_types if t in found_types]
            if matches:
                return True, f"Found action types: {found_types}"
            return (
                False,
                f"Missing action types. Expected: {action_types}, Found: {found_types}",
            )
        return True, f"Has {len(actions)} actions"

    return validator


def has_activity_events(min_events: int = 1):
    """Validate response includes activity events."""

    def validator(response: Dict) -> tuple:
        events = response.get("activity_events", [])
        if len(events) >= min_events:
            return True, f"Has {len(events)} activity events"
        return False, f"Too few activity events: {len(events)} (min: {min_events})"

    return validator


def response_is_contextual():
    """Validate response shows understanding of the project context."""

    def validator(response: Dict) -> tuple:
        content = response.get("content", "").lower()
        # Check for project-specific terms
        contextual_terms = [
            "navi",
            "vscode",
            "extension",
            "backend",
            "frontend",
            "react",
            "typescript",
            "python",
            "fastapi",
            "llm",
            "workspace",
            "project",
            "file",
            "code",
        ]
        matches = [t for t in contextual_terms if t in content]
        if len(matches) >= 2:
            return True, f"Contextual terms found: {matches[:5]}"
        return False, f"Response lacks context. Only found: {matches}"

    return validator


# ============================================================================
# TEST CASES
# ============================================================================


async def run_all_tests():
    """Run comprehensive NAVI tests."""

    async with NaviTester() as tester:

        # ====================================================================
        # TEST 1: Basic project understanding
        # ====================================================================
        await tester.run_test(
            name="Project Understanding",
            message="What is this project? Give me a brief overview of the codebase structure.",
            validators=[
                has_content(100),
                no_hardcoded_response(),
                response_is_contextual(),
            ],
        )

        # ====================================================================
        # TEST 2: Code explanation request
        # ====================================================================
        await tester.run_test(
            name="Code Explanation",
            message="Explain how the LLM routing works in this project. Which providers are supported?",
            validators=[
                has_content(150),
                no_hardcoded_response(),
                contains_keywords(["openai", "anthropic", "provider", "router"], 2),
            ],
        )

        # ====================================================================
        # TEST 3: Bug fix request (vague)
        # ====================================================================
        await tester.run_test(
            name="Vague Bug Fix Request",
            message="There's an issue where the chat sometimes returns empty responses. Can you investigate and fix it?",
            validators=[
                has_content(100),
                no_hardcoded_response(),
            ],
        )

        # ====================================================================
        # TEST 4: Feature implementation request
        # ====================================================================
        await tester.run_test(
            name="Feature Implementation",
            message="I want to add rate limiting to the NAVI API endpoints. Show me how to implement this with a sliding window approach.",
            validators=[
                has_content(200),
                no_hardcoded_response(),
                contains_keywords(["rate", "limit", "window", "request"], 2),
            ],
        )

        # ====================================================================
        # TEST 5: Complex debugging scenario
        # ====================================================================
        await tester.run_test(
            name="Complex Debugging",
            message="""The streaming response sometimes gets stuck and never completes.
            Users report that the loading spinner keeps spinning indefinitely.
            The issue seems intermittent and hard to reproduce.
            Can you help me debug this and suggest fixes?""",
            validators=[
                has_content(150),
                no_hardcoded_response(),
                contains_keywords(["stream", "timeout", "async", "response"], 1),
            ],
        )

        # ====================================================================
        # TEST 6: Multi-step task
        # ====================================================================
        await tester.run_test(
            name="Multi-step Task",
            message="""Create a new utility module for input validation that:
            1. Validates email format
            2. Validates URL format
            3. Sanitizes user input for SQL injection
            4. Has proper error messages
            Where should I put this file?""",
            validators=[
                has_content(200),
                no_hardcoded_response(),
                contains_keywords(["valid", "email", "url", "input"], 2),
            ],
        )

        # ====================================================================
        # TEST 7: Architecture question
        # ====================================================================
        await tester.run_test(
            name="Architecture Question",
            message="Why does the project have both backend/ai/llm_router.py and backend/services/llm_router.py? Are they duplicates?",
            validators=[
                has_content(100),
                no_hardcoded_response(),
            ],
        )

        # ====================================================================
        # TEST 8: Run project request
        # ====================================================================
        await tester.run_test(
            name="Run Project Request",
            message="How do I run this project? What commands do I need?",
            validators=[
                has_content(100),
                no_hardcoded_response(),
                contains_keywords(
                    ["npm", "pip", "python", "install", "run", "start"], 2
                ),
            ],
        )

        # ====================================================================
        # TEST 9: Error with stack trace
        # ====================================================================
        await tester.run_test(
            name="Error with Stack Trace",
            message="""I'm getting this error:

            TypeError: Cannot read properties of undefined (reading 'content')
                at _extract_text (llm_router.py:898)
                at run (llm_router.py:450)

            What's causing this and how do I fix it?""",
            validators=[
                has_content(100),
                no_hardcoded_response(),
                contains_keywords(["content", "undefined", "null", "check", "fix"], 2),
            ],
        )

        # ====================================================================
        # TEST 10: Refactoring request
        # ====================================================================
        await tester.run_test(
            name="Refactoring Request",
            message="The navi_brain.py file is over 5000 lines. How should I refactor it to be more maintainable?",
            validators=[
                has_content(150),
                no_hardcoded_response(),
                contains_keywords(
                    ["split", "module", "class", "extract", "refactor"], 2
                ),
            ],
        )

        # ====================================================================
        # TEST 11: Performance optimization
        # ====================================================================
        await tester.run_test(
            name="Performance Optimization",
            message="The LLM responses are taking 5-10 seconds. What can I do to make them faster?",
            validators=[
                has_content(100),
                no_hardcoded_response(),
                contains_keywords(["cache", "stream", "timeout", "model", "fast"], 2),
            ],
        )

        # ====================================================================
        # TEST 12: Test with code attachment
        # ====================================================================
        code_snippet = """
def process_request(data):
    result = data["items"][0]["value"]
    return result * 2
"""
        await tester.run_test(
            name="Code Review with Attachment",
            message="Review this code and tell me what could go wrong:",
            attachments=[
                {
                    "kind": "code",
                    "path": "example.py",
                    "content": code_snippet,
                    "language": "python",
                }
            ],
            validators=[
                has_content(100),
                no_hardcoded_response(),
                contains_keywords(
                    ["index", "key", "error", "empty", "none", "check"], 2
                ),
            ],
        )

        # ====================================================================
        # TEST 13: Ambiguous request
        # ====================================================================
        await tester.run_test(
            name="Ambiguous Request",
            message="Fix the thing that's broken",
            validators=[
                has_content(50),
                no_hardcoded_response(),
                # Should ask for clarification or explain it needs more info
            ],
        )

        # ====================================================================
        # TEST 14: Chat mode test
        # ====================================================================
        await tester.run_test(
            name="Chat Mode - Simple Question",
            message="What's the difference between async and sync programming?",
            mode="chat",
            validators=[
                has_content(100),
                no_hardcoded_response(),
                contains_keywords(
                    ["async", "sync", "wait", "concurrent", "parallel"], 2
                ),
            ],
        )

        # ====================================================================
        # TEST 15: Security-related request
        # ====================================================================
        await tester.run_test(
            name="Security Review",
            message="Are there any security vulnerabilities in how we handle API keys and secrets in this project?",
            validators=[
                has_content(100),
                no_hardcoded_response(),
                contains_keywords(["env", "secret", "key", "secure", "variable"], 2),
            ],
        )

        # ====================================================================
        # PRINT SUMMARY
        # ====================================================================
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)

        passed = sum(1 for r in tester.results if r.passed)
        failed = len(tester.results) - passed

        print(f"\nTotal: {len(tester.results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"Success Rate: {passed/len(tester.results)*100:.1f}%")

        if failed > 0:
            print("\nFailed Tests:")
            for r in tester.results:
                if not r.passed:
                    print(f"  - {r.name}")
                    if r.error:
                        print(f"    Error: {r.error}")
                    for note in r.notes or []:
                        if "FAILED" in note or "Missing" in note or "too short" in note:
                            print(f"    {note}")

        return passed, failed


if __name__ == "__main__":
    passed, failed = asyncio.run(run_all_tests())
    sys.exit(0 if failed == 0 else 1)
