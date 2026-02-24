"""Tests for production security validator in backend/core/config.py.

This test suite verifies that the enforce_production_security validator:
1. Blocks insecure configurations in staging/production environments
2. Allows flexible configurations in development environments
3. Provides clear error messages for configuration violations
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.core.config import Settings, _reset_env_cache
import os


def test_production_requires_jwt_enabled(monkeypatch):
    """Test that production environment requires JWT_ENABLED=true."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_ENABLED", "false")
    monkeypatch.setenv("ALLOW_DEV_AUTH_BYPASS", "false")
    monkeypatch.setenv("VSCODE_AUTH_REQUIRED", "true")
    _reset_env_cache()

    with pytest.raises(ValueError) as exc_info:
        Settings()

    assert "JWT_ENABLED must be true in production environment" in str(exc_info.value)


def test_production_forbids_dev_auth_bypass(monkeypatch):
    """Test that production environment forbids ALLOW_DEV_AUTH_BYPASS=true."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_ENABLED", "true")
    monkeypatch.setenv("ALLOW_DEV_AUTH_BYPASS", "true")
    monkeypatch.setenv("VSCODE_AUTH_REQUIRED", "true")
    _reset_env_cache()

    with pytest.raises(ValueError) as exc_info:
        Settings()

    assert "ALLOW_DEV_AUTH_BYPASS must be false in production environment" in str(
        exc_info.value
    )


def test_production_requires_vscode_auth(monkeypatch):
    """Test that production environment requires VSCODE_AUTH_REQUIRED=true."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_ENABLED", "true")
    monkeypatch.setenv("ALLOW_DEV_AUTH_BYPASS", "false")
    monkeypatch.setenv("VSCODE_AUTH_REQUIRED", "false")
    _reset_env_cache()

    with pytest.raises(ValueError) as exc_info:
        Settings()

    assert "VSCODE_AUTH_REQUIRED must be true in production environment" in str(
        exc_info.value
    )


def test_production_multiple_violations_all_reported(monkeypatch):
    """Test that all security violations are reported together."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_ENABLED", "false")
    monkeypatch.setenv("ALLOW_DEV_AUTH_BYPASS", "true")
    monkeypatch.setenv("VSCODE_AUTH_REQUIRED", "false")
    _reset_env_cache()

    with pytest.raises(ValueError) as exc_info:
        Settings()

    error_msg = str(exc_info.value)
    # All three violations should be reported in a single error
    assert "JWT_ENABLED must be true" in error_msg
    assert "ALLOW_DEV_AUTH_BYPASS must be false" in error_msg
    assert "VSCODE_AUTH_REQUIRED must be true" in error_msg


def test_production_valid_configuration(monkeypatch):
    """Test that production environment accepts valid secure configuration."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_ENABLED", "true")
    monkeypatch.setenv("ALLOW_DEV_AUTH_BYPASS", "false")
    monkeypatch.setenv("VSCODE_AUTH_REQUIRED", "true")
    _reset_env_cache()

    # Should not raise any exception
    settings = Settings()
    assert settings.app_env == "production"
    assert settings.jwt_enabled is True
    assert settings.allow_dev_auth_bypass is False
    assert settings.vscode_auth_required is True


def test_staging_requires_jwt_enabled(monkeypatch):
    """Test that staging environment has same requirements as production."""
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("JWT_ENABLED", "false")
    monkeypatch.setenv("ALLOW_DEV_AUTH_BYPASS", "false")
    monkeypatch.setenv("VSCODE_AUTH_REQUIRED", "true")
    _reset_env_cache()

    with pytest.raises(ValueError) as exc_info:
        Settings()

    assert "JWT_ENABLED must be true in staging environment" in str(exc_info.value)


def test_staging_valid_configuration(monkeypatch):
    """Test that staging environment accepts valid secure configuration."""
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("JWT_ENABLED", "true")
    monkeypatch.setenv("ALLOW_DEV_AUTH_BYPASS", "false")
    monkeypatch.setenv("VSCODE_AUTH_REQUIRED", "true")
    _reset_env_cache()

    # Should not raise any exception
    settings = Settings()
    assert settings.app_env == "staging"
    assert settings.jwt_enabled is True
    assert settings.allow_dev_auth_bypass is False
    assert settings.vscode_auth_required is True


def test_development_allows_insecure_config(monkeypatch):
    """Test that development environment allows flexible configuration."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_ENABLED", "false")
    monkeypatch.setenv("ALLOW_DEV_AUTH_BYPASS", "true")
    monkeypatch.setenv("VSCODE_AUTH_REQUIRED", "false")
    _reset_env_cache()

    # Should not raise any exception - development is permissive
    settings = Settings()
    assert settings.app_env == "development"
    assert settings.jwt_enabled is False
    assert settings.allow_dev_auth_bypass is True
    assert settings.vscode_auth_required is False


def test_dev_env_allows_insecure_config(monkeypatch):
    """Test that 'dev' environment (normalized to development) allows flexibility."""
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("JWT_ENABLED", "false")
    monkeypatch.setenv("ALLOW_DEV_AUTH_BYPASS", "true")
    monkeypatch.setenv("VSCODE_AUTH_REQUIRED", "false")
    _reset_env_cache()

    # Should not raise any exception
    settings = Settings()
    assert settings.app_env == "dev"


def test_test_env_allows_insecure_config(monkeypatch):
    """Test that test environment allows flexible configuration."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("JWT_ENABLED", "false")
    monkeypatch.setenv("VSCODE_AUTH_REQUIRED", "false")
    # Note: ALLOW_DEV_AUTH_BYPASS is auto-set to true in test env (line 131-136 in config.py)
    _reset_env_cache()

    # Should not raise any exception
    settings = Settings()
    assert settings.app_env == "test"
    assert settings.allow_dev_auth_bypass is True  # Auto-enabled in test env


def test_ci_env_allows_insecure_config(monkeypatch):
    """Test that CI environment allows flexible configuration."""
    monkeypatch.setenv("APP_ENV", "ci")
    monkeypatch.setenv("JWT_ENABLED", "false")
    monkeypatch.setenv("VSCODE_AUTH_REQUIRED", "false")
    # Note: ALLOW_DEV_AUTH_BYPASS is auto-set to true in CI env (line 131-136 in config.py)
    _reset_env_cache()

    # Should not raise any exception
    settings = Settings()
    assert settings.app_env == "ci"
    assert settings.allow_dev_auth_bypass is True  # Auto-enabled in CI env
