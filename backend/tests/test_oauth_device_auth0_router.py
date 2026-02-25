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
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_DEVICE_CLIENT_ID", "test-client")
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
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_DEVICE_CLIENT_ID", "test-client")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_AUDIENCE", "https://api.example.com")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_DOMAIN", "https://auth.example.com")

    client = _build_client()
    response = client.post("/oauth/device/start")

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["error"] == "auth0_configuration_error"
    assert "bare host" in payload["detail"]["error_description"]


def test_start_validates_missing_device_client_id(monkeypatch):
    """Test that missing AUTH0_DEVICE_CLIENT_ID is caught by validator."""
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_DEVICE_CLIENT_ID", "")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_AUDIENCE", "https://api.example.com")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_DOMAIN", "auth.example.com")

    client = _build_client()
    response = client.post("/oauth/device/start")

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["error"] == "auth0_configuration_error"
    assert "AUTH0_DEVICE_CLIENT_ID" in payload["detail"]["hint"]


# ===== Tests for /oauth/device/refresh endpoint =====


def test_refresh_success_with_token_rotation(monkeypatch):
    """Test successful refresh with Auth0 returning rotated refresh token."""
    monkeypatch.setattr(
        oauth_auth0_router, "AUTH0_DEVICE_CLIENT_ID", "test-device-client"
    )
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_AUDIENCE", "https://api.example.com")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_DOMAIN", "auth.example.com")

    # Mock successful Auth0 token refresh response
    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "access_token": "new-auth0-access-token",
                "id_token": "mock.id.token",
                "refresh_token": "new-rotated-refresh-token",
                "token_type": "Bearer",
                "expires_in": 86400,
            }

    async def _mock_post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

    # Mock JWT verification (must be async now)
    async def _mock_verify(id_token: str):  # type: ignore[no-untyped-def]
        return {
            "sub": "auth0|test-user-123",
            "email": "test@example.com",
            "name": "Test User",
        }

    monkeypatch.setattr(oauth_auth0_router, "verify_auth0_id_token", _mock_verify)

    client = _build_client()
    response = client.post(
        "/oauth/device/refresh", json={"refresh_token": "old-refresh-token"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert "access_token" in payload
    assert payload["expires_in"] == 3600
    assert payload["refresh_token"] == "new-rotated-refresh-token"


def test_refresh_success_without_token_rotation(monkeypatch):
    """Test successful refresh when Auth0 doesn't rotate refresh token."""
    monkeypatch.setattr(
        oauth_auth0_router, "AUTH0_DEVICE_CLIENT_ID", "test-device-client"
    )
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_AUDIENCE", "https://api.example.com")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_DOMAIN", "auth.example.com")

    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "access_token": "new-auth0-access-token",
                "id_token": "mock.id.token",
                # No refresh_token in response (rotation not enabled)
                "token_type": "Bearer",
                "expires_in": 86400,
            }

    async def _mock_post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

    async def _mock_verify(id_token: str):  # type: ignore[no-untyped-def]
        return {
            "sub": "auth0|test-user-123",
            "email": "test@example.com",
            "name": "Test User",
        }

    monkeypatch.setattr(oauth_auth0_router, "verify_auth0_id_token", _mock_verify)

    client = _build_client()
    response = client.post(
        "/oauth/device/refresh", json={"refresh_token": "old-refresh-token"}
    )

    assert response.status_code == 200
    payload = response.json()
    assert "access_token" in payload
    assert payload["expires_in"] == 3600
    assert payload.get("refresh_token") is None


def test_refresh_fails_when_auth0_unreachable(monkeypatch):
    """Test refresh returns 503 when Auth0 is unreachable."""
    monkeypatch.setattr(
        oauth_auth0_router, "AUTH0_DEVICE_CLIENT_ID", "test-device-client"
    )
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_AUDIENCE", "https://api.example.com")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_DOMAIN", "auth.example.com")

    async def _raise_connect_error(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise httpx.ConnectError("dns resolution failed")

    monkeypatch.setattr(httpx.AsyncClient, "post", _raise_connect_error)

    client = _build_client()
    response = client.post(
        "/oauth/device/refresh", json={"refresh_token": "old-refresh-token"}
    )

    assert response.status_code == 503
    payload = response.json()
    assert payload["detail"]["error"] == "auth0_unreachable"


def test_refresh_fails_with_invalid_refresh_token(monkeypatch):
    """Test refresh returns 401 when refresh token is expired/invalid."""
    monkeypatch.setattr(
        oauth_auth0_router, "AUTH0_DEVICE_CLIENT_ID", "test-device-client"
    )
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_AUDIENCE", "https://api.example.com")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_DOMAIN", "auth.example.com")

    class MockResponse:
        status_code = 403

        def json(self):
            return {
                "error": "invalid_grant",
                "error_description": "Refresh token is expired or invalid",
            }

    async def _mock_post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

    client = _build_client()
    response = client.post(
        "/oauth/device/refresh", json={"refresh_token": "expired-refresh-token"}
    )

    assert response.status_code == 401
    payload = response.json()
    assert payload["detail"]["error"] == "refresh_failed"


def test_refresh_fails_when_id_token_missing(monkeypatch):
    """Test refresh returns 401 when Auth0 response missing id_token."""
    monkeypatch.setattr(
        oauth_auth0_router, "AUTH0_DEVICE_CLIENT_ID", "test-device-client"
    )
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_AUDIENCE", "https://api.example.com")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_DOMAIN", "auth.example.com")

    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "access_token": "new-auth0-access-token",
                # Missing id_token!
                "token_type": "Bearer",
                "expires_in": 86400,
            }

    async def _mock_post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

    client = _build_client()
    response = client.post(
        "/oauth/device/refresh", json={"refresh_token": "valid-refresh-token"}
    )

    assert response.status_code == 401
    payload = response.json()
    assert payload["detail"]["error"] == "invalid_token"
    assert "id_token" in payload["detail"]["error_description"]


def test_refresh_fails_when_sub_claim_missing(monkeypatch):
    """Test refresh returns 401 when id_token missing sub claim."""
    monkeypatch.setattr(
        oauth_auth0_router, "AUTH0_DEVICE_CLIENT_ID", "test-device-client"
    )
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_AUDIENCE", "https://api.example.com")
    monkeypatch.setattr(oauth_auth0_router, "AUTH0_DOMAIN", "auth.example.com")

    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "access_token": "new-auth0-access-token",
                "id_token": "mock.id.token",
                "token_type": "Bearer",
                "expires_in": 86400,
            }

    async def _mock_post(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", _mock_post)

    # Mock JWT verification returning claims without sub (must be async now)
    async def _mock_verify(id_token: str):  # type: ignore[no-untyped-def]
        return {
            # Missing sub!
            "email": "test@example.com",
            "name": "Test User",
        }

    monkeypatch.setattr(oauth_auth0_router, "verify_auth0_id_token", _mock_verify)

    client = _build_client()
    response = client.post(
        "/oauth/device/refresh", json={"refresh_token": "valid-refresh-token"}
    )

    assert response.status_code == 401
    payload = response.json()
    assert payload["detail"]["error"] == "invalid_token"
    assert "sub claim" in payload["detail"]["error_description"]
