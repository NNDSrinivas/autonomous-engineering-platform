import os
import asyncio
from uuid import uuid4

import pytest
import redis.asyncio as redis

from backend.services.job_manager import JobManager


def _redis_required_in_ci() -> bool:
    return os.getenv("REQUIRE_REDIS_FOR_LOCK_TESTS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _connect_test_redis() -> redis.Redis:
    url = (
        os.getenv("NAVI_TEST_REDIS_URL")
        or os.getenv("REDIS_URL")
        or "redis://127.0.0.1:6379/15"
    )
    client = redis.from_url(url, encoding="utf-8", decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:
        await client.aclose()
        if os.getenv("CI") and _redis_required_in_ci():
            pytest.fail(
                f"Redis required in CI for lock integration test ({url}): {exc}"
            )
        pytest.skip(f"Redis unreachable for integration lock test ({url}): {exc}")
    return client


async def _cleanup_namespace(client: redis.Redis, namespace: str) -> None:
    cursor = 0
    pattern = f"{namespace}:*"
    while True:
        cursor, keys = await client.scan(cursor=cursor, match=pattern, count=100)
        if keys:
            await client.delete(*keys)
        if cursor == 0:
            break


@pytest.mark.asyncio
async def test_runner_lock_lua_with_real_redis() -> None:
    client = await _connect_test_redis()
    namespace = f"navi:test:jobs:{uuid4().hex}"

    manager_a = JobManager()
    manager_b = JobManager()
    for manager in (manager_a, manager_b):
        manager._redis = client
        manager._redis_available = True
        manager._namespace = namespace

    job_id = "job-lock-redis"
    token_a = "redis-token-a"
    token_b = "redis-token-b"

    try:
        assert await manager_a.acquire_runner_lock(job_id, token_a, ttl_seconds=30)
        # Simulate a second worker trying to start the same job.
        assert not await manager_b.acquire_runner_lock(job_id, token_b, ttl_seconds=30)

        # Wrong token cannot renew/release.
        assert not await manager_b.renew_runner_lock(job_id, token_b, ttl_seconds=30)
        await manager_b.release_runner_lock(job_id, token_b)
        assert await manager_a.has_active_runner(job_id)

        # Correct owner can renew.
        assert await manager_a.renew_runner_lock(job_id, token_a, ttl_seconds=30)

        # Force short expiry and verify lock can be reacquired after expiration.
        await client.expire(manager_a._lock_key(job_id), 1)
        await asyncio.sleep(1.2)
        assert await manager_b.acquire_runner_lock(job_id, token_b, ttl_seconds=30)

        # Old token can no longer renew/release.
        assert not await manager_a.renew_runner_lock(job_id, token_a, ttl_seconds=30)
        await manager_a.release_runner_lock(job_id, token_a)
        assert await manager_b.has_active_runner(job_id)

        # Current owner releases lock.
        await manager_b.release_runner_lock(job_id, token_b)
        assert not await manager_a.has_active_runner(job_id)
    finally:
        await _cleanup_namespace(client, namespace)
        await client.aclose()
