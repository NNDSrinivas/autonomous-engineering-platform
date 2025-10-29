"""Tests for JWT authentication and token verification."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jose import jwt

from backend.core.auth.deps import get_current_user
from backend.core.auth.jwt import (
    JWTVerificationError,
    decode_jwt,
    extract_user_claims,
    verify_token,
)
from backend.core.auth.models import User
from backend.core.settings import settings


@pytest.fixture
def jwt_secret():
    """Provide a test JWT secret."""
    return "test-secret-key-for-unit-tests"


@pytest.fixture
def enable_jwt(jwt_secret, monkeypatch):
    """Enable JWT mode and configure settings for tests."""
    monkeypatch.setattr(settings, "JWT_ENABLED", True)
    monkeypatch.setattr(settings, "JWT_SECRET", jwt_secret)
    monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", None)
    monkeypatch.setattr(settings, "JWT_ISSUER", None)


@pytest.fixture
def configure_jwt(jwt_secret, monkeypatch):
    """
    Helper fixture to configure JWT settings with custom values.

    Usage:
        configure_jwt(audience="api.example.com")
        configure_jwt(issuer="auth.example.com")
    """

    def _configure(
        enabled: bool = True,
        secret: str | None = None,
        audience: str | None = None,
        issuer: str | None = None,
    ):
        monkeypatch.setattr(settings, "JWT_ENABLED", enabled)
        monkeypatch.setattr(settings, "JWT_SECRET", secret or jwt_secret)
        monkeypatch.setattr(settings, "JWT_ALGORITHM", "HS256")
        monkeypatch.setattr(settings, "JWT_AUDIENCE", audience)
        monkeypatch.setattr(settings, "JWT_ISSUER", issuer)

    return _configure


@pytest.fixture
def test_app():
    """Create a FastAPI test app with authentication endpoint."""
    app = FastAPI()

    @app.get("/test")
    def test_endpoint(user: User = Depends(get_current_user)):
        return {
            "user_id": user.user_id,
            "role": user.role.value,
            "org_id": user.org_id,
        }

    return app


def create_test_token(
    jwt_secret: str,
    user_id: str = "test-user-123",
    org_id: str = "org-abc",
    role: str = "planner",
    email: str = "test@example.com",
    name: str = "Test User",
    projects: list[str] | None = None,
    exp_delta: timedelta = timedelta(hours=1),
    **extra_claims,
) -> str:
    """Helper to create test JWT tokens."""
    if projects is None:
        projects = ["proj1", "proj2"]

    payload = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "email": email,
        "name": name,
        "projects": projects,
        "exp": datetime.now(timezone.utc) + exp_delta,
        "iat": datetime.now(timezone.utc),
        **extra_claims,
    }

    return jwt.encode(payload, jwt_secret, algorithm="HS256")


class TestDecodeJWT:
    """Tests for decode_jwt function."""

    def test_decode_valid_token(self, enable_jwt, jwt_secret):
        """Test decoding a valid JWT token."""
        token = create_test_token(jwt_secret)
        payload = decode_jwt(token)

        assert payload["sub"] == "test-user-123"
        assert payload["org_id"] == "org-abc"
        assert payload["role"] == "planner"
        assert payload["email"] == "test@example.com"

    def test_decode_expired_token(self, enable_jwt, jwt_secret):
        """Test that expired tokens are rejected."""
        # Create token that expired 1 hour ago
        token = create_test_token(jwt_secret, exp_delta=timedelta(hours=-1))

        with pytest.raises(JWTVerificationError, match="expired"):
            decode_jwt(token)

    def test_decode_invalid_signature(self, enable_jwt, jwt_secret):
        """Test that tokens with invalid signatures are rejected."""
        # Create token with wrong secret
        token = create_test_token("wrong-secret")

        with pytest.raises(JWTVerificationError, match="verification failed"):
            decode_jwt(token)

    def test_decode_malformed_token(self, enable_jwt):
        """Test that malformed tokens are rejected."""
        with pytest.raises(JWTVerificationError):
            decode_jwt("not-a-jwt-token")

    def test_decode_missing_secret(self, monkeypatch):
        """Test that decoding fails if JWT_SECRET is not configured."""
        monkeypatch.setattr(settings, "JWT_ENABLED", True)
        monkeypatch.setattr(settings, "JWT_SECRET", None)

        with pytest.raises(JWTVerificationError, match="JWT_SECRET is required"):
            decode_jwt("any-token")

    def test_decode_jwt_disabled(self):
        """Test that decoding fails if JWT is disabled."""
        with pytest.raises(JWTVerificationError, match="not enabled"):
            decode_jwt("any-token")

    def test_decode_with_audience(self, jwt_secret, configure_jwt):
        """Test token verification with audience claim."""
        configure_jwt(audience="api.example.com")

        # Token with correct audience
        token = create_test_token(jwt_secret, aud="api.example.com")
        payload = decode_jwt(token)
        assert payload["aud"] == "api.example.com"

        # Token with wrong audience
        wrong_token = create_test_token(jwt_secret, aud="wrong-audience")
        with pytest.raises(JWTVerificationError, match="claims"):
            decode_jwt(wrong_token)

    def test_decode_with_issuer(self, jwt_secret, configure_jwt):
        """Test token verification with issuer claim."""
        configure_jwt(issuer="auth.example.com")

        # Token with correct issuer
        token = create_test_token(jwt_secret, iss="auth.example.com")
        payload = decode_jwt(token)
        assert payload["iss"] == "auth.example.com"

        # Token with wrong issuer
        wrong_token = create_test_token(jwt_secret, iss="wrong-issuer")
        with pytest.raises(JWTVerificationError, match="claims"):
            decode_jwt(wrong_token)


class TestExtractUserClaims:
    """Tests for extract_user_claims function."""

    def test_extract_complete_claims(self):
        """Test extracting all user claims."""
        payload = {
            "sub": "user-123",
            "email": "user@example.com",
            "name": "User Name",
            "org_id": "org-456",
            "role": "admin",
            "projects": ["p1", "p2", "p3"],
        }

        claims = extract_user_claims(payload)

        assert claims["user_id"] == "user-123"
        assert claims["email"] == "user@example.com"
        assert claims["display_name"] == "User Name"
        assert claims["org_id"] == "org-456"
        assert claims["role"] == "admin"
        assert claims["projects"] == ["p1", "p2", "p3"]

    def test_extract_minimal_claims(self):
        """Test extracting with only required claims."""
        payload = {
            "sub": "user-123",
            "org_id": "org-456",
        }

        claims = extract_user_claims(payload)

        assert claims["user_id"] == "user-123"
        assert claims["org_id"] == "org-456"
        assert claims["role"] == "viewer"  # Default role
        assert claims["email"] is None
        assert claims["display_name"] is None
        assert claims["projects"] == []

    def test_extract_missing_user_id(self):
        """Test that missing user_id (sub) raises error."""
        payload = {"org_id": "org-456"}

        with pytest.raises(JWTVerificationError, match="sub"):
            extract_user_claims(payload)

    def test_extract_missing_org_id(self):
        """Test that missing org_id raises error."""
        payload = {"sub": "user-123"}

        with pytest.raises(JWTVerificationError, match="org_id"):
            extract_user_claims(payload)

    def test_extract_invalid_role_defaults_to_viewer(self):
        """Test that invalid roles default to viewer for security."""
        payload = {
            "sub": "user-123",
            "org_id": "org-456",
            "role": "superuser",  # Invalid role
        }

        claims = extract_user_claims(payload)
        assert claims["role"] == "viewer"

    def test_extract_projects_from_string(self):
        """Test parsing projects from comma-separated string."""
        payload = {
            "sub": "user-123",
            "org_id": "org-456",
            "projects": "p1, p2, p3",  # String instead of list
        }

        claims = extract_user_claims(payload)
        assert claims["projects"] == ["p1", "p2", "p3"]


class TestVerifyToken:
    """Integration tests for verify_token function."""

    def test_verify_valid_token(self, enable_jwt, jwt_secret):
        """Test end-to-end token verification."""
        token = create_test_token(
            jwt_secret,
            user_id="user-xyz",
            org_id="org-abc",
            role="planner",
            email="planner@example.com",
            name="Plan Master",
            projects=["proj-a", "proj-b"],
        )

        claims = verify_token(token)

        assert claims["user_id"] == "user-xyz"
        assert claims["org_id"] == "org-abc"
        assert claims["role"] == "planner"
        assert claims["email"] == "planner@example.com"
        assert claims["display_name"] == "Plan Master"
        assert claims["projects"] == ["proj-a", "proj-b"]

    def test_verify_expired_token(self, enable_jwt, jwt_secret):
        """Test that expired tokens fail verification."""
        token = create_test_token(jwt_secret, exp_delta=timedelta(seconds=-10))

        with pytest.raises(JWTVerificationError, match="expired"):
            verify_token(token)

    def test_verify_token_missing_claims(self, enable_jwt, jwt_secret):
        """Test that tokens missing required claims fail."""
        # Manually create token without org_id
        payload = {
            "sub": "user-123",
            # Missing org_id
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        token = jwt.encode(payload, jwt_secret, algorithm="HS256")

        with pytest.raises(JWTVerificationError, match="org_id"):
            verify_token(token)


class TestJWTWithFastAPI:
    """Integration tests with FastAPI dependency."""

    def test_get_current_user_with_jwt(self, enable_jwt, jwt_secret, test_app):
        """Test get_current_user dependency with valid JWT."""
        client = TestClient(test_app)

        # Create valid token
        token = create_test_token(
            jwt_secret,
            user_id="api-user",
            org_id="api-org",
            role="admin",
        )

        # Request with valid token
        response = client.get("/test", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()["user_id"] == "api-user"
        assert response.json()["role"] == "admin"
        assert response.json()["org_id"] == "api-org"

    def test_get_current_user_missing_token(self, enable_jwt, test_app):
        """Test get_current_user rejects requests without token."""
        client = TestClient(test_app)

        # Request without token
        response = client.get("/test")

        assert response.status_code == 401
        assert "Authorization" in response.json()["detail"]

    def test_get_current_user_invalid_token(self, enable_jwt, test_app):
        """Test get_current_user rejects invalid tokens."""
        client = TestClient(test_app)

        # Request with malformed token
        response = client.get(
            "/test", headers={"Authorization": "Bearer invalid-token"}
        )

        assert response.status_code == 401
        assert "Invalid or expired" in response.json()["detail"]
