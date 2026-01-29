#!/usr/bin/env python3
"""Lightweight deterministic E2E smoke runner for NAVI."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request

BASE_URL = os.getenv("NAVI_BASE_URL", "http://localhost:8787")
TEST_CMD = [sys.executable, "tests/test_navi_true_e2e.py"]
HEALTH_URL = f"{BASE_URL}/health"


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

    start = time.time()
    result = subprocess.run(TEST_CMD, text=True)
    elapsed = time.time() - start

    if result.returncode == 0:
        print(f"✅ E2E smoke passed in {elapsed:.1f}s")
        return 0

    print(f"❌ E2E smoke failed in {elapsed:.1f}s (exit {result.returncode})")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
