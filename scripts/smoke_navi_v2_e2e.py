#!/usr/bin/env python3
"""
E2E smoke test for NAVI V2 plan -> approve -> apply.
Uses TestClient with mocked NaviBrain to avoid real LLM calls.
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Disable rate limiting for the smoke gate to allow repeated runs in CI/dev.
os.environ.setdefault("RATE_LIMITING_ENABLED", "false")
# Force test env to avoid prod-only middleware and noisy audit DB expectations.
os.environ.setdefault("APP_ENV", "test")
# Allow auth bypass for local E2E smoke runs.
os.environ.setdefault("ALLOW_DEV_AUTH_BYPASS", "true")
# Disable in-memory OAuth device store warnings for smoke gate.
os.environ.setdefault("OAUTH_DEVICE_USE_IN_MEMORY_STORE", "false")

from backend.api.main import app


def _should_retry(status_code: int) -> bool:
    return status_code in (500, 502, 503, 504)


def _post_with_retry(
    client: TestClient,
    url: str,
    json: dict,
    label: str,
    max_retries: int,
    retry_delay: float,
):
    for attempt in range(1, max_retries + 1):
        resp = client.post(url, json=json)
        if resp.status_code == 200 or not _should_retry(resp.status_code):
            return resp
        print(
            f"{label} attempt {attempt} failed with {resp.status_code}; retrying...",
            flush=True,
        )
        time.sleep(retry_delay)
    return resp


def run_once(run_id: int, *, max_retries: int, retry_delay: float) -> int:
    async def fake_execute_plan(plan_id, approved_action_indices):
        yield {"type": "action_start", "index": 0}
        yield {"type": "action_complete", "index": 0, "success": True}
        yield {"type": "plan_complete"}

    print(f"Starting TestClient (run {run_id})...", flush=True)
    with TestClient(app) as client:
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            file_path = "hello.txt"
            file_content = "hello from navi"
            python_cmd = f'"{sys.executable}" -c \'print("ok")\''

            actions = [
                {
                    "type": "createFile",
                    "path": file_path,
                    "content": file_content,
                    "risk": "low",
                },
                {
                    "type": "runCommand",
                    "command": python_cmd,
                    "risk": "low",
                },
            ]

            fake_response = SimpleNamespace(
                plan_id="plan-e2e-123",
                message="plan created",
                requires_approval=True,
                actions_with_risk=actions,
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

                print("Calling /api/navi/v2/plan...", flush=True)
                resp = _post_with_retry(
                    client,
                    "/api/navi/v2/plan",
                    {
                        "message": "create a file",
                        "workspace": str(workspace),
                        "llm_provider": "ollama",
                    },
                    "Plan",
                    max_retries,
                    retry_delay,
                )
                if resp.status_code != 200:
                    print(f"Plan failed: {resp.status_code} {resp.text}")
                    return 1

                plan_id = resp.json().get("plan_id")
                if not plan_id:
                    print("Plan response missing plan_id")
                    return 1

                print("Calling /api/navi/v2/plan/{plan_id}/approve...", flush=True)
                approve = _post_with_retry(
                    client,
                    f"/api/navi/v2/plan/{plan_id}/approve",
                    {"approved_action_indices": [0]},
                    "Approve",
                    max_retries,
                    retry_delay,
                )
                if approve.status_code != 200:
                    print(f"Approve failed: {approve.status_code} {approve.text}")
                    return 1

                payload = approve.json()
                if payload.get("status") != "completed":
                    print(f"Approve did not complete: {payload}")
                    return 1

            file_edits = [
                {
                    "path": file_path,
                    "content": file_content,
                    "operation": "create",
                }
            ]

            print("Calling /api/navi/apply...", flush=True)
            apply_resp = _post_with_retry(
                client,
                "/api/navi/apply",
                {
                    "workspace": str(workspace),
                    "file_edits": file_edits,
                    "commands_run": [python_cmd],
                    "allow_commands": True,
                },
                "Apply",
                max_retries,
                retry_delay,
            )

            if apply_resp.status_code != 200:
                print(f"Apply failed: {apply_resp.status_code} {apply_resp.text}")
                return 1

            result = apply_resp.json()
            if not result.get("success"):
                print(f"Apply returned failure: {result}")
                return 1

            created_files = result.get("files_created", [])
            if not created_files:
                print(f"Apply did not create files: {result}")
                return 1

            created_path = workspace / file_path
            if not created_path.exists():
                print("Expected file was not created")
                return 1

            if created_path.read_text() != file_content:
                print("File content mismatch after apply")
                return 1

            print("Verifying command execution...", flush=True)
            verify_cmd = [sys.executable, "-c", "print('ok')"]
            verify = subprocess.run(
                verify_cmd,
                cwd=str(workspace),
                capture_output=True,
                text=True,
            )
            if verify.returncode != 0:
                print(f"Verify command failed: {verify.stderr.strip()}")
                return 1
            if "ok" not in verify.stdout:
                print(f"Verify command output missing: {verify.stdout.strip()}")
                return 1

            print("Calling /api/navi/apply for rollback...", flush=True)
            rollback_resp = _post_with_retry(
                client,
                "/api/navi/apply",
                {
                    "workspace": str(workspace),
                    "file_edits": [
                        {"path": file_path, "operation": "delete"},
                    ],
                    "allow_commands": False,
                },
                "Rollback",
                max_retries,
                retry_delay,
            )
            if rollback_resp.status_code != 200:
                print(
                    f"Rollback apply failed: {rollback_resp.status_code} {rollback_resp.text}"
                )
                return 1
            if created_path.exists():
                print("Rollback did not remove created file")
                return 1

    print(f"✅ NAVI V2 plan -> approve -> apply e2e smoke test passed (run {run_id}).")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NAVI V2 E2E smoke test")
    parser.add_argument(
        "--runs", type=int, default=1, help="Number of consecutive runs"
    )
    parser.add_argument(
        "--max-retries", type=int, default=2, help="Max retries per step"
    )
    parser.add_argument(
        "--retry-delay", type=float, default=0.25, help="Delay between retries"
    )
    args = parser.parse_args()

    total_runs = max(1, args.runs)
    for i in range(1, total_runs + 1):
        result = run_once(i, max_retries=args.max_retries, retry_delay=args.retry_delay)
        if result != 0:
            raise SystemExit(result)
    raise SystemExit(0)
