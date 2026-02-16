import asyncio
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from backend.api import navi as navi_api
from backend.services.job_manager import get_job_manager


@pytest.mark.asyncio
async def test_duplicate_runner_prevention_concurrent_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_started = asyncio.Event()
    allow_complete = asyncio.Event()
    manager = get_job_manager()
    original_redis = manager._redis
    original_redis_available = manager._redis_available
    manager._redis = None
    manager._redis_available = False

    user = SimpleNamespace(user_id="user-1", id="user-1", org_id="org-1")

    async def _fake_run_autonomous_job(job_id: str) -> None:
        await manager.append_event(
            job_id,
            {"type": "job_started", "message": "Background execution started"},
        )
        run_started.set()
        await allow_complete.wait()
        await manager.set_status(job_id, status="completed", phase="completed")
        await manager.append_event(
            job_id,
            {"type": "job_completed", "message": "Background job completed"},
        )

    monkeypatch.setattr(navi_api, "_run_autonomous_job", _fake_run_autonomous_job)

    try:
        create_body = await navi_api.create_background_job(
            navi_api.JobCreateRequest(
                message="duplicate runner harness",
                auto_start=False,
                metadata={"test": True},
            ),
            user=user,
        )
        assert create_body.get("success") is True, create_body
        job = create_body.get("job", {})
        job_id = job.get("job_id")
        assert job_id, create_body

        async def _start() -> Dict[str, Any]:
            return await navi_api.start_background_job(job_id, user=user)

        first, second = await asyncio.gather(_start(), _start())
        for body in (first, second):
            assert body.get("success") is True, body

        started_flags = [
            bool(first.get("started")),
            bool(second.get("started")),
        ]
        assert started_flags.count(True) == 1, {
            "first": first,
            "second": second,
        }
        non_started = first if not first.get("started") else second
        assert non_started.get("started") is False, non_started
        assert non_started.get("message") == "Job already running", non_started

        await asyncio.wait_for(run_started.wait(), timeout=3)

        third_body = await navi_api.start_background_job(job_id, user=user)
        assert third_body.get("success") is True, third_body
        assert third_body.get("started") is False, third_body

        events = await manager.get_events_after(job_id, 0)
        job_started_count = sum(
            1 for event in events if event.get("type") == "job_started"
        )
        assert job_started_count == 1, [event.get("type") for event in events]

        allow_complete.set()
        for _ in range(20):
            job_body = await navi_api.get_background_job(job_id, user=user)
            status = (job_body.get("job") or {}).get("status")
            if status in {"completed", "failed", "canceled"}:
                break
            await asyncio.sleep(0.1)
        else:
            pytest.fail("Job did not reach a terminal state in time")
    finally:
        allow_complete.set()
        manager._redis = original_redis
        manager._redis_available = original_redis_available
