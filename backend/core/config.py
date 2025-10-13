"""
Configuration management for Autonomous Engineering Intelligence Platform
"""
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    app_env: str = "dev"
    app_name: str = "autonomous-engineering-platform"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    realtime_port: int = 8001

    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://localhost:3001"  # comma-separated list or "*"

    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "mentor"
    db_password: str = "mentor"
    db_name: str = "mentor"

    redis_url: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def cors_origins_list(self) -> List[str]:
        return ["*"] if self.cors_origins == "*" else [s.strip() for s in self.cors_origins.split(",") if s.strip()]

settings = Settings()
