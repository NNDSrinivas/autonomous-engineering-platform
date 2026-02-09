"""
Configuration management for Autonomous Engineering Intelligence Platform

ARCHITECTURAL DEBT WARNING (P1 - High Priority):
================================================================================
This module (backend/core/config.py) duplicates functionality with
backend/core/settings.py, creating confusion and maintenance overhead.

Issue: Two separate Settings classes exist:
- backend/core/settings.py (27 files importing) - Simple settings
- backend/core/config.py (75 files importing) - Complex settings with validation

Impact: 102 files affected, developers confused about which to use.

Action Required: Consolidate into single Settings class.
Tracking: See docs/SETTINGS_CONSOLIDATION_TODO.md for detailed refactoring plan.

Estimated Effort: 3.5 days (28 hours)
Timeline: After current production deployment (post Feb 26, 2026)

DO NOT extend either Settings class without consulting the consolidation plan.
================================================================================
"""

import os
import string
import threading
from typing import Optional, List
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.security import sanitize_for_logging
from backend.core.settings import normalize_env

# Module-level constants for performance
PUNCTUATION_SET = set(string.punctuation)

# Cache APP_ENV at module load time for consistent behavior.
# NOTE: These are cached for performance and consistency, but this means
# that changes to the environment variable after import will not be reflected.
# For testing or hot-reload scenarios, use `_reset_env_cache()` to refresh.
# Thread-safety: Protected by _ENV_CACHE_LOCK for multi-threaded environments.
_ENV_CACHE_LOCK = threading.Lock()
_CACHED_APP_ENV = os.environ.get("APP_ENV", "dev")
_CACHED_APP_ENV_SET = "APP_ENV" in os.environ


