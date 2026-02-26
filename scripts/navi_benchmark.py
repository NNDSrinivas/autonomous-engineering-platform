#!/usr/bin/env python3
"""
NAVI benchmark harness.

Runs a set of pytest targets, measures duration, and writes a JSON scorecard.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_task(repo_root: Path, task: dict, default_timeout: int | None = None) -> dict:
    pytest_args = task.get("pytest_args", [])
    if not pytest_args:
        return {
            "id": task.get("id", "unknown"),
            "label": task.get("label", ""),
            "success": False,
            "error": "No pytest_args configured",
            "duration_seconds": 0.0,
            "returncode": 1,
        }

    cmd = ["python3", "-m", "pytest"] + pytest_args
    timeout_seconds = task.get("timeout_seconds", default_timeout)
    start = time.monotonic()
    timed_out = False
    error = None
    stdout_tail: list[str] = []
    stderr_tail: list[str] = []
    returncode = 1

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        duration = time.monotonic() - start
        returncode = proc.returncode
        stdout_tail = (proc.stdout or "").splitlines()[-20:]
        stderr_tail = (proc.stderr or "").splitlines()[-20:]
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        timed_out = True
        error = f"Timeout after {timeout_seconds}s"
        stdout_tail = (exc.stdout or "").splitlines()[-20:]
        stderr_tail = (exc.stderr or "").splitlines()[-20:]

    return {
        "id": task.get("id", "unknown"),
        "label": task.get("label", ""),
        "description": task.get("description", ""),
        "success": (returncode == 0) and not timed_out,
        "duration_seconds": round(duration, 2),
        "returncode": returncode,
        "cmd": " ".join(cmd),
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "timed_out": timed_out,
        "timeout_seconds": timeout_seconds,
        "error": error,
    }


def write_scorecard(report: dict, path: Path) -> None:
    lines = [
        "# NAVI Benchmark Scorecard",
        "",
        f"Generated: {report.get('generated_at', '')}",
        "",
        "## Summary",
        "",
        f"- Tasks: {report['summary']['passed'] + report['summary']['failed']}",
        f"- Passed: {report['summary']['passed']}",
        f"- Failed: {report['summary']['failed']}",
        f"- Total Duration (s): {report['summary']['total_duration_seconds']}",
        "",
        "## Results",
        "",
        "| Task | Label | Success | Timed Out | Duration (s) | Command |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for result in report.get("results", []):
        cmd = result.get("cmd", "")
        timed_out = result.get("timed_out", False)
        lines.append(
            f"| {result.get('id', '')} | {result.get('label', '')} | {result.get('success', False)} | {timed_out} | {result.get('duration_seconds', 0)} | `{cmd}` |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Durations are wall-clock time for each benchmark task.",
            "- Use this scorecard to track regressions/improvements over time.",
            "",
        ]
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config/navi_benchmark_tasks.json",
        help="Path to benchmark config JSON",
    )
    parser.add_argument(
        "--output",
        default="tmp/navi_benchmark_report.json",
        help="Path to write JSON report",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        default=[],
        help="Optional task ids to run (space-separated)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Default timeout in seconds per task (overridden by task config)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / args.config
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        return 1

    config = load_config(config_path)
    tasks = config.get("tasks", [])
    if args.only:
        task_set = set(args.only)
        tasks = [t for t in tasks if t.get("id") in task_set]

    if not tasks:
        print("No tasks to run.")
        return 1

    results = []
    for task in tasks:
        results.append(run_task(repo_root, task, default_timeout=args.timeout))

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "repo_root": str(repo_root),
        "task_count": len(results),
        "results": results,
        "summary": {
            "passed": sum(1 for r in results if r.get("success")),
            "failed": sum(1 for r in results if not r.get("success")),
            "total_duration_seconds": round(
                sum(r.get("duration_seconds", 0) for r in results), 2
            ),
        },
    }

    output_path = repo_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    scorecard_path = repo_root / "docs/NAVI_BENCHMARK_SCORECARD.md"
    write_scorecard(report, scorecard_path)

    print(json.dumps(report["summary"], indent=2))
    return 0 if report["summary"]["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
