#!/usr/bin/env python3
"""
Smoke test for NAVI V2 plan/approve flow without hitting real LLMs.

Usage:
  python scripts/smoke_navi_v2_plan.py
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.api.main import app


def main() -> int:
    client = TestClient(app)

    async def fake_execute_plan(plan_id, approved_action_indices):
        yield {"type": "action_start", "index": 0}
        yield {"type": "action_complete", "index": 0, "success": True}
        yield {"type": "plan_complete"}

    fake_response = SimpleNamespace(
        plan_id="plan-smoke-123",
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
        if resp.status_code != 200:
            print(f"Plan failed: {resp.status_code} {resp.text}")
            return 1

        plan_id = resp.json().get("plan_id")
        if not plan_id:
            print("Plan response missing plan_id")
            return 1

        approve = client.post(
            f"/api/navi/v2/plan/{plan_id}/approve",
            json={"approved_action_indices": [0]},
        )
        if approve.status_code != 200:
            print(f"Approve failed: {approve.status_code} {approve.text}")
            return 1

        payload = approve.json()
        if payload.get("status") != "completed":
            print(f"Approve did not complete: {payload}")
            return 1

    print("✅ NAVI V2 plan/approve smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