def _reset_env_cache():
    """
    Reset the cached APP_ENV values from the current environment.
    This is useful for testing or hot-reload scenarios where the environment
    may change after module import.

    Thread-safe: Uses lock to prevent race conditions in multi-threaded environments.
    """
    global _CACHED_APP_ENV, _CACHED_APP_ENV_SET
    with _ENV_CACHE_LOCK:
        _CACHED_APP_ENV = os.environ.get("APP_ENV", "dev")
        _CACHED_APP_ENV_SET = "APP_ENV" in os.environ


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
        """Enforce 'forbid' behavior for extra fields in dev/test environments and ensure app_env consistency.

        Security Rationale:
        - In development and test environments, this validator raises an error if any extra (undefined)
          fields are present in the configuration. This helps catch configuration mistakes and typos early,
          ensuring that only explicitly defined settings are used.
        - In production, extra fields are allowed (via the 'ignore' setting in model_config) to prevent
          configuration errors from breaking deployed systems. This is a deliberate trade-off favoring
          availability and robustness in production, at the cost of potentially ignoring unexpected fields.

        Important: This behavior is a significant deviation from standard Pydantic models where the 'extra'
        config option is static. Here, stricter validation is enforced only in non-production environments.
        Future maintainers should be aware of this trade-off: while it helps catch errors early in dev/test,
        it may allow unnoticed configuration issues in production.

        Note: This validator uses module-level cached environment variables that are set at import time.
        If you need to change the environment during tests, call _reset_env_cache() manually after
        updating os.environ to refresh the cached values.
        """
        if isinstance(values, dict):
            # Check environment independently to prevent bypass via app_env manipulation
            # Use cached values for consistent behavior (thread-safe read)
            with _ENV_CACHE_LOCK:
                env_app_env_set = _CACHED_APP_ENV_SET
                env_app_env = _CACHED_APP_ENV
            input_app_env = values.get("app_env")
            if (
                input_app_env is not None
                and env_app_env_set
                and input_app_env != env_app_env
            ):
                raise ValueError(
                    f"Inconsistent app_env: input 'app_env' is '{sanitize_for_logging(str(input_app_env))}', "
                    f"but environment variable 'APP_ENV' is '{sanitize_for_logging(str(env_app_env))}'. "
                    f"Please ensure they match."
                )
            if env_app_env in ["dev", "test"]:
                # Check for any fields in the input data that aren't defined in the model
                allowed_fields = set(cls.model_fields.keys())
                input_fields = set(values.keys())
                extra_fields = input_fields - allowed_fields
                if extra_fields:
                    sanitized_fields = ", ".join(
                        sorted(sanitize_for_logging(str(f)) for f in extra_fields)
                    )
                    raise ValueError(
                        f"Extra fields not permitted in app_env '{sanitize_for_logging(str(env_app_env))}': {sanitized_fields}"
                    )
            # Allow auth bypass automatically in test/ci unless explicitly configured
            # Default to "development" if env_app_env is None to avoid normalize_env error
            normalized_env = normalize_env(env_app_env or "development")
            if (
                normalized_env in ("test", "ci")
                and "ALLOW_DEV_AUTH_BYPASS" not in os.environ
                and "allow_dev_auth_bypass" not in values
            ):
                values["allow_dev_auth_bypass"] = True
        else:
            # Log warning if values is not a dict (unexpected validation context)
            import logging

            logging.warning(
                "Settings validator received non-dict values (type: %s). Skipping validation.",
                type(values).__name__,
            )
        return values

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    realtime_port: int = 8001

    log_level: str = "INFO"
    cors_origins: str = (
        ""  # comma-separated list of allowed origins; empty means strict deny
    )
    allow_dev_cors: bool = False  # Explicit dev override for localhost/vscode-webview
    allow_vscode_webview: bool = True  # Allow VS Code webview origins when enabled

    # VS Code/webview auth enforcement
    vscode_auth_required: bool = True
    allow_dev_auth_bypass: bool = False

    # Database configuration
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "mentor"
    db_password: str = "mentor"
    db_name: str = "mentor"
    database_url: Optional[str] = None  # Allow override with full URL

    redis_url: str = "redis://localhost:6379/0"

    # OAuth Device Code Configuration
    oauth_device_use_in_memory_store: bool = False
    oauth_device_auto_approve: bool = False
    oauth_device_code_ttl_seconds: int = 600
    oauth_device_access_token_ttl_seconds: int = 86400
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
    openai_model: str = "gpt-3.5-turbo"
    anthropic_api_key: Optional[str] = None
    default_llm_provider: str = "openai"

    # Jira Integration Configuration
    aep_jira_base_url: Optional[str] = None
    aep_jira_email: Optional[str] = None
    aep_jira_api_token: Optional[str] = None
    aep_jira_jql_assigned_to_me: str = "assignee = currentUser() ORDER BY updated DESC"

    # Platform Configuration
    debug: bool = False
    environment: str = "development"
    # Security keys: Override via environment variables in production
    secret_key: str = "dev-secret-change-in-production"
    jwt_secret: str = "dev-jwt-secret-change-in-production"
    jwt_enabled: bool = False
    jwt_secret_previous: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_audience: Optional[str] = None
    jwt_issuer: Optional[str] = None
    jwt_jwks_url: Optional[str] = None
    jwt_jwks_cache_ttl: int = 300

    # API Configuration
    api_v1_prefix: str = "/api"
    public_base_url: Optional[str] = None  # External base URL for OAuth callbacks

    # Auth0 Configuration
    auth0_domain: Optional[str] = None
    auth0_client_id: Optional[str] = None
    auth0_client_secret: Optional[str] = None
    auth0_audience: Optional[str] = None
    auth0_algorithm: str = "RS256"

    # AEP JWT Session Management
    aep_jwt_secret: Optional[str] = None
    aep_jwt_issuer: str = "aep"
    aep_jwt_ttl_seconds: int = 3600
    aep_jwt_alg: str = "HS256"

    # Organization and Webhook Secrets
    x_org_id: Optional[str] = None
    jira_webhook_secret: Optional[str] = None
    github_webhook_secret: Optional[str] = None
    slack_signing_secret: Optional[str] = None
    teams_webhook_secret: Optional[str] = None
    docs_webhook_secret: Optional[str] = None
    ci_webhook_secret: Optional[str] = None
    zoom_webhook_secret: Optional[str] = None
    meet_webhook_secret: Optional[str] = None

    # OAuth connector settings
    oauth_state_ttl_seconds: int = 600
    slack_client_id: Optional[str] = None
    slack_client_secret: Optional[str] = None
    slack_oauth_scopes: Optional[str] = None
    slack_user_scopes: Optional[str] = None
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None
    github_oauth_scopes: Optional[str] = None
    confluence_client_id: Optional[str] = None
    confluence_client_secret: Optional[str] = None
    confluence_oauth_scopes: Optional[str] = None
    teams_client_id: Optional[str] = None
    teams_client_secret: Optional[str] = None
    teams_tenant_id: Optional[str] = None
    teams_oauth_scopes: Optional[str] = None
    zoom_account_id: Optional[str] = None
    zoom_client_id: Optional[str] = None
    zoom_client_secret: Optional[str] = None
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_oauth_scopes: Optional[str] = None

    # GitLab Integration
    gitlab_client_id: Optional[str] = None
    gitlab_client_secret: Optional[str] = None
    gitlab_oauth_scopes: Optional[str] = None
    gitlab_base_url: Optional[str] = None  # For self-hosted GitLab
    gitlab_webhook_secret: Optional[str] = None

    # Linear Integration
    linear_client_id: Optional[str] = None
    linear_client_secret: Optional[str] = None
    linear_oauth_scopes: Optional[str] = None
    linear_webhook_secret: Optional[str] = None

    # Notion Integration
    notion_client_id: Optional[str] = None
    notion_client_secret: Optional[str] = None

    # Bitbucket Integration
    bitbucket_client_id: Optional[str] = None
    bitbucket_client_secret: Optional[str] = None
    bitbucket_oauth_scopes: Optional[str] = None
    bitbucket_webhook_secret: Optional[str] = None

    # Jira OAuth Integration (Atlassian Cloud)
    jira_client_id: Optional[str] = None
    jira_client_secret: Optional[str] = None
    jira_oauth_scopes: Optional[str] = None

    # Discord Integration (Phase 2)
    discord_client_id: Optional[str] = None
    discord_client_secret: Optional[str] = None
    discord_oauth_scopes: Optional[str] = None
    discord_bot_token: Optional[str] = None
    discord_webhook_secret: Optional[str] = None

    # Google Docs/Drive Integration (Phase 2)
    gdocs_client_id: Optional[str] = None
    gdocs_client_secret: Optional[str] = None
    gdocs_oauth_scopes: Optional[str] = None

    # Figma Integration (Phase 2)
    figma_client_id: Optional[str] = None
    figma_client_secret: Optional[str] = None
    figma_oauth_scopes: Optional[str] = None
    figma_access_token: Optional[str] = None  # Personal access token
    figma_webhook_passcode: Optional[str] = None

    # Loom Integration (Phase 2)
    loom_access_token: Optional[str] = None

    # CircleCI Integration (Phase 3)
    circleci_client_id: Optional[str] = None
    circleci_client_secret: Optional[str] = None
    circleci_oauth_scopes: Optional[str] = None
    circleci_api_token: Optional[str] = None
    circleci_webhook_secret: Optional[str] = None

    # Vercel Integration (Phase 3)
    vercel_client_id: Optional[str] = None
    vercel_client_secret: Optional[str] = None
    vercel_oauth_scopes: Optional[str] = None
    vercel_api_token: Optional[str] = None
    vercel_webhook_secret: Optional[str] = None

    # Datadog Integration (Phase 3)
    datadog_api_key: Optional[str] = None
    datadog_app_key: Optional[str] = None
    datadog_site: str = "datadoghq.com"

    # Asana Integration (Phase 4)
    asana_client_id: Optional[str] = None
    asana_client_secret: Optional[str] = None
    asana_oauth_scopes: Optional[str] = None
    asana_access_token: Optional[str] = None
    asana_webhook_secret: Optional[str] = None

    # Trello Integration (Phase 4)
    trello_api_key: Optional[str] = None
    trello_api_token: Optional[str] = None
    trello_oauth_scopes: Optional[str] = None
    trello_webhook_secret: Optional[str] = None

    # Monday.com Integration (Phase 4)
    monday_client_id: Optional[str] = None
    monday_client_secret: Optional[str] = None
    monday_oauth_scopes: Optional[str] = None
    monday_api_token: Optional[str] = None

    # ClickUp Integration (Phase 4)
    clickup_client_id: Optional[str] = None
    clickup_client_secret: Optional[str] = None
    clickup_oauth_scopes: Optional[str] = None
    clickup_api_token: Optional[str] = None
    clickup_webhook_secret: Optional[str] = None

    # Snyk Integration (Phase 5)
    snyk_api_token: Optional[str] = None
    snyk_org_id: Optional[str] = None
    snyk_webhook_secret: Optional[str] = None

    # SonarQube Integration (Phase 5)
    sonarqube_url: Optional[str] = None
    sonarqube_token: Optional[str] = None
    sonarqube_webhook_secret: Optional[str] = None

    # PagerDuty Integration (Phase 5)
    pagerduty_api_token: Optional[str] = None
    pagerduty_webhook_secret: Optional[str] = None

    # Sentry Integration (Phase 5)
    sentry_client_id: Optional[str] = None
    sentry_client_secret: Optional[str] = None
    sentry_oauth_scopes: Optional[str] = None
    sentry_auth_token: Optional[str] = None
    sentry_org_slug: Optional[str] = None
    sentry_webhook_secret: Optional[str] = None

    # Development Authentication
    dev_user_id: Optional[str] = None

    # Organization ID
    x_org_id: Optional[str] = None

    # Jira Integration
    aep_jira_base_url: Optional[str] = None
    aep_jira_email: Optional[str] = None
    aep_jira_api_token: Optional[str] = None
    aep_jira_jql_assigned_to_me: Optional[str] = None

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

    # NAVI Memory System Configuration
    embedding_model: str = "text-embedding-3-small"  # OpenAI embedding model
    embedding_dimensions: int = 1536  # Embedding vector dimensions
    memory_cache_ttl: int = 3600  # Memory cache TTL in seconds
    memory_index_batch_size: int = 100  # Batch size for codebase indexing
    memory_max_context_items: int = 10  # Max items to include in context
    memory_min_similarity: float = 0.5  # Minimum similarity for search results

    # MCP (Model Context Protocol) Server Configuration
    mcp_enabled: bool = True  # Enable MCP server
    mcp_server_name: str = "navi-tools"  # MCP server name
    mcp_server_version: str = "1.0.0"  # MCP server version
    mcp_transport: str = "stdio"  # Transport: stdio, http, websocket
    mcp_http_port: int = 8765  # Port for HTTP transport
    mcp_websocket_port: int = 8766  # Port for WebSocket transport
    # External MCP server policy controls (enterprise safety)
    mcp_require_https: bool = True  # Enforce HTTPS for external MCP servers
    mcp_block_private_networks: bool = True  # Block localhost/private IPs
    mcp_allowed_hosts: List[str] = Field(
        default_factory=list
    )  # Optional allowlist for external MCP hosts
    mcp_allowed_tools: List[str] = [  # Tools exposed via MCP
        "git_operations",
        "database_operations",
        "code_debugging",
        "file_operations",
        "test_execution",
        "code_analysis",
    ]

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
        # Keep pytest runs self-contained to avoid hanging on missing Postgres.
        if os.getenv("PYTEST_CURRENT_TEST"):
            return "sqlite:///./data/aep_test.db"
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
