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
    Create test client with DATABASE_URL set.

    This simulates the CI/Docker environment where DATABASE_URL is available
    and the health check imports should succeed (backend.core.db path).
    """
    # Ensure DATABASE_URL is set for these tests
    # Use SQLite in-memory for fast testing
    original_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    try:
        # Import after setting env var so settings picks it up
        from backend.api.main import app

        yield TestClient(app)
    finally:
        # Restore original DATABASE_URL
        if original_db_url is not None:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)


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
    /health/ready should include at minimum self and db checks.

    Redis check is optional (may not be present if cache import fails
    or REDIS_URL is not set). This test verifies the mandatory checks
    are included without requiring redis to be configured.
    """
    response = client.get("/health/ready")
    data = response.json()

    check_names = {check["name"] for check in data["checks"]}
    assert "self" in check_names, "self check is mandatory for readiness"
    assert "db" in check_names, "db check is mandatory when DATABASE_URL is set"
    # Redis check is optional - not asserted here


def test_health_startup_mirrors_ready(client):
    """
    /health/startup should behave identically to /health/ready.

    Some platforms (Kubernetes) use separate startup probes.
    """
    ready_response = client.get("/health/ready")
    startup_response = client.get("/health/startup")

    assert startup_response.status_code == ready_response.status_code
    assert startup_response.json() == ready_response.json()
