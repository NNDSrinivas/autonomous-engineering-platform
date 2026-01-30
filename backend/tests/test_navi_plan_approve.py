from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.routers import navi as navi_router


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_plan_storage():
    navi_router._PLAN_BRAINS.clear()
    navi_router._PLAN_CREATED_AT.clear()
    yield
    navi_router._PLAN_BRAINS.clear()
    navi_router._PLAN_CREATED_AT.clear()


def test_plan_and_approve_executes_actions(client):
    async def fake_execute_plan(plan_id, approved_action_indices):
        yield {"type": "action_start", "index": 0}
        yield {"type": "action_complete", "index": 0, "success": True}
        yield {"type": "plan_complete"}

    fake_response = SimpleNamespace(
        plan_id="plan-test-123",
        message="plan created",
        requires_approval=True,
        actions_with_risk=[{"type": "createFile", "path": "x.txt", "content": "hi"}],
        thinking_steps=[],
        files_read=[],
        project_type=None,
        framework=None,
    )

    with patch("backend.services.navi_brain.NaviBrain") as mock_brain_cls:
        brain = mock_brain_cls.return_value
        brain.plan = AsyncMock(return_value=fake_response)
        brain.execute_plan = fake_execute_plan
        brain.get_plan.return_value = SimpleNamespace()
        brain.close = AsyncMock()

        resp = client.post(
            "/api/navi/v2/plan",
            json={
                "message": "create a file",
                "workspace": "/tmp",
                "llm_provider": "ollama",
            },
        )
        assert resp.status_code == 200
        plan_id = resp.json()["plan_id"]
        assert plan_id == "plan-test-123"

        approve = client.post(
            f"/api/navi/v2/plan/{plan_id}/approve",
            json={"approved_action_indices": [0]},
        )
        assert approve.status_code == 200
        payload = approve.json()
        assert payload["status"] == "completed"
        assert any(u.get("type") == "plan_complete" for u in payload["updates"])
