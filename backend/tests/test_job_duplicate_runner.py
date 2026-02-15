import asyncio
from typing import Any, Dict

import httpx
import pytest

from backend.api.main import app
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

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        try:
            create_resp = await client.post(
                "/api/jobs",
                json={
                    "message": "duplicate runner harness",
                    "auto_start": False,
                    "metadata": {"test": True},
                },
            )
            assert create_resp.status_code in (200, 201), create_resp.text
            create_body = create_resp.json()
            assert create_body.get("success") is True, create_body
            job = create_body.get("job", {})
            job_id = job.get("job_id")
            assert job_id, create_body

            async def _start() -> tuple[int, Dict[str, Any]]:
                resp = await client.post(f"/api/jobs/{job_id}/start")
                return resp.status_code, resp.json()

            first, second = await asyncio.gather(_start(), _start())
            for status_code, body in (first, second):
                assert status_code == 200, body
                assert body.get("success") is True, body

            started_flags = [
                bool(first[1].get("started")),
                bool(second[1].get("started")),
            ]
            assert started_flags.count(True) == 1, {
                "first": first[1],
                "second": second[1],
            }
            non_started = first[1] if not first[1].get("started") else second[1]
            assert non_started.get("started") is False, non_started
            assert non_started.get("message") == "Job already running", non_started

            await asyncio.wait_for(run_started.wait(), timeout=3)

            third_resp = await client.post(f"/api/jobs/{job_id}/start")
            assert third_resp.status_code == 200, third_resp.text
            third_body = third_resp.json()
            assert third_body.get("success") is True, third_body
            assert third_body.get("started") is False, third_body

            events = await manager.get_events_after(job_id, 0)
            job_started_count = sum(
                1 for event in events if event.get("type") == "job_started"
            )
            assert job_started_count == 1, [event.get("type") for event in events]

            allow_complete.set()
            for _ in range(20):
                job_resp = await client.get(f"/api/jobs/{job_id}")
                assert job_resp.status_code == 200, job_resp.text
                job_body = job_resp.json()
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
