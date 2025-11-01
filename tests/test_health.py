import pytest
from fastapi.testclient import TestClient

# Import the app directly for testing
from backend.api.main import app

# Use FastAPI TestClient instead of requiring running servers
client = TestClient(app)


def test_liveness_ok():
    """Test liveness endpoint - should always be OK"""
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json().get("ok") is True
    assert "checks" in r.json()


def test_readiness_works():
    """Test readiness endpoint - may fail depending on dependencies"""
    r = client.get("/health/ready")
    # In dev with no DB/Redis, this might be 503; either way payload exists
    assert r.status_code in (200, 503)
    assert "checks" in r.json()


def test_startup_endpoint():
    """Test startup endpoint - mirrors readiness"""
    r = client.get("/health/startup")
    # mirrors readiness
    assert r.status_code in (200, 503)
    assert "checks" in r.json()


def test_version_endpoint():
    """Test version endpoint using TestClient (no server required)"""
    response = client.get("/version")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data


# Keep original tests for integration testing (when servers are running)
def test_integration_health_endpoints():
    """Integration test - only runs if servers are already started"""
    import requests

    try:
        r1 = requests.get("http://localhost:8002/health", timeout=1)
        if r1.status_code == 200:
            data = r1.json()
            assert data["status"] == "ok"
            assert data["service"] == "core"
    except requests.exceptions.ConnectionError:
        pytest.skip("Integration test skipped - server not running")


def test_integration_version_endpoints():
    """Integration test - only runs if servers are already started"""
    import requests

    try:
        v1 = requests.get("http://localhost:8002/version", timeout=1)
        if v1.status_code == 200:
            data = v1.json()
            assert "name" in data and "version" in data
    except requests.exceptions.ConnectionError:
        pytest.skip("Integration test skipped - server not running")
