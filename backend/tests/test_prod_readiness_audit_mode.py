import json

import pytest
from fastapi.testclient import TestClient

from backend.agent.intent_classifier import classify_intent
from backend.agent.intent_schema import IntentKind
from backend.api.main import app
from backend.services.autonomous_agent import AutonomousAgent, TaskContext


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_prod_readiness_intent_classifies_to_audit_kind() -> None:
    intent = classify_intent(
        "is this project ready for prod deployment and go-live security review?"
    )
    assert intent.kind == IntentKind.PROD_READINESS_AUDIT


def test_chat_endpoint_returns_deterministic_prod_readiness_plan(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/navi/chat",
        json={
            "message": "Is this project production ready and safe to go live?",
            "mode": "chat-only",
            "workspace_root": "/tmp/demo-repo",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "PROD_READINESS_AUDIT (Deterministic Plan)" in data.get("content", "")
    assert "run these checks now" in data.get("content", "").lower()
    state = data.get("state") or {}
    assert state.get("intent") == "prod_readiness_audit"
    assert state.get("mode") == "plan_only"


def test_stream_v2_short_circuits_to_prod_readiness_plan(client: TestClient) -> None:
    response = client.post(
        "/api/navi/chat/stream/v2",
        json={
            "message": "Is this project ready for prod deployment and go live?",
            "workspace_root": "/tmp/demo-repo",
            "mode": "chat-only",
        },
    )
    assert response.status_code == 200, response.text
    body = response.text
    assert '"kind": "prod_readiness_audit"' in body
    assert "PROD_READINESS_AUDIT (Deterministic Plan)" in body
    assert "data: [DONE]" in body


@pytest.mark.asyncio
async def test_decomposition_json_parse_failure_emits_nonfatal_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    class FakeDecomposer:
        def __init__(self, *args, **kwargs):
            pass

        async def decompose_goal(self, *args, **kwargs):
            raise json.JSONDecodeError("invalid", "not-json", 0)

    monkeypatch.setattr(
        "backend.services.autonomous_agent.TaskDecomposer",
        FakeDecomposer,
        raising=True,
    )

    agent = AutonomousAgent(
        workspace_path=str(tmp_path),
        api_key="test",
        provider="openai",
        model="gpt-4o-mini",
    )
    context = TaskContext(
        task_id="task-json-fallback",
        original_request="build full app",
        workspace_path=str(tmp_path),
    )

    events = [
        event
        async for event in agent._execute_with_decomposition_generator(
            "build full app", context
        )
    ]
    event_types = [str(evt.get("type")) for evt in events]
    assert "decomposition_start" in event_types
    assert "decomposition_failed_fallback" in event_types
