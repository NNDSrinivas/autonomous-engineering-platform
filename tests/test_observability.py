import os
from fastapi.testclient import TestClient
from backend.api.main import app

client = TestClient(app)

def test_metrics_endpoint_present_or_disabled():
    r = client.get("/metrics")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert "http_requests_total" in r.text

def test_request_id_header_set():
    r = client.get("/health")
    # either 200 or 401 depending on auth in your env; just check header behavior
    assert "X-Request-Id" in r.headers