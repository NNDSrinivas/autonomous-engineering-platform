from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx

import backend.api.routers.oauth_device_auth0 as oauth_auth0_router


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(oauth_auth0_router.router)
    return TestClient(app)


def test_start_returns_structured_error_when_auth0_unreachable(monkeypatch):
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_CLIENT_ID", "test-client")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_AUDIENCE", "https://api.example.com")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_DOMAIN", "auth.example.com")

    async def _raise_connect_error(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise httpx.ConnectError("dns resolution failed")

    monkeypatch.setattr(httpx.AsyncClient, "post", _raise_connect_error)

    client = _build_client()
    response = client.post("/oauth/device/start")

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["error"] == "auth0_unreachable"
    assert "AUTH0_DOMAIN" in payload["detail"]["hint"]


def test_start_validates_auth0_domain_format(monkeypatch):
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_CLIENT_ID", "test-client")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_AUDIENCE", "https://api.example.com")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_DOMAIN", "https://auth.example.com")

    client = _build_client()
    response = client.post("/oauth/device/start")

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["error"] == "auth0_configuration_error"
    assert "bare host" in payload["detail"]["error_description"]
