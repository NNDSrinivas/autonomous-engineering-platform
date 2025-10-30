#!/usr/bin/env python3
"""
Verification script for Copilot PR review fixes.

This script tests the key fixes implemented to address Copilot's feedback:
1. Role service validation and type casting
2. Thread-safe cache operations
3. Error handling improvements
4. Memory leak prevention in log throttling
"""

import asyncio
import importlib
import os
import time

import backend.core.auth.deps as deps
from backend.core.auth.role_service import ROLE_RANK, RoleName
from backend.infra.cache.redis_cache import cache
from backend.core.auth.deps import _log_once, _LOG_THROTTLE_SECONDS


def test_role_validation():
    """Test role validation with proper type casting."""
    print("=== Testing Role Validation ===")

    test_roles = ["viewer", "planner", "admin", "invalid_role", "editor"]
    valid_roles = []

    for role_name in test_roles:
        if role_name in ROLE_RANK:
            validated_role: RoleName = (
                role_name  # Type hint for static analysis (validated above)
            )
            valid_roles.append(validated_role)
            print(f"✓ Valid role: {validated_role}")
        else:
            print(f"✗ Invalid role skipped: {role_name}")

    assert len(valid_roles) == 3, f"Expected 3 valid roles, got {len(valid_roles)}"
    print(f"✓ Role validation test passed - {len(valid_roles)} valid roles found\n")


async def test_cache_thread_safety():
    """Test cache thread safety with concurrent operations."""
    print("=== Testing Cache Thread Safety ===")

    async def cache_worker(worker_id: int):
        """Worker function for concurrent cache operations."""
        key = f"test_key_{worker_id}"
        value = {"worker": worker_id, "timestamp": time.time()}

        # Set, get, and delete operations
        await cache.set_json(key, value, ttl_sec=30)
        result = await cache.get_json(key)
        await cache.delete(key)

        return result == value

    # Run multiple concurrent cache operations
    tasks = [cache_worker(i) for i in range(10)]
    results = await asyncio.gather(*tasks)

    success_count = sum(results)
    print(f"✓ Cache operations: {success_count}/10 successful")
    assert (
        success_count == 10
    ), f"Expected all operations to succeed, got {success_count}/10"
    print("✓ Cache thread safety test passed\n")


def test_error_handling():
    """Test improved error handling for environment variables."""
    print("=== Testing Error Handling ===")

    # Save original value
    original_value = os.environ.get("LOG_THROTTLE_SECONDS")

    try:
        # Test with invalid value
        os.environ["LOG_THROTTLE_SECONDS"] = "not_a_number"

        # Import should handle this gracefully
        importlib.reload(deps)

        # Should fallback to default (300)
        assert (
            deps._LOG_THROTTLE_SECONDS == 300
        ), f"Expected 300, got {deps._LOG_THROTTLE_SECONDS}"
        print("✓ Invalid LOG_THROTTLE_SECONDS handled correctly")

        # Test with valid value
        os.environ["LOG_THROTTLE_SECONDS"] = "60"
        importlib.reload(deps)
        assert (
            deps._LOG_THROTTLE_SECONDS == 60
        ), f"Expected 60, got {deps._LOG_THROTTLE_SECONDS}"
        print("✓ Valid LOG_THROTTLE_SECONDS parsed correctly")

    finally:
        # Restore original value
        if original_value is not None:
            os.environ["LOG_THROTTLE_SECONDS"] = original_value
        else:
            os.environ.pop("LOG_THROTTLE_SECONDS", None)

    print("✓ Error handling test passed\n")


def test_log_throttling_cleanup():
    """Test memory leak prevention in log throttling."""
    print("=== Testing Log Throttling Cleanup ===")

    # Clear existing timestamps
    with deps._log_lock:
        deps._log_timestamps.clear()

    # Add some old entries manually (simulating old logs)
    old_time = time.time() - (
        3 * _LOG_THROTTLE_SECONDS
    )  # Older than 2x throttle period
    recent_time = time.time() - 10  # Recent

    with deps._log_lock:
        deps._log_timestamps["old_message_1"] = old_time
        deps._log_timestamps["old_message_2"] = old_time
        deps._log_timestamps["recent_message"] = recent_time

    initial_count = len(deps._log_timestamps)
    print(f"Initial timestamp count: {initial_count}")

    # Trigger cleanup by calling _log_once
    _log_once("trigger_cleanup_message")

    final_count = len(deps._log_timestamps)
    print(f"Final timestamp count: {final_count}")

    # Should have cleaned up old entries but kept recent ones
    assert final_count < initial_count, "Cleanup should have removed old entries"
    assert (
        "recent_message" in deps._log_timestamps
    ), "Recent entries should be preserved"
    print("✓ Log throttling cleanup test passed\n")


async def main():
    """Run all verification tests."""
    print("Running Copilot fixes verification...\n")

    test_role_validation()
    await test_cache_thread_safety()
    test_error_handling()
    test_log_throttling_cleanup()

    print("🎉 All Copilot fixes verified successfully!")


if __name__ == "__main__":
    asyncio.run(main())
