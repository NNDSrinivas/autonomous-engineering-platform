"""
Integration tests for /health/* endpoints.

Ensures health checks work correctly when dependencies are configured.
Prevents regression of import path issues that cause silent failures.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """
    Create test client for health endpoint integration tests.

    The database engine URL is resolved by settings at test collection time
    (either from DATABASE_URL in the environment or from the pytest-time
    SQLite fallback used by Settings.sqlalchemy_url). The
    backend.core.config.settings singleton is loaded during test collection,
    so modifying os.environ here won't affect it.

    A "db not configured" response from the DB health check indicates that
    the DB-related imports failed (e.g., get_engine/text is None due to an
    import path issue), not that DATABASE_URL is missing.
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


def test_health_ready_succeeds_with_normal_imports(client):
    """
    /health/ready should return 200 in normal pytest configuration.

    Regression test for import path bug: checks.py originally imported from
    core.db instead of backend.core.db, causing get_engine to be None in
    Docker/pytest (where PYTHONPATH is repo root, not backend/ subdir).
    This test verifies the DB check succeeds with proper import paths.

    If this test fails with 503 and "db not configured", the import path
    fallback logic in checks.py is broken again (get_engine/text are None).
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
