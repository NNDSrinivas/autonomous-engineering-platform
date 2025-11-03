"""
Configuration management for Autonomous Engineering Intelligence Platform
"""

import os
import string
from typing import List
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Module-level constants for performance
PUNCTUATION_SET = set(string.punctuation)


class Settings(BaseSettings):
    # Use 'ignore' to prevent pydantic validation errors in production
    # while still catching config issues via validator in dev/test environments
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )
    app_env: str = "dev"
    app_name: str = "autonomous-engineering-platform"

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values):
        """Enforce 'forbid' behavior in dev/test environments."""
        if isinstance(values, dict):
            # Check environment independently to prevent bypass via app_env manipulation
            app_env = os.environ.get("APP_ENV", "dev")
            if app_env in ["dev", "test"]:
                # Check for any fields in the input data that aren't defined in the model
                allowed_fields = set(cls.model_fields.keys())
                input_fields = set(values.keys())
                extra_fields = input_fields - allowed_fields
                if extra_fields:
                    raise ValueError(
                        f"Extra fields not permitted in app_env '{app_env}'. {len(extra_fields)} extra field(s) found."
                    )
        return values

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
    redis_max_connections: int = (
        20  # Maximum connections in Redis pool (default 20 for high concurrency)
    )
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
    # Security keys: Override via environment variables in production
    secret_key: str = "dev-secret-change-in-production"
    jwt_secret: str = "dev-jwt-secret-change-in-production"

    # API Configuration
    api_v1_prefix: str = "/api"

    def __init__(self, **values):
        super().__init__(**values)
        # Validate secrets in production
        if self.environment.lower() == "production":
            if self.secret_key == "dev-secret-change-in-production":
                raise ValueError(
                    "In production, 'secret_key' must be set to a secure value via environment variable."
                )
            if self.jwt_secret == "dev-jwt-secret-change-in-production":
                raise ValueError(
                    "In production, 'jwt_secret' must be set to a secure value via environment variable."
                )

            # Validate minimum security requirements for secrets
            self._validate_secret_security(self.secret_key, "secret_key")
            self._validate_secret_security(self.jwt_secret, "jwt_secret")

    def _validate_secret_security(self, secret: str, secret_name: str) -> None:
        """Validate that secrets meet minimum security requirements."""
        if len(secret) < 32:
            raise ValueError(
                f"In production, '{secret_name}' must be at least 32 characters long for security."
            )

        # Check for basic complexity (at least mix of letters and numbers/symbols)
        has_letters = any(c.isalpha() for c in secret)
        has_numbers = any(c.isdigit() for c in secret)
        # Use module-level set to avoid repeated set creation; per-character lookup is O(1), but overall check is O(n)
        has_symbols = any(c in PUNCTUATION_SET for c in secret)

        if not (has_letters and (has_numbers or has_symbols)):
            raise ValueError(
                f"In production, '{secret_name}' must contain a mix of letters and numbers/symbols for security."
            )

    # Storage
    vector_db_path: str = "./data/vector_store"

    # Vector search backend configuration (PR-16)
    # Options: pgvector (production, PostgreSQL), faiss (experimental), json (fallback, linear scan)
    vector_backend: str = "pgvector"
    # NOTE: embed_dim must match the actual embedding model's output dimension and must be kept in sync with the EMBED_DIM environment variable used in database migrations.
    embed_dim: int = 1536  # Embedding dimension (OpenAI text-embedding-ada-002 default)
    pgvector_index: str = "hnsw"  # Options: hnsw | ivfflat
    bm25_enabled: bool = True  # Enable BM25/FTS hybrid ranking
    faiss_index_path: str = "./data/faiss/index.faiss"  # FAISS index file path

    # Features
    enable_real_time: bool = True
    enable_github_integration: bool = True
    enable_analytics: bool = True
    enable_ai_assistance: bool = True
    enable_audit_logging: bool = Field(
        default=True,
        alias="ENABLE_AUDIT_LOGGING",
        description="Disable in test environments to prevent DB errors from missing audit tables or incomplete schema initialization",
    )

    # Common file extensions to validate against for code analysis
    valid_extensions: List[str] = [
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".go",
        ".rs",
        ".php",
        ".rb",
        ".cs",
        ".swift",
        ".kt",
        ".scala",
        ".html",
        ".css",
        ".scss",
        ".sass",
        ".vue",
        ".svelte",
        ".md",
        ".txt",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".sh",
        ".bat",
        ".ps1",
        ".sql",
        ".dockerfile",
        ".tf",
    ]

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


def get_settings() -> Settings:
    """Get the current settings instance (for dependency injection)."""
    return settings
