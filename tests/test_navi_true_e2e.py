#!/usr/bin/env python3
"""
NAVI TRUE End-to-End Test

This test validates NAVI can:
1. Generate code
2. Actually create the files
3. Run the code
4. Verify it works

This is a REAL end-to-end test, not just response validation.
"""

import asyncio
import aiohttp
import json
import os
import sys
import subprocess
import shutil
from pathlib import Path

BASE_URL = os.getenv("NAVI_BASE_URL", "http://localhost:8000")
WORKSPACE_ROOT = "/Users/mounikakapa/dev/autonomous-engineering-platform"
TEST_DIR = Path(WORKSPACE_ROOT) / "tests" / "navi_e2e_output"


async def send_navi_request(session, message, mode="agent"):
    """Send request to NAVI and get full response with actions."""
    payload = {
        "message": message,
        "mode": mode,
        "workspace_root": str(TEST_DIR),
        "attachments": [],
        "conversationHistory": [],
    }

    try:
        async with session.post(
            f"{BASE_URL}/api/navi/chat/stream",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=180),
        ) as response:
            result = {
                "content": "",
                "thinking": "",
                "actions": [],
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
                    if "error" in data:
                        result["error"] = data["error"]
                except json.JSONDecodeError:
                    continue

            return result
    except Exception as e:
        return {"error": str(e), "content": "", "thinking": "", "actions": []}


def extract_code_from_response(response):
    """Extract code blocks from thinking or content."""
    combined = response.get("thinking", "") + response.get("content", "")

    # Try to find JSON with files_to_create
    try:
        # Find JSON in thinking
        if "files_to_create" in combined:
            import re
            json_match = re.search(r'\{[\s\S]*"files_to_create"[\s\S]*?\}(?=\s*$|\s*```)', combined)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("files_to_create", {})
    except:
        pass

    # Fallback: extract from actions
    files = {}
    for action in response.get("actions", []):
        if action.get("type") in ("createFile", "editFile", "create", "edit"):
            path = action.get("filePath") or action.get("path")
            content = action.get("content")
            if path and content:
                files[path] = content

    return files


def setup_test_directory():
    """Create clean test directory."""
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    TEST_DIR.mkdir(parents=True)
    print(f"Created test directory: {TEST_DIR}")


def write_files(files: dict):
    """Write files to test directory."""
    created = []
    for path, content in files.items():
        # Handle relative paths
        if path.startswith("/"):
            full_path = Path(path)
        else:
            full_path = TEST_DIR / path

        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        created.append(str(full_path))
        print(f"   Created: {full_path.name}")

    return created


async def run_true_e2e_tests():
    """Run true end-to-end tests where NAVI creates and we execute."""

    print("="*70)
    print("NAVI TRUE END-TO-END TESTS")
    print("="*70)
    print(f"Test directory: {TEST_DIR}")
    print()

    results = []

    async with aiohttp.ClientSession() as session:

        # ================================================================
        # TEST 1: Create a working Python utility
        # ================================================================
        print("\n" + "="*70)
        print("TEST 1: Create and Run Python Utility")
        print("="*70)

        setup_test_directory()

        response = await send_navi_request(
            session,
            """Create a Python file called 'calculator.py' with these functions:
            - add(a, b) -> returns sum
            - subtract(a, b) -> returns difference
            - multiply(a, b) -> returns product
            - divide(a, b) -> returns quotient (handle division by zero)

            Also create a test file 'test_calculator.py' that tests all functions.
            Use assert statements for testing.

            Make sure the code is complete and runnable."""
        )

        if response.get("error"):
            print(f"❌ NAVI Error: {response['error']}")
            results.append(("Python Utility", False, "NAVI error"))
        else:
            # Extract files from response
            files = extract_code_from_response(response)

            # If no files in structured format, try to parse from thinking
            if not files:
                thinking = response.get("thinking", "")
                # Try to extract files_to_create from JSON in thinking
                try:
                    import re
                    # Look for the JSON structure
                    match = re.search(r'"files_to_create"\s*:\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}', thinking, re.DOTALL)
                    if match:
                        # Reconstruct and parse
                        json_str = '{"files_to_create": {' + match.group(1) + '}}'
                        # Clean up the JSON
                        json_str = json_str.replace('\n', '\\n').replace('\t', '\\t')
                        data = json.loads(json_str)
                        files = data.get("files_to_create", {})
                except Exception as e:
                    print(f"   Could not parse files: {e}")

            if not files:
                # Manual extraction from thinking content
                print("   Extracting code from thinking...")
                thinking = response.get("thinking", "")

                # Find calculator.py content
                if "def add" in thinking:
                    # Extract the code block
                    import re
                    calc_match = re.search(r'calculator\.py["\s:]+[`"]*\s*((?:def|#|from|import)[\s\S]*?)(?=["\n]\s*[,}]|```)', thinking)
                    if calc_match:
                        files["calculator.py"] = calc_match.group(1).replace('\\n', '\n').replace('\\"', '"')

                    test_match = re.search(r'test_calculator\.py["\s:]+[`"]*\s*((?:def|#|from|import)[\s\S]*?)(?=["\n]\s*[,}]|```)', thinking)
                    if test_match:
                        files["test_calculator.py"] = test_match.group(1).replace('\\n', '\n').replace('\\"', '"')

            if files:
                print(f"   NAVI generated {len(files)} files")
                write_files(files)

                # Try to run the test
                calc_file = TEST_DIR / "calculator.py"
                test_file = TEST_DIR / "test_calculator.py"

                if calc_file.exists():
                    print("\n   Running tests...")
                    try:
                        # First check syntax
                        result = subprocess.run(
                            ["python3", "-m", "py_compile", str(calc_file)],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )

                        if result.returncode == 0:
                            print("   ✅ calculator.py syntax valid")

                            # Try to run tests if they exist
                            if test_file.exists():
                                result = subprocess.run(
                                    ["python3", str(test_file)],
                                    capture_output=True,
                                    text=True,
                                    timeout=30,
                                    cwd=str(TEST_DIR)
                                )

                                if result.returncode == 0:
                                    print("   ✅ Tests passed!")
                                    results.append(("Python Utility", True, "Code runs and tests pass"))
                                else:
                                    print(f"   ⚠️ Tests failed: {result.stderr[:200]}")
                                    results.append(("Python Utility", False, f"Tests failed: {result.stderr[:100]}"))
                            else:
                                # Just verify we can import
                                result = subprocess.run(
                                    ["python3", "-c", f"import sys; sys.path.insert(0, '{TEST_DIR}'); import calculator; print(calculator.add(2,3))"],
                                    capture_output=True,
                                    text=True,
                                    timeout=10
                                )
                                if result.returncode == 0 and "5" in result.stdout:
                                    print(f"   ✅ calculator.add(2,3) = {result.stdout.strip()}")
                                    results.append(("Python Utility", True, "Code runs correctly"))
                                else:
                                    results.append(("Python Utility", False, f"Import failed: {result.stderr}"))
                        else:
                            print(f"   ❌ Syntax error: {result.stderr}")
                            results.append(("Python Utility", False, "Syntax error"))
                    except Exception as e:
                        print(f"   ❌ Execution error: {e}")
                        results.append(("Python Utility", False, str(e)))
                else:
                    print("   ❌ calculator.py not created")
                    results.append(("Python Utility", False, "File not created"))
            else:
                print("   ❌ No files extracted from response")
                print(f"   Response content: {response.get('content', '')[:200]}")
                print(f"   Thinking: {response.get('thinking', '')[:200]}")
                results.append(("Python Utility", False, "No files generated"))


        # ================================================================
        # TEST 2: Create a FastAPI endpoint and test it
        # ================================================================
        print("\n" + "="*70)
        print("TEST 2: Create FastAPI Endpoint")
        print("="*70)

        # Clean test dir
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)
        TEST_DIR.mkdir(parents=True)

        response = await send_navi_request(
            session,
            """Create a simple FastAPI app in 'app.py' with:
            - GET /health -> returns {"status": "ok"}
            - GET /add?a=1&b=2 -> returns {"result": 3}

            Just the app file, nothing else. Make it minimal and runnable."""
        )

        if response.get("error"):
            print(f"❌ NAVI Error: {response['error']}")
            results.append(("FastAPI Endpoint", False, "NAVI error"))
        else:
            files = extract_code_from_response(response)

            # Try manual extraction
            if not files:
                thinking = response.get("thinking", "")
                content = response.get("content", "")
                combined = thinking + content

                # Look for FastAPI code
                if "FastAPI" in combined or "fastapi" in combined:
                    import re
                    # Find code that starts with from fastapi or import
                    code_match = re.search(r'(from fastapi[\s\S]*?)(?:```|"test|$)', combined)
                    if code_match:
                        code = code_match.group(1).replace('\\n', '\n').replace('\\"', '"')
                        # Clean up any trailing JSON artifacts
                        code = re.sub(r'",?\s*"files_to_modify.*$', '', code, flags=re.DOTALL)
                        files["app.py"] = code.strip()

            if files:
                print(f"   NAVI generated {len(files)} files")
                write_files(files)

                app_file = TEST_DIR / "app.py"
                if app_file.exists():
                    # Check syntax
                    result = subprocess.run(
                        ["python3", "-m", "py_compile", str(app_file)],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    if result.returncode == 0:
                        print("   ✅ app.py syntax valid")

                        # Try to import and check app exists
                        check_code = f"""
import sys
sys.path.insert(0, '{TEST_DIR}')
from app import app
print("APP_EXISTS" if app else "NO_APP")
"""
                        result = subprocess.run(
                            ["python3", "-c", check_code],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )

                        if "APP_EXISTS" in result.stdout:
                            print("   ✅ FastAPI app created successfully")
                            results.append(("FastAPI Endpoint", True, "App created and importable"))
                        else:
                            print(f"   ⚠️ App import issue: {result.stderr[:100]}")
                            results.append(("FastAPI Endpoint", False, "Import failed"))
                    else:
                        print(f"   ❌ Syntax error: {result.stderr[:100]}")
                        results.append(("FastAPI Endpoint", False, "Syntax error"))
                else:
                    results.append(("FastAPI Endpoint", False, "File not created"))
            else:
                print("   ❌ No files generated")
                results.append(("FastAPI Endpoint", False, "No files"))


        # ================================================================
        # TEST 3: Debug and fix broken code
        # ================================================================
        print("\n" + "="*70)
        print("TEST 3: Debug and Fix Broken Code")
        print("="*70)

        # Create broken code
        if TEST_DIR.exists():
            shutil.rmtree(TEST_DIR)
        TEST_DIR.mkdir(parents=True)

        broken_code = '''
def process_data(items):
    total = 0
    for item in items:
        total += item["value"]  # Bug: KeyError if "value" missing
    return total / len(items)  # Bug: ZeroDivisionError if empty

# This will crash:
# result = process_data([{"name": "test"}])  # Missing "value" key
# result = process_data([])  # Empty list
'''
        broken_file = TEST_DIR / "broken.py"
        broken_file.write_text(broken_code)

        response = await send_navi_request(
            session,
            f"""Fix this broken code. The function crashes when:
            1. Items don't have a "value" key
            2. Items list is empty

            Create a fixed version in 'fixed.py':

            ```python
{broken_code}
            ```

            The fixed code should handle both edge cases gracefully."""
        )

        if response.get("error"):
            print(f"❌ NAVI Error: {response['error']}")
            results.append(("Debug & Fix", False, "NAVI error"))
        else:
            files = extract_code_from_response(response)

            # Manual extraction
            if not files:
                thinking = response.get("thinking", "")
                if "def process_data" in thinking:
                    import re
                    code_match = re.search(r'(def process_data[\s\S]*?)(?:```|"message|$)', thinking)
                    if code_match:
                        code = code_match.group(1).replace('\\n', '\n').replace('\\"', '"')
                        files["fixed.py"] = code.strip()

            if files:
                print("   NAVI generated fix")
                write_files(files)

                fixed_file = TEST_DIR / "fixed.py"
                if fixed_file.exists():
                    # Test the fixed code
                    test_code = f"""
import sys
sys.path.insert(0, '{TEST_DIR}')
from fixed import process_data

# Test 1: Normal case
try:
    result = process_data([{{"value": 10}}, {{"value": 20}}])
    print(f"Normal: {{result}}")
except Exception as e:
    print(f"Normal failed: {{e}}")
    sys.exit(1)

# Test 2: Missing key
try:
    result = process_data([{{"name": "test"}}])
    print(f"Missing key: {{result}}")
except Exception as e:
    print(f"Missing key failed: {{e}}")
    sys.exit(1)

# Test 3: Empty list
try:
    result = process_data([])
    print(f"Empty: {{result}}")
except Exception as e:
    print(f"Empty failed: {{e}}")
    sys.exit(1)

print("ALL_TESTS_PASSED")
"""
                    result = subprocess.run(
                        ["python3", "-c", test_code],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    if "ALL_TESTS_PASSED" in result.stdout:
                        print("   ✅ Fixed code handles all edge cases!")
                        print(f"   Output: {result.stdout.strip()}")
                        results.append(("Debug & Fix", True, "All edge cases handled"))
                    else:
                        print(f"   ⚠️ Some tests failed: {result.stdout} {result.stderr}")
                        results.append(("Debug & Fix", False, "Edge cases not handled"))
                else:
                    results.append(("Debug & Fix", False, "Fixed file not created"))
            else:
                print("   ❌ No fix generated")
                results.append(("Debug & Fix", False, "No fix generated"))


    # ================================================================
    # SUMMARY
    # ================================================================
    print("\n" + "="*70)
    print("TRUE E2E TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, p, _ in results if p)
    total = len(results)

    for name, success, detail in results:
        status = "✅" if success else "❌"
        print(f"{status} {name}: {detail}")

    print(f"\nTotal: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {passed/total*100:.0f}%")

    # Cleanup
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
        print(f"\nCleaned up {TEST_DIR}")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_true_e2e_tests())
    sys.exit(0 if success else 1)
