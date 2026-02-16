import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.api import navi as navi_api
from backend.services.job_manager import JobManager


def _fake_user() -> SimpleNamespace:
    return SimpleNamespace(user_id="user-1", id="user-1", org_id="org-1")


async def _collect_sse_payloads(streaming_response) -> list[str]:
    payloads: list[str] = []
    async for chunk in streaming_response.body_iterator:
        text = chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
        for line in text.splitlines():
            if not line.startswith("data: "):
                continue
            payload = line[6:].strip()
            payloads.append(payload)
            if payload == "[DONE]":
                return payloads
    return payloads


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


@pytest.mark.asyncio
async def test_approve_uses_decision_field_for_consent_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager()
    manager._redis = None
    manager._redis_available = False

    record = await manager.create_job(
        payload={"message": "consent approval decision"},
        user_id="user-1",
        org_id="org-1",
    )
    await manager.set_status(
        record.job_id,
        status="paused_for_approval",
        phase="awaiting_consent",
        pending_approval={
            "type": "consent",
            "consent_id": "consent-123",
            "command": "rm -rf /tmp/data",
        },
    )

    captured: dict[str, str] = {}

    async def _fake_require_owned_job(job_id: str, user: object):
        return await manager.require_job(job_id)

    async def _fake_apply_consent_decision(**kwargs):
        captured["choice"] = kwargs["choice"]
        return {
            "success": True,
            "consent_id": kwargs["consent_id"],
            "choice": kwargs["choice"],
            "message": "ok",
        }

    monkeypatch.setattr(navi_api, "get_job_manager", lambda: manager, raising=True)
    monkeypatch.setattr(
        navi_api, "_require_owned_job", _fake_require_owned_job, raising=True
    )
    monkeypatch.setattr(
        navi_api, "_apply_consent_decision", _fake_apply_consent_decision, raising=True
    )

    response = await navi_api.approve_background_job_gate(
        record.job_id,
        navi_api.JobApprovalRequest(
            consent_id="consent-123",
            decision="deny",
        ),
        _fake_user(),
    )

    assert response["success"] is True
    assert captured["choice"] == "deny"


@pytest.mark.asyncio
async def test_job_terminal_event_sequence_is_stable_on_reattach(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = JobManager()
    manager._redis = None
    manager._redis_available = False

    record = await manager.create_job(
        payload={"message": "terminal sequence"},
        user_id="user-1",
        org_id="org-1",
    )
    await manager.append_event(
        record.job_id,
        {"type": "job_completed", "job_status": "completed"},
    )
    await manager.set_status(
        record.job_id,
        status="completed",
        phase="completed",
    )

    async def _fake_require_owned_job(job_id: str, user: object):
        return await manager.require_job(job_id)

    monkeypatch.setattr(navi_api, "get_job_manager", lambda: manager, raising=True)
    monkeypatch.setattr(
        navi_api, "_require_owned_job", _fake_require_owned_job, raising=True
    )

    first = await navi_api.stream_background_job_events(
        record.job_id,
        after_sequence=0,
        user=_fake_user(),
    )
    first_payloads = await _collect_sse_payloads(first)
    first_events = [json.loads(p) for p in first_payloads if p != "[DONE]"]
    terminal_first = [e for e in first_events if e.get("type") == "job_terminal"]
    assert len(terminal_first) == 1
    max_persisted_sequence = max(
        int(e.get("sequence", 0))
        for e in first_events
        if e.get("type") != "job_terminal"
    )
    terminal_sequence = int(terminal_first[0].get("sequence", 0))
    assert terminal_sequence == max_persisted_sequence

    second = await navi_api.stream_background_job_events(
        record.job_id,
        after_sequence=terminal_sequence,
        user=_fake_user(),
    )
    second_payloads = await _collect_sse_payloads(second)
    second_events = [json.loads(p) for p in second_payloads if p != "[DONE]"]
    assert all(event.get("type") != "job_terminal" for event in second_events)
