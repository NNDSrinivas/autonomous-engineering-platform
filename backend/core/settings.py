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
