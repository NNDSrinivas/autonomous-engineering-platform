"""Application settings and configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    APP_NAME: str = "Autonomous Engineering Platform"

    # Redis configuration
    REDIS_URL: str | None = None

    # Channel namespace for plan streams
    PLAN_CHANNEL_PREFIX: str = "plan:"

    # Pydantic v2 settings: ignore unknown/extra env vars coming from .env
    # Pydantic v2 settings: ignore unknown/extra env vars coming from .env
    # During test runs (pytest), avoid loading the repository .env to prevent
    # test environment contamination. Pytest sets the PYTEST_CURRENT_TEST
    # environment variable during collection/execution.
    _env_file = None if os.environ.get("PYTEST_CURRENT_TEST") else ".env"
    model_config = {
        "env_file": _env_file,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Global settings instance
settings = Settings()
