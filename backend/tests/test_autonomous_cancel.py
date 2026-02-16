import asyncio
import os
import time
from pathlib import Path

import pytest

from backend.services.autonomous_agent import AutonomousAgent, TaskContext


@pytest.fixture
def patched_project_detection(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "backend.services.autonomous_agent.ProjectAnalyzer.detect_project_type",
        lambda _workspace_path: ("generic", "generic", []),
    )


@pytest.mark.asyncio
async def test_terminate_process_tree_kills_process_group(
    tmp_path: Path, patched_project_detection
) -> None:
    if os.name == "nt":
        pytest.skip("process-group cancel test targets POSIX behavior")

    agent = AutonomousAgent(
        workspace_path=str(tmp_path),
        api_key="test",
        provider="openai",
        model="gpt-4o",
    )
    process = await asyncio.create_subprocess_shell(
        "sleep 60 & sleep 60 & wait",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(tmp_path),
        executable="/bin/bash",
        start_new_session=True,
    )
    assert process.pid is not None
    pgid = os.getpgid(process.pid)

    started_at = time.monotonic()
    await agent._terminate_process_tree(process, reason="unit_test")
    elapsed = time.monotonic() - started_at

    assert elapsed < 8, "process-group termination should be quick"
    assert process.returncode is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(pgid, 0)


@pytest.mark.asyncio
async def test_run_command_honors_cancel_check(
    tmp_path: Path, patched_project_detection
) -> None:
    cancel_event = asyncio.Event()

    async def _cancel_check() -> bool:
        return cancel_event.is_set()

    agent = AutonomousAgent(
        workspace_path=str(tmp_path),
        api_key="test",
        provider="openai",
        model="gpt-4o",
        cancel_check=_cancel_check,
    )
    context = TaskContext(
        task_id="task-cancel",
        original_request="run a long command",
        workspace_path=str(tmp_path),
    )

    async def _trigger_cancel():
        await asyncio.sleep(0.8)
        cancel_event.set()

    trigger = asyncio.create_task(_trigger_cancel())
    started_at = time.monotonic()
    result = await agent._execute_tool(
        "run_command",
        {"command": 'bash -lc "sleep 60 & sleep 60 & wait"', "timeout_seconds": 300},
        context,
    )
    elapsed = time.monotonic() - started_at
    trigger.cancel()

    assert elapsed < 8, "cancel should stop long command quickly"
    assert result.get("success") is False
    assert result.get("exit_code") == -2
    combined = f"{result.get('stderr', '')} {result.get('error', '')}".lower()
    assert "cancel" in combined
