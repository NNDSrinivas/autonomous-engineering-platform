"""
Configuration management for Autonomous Engineering Intelligence Platform
"""
import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # API Configuration
    api_port: int = Field(default=8000, env="API_PORT")
    realtime_port: int = Field(default=8001, env="REALTIME_PORT")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Security
    jwt_secret_key: str = Field(default="dev-secret", env="JWT_SECRET_KEY")
    encryption_key: str = Field(default="dev-encryption-key", env="ENCRYPTION_KEY")
    
    # Database
    database_url: str = Field(default="sqlite+aiosqlite:///./data/engineering_platform.db", env="DATABASE_URL")
    vector_db_path: str = Field(default="./data/vector_store", env="VECTOR_DB_PATH")
    
    # Redis (Optional)
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    
    # AI Services
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4", env="OPENAI_MODEL")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    
    # External Integrations
    github_token: Optional[str] = Field(default=None, env="GITHUB_TOKEN")
    github_webhook_secret: Optional[str] = Field(default=None, env="GITHUB_WEBHOOK_SECRET")
    
    jira_url: Optional[str] = Field(default=None, env="JIRA_URL")
    jira_user: Optional[str] = Field(default=None, env="JIRA_USER")
    jira_token: Optional[str] = Field(default=None, env="JIRA_TOKEN")
    
    # Autonomous Coding
    enable_autonomous_coding: bool = Field(default=False, env="ENABLE_AUTONOMOUS_CODING")
    max_autonomous_files_per_pr: int = Field(default=5, env="MAX_AUTONOMOUS_FILES_PER_PR")
    require_human_approval: bool = Field(default=True, env="REQUIRE_HUMAN_APPROVAL")
    
    # Memory and Context
    max_context_window: int = Field(default=8000, env="MAX_CONTEXT_WINDOW")
    memory_retention_days: int = Field(default=365, env="MEMORY_RETENTION_DAYS")
    enable_team_memory: bool = Field(default=True, env="ENABLE_TEAM_MEMORY")
    
    # CORS
    enable_cors: bool = Field(default=True, env="ENABLE_CORS")
    allow_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"],
        env="ALLOW_ORIGINS"
    )
    
    # Monitoring
    enable_analytics: bool = Field(default=False, env="ENABLE_ANALYTICS")
    sentry_dsn: Optional[str] = Field(default=None, env="SENTRY_DSN")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings"""
    return Settings()
