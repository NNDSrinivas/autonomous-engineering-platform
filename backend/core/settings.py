"""Application settings and configuration."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


def normalize_env(env: str) -> str:
    """
    Normalize environment name to canonical form.

    Handles common aliases:
    - "prod" → "production"
    - "stage" → "staging"
    - "dev" → "development"
    - "test" / "ci" → normalized as-is

    Args:
        env: Environment name to normalize

    Returns:
        Normalized environment name
    """
    env_lower = env.lower().strip()

    # Normalize common production aliases
    if env_lower in ("prod", "production"):
        return "production"

    # Normalize common staging aliases
    if env_lower in ("stage", "staging"):
        return "staging"

    # Normalize development aliases
    if env_lower in ("dev", "development"):
        return "development"

    # Return as-is for test, ci, and other values
    return env_lower


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_NAME: str = "Autonomous Engineering Platform"  # Human-readable application name
    APP_SLUG: str = (
        "autonomous-engineering-platform"  # Machine-friendly identifier (e.g., for URLs, config)
    )

    # Redis configuration
    REDIS_URL: str | None = None

    # Channel namespace for plan streams
    PLAN_CHANNEL_PREFIX: str = "plan:"

    # Presence/cursor configuration
    # NOTE: HEARTBEAT_SEC should be significantly smaller than PRESENCE_TTL_SEC
    # to avoid race conditions where a user could be marked expired between
    # heartbeats. As a guideline we prefer HEARTBEAT_SEC < PRESENCE_TTL_SEC / 2
    # so that a single missed heartbeat doesn't immediately expire a user.
    PRESENCE_TTL_SEC: int = 60
    HEARTBEAT_SEC: int = 20
    PRESENCE_CLEANUP_INTERVAL_SEC: int = 60  # How often to clean expired cache entries

    # JWT Authentication configuration
    # Set JWT_ENABLED=true to require JWT tokens instead of DEV_* env variables
    # Note: Token expiration is verified using the 'exp' claim in the JWT itself.
    #       Typical expiration: 1 hour (3600 seconds). Configure this in your auth service.
    JWT_ENABLED: bool = False  # Default: use dev shim for local development
    JWT_SECRET: str | None = None  # Required when JWT_ENABLED=true
    JWT_SECRET_PREVIOUS: str | None = None  # Optional previous secrets for rotation
    JWT_ALGORITHM: str = "HS256"  # Algorithm for JWT signature verification
    JWT_AUDIENCE: str | None = None  # Expected 'aud' claim (optional)
    JWT_ISSUER: str | None = None  # Expected 'iss' claim (optional)
    JWT_JWKS_URL: str | None = None  # Optional JWKS URL for RS256 validation
    JWT_JWKS_CACHE_TTL: int = 300  # JWKS cache TTL in seconds

    # Rate limiting configuration
    RATE_LIMITING_ENABLED: bool = True
    RATE_LIMITING_REDIS_KEY_PREFIX: str = "aep:rate_limit:"
    RATE_LIMITING_FALLBACK_ENABLED: bool = (
        True  # Use in-memory fallback when Redis unavailable
    )
    # CRITICAL LIMITATION: Estimated active users per org for rate limiting calculations
    # TODO: HIGH PRIORITY - Replace with actual active user tracking from presence system
    # This is a temporary workaround that may cause incorrect rate limiting for orgs
    # with significantly different user counts. Production deployments should monitor
    # and adjust this value based on actual org sizes.
    RATE_LIMITING_ESTIMATED_ACTIVE_USERS: int = 5

    # CORS configuration
    CORS_ORIGINS: str = (
        ""  # Comma-separated list of allowed origins; empty means strict deny
    )
    ALLOW_DEV_CORS: bool = False  # Explicit dev override for localhost/vscode-webview
    ALLOW_VSCODE_WEBVIEW: bool = True  # Allow VS Code webview origins when enabled

    # VS Code/webview auth enforcement
    VSCODE_AUTH_REQUIRED: bool = True
    ALLOW_DEV_AUTH_BYPASS: bool = False

    # OAuth device token TTLs
    OAUTH_DEVICE_CODE_TTL_SECONDS: int = 600
    OAUTH_DEVICE_TOKEN_TTL_SECONDS: int = 86400

    # API server configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Application environment
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    DEBUG: bool = False  # Enable debug mode for development
    # Defer optional/auxiliary router imports until first request hits those paths
    DEFER_OPTIONAL_ROUTERS: bool = True

    # Audit logging configuration
    ENABLE_AUDIT_LOGGING: bool = True
    AUDIT_RETENTION_ENABLED: bool = True
    AUDIT_RETENTION_DAYS: int = 90
    AUDIT_ENCRYPTION_KEY: str | None = None
    AUDIT_ENCRYPTION_KEY_ID: str = "default"

    # Webhook secrets (shared secrets for inbound webhooks)
    JIRA_WEBHOOK_SECRET: str | None = None
    GITHUB_WEBHOOK_SECRET: str | None = None
    SLACK_WEBHOOK_SECRET: str | None = None
    SLACK_SIGNING_SECRET: str | None = None
    TEAMS_WEBHOOK_SECRET: str | None = None
    DOCS_WEBHOOK_SECRET: str | None = None
    CI_WEBHOOK_SECRET: str | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return [origin for origin in origins if origin]

    @property
    def APP_ENV(self) -> str:
        """Backwards compatibility alias for app_env (uppercase)."""
        return self.app_env

    @APP_ENV.setter
    def APP_ENV(self, value: str) -> None:
        """Backwards compatibility setter for APP_ENV."""
        self.app_env = value

    def _normalize_env(self) -> str:
        """
        Normalize this instance's environment name to canonical form.

        Returns:
            Normalized environment name
        """
        return normalize_env(self.app_env)

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self._normalize_env() == "production"

    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self._normalize_env() == "staging"

    def is_production_like(self) -> bool:
        """
        Check if running in production-like environment (production or staging).

        Use this for checks that should apply to both production and staging,
        such as security requirements, encryption enforcement, etc.
        """
        return self._normalize_env() in ("production", "staging")

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self._normalize_env() == "development"

    def is_test(self) -> bool:
        """Check if running in test/CI environment."""
        return self._normalize_env() in ("test", "ci")

    @property
    def enable_audit_logging(self) -> bool:
        """
        Backwards-compatible alias for ENABLE_AUDIT_LOGGING.
        Deprecated: prefer using ENABLE_AUDIT_LOGGING directly.
        """
        return self.ENABLE_AUDIT_LOGGING

    @enable_audit_logging.setter
    def enable_audit_logging(self, value: bool) -> None:
        self.ENABLE_AUDIT_LOGGING = value

    # Pydantic v2 settings: ignore unknown/extra env vars coming from .env
    # Note: To avoid loading .env during tests, override settings in pytest fixtures
    # or set environment variables explicitly in test configuration instead of
    # relying on import-time detection (which can be unreliable).
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Global settings instance
settings = Settings()

# Basic runtime validation to catch obviously invalid configurations early.
# This is intentionally done at import time because settings are loaded from
# environment variables and we want misconfigurations to fail fast.
if settings.HEARTBEAT_SEC * 2 >= settings.PRESENCE_TTL_SEC:
    raise ValueError(
        f"Invalid presence timing: HEARTBEAT_SEC={settings.HEARTBEAT_SEC} must be < PRESENCE_TTL_SEC/2={settings.PRESENCE_TTL_SEC / 2}"
    )

# Validate JWT configuration: at least one secret is required when JWT_ENABLED=true
if settings.JWT_ENABLED and not (
    settings.JWT_SECRET or settings.JWT_SECRET_PREVIOUS or settings.JWT_JWKS_URL
):
    raise ValueError(
        "JWT_SECRET (or JWT_SECRET_PREVIOUS) or JWT_JWKS_URL must be set when JWT_ENABLED=true. "
        "Set JWT_SECRET/JWT_SECRET_PREVIOUS for HS256 or JWT_JWKS_URL for RS256."
    )


def validate_production_settings(settings_obj: "Settings | None" = None) -> None:
    """
    Validate production/staging-specific settings.

    This function should be called explicitly during app startup (not at import time)
    to allow CLI tools, tests, and offline scripts to import settings without
    triggering validation errors.

    Args:
        settings_obj: Settings object to validate. If None, uses module-level settings.

    Raises:
        ValueError: If required production settings are missing or invalid
    """
    if settings_obj is None:
        settings_obj = settings

    # Validate audit encryption: encryption key is REQUIRED in production/staging
    if settings_obj.is_production_like() and settings_obj.ENABLE_AUDIT_LOGGING:
        if not settings_obj.AUDIT_ENCRYPTION_KEY:
            raise ValueError(
                f"AUDIT_ENCRYPTION_KEY is REQUIRED when app_env={settings_obj.app_env} "
                f"(normalized: {settings_obj._normalize_env()}) and audit logging is enabled. "
                "Set AUDIT_ENCRYPTION_KEY environment variable to a Fernet-compatible encryption key. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
