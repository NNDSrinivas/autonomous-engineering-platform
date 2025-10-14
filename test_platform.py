#!/usr/bin/env python3
"""
Comprehensive test script for Autonomous Engineering Intelligence Platform
"""
import json
import sys

import requests


def test_endpoint(name, url, method="GET", data=None, expected_status=200):
    """Test a single API endpoint"""
    try:
        print(f"🧪 Testing {name}...")

        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)

        print(f"   Status: {response.status_code}")

        if response.status_code == expected_status:
            try:
                result = response.json()
                print("   ✅ Success")
                if isinstance(result, dict) and len(str(result)) < 300:
                    print(f"   Response: {json.dumps(result, indent=2)}")
                else:
                    print("   Response: Large response received")
            except Exception:
                print("   ✅ Success (non-JSON response)")
        else:
            print(f"   ❌ Failed: {response.text[:200]}")

        print()
        return response.status_code == expected_status

    except Exception as e:
        print(f"   ❌ Error: {e}")
        print()
        return False


def main():
    base_url = "http://localhost:8000"
    print("🚀 Testing Autonomous Engineering Intelligence Platform")
    print("=" * 60)

    # Test 1: Health Check
    success = test_endpoint("Health Check", f"{base_url}/health")

    if not success:
        print("❌ Backend is not running. Start it with:")
        print(
            "cd autonomous-engineering-platform && source .venv/bin/activate && PYTHONPATH=. python -m backend.api.main"
        )
        return 1

    # Test 2: AI Assistant (will work with API key)
    test_endpoint(
        "AI Assistant - Code Question",
        f"{base_url}/api/ask",
        "POST",
        {
            "question": "What's the difference between async and sync programming in Python?",
            "context": {"language": "python", "topic": "concurrency"},
        },
    )

    # Test 3: Code Analysis
    test_endpoint(
        "Code Analysis",
        f"{base_url}/api/analyze-code",
        "POST",
        {
            "code": """
def calculate_fibonacci(n):
    if n <= 1:
        return n
    return calculate_fibonacci(n-1) + calculate_fibonacci(n-2)

result = calculate_fibonacci(10)
print(f"Fibonacci of 10 is: {result}")
""",
            "language": "python",
            "analysis_type": "performance",
        },
    )

    # Test 4: Team Context Search
    test_endpoint(
        "Team Context Search",
        f"{base_url}/api/team-context",
        "POST",
        {
            "query": "API design patterns and best practices",
            "project_id": "demo-project",
            "limit": 3,
        },
    )

    # Test 5: API Documentation
    print("🧪 Testing API Documentation...")
    try:
        response = requests.get(f"{base_url}/docs", timeout=5)
        if response.status_code == 200:
            print("   ✅ API docs available at http://localhost:8000/docs")
        else:
            print("   ❌ API docs not accessible")
    except Exception as e:
        print(f"   ❌ Error accessing docs: {e}")

    print()
    print("📊 Test Complete!")
    print("🔗 Access your platform:")
    print("   • API Documentation: http://localhost:8000/docs")
    print("   • Health Check: http://localhost:8000/health")
    print("   • Raw API: http://localhost:8000")
    print()
    print("⚠️  To enable AI features:")
    print("   1. Add your OpenAI API key to .env file")
    print("   2. Restart the backend server")

    return 0


if __name__ == "__main__":
    sys.exit(main())
