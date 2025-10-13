"""
Configuration management for Autonomous Engineering Intelligence Platform
"""

from typing import List
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "dev"
    app_name: str = "autonomous-engineering-platform"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    realtime_port: int = 8001

    log_level: str = "INFO"
    cors_origins: str = (
        "http://localhost:3000,http://localhost:3001"  # comma-separated list or "*"
    )

    # Database configuration
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "mentor"
    db_password: str = "mentor"
    db_name: str = "mentor"
    database_url: Optional[str] = None  # Allow override with full URL

    redis_url: str = "redis://localhost:6379/0"
    redis_rate_limit_ttl: int = 3600  # Rate limit key TTL in seconds (1 hour)

    # Rate limiting configuration
    trusted_proxies: List[str] = [
        "127.0.0.1",
        "::1",
    ]  # Trusted proxy IPs for X-Forwarded-For validation

    # AI Configuration
    openai_api_key: Optional[str] = None

    # Platform Configuration
    debug: bool = False
    environment: str = "development"
    secret_key: str  # Required, must be set via environment variable
    jwt_secret: str  # Required, must be set via environment variable

    # API Configuration
    api_v1_prefix: str = "/api"

    # Storage
    vector_db_path: str = "./data/vector_store"

    # Features
    enable_real_time: bool = True
    enable_github_integration: bool = True
    enable_analytics: bool = True
    enable_ai_assistance: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def sqlalchemy_url(self) -> str:
        # Use database_url if provided, otherwise construct from components
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def cors_origins_list(self) -> List[str]:
        return (
            ["*"]
            if self.cors_origins == "*"
            else [s.strip() for s in self.cors_origins.split(",") if s.strip()]
        )


settings = Settings()
