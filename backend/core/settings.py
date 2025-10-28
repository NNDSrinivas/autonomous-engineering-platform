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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
