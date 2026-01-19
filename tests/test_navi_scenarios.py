#!/usr/bin/env python3
"""
NAVI Scenario Tests - Tests for complex real-world scenarios
"""

import asyncio
import aiohttp
import json
import os
import sys
from typing import Dict, List, Tuple

BASE_URL = os.getenv("NAVI_BASE_URL", "http://localhost:8000")
WORKSPACE_ROOT = "/Users/mounikakapa/dev/autonomous-engineering-platform"


async def send_navi_request(
    session: aiohttp.ClientSession,
    message: str,
    attachments: List[Dict] = None,
    mode: str = "agent",
) -> Tuple[str, str, List[Dict], List[Dict], Dict]:
    """Send request and return (content, thinking, actions, activities, metrics)."""

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
            if response.status != 200:
                error = await response.text()
                return f"ERROR: {error}", "", [], [], {}

            content = ""
            thinking = ""
            actions = []
            activities = []
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
                        content += data["content"]
                    if "thinking" in data:
                        thinking += data["thinking"]
                    if "actions" in data:
                        actions.extend(data["actions"])
                    if "activity" in data:
                        activities.append(data["activity"])
                    if "metrics" in data:
                        metrics = data["metrics"]
                    if "error" in data:
                        return f"ERROR: {data['error']}", "", [], [], {}
                except json.JSONDecodeError:
                    continue

            return content, thinking, actions, activities, metrics

    except Exception as e:
        return f"EXCEPTION: {e}", "", [], [], {}


