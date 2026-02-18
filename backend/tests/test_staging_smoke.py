"""
Staging smoke tests.

Verifies that the live staging environment at https://staging.navralabs.com
is healthy and responding correctly.

Usage:
    STAGING_URL=https://staging.navralabs.com pytest backend/tests/test_staging_smoke.py -q

These tests are automatically skipped when STAGING_URL is not set, so they
never interfere with local development or the regular unit-test suite.
"""

import os

import pytest
import requests

STAGING_URL = os.getenv("STAGING_URL", "").rstrip("/")

pytestmark = pytest.mark.skipif(
    not STAGING_URL,
    reason="STAGING_URL not set — skipping staging smoke tests",
)


def test_health_live():
    """Backend liveness probe must return 200."""
    resp = requests.get(f"{STAGING_URL}/health/live", timeout=15)
    assert resp.status_code == 200, f"/health/live returned {resp.status_code}: {resp.text}"


def test_health_ready():
    """Backend readiness probe must return 200 (DB + Redis connected)."""
    resp = requests.get(f"{STAGING_URL}/health/ready", timeout=15)
    assert resp.status_code == 200, f"/health/ready returned {resp.status_code}: {resp.text}"


def test_frontend_serves_html():
    """nginx must serve the React app at the root path."""
    resp = requests.get(f"{STAGING_URL}/", timeout=15)
    assert resp.status_code == 200, f"/ returned {resp.status_code}"
    assert "text/html" in resp.headers.get("content-type", ""), (
        f"Expected text/html, got: {resp.headers.get('content-type')}"
    )
