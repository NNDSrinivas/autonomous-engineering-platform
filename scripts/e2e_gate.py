#!/usr/bin/env python3
"""Deterministic E2E gate runner: N consecutive clean runs."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request

BASE_URL = os.getenv("NAVI_BASE_URL", "http://localhost:8787")
HEALTH_URL = f"{BASE_URL}/health"
TEST_CMD = [sys.executable, "tests/test_navi_true_e2e.py"]
RUNS = int(os.getenv("E2E_GATE_RUNS", "20"))
SLEEP_BETWEEN = float(os.getenv("E2E_GATE_SLEEP_SEC", "1"))


def _check_health(timeout_sec: int = 5) -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout_sec) as resp:
            return resp.status == 200
    except Exception:
        return False


def main() -> int:
    if not _check_health():
        print(f"❌ NAVI backend not reachable at {HEALTH_URL}")
        return 2

    failures = 0
    start = time.time()
    for i in range(1, RUNS + 1):
        print(f"\n=== E2E Gate Run {i}/{RUNS} ===")
        result = subprocess.run(TEST_CMD, text=True)
        if result.returncode != 0:
            failures += 1
            print(f"❌ Run {i} failed (exit {result.returncode})")
            break
        print(f"✅ Run {i} passed")
        if i < RUNS:
            time.sleep(SLEEP_BETWEEN)

    elapsed = time.time() - start
    if failures:
        print(f"\n❌ E2E gate failed after {elapsed:.1f}s")
        return 1

    print(f"\n✅ E2E gate passed ({RUNS}/{RUNS}) in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