async def run_scenario_tests():
    """Run complex scenario tests."""

    passed = 0
    failed = 0

    async with aiohttp.ClientSession() as session:

        # ================================================================
        # SCENARIO 1: Complex error analysis with stack trace
        # ================================================================
        print("\n" + "="*60)
        print("SCENARIO 1: Complex Error Analysis")
        print("="*60)

        error_message = """
I'm getting this error in production:

Traceback (most recent call last):
  File "/app/backend/services/navi_brain.py", line 4549, in _call_openai_compatible
    return data["choices"][0]["message"]["content"]
KeyError: 'choices'

The API call sometimes returns a different format. How do I make this more robust?
"""
        content, thinking, actions, activities, metrics = await send_navi_request(
            session, error_message
        )

        # Check quality
        checks = [
            ("Has meaningful content", len(content) > 100),
            ("Mentions KeyError/choices", "keyerror" in (content + thinking).lower() or "choices" in (content + thinking).lower()),
            ("Suggests defensive coding", any(k in (content + thinking).lower() for k in [".get(", "try", "except", "if ", "check"])),
        ]

        all_passed = all(c[1] for c in checks)
        status = "✅ PASSED" if all_passed else "❌ FAILED"
        print(f"Result: {status}")
        for name, passed_check in checks:
            print(f"   {'✅' if passed_check else '❌'} {name}")
        print(f"   Content: {content[:200]}...")

        if all_passed:
            passed += 1
        else:
            failed += 1


        # ================================================================
        # SCENARIO 2: Architecture decision request
        # ================================================================
        print("\n" + "="*60)
        print("SCENARIO 2: Architecture Decision")
        print("="*60)

        content, thinking, actions, activities, metrics = await send_navi_request(
            session,
            "Should I use Redis or PostgreSQL for caching LLM responses? Consider that we have 100k+ users and responses can be up to 10KB each."
        )

        checks = [
            ("Has meaningful content", len(content) > 200),
            ("Discusses Redis", "redis" in (content + thinking).lower()),
            ("Discusses PostgreSQL", any(k in (content + thinking).lower() for k in ["postgresql", "postgres", "pg"])),
            ("Considers scale", any(k in (content + thinking).lower() for k in ["scale", "user", "100k", "performance"])),
        ]

        all_passed = all(c[1] for c in checks)
        status = "✅ PASSED" if all_passed else "❌ FAILED"
        print(f"Result: {status}")
        for name, passed_check in checks:
            print(f"   {'✅' if passed_check else '❌'} {name}")
        print(f"   Content: {content[:200]}...")

        if all_passed:
            passed += 1
        else:
            failed += 1


        # ================================================================
        # SCENARIO 3: Multi-file refactoring plan
        # ================================================================
        print("\n" + "="*60)
        print("SCENARIO 3: Multi-file Refactoring")
        print("="*60)

        content, thinking, actions, activities, metrics = await send_navi_request(
            session,
            "I want to extract all the LLM-related code from navi_brain.py into a separate module. Give me a step-by-step refactoring plan."
        )

        checks = [
            ("Has meaningful content", len(content) > 200),
            ("Mentions files/modules", any(k in (content + thinking).lower() for k in ["module", "file", ".py", "import"])),
            ("Has steps", any(k in (content + thinking).lower() for k in ["step", "1.", "first", "then", "next"])),
            ("Mentions navi_brain", "navi_brain" in (content + thinking).lower() or "navi" in (content + thinking).lower()),
        ]

        all_passed = all(c[1] for c in checks)
        status = "✅ PASSED" if all_passed else "❌ FAILED"
        print(f"Result: {status}")
        for name, passed_check in checks:
            print(f"   {'✅' if passed_check else '❌'} {name}")
        print(f"   Content: {content[:200]}...")

        if all_passed:
            passed += 1
        else:
            failed += 1


        # ================================================================
        # SCENARIO 4: Debugging intermittent issue
        # ================================================================
        print("\n" + "="*60)
        print("SCENARIO 4: Intermittent Bug Debugging")
        print("="*60)

        content, thinking, actions, activities, metrics = await send_navi_request(
            session,
            "Users report that sometimes the chat just shows a loading spinner forever but only about 10% of the time. How do I debug this?"
        )

        checks = [
            ("Has meaningful content", len(content) > 100),
            ("Suggests debugging approaches", any(k in (content + thinking).lower() for k in ["log", "debug", "trace", "monitor", "timeout"])),
            ("Addresses intermittent nature", any(k in (content + thinking).lower() for k in ["intermittent", "sometimes", "random", "race", "async"])),
        ]

        all_passed = all(c[1] for c in checks)
        status = "✅ PASSED" if all_passed else "❌ FAILED"
        print(f"Result: {status}")
        for name, passed_check in checks:
            print(f"   {'✅' if passed_check else '❌'} {name}")
        print(f"   Content: {content[:200]}...")

        if all_passed:
            passed += 1
        else:
            failed += 1


        # ================================================================
        # SCENARIO 5: Create complete feature with tests
        # ================================================================
        print("\n" + "="*60)
        print("SCENARIO 5: Complete Feature Implementation")
        print("="*60)

        content, thinking, actions, activities, metrics = await send_navi_request(
            session,
            "Create a health check endpoint at /health that returns the status of all dependencies (database, LLM providers, Redis if configured). Include tests."
        )

        checks = [
            ("Has content", len(content) > 50),
            ("Proposes code or actions", len(actions) > 0 or "def " in content or "async def" in content or "```" in content),
            ("Mentions health/status", any(k in (content + thinking).lower() for k in ["health", "status", "check", "endpoint"])),
        ]

        all_passed = all(c[1] for c in checks)
        status = "✅ PASSED" if all_passed else "❌ FAILED"
        print(f"Result: {status}")
        for name, passed_check in checks:
            print(f"   {'✅' if passed_check else '❌'} {name}")
        if actions:
            print(f"   Actions: {len(actions)} proposed")
            for a in actions[:3]:
                print(f"      - {a.get('type')}: {str(a.get('filePath', a.get('command', '')))[:50]}")
        print(f"   Content: {content[:200]}...")

        if all_passed:
            passed += 1
        else:
            failed += 1


        # ================================================================
        # SCENARIO 6: Security vulnerability scan
        # ================================================================
        print("\n" + "="*60)
        print("SCENARIO 6: Security Analysis")
        print("="*60)

        vuln_code = '''
@app.get("/user/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db)):
    query = f"SELECT * FROM users WHERE id = '{user_id}'"
    result = db.execute(query)
    return result.fetchone()
'''
        content, thinking, actions, activities, metrics = await send_navi_request(
            session,
            "Is this code secure? What are the vulnerabilities?",
            attachments=[{
                "kind": "code",
                "path": "vulnerable.py",
                "content": vuln_code,
                "language": "python"
            }]
        )

        combined = (content + thinking).lower()
        checks = [
            ("Has content", len(content) > 50 or len(thinking) > 100),
            ("Identifies SQL injection", any(k in combined for k in ["sql injection", "injection", "f-string", "parameterized", "sanitize"])),
            ("Suggests fix", any(k in combined for k in ["parameterized", "prepared", "bind", "placeholder", "?", ":"])),
        ]

        all_passed = all(c[1] for c in checks)
        status = "✅ PASSED" if all_passed else "❌ FAILED"
        print(f"Result: {status}")
        for name, passed_check in checks:
            print(f"   {'✅' if passed_check else '❌'} {name}")
        if thinking:
            print(f"   Thinking: {thinking[:200]}...")
        print(f"   Content: {content[:200]}...")

        if all_passed:
            passed += 1
        else:
            failed += 1


    # ================================================================
    # SUMMARY
    # ================================================================
    print("\n" + "="*60)
    print("SCENARIO TEST SUMMARY")
    print("="*60)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    print(f"Success Rate: {passed/(passed+failed)*100:.1f}%")

    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_scenario_tests())
    sys.exit(0 if success else 1)
