import pytest

from backend.services.job_manager import JobManager


class _FakeRedis:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        if nx and key in self._data:
            return False
        self._data[key] = str(value)
        return True

    async def get(self, key: str):
        return self._data.get(key)

    async def eval(self, script: str, numkeys: int, key: str, *args):
        if numkeys != 1:
            raise AssertionError("Fake redis only supports one key in eval")
        if "DEL" in script:
            token = str(args[0])
            if self._data.get(key) == token:
                del self._data[key]
                return 1
            return 0
        if "PEXPIRE" in script:
            token = str(args[0])
            if self._data.get(key) == token:
                return 1
            return 0
        raise AssertionError("Unsupported lua script in fake redis")

    async def expire(self, key: str, seconds: int):
        return 1 if key in self._data else 0

    async def delete(self, key: str):
        return 1 if self._data.pop(key, None) is not None else 0


@pytest.mark.asyncio
async def test_runner_lock_renew_and_release_require_owner_token() -> None:
    manager = JobManager()
    manager._redis = _FakeRedis()
    manager._redis_available = True

    job_id = "job-lock-1"
    owner_a = "token-a"
    owner_b = "token-b"

    acquired = await manager.acquire_runner_lock(job_id, owner_a, ttl_seconds=30)
    assert acquired is True
    assert await manager.has_active_runner(job_id) is True

    renewed_by_other = await manager.renew_runner_lock(job_id, owner_b, ttl_seconds=30)
    assert renewed_by_other is False
    assert await manager.has_active_runner(job_id) is True

    await manager.release_runner_lock(job_id, owner_b)
    assert await manager.has_active_runner(job_id) is True

    renewed_by_owner = await manager.renew_runner_lock(job_id, owner_a, ttl_seconds=30)
    assert renewed_by_owner is True

    await manager.release_runner_lock(job_id, owner_a)
    assert await manager.has_active_runner(job_id) is False

    renewed_after_release = await manager.renew_runner_lock(job_id, owner_a, ttl_seconds=30)
    assert renewed_after_release is False


@pytest.mark.asyncio
async def test_create_job_requires_user_id() -> None:
    manager = JobManager()
    with pytest.raises(ValueError, match="user_id is required"):
        await manager.create_job(payload={"message": "x"}, user_id="", org_id="org-1")
