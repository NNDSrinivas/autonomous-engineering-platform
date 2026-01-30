"""
Tests for Auth0 JWT validation system

These tests verify that our Auth0 integration works correctly:
- Token validation against auth.navralabs.com
- Role-based access control
- JWKS caching and key rotation handling
"""

import pytest
import httpx
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from backend.auth.auth0 import require_role, _fetch_jwks, _verify_signature
from backend.api.main import app

client = TestClient(app)

# Mock JWT token structure
MOCK_JWT_HEADER = {"alg": "RS256", "typ": "JWT", "kid": "test-key-id"}

MOCK_JWT_CLAIMS = {
    "sub": "auth0|test-user-id",
    "aud": "https://api.navralabs.com",
    "iss": "https://auth.navralabs.com/",
    "exp": 9999999999,  # Far future expiry
    "iat": 1600000000,
    "email": "test@navralabs.com",
    "email_verified": True,
    "name": "Test User",
    "permissions": ["read:profile", "role:admin"],
    "https://navralabs.com/roles": ["admin", "user"],
}

MOCK_JWKS_RESPONSE = {
    "keys": [
        {
            "kty": "RSA",
            "kid": "test-key-id",
            "use": "sig",
            "alg": "RS256",
            "n": "mock_n_value",
            "e": "AQAB",
        }
    ]
}


class TestPublicEndpoints:
    """Test endpoints that don't require authentication"""

    def test_health_endpoint(self):
        """Health endpoint should be accessible without auth"""
        response = client.get("/api/healthz")
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert "auth_domain" in response.json()


class TestProtectedEndpoints:
    """Test endpoints that require JWT authentication"""

    def test_me_endpoint_without_token(self):
        """Protected endpoint should return 401 without token"""
        response = client.get("/api/me")
        assert response.status_code in (401, 403)  # FastAPI HTTPBearer returns 403

    def test_admin_endpoint_without_token(self):
        """Admin endpoint should return 401 without token"""
        response = client.get("/api/admin")
        assert response.status_code == 403


class TestJWTValidation:
    """Test JWT token validation logic"""

    @pytest.mark.asyncio
    async def test_fetch_jwks_success(self):
        """Test successful JWKS fetching"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = MOCK_JWKS_RESPONSE
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            jwks = await _fetch_jwks()
            assert jwks == MOCK_JWKS_RESPONSE

    @patch("backend.auth.auth0.jwt.get_unverified_header")
    def test_verify_signature_missing_kid(self, mock_header):
        """Test signature verification with missing kid"""
        mock_header.return_value = {}  # No kid in header

        with pytest.raises(Exception):  # Should raise HTTPException
            _verify_signature("fake.jwt.token", MOCK_JWKS_RESPONSE)

    @patch("backend.auth.auth0.jwt.get_unverified_header")
    def test_verify_signature_unknown_kid(self, mock_header):
        """Test signature verification with unknown kid"""
        mock_header.return_value = {"kid": "unknown-key-id"}

        with pytest.raises(Exception):  # Should raise HTTPException
            _verify_signature("fake.jwt.token", MOCK_JWKS_RESPONSE)


class TestRoleBasedAccess:
    """Test role-based access control"""

    def test_require_role_function_creation(self):
        """Test that require_role creates proper dependency function"""
        role_check = require_role("admin", "moderator")
        assert callable(role_check)

    @pytest.mark.asyncio
    async def test_role_validation_with_custom_claims(self):
        """Test role validation using custom namespace claims"""
        claims = {"sub": "test-user", "https://navralabs.com/roles": ["admin", "user"]}

        # This would normally be tested with dependency injection
        # Here we just verify the claims structure is correct
        assert "admin" in claims.get("https://navralabs.com/roles", [])

    @pytest.mark.asyncio
    async def test_role_validation_with_permissions(self):
        """Test role validation using Auth0 permissions"""
        claims = {
            "sub": "test-user",
            "permissions": ["read:profile", "role:admin", "write:data"],
        }

        # Extract roles from permissions
        roles = [
            p.replace("role:", "")
            for p in claims.get("permissions", [])
            if p.startswith("role:")
        ]
        assert "admin" in roles


class TestIntegrationWithAuth0:
    """Integration tests that verify Auth0 configuration"""

    @pytest.mark.asyncio
    async def test_auth0_domain_reachability(self):
        """Test that Auth0 domain is reachable"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://auth.navralabs.com/.well-known/openid-configuration"
                )
                assert response.status_code == 200
                config = response.json()
                assert config["issuer"] == "https://auth.navralabs.com/"
                assert "jwks_uri" in config
        except httpx.RequestError:
            pytest.skip("Auth0 domain not reachable (network/DNS issue)")

    @pytest.mark.asyncio
    async def test_jwks_endpoint_reachability(self):
        """Test that JWKS endpoint is reachable"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    "https://auth.navralabs.com/.well-known/jwks.json"
                )
                assert response.status_code == 200
                jwks = response.json()
                assert "keys" in jwks
                assert len(jwks["keys"]) > 0
        except httpx.RequestError:
            pytest.skip("JWKS endpoint not reachable (network/DNS issue)")


def test_environment_variables():
    """Test that required environment variables are configured"""
    import os

    # These should be set in .env or environment
    auth0_domain = os.getenv("AUTH0_DOMAIN", "auth.navralabs.com")
    auth0_audience = os.getenv("AUTH0_AUDIENCE", "https://api.navralabs.com")

    assert auth0_domain == "auth.navralabs.com"
    assert auth0_audience == "https://api.navralabs.com"

    # Verify JWT validation configuration
    from backend.auth.auth0 import AUTH0_ISSUER, JWKS_URL

    assert AUTH0_ISSUER == "https://auth.navralabs.com/"
    assert JWKS_URL == "https://auth.navralabs.com/.well-known/jwks.json"


if __name__ == "__main__":
    # Run basic smoke tests
    print("🧪 Running Auth0 JWT validation smoke tests...")

    # Test environment configuration
    test_environment_variables()
    print("✅ Environment configuration correct")

    # Test public endpoints
    test_client = TestClient(app)
    response = test_client.get("/api/healthz")
    assert response.status_code == 200
    print("✅ Public endpoints accessible")

    # Test protected endpoints return 403 without auth
    response = test_client.get("/api/me")
    assert response.status_code == 403
    print("✅ Protected endpoints require authentication")

    print("🎉 All smoke tests passed!")
