from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.api import navi as navi_api
from backend.services.job_manager import JobManager


def _fake_user() -> SimpleNamespace:
    return SimpleNamespace(user_id="user-1", id="user-1", org_id="org-1")


@pytest.mark.asyncio
async def test_approve_accepts_nested_human_gate_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager()
    manager._redis = None
    manager._redis_available = False

    record = await manager.create_job(
        payload={"message": "approval test"},
        user_id="user-1",
        org_id="org-1",
    )
    await manager.set_status(
        record.job_id,
        status="paused_for_approval",
        phase="awaiting_human_gate",
        pending_approval={
            "type": "human_gate",
            # No top-level gate_id on purpose; only nested.
            "gate": {"id": "gate-abc-123", "title": "Approve"},
        },
    )

    async def _fake_require_owned_job(job_id: str, user: object):
        return await manager.require_job(job_id)

    async def _fake_start_job_runner(job_id: str):
        return {"started": False, "reason": "already_running"}

    monkeypatch.setattr(navi_api, "get_job_manager", lambda: manager, raising=True)
    monkeypatch.setattr(
        navi_api, "_require_owned_job", _fake_require_owned_job, raising=True
    )
    monkeypatch.setattr(
        navi_api, "_start_job_runner", _fake_start_job_runner, raising=True
    )

    response = await navi_api.approve_background_job_gate(
        record.job_id,
        navi_api.JobApprovalRequest(gate_id="gate-abc-123", decision="approved"),
        _fake_user(),
    )

    assert response["success"] is True
    assert response["started"] is False
    assert response["message"] == "Job already running"


@pytest.mark.asyncio
async def test_approve_surfaces_resume_start_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager()
    manager._redis = None
    manager._redis_available = False

    record = await manager.create_job(
        payload={"message": "approval failure test"},
        user_id="user-1",
        org_id="org-1",
    )
    await manager.set_status(
        record.job_id,
        status="paused_for_approval",
        phase="awaiting_human_gate",
        pending_approval={
            "type": "human_gate",
            "gate": {"id": "gate-lock-001", "title": "Approve"},
        },
    )

    async def _fake_require_owned_job(job_id: str, user: object):
        return await manager.require_job(job_id)

    async def _fake_start_job_runner(job_id: str):
        return {"started": False, "reason": "distributed_lock_unavailable"}

    monkeypatch.setattr(navi_api, "get_job_manager", lambda: manager, raising=True)
    monkeypatch.setattr(
        navi_api, "_require_owned_job", _fake_require_owned_job, raising=True
    )
    monkeypatch.setattr(
        navi_api, "_start_job_runner", _fake_start_job_runner, raising=True
    )

    with pytest.raises(HTTPException) as exc_info:
        await navi_api.approve_background_job_gate(
            record.job_id,
            navi_api.JobApprovalRequest(gate_id="gate-lock-001", decision="approved"),
            _fake_user(),
        )

    assert exc_info.value.status_code == 503
    assert "Distributed runner lock unavailable" in str(exc_info.value.detail)

    current = await manager.require_job(record.job_id)
    assert current.status == "queued"
