"""Application settings and configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings


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
    JWT_ALGORITHM: str = "HS256"  # Algorithm for JWT signature verification
    JWT_AUDIENCE: str | None = None  # Expected 'aud' claim (optional)
    JWT_ISSUER: str | None = None  # Expected 'iss' claim (optional)

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
    CORS_ORIGINS: str = "*"  # Comma-separated list of allowed origins or "*" for all

    # API server configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Application environment
    APP_ENV: str = "development"
    # Defer optional/auxiliary router imports until first request hits those paths
    DEFER_OPTIONAL_ROUTERS: bool = True

    # Audit logging configuration
    enable_audit_logging: bool = True

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

# Validate JWT configuration: JWT_SECRET is required when JWT_ENABLED=true
if settings.JWT_ENABLED and not settings.JWT_SECRET:
    raise ValueError(
        "JWT_SECRET must be set when JWT_ENABLED=true. "
        "Set the JWT_SECRET environment variable or disable JWT authentication."
    )
