"""
Integration tests for /health/* endpoints.

Ensures health checks work correctly when dependencies are configured.
Prevents regression of import path issues that cause silent failures.
"""

import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """
    Create test client for health endpoint integration tests.

    Assumes DATABASE_URL is already set in the test environment (via pytest
    config or CI). The backend.core.config.settings singleton is loaded during
    test collection, so modifying os.environ here won't affect it.

    If DATABASE_URL is not set, the db health check will gracefully report
    "db not configured" (get_engine=None from failed import).
    """
    from backend.api.main import app

    yield TestClient(app)


def test_health_live_returns_200(client):
    """
    /health/live should always return 200 (simple liveness check).

    This is the ALB target health check — must never fail.
    """
    response = client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert any(check["name"] == "self" for check in data["checks"])


def test_health_ready_returns_200_when_db_configured(client):
    """
    /health/ready should return 200 when DATABASE_URL is set.

    Regression test for import path bug: checks.py imported from core.db
    instead of backend.core.db, causing get_engine to be None in Docker.
    This test runs with DATABASE_URL set (like CI/staging) and verifies
    the DB check succeeds (not \"db not configured\").

    If this test fails with 503 and \"db not configured\", the import
    path fallback logic in checks.py is broken again.
    """
    response = client.get("/health/ready")

    # Should be 200 (ready) not 503 (not ready)
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}. "
        f"Response: {response.json()}. "
        "This likely means the DB health check import failed silently."
    )

    data = response.json()
    assert data["ok"] is True, (
        f"Expected ok=true but got {data}. "
        "Check if db/redis imports are failing in checks.py."
    )

    # Verify DB check specifically succeeded
    db_check = next((c for c in data["checks"] if c["name"] == "db"), None)
    assert db_check is not None, "DB check missing from readiness payload"
    assert db_check["ok"] is True, (
        f"DB check failed: {db_check}. "
        "This means either get_engine is None (import failed) or DB connection failed."
    )


def test_health_ready_includes_required_checks(client):
    """
    /health/ready should include self, db, and redis checks.

    All three checks are always present in the response (readiness_payload
    always appends them). Individual checks may report ok=false if the
    dependency is not configured (e.g., REDIS_URL not set), but the check
    name will still appear. This test only verifies check presence, not status.
    """
    response = client.get("/health/ready")
    data = response.json()

    check_names = {check["name"] for check in data["checks"]}
    assert "self" in check_names, "self check is mandatory for readiness"
    assert "db" in check_names, "db check is mandatory for readiness"
    assert "redis" in check_names, "redis check is always included (may report ok=false)"


def test_health_startup_mirrors_ready(client):
    """
    /health/startup should behave identically to /health/ready.

    Some platforms (Kubernetes) use separate startup probes.
    Compares stable fields (status code, ok flag, check names) and ignores
    latency_ms which naturally varies between calls.
    """
    ready_response = client.get("/health/ready")
    startup_response = client.get("/health/startup")

    # Status codes should match
    assert startup_response.status_code == ready_response.status_code

    ready_data = ready_response.json()
    startup_data = startup_response.json()

    # Top-level ok flag should be the same
    assert startup_data.get("ok") == ready_data.get("ok")

    # Both endpoints should expose the same set of checks (by name)
    ready_check_names = {check["name"] for check in ready_data.get("checks", [])}
    startup_check_names = {check["name"] for check in startup_data.get("checks", [])}
    assert startup_check_names == ready_check_names
