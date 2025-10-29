"""Application settings and configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_NAME: str = "Autonomous Engineering Platform"

    # Redis configuration
    REDIS_URL: str | None = None

    # Channel namespace for plan streams
    PLAN_CHANNEL_PREFIX: str = "plan:"

    # Presence/cursor configuration
    # Presence/cursor configuration
    # NOTE: HEARTBEAT_SEC should be significantly smaller than PRESENCE_TTL_SEC
    # to avoid race conditions where a user could be marked expired between
    # heartbeats. As a guideline we prefer HEARTBEAT_SEC < PRESENCE_TTL_SEC / 2
    # so that a single missed heartbeat doesn't immediately expire a user.
    PRESENCE_TTL_SEC: int = 60
    HEARTBEAT_SEC: int = 20
    PRESENCE_CLEANUP_INTERVAL_SEC: int = 60  # How often to clean expired cache entries

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
if not (settings.HEARTBEAT_SEC * 2 < settings.PRESENCE_TTL_SEC):
    raise ValueError(
        f"Invalid presence timing: HEARTBEAT_SEC={settings.HEARTBEAT_SEC} must be < PRESENCE_TTL_SEC/2={settings.PRESENCE_TTL_SEC/2}"
    )
