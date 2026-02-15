import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple
from uuid import uuid4

import httpx
import pytest
import redis.asyncio as redis


def _redis_required_in_ci() -> bool:
    return os.getenv("REQUIRE_REDIS_FOR_LOCK_TESTS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _repo_root() -> Path:
    # backend/tests -> backend -> repo root
    return Path(__file__).resolve().parents[2]


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _connect_test_redis() -> redis.Redis:
    url = (
        os.getenv("NAVI_TEST_REDIS_URL")
        or os.getenv("REDIS_URL")
        or "redis://127.0.0.1:6379/15"
    )
    client = redis.from_url(url, encoding="utf-8", decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:
        await client.aclose()
        if os.getenv("CI") and _redis_required_in_ci():
            pytest.fail(
                f"Redis required in CI for 2-worker lock harness ({url}): {exc}"
            )
        pytest.skip(f"Redis unreachable for 2-worker lock harness ({url}): {exc}")
    return client


async def _cleanup_namespace(client: redis.Redis, namespace: str) -> None:
    cursor = 0
    pattern = f"{namespace}:*"
    while True:
        cursor, keys = await client.scan(cursor=cursor, match=pattern, count=250)
        if keys:
            await client.delete(*keys)
        if cursor == 0:
            break


def _tail_file(path: str, max_chars: int = 8000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            content = fh.read()
            if len(content) > max_chars:
                return content[-max_chars:]
            return content
    except Exception:
        return ""


async def _wait_http_ready(
    base_url: str,
    *,
    proc: subprocess.Popen,
    log_path: str,
    timeout_seconds: float = 90.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    readiness_paths = ("/health", "/health-fast", "/ready")
    async with httpx.AsyncClient(timeout=3.0) as client:
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                logs = _tail_file(log_path)
                raise RuntimeError(
                    f"uvicorn exited early with code {proc.returncode}. recent logs:\n{logs}"
                )

            for path in readiness_paths:
                try:
                    response = await client.get(f"{base_url}{path}")
                    if response.status_code == 200:
                        return
                except Exception:
                    continue
            await asyncio.sleep(0.25)

    logs = _tail_file(log_path)
    raise TimeoutError(
        f"Timed out waiting for server readiness at {base_url} "
        f"(checked: {', '.join(readiness_paths)}). recent logs:\n{logs}"
    )


async def _wait_non_queued_status(
    base_url: str, job_id: str, timeout_seconds: float = 10.0
) -> str:
    deadline = time.monotonic() + timeout_seconds
    async with httpx.AsyncClient(timeout=5.0) as client:
        while time.monotonic() < deadline:
            response = await client.get(f"{base_url}/api/jobs/{job_id}")
            if response.status_code == 200:
                payload = response.json()
                status = str((payload.get("job") or {}).get("status") or "")
                if status and status != "queued":
                    return status
            await asyncio.sleep(0.25)
    raise TimeoutError("Job remained queued too long after concurrent starts")


async def _read_job_events_from_redis(
    client: redis.Redis,
    namespace: str,
    job_id: str,
) -> List[Dict[str, Any]]:
    key = f"{namespace}:{job_id}:events"
    rows = await client.lrange(key, 0, -1)
    events: List[Dict[str, Any]] = []
    for row in rows:
        try:
            parsed = json.loads(row)
        except Exception:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def _terminate_server_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.name == "nt", reason="uvicorn process-group control test targets POSIX"
)
async def test_two_worker_uvicorn_duplicate_runner_lock() -> None:
    redis_client = await _connect_test_redis()
    namespace = f"navi:test:workers2:{uuid4().hex}"
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["JWT_ENABLED"] = "false"
    env["NAVI_JOB_NAMESPACE"] = namespace
    env["AEP_ALLOW_DISTRIBUTED_DEGRADE"] = "false"
    # Use local Redis directly for locking semantics in this harness.
    env.setdefault("REDIS_URL", "redis://127.0.0.1:6379/15")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--workers",
        "2",
        "--log-level",
        "warning",
    ]
    with tempfile.NamedTemporaryFile(
        mode="w+",
        prefix="uvicorn-two-workers-",
        suffix=".log",
        delete=False,
    ) as log_file:
        log_path = log_file.name

    log_handle = open(log_path, "a", encoding="utf-8")
    proc = subprocess.Popen(
        cmd,
        cwd=str(_repo_root()),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    try:
        await _wait_http_ready(base_url, proc=proc, log_path=log_path)
        async with httpx.AsyncClient(timeout=20.0) as client:
            create_resp = await client.post(
                f"{base_url}/api/jobs",
                json={
                    "message": "two worker duplicate-runner race harness",
                    "auto_start": False,
                    "metadata": {"test": "two-workers"},
                },
            )
            assert create_resp.status_code in (200, 201), create_resp.text
            create_body = create_resp.json()
            assert create_body.get("success") is True, create_body
            job_id = (create_body.get("job") or {}).get("job_id")
            assert job_id, create_body

            async def _start() -> Tuple[int, Dict[str, Any]]:
                response = await client.post(f"{base_url}/api/jobs/{job_id}/start")
                return response.status_code, response.json()

            first, second = await asyncio.gather(_start(), _start())
            assert first[0] == 200, first
            assert second[0] == 200, second
            assert first[1].get("success") is True, first
            assert second[1].get("success") is True, second

            started_count = [
                bool(first[1].get("started")),
                bool(second[1].get("started")),
            ].count(True)
            assert started_count == 1, {"first": first[1], "second": second[1]}
            non_started = first[1] if not first[1].get("started") else second[1]
            assert non_started.get("started") is False, non_started
            assert non_started.get("message") == "Job already running", non_started

            third_resp = await client.post(f"{base_url}/api/jobs/{job_id}/start")
            assert third_resp.status_code == 200, third_resp.text
            third_body = third_resp.json()
            assert third_body.get("success") is True, third_body
            assert third_body.get("started") is False, third_body

            status = await _wait_non_queued_status(base_url, job_id)
            assert status in {
                "running",
                "paused_for_approval",
                "failed",
                "completed",
                "canceled",
            }

            # Allow event persistence to settle and verify only one job_started emission.
            job_started_count = 0
            for _ in range(20):
                events = await _read_job_events_from_redis(
                    redis_client, namespace, job_id
                )
                job_started_count = sum(
                    1 for event in events if str(event.get("type")) == "job_started"
                )
                if job_started_count >= 1:
                    break
                await asyncio.sleep(0.25)
            assert job_started_count == 1, {"job_started_count": job_started_count}

            # Best effort cleanup if still running.
            await client.post(f"{base_url}/api/jobs/{job_id}/cancel")
    finally:
        try:
            log_handle.close()
        except Exception:
            pass
        _terminate_server_process(proc)
        await _cleanup_namespace(redis_client, namespace)
        await redis_client.aclose()
        try:
            os.unlink(log_path)
        except OSError:
            pass
