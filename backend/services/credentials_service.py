"""
Credentials Management Service

Centralized credential management for:
- LLM Providers (OpenAI, Anthropic, Google, etc.)
- Cloud Providers (AWS, GCP, Azure)
- CI/CD (GitHub, GitLab, CircleCI)
- Databases (PostgreSQL, MongoDB, Redis)
- Payment Processors (Stripe, PayPal)

Supports BYOK (Bring Your Own Key) - users can provide their own credentials.
Credentials can come from:
1. Environment variables (default)
2. User-provided BYOK credentials (stored per session/project)
3. Encrypted database storage (for persistent user credentials)

Security:
- Credentials are never logged
- BYOK credentials are session-scoped (not persisted by default)
- Database-stored credentials use AES encryption
"""

import os
import base64
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Union

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


logger = logging.getLogger(__name__)


class CredentialProvider(Enum):
    """Supported credential providers"""

    # LLM Providers
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    GROQ = "groq"
    OPENROUTER = "openrouter"
    TOGETHER = "together"
    MISTRAL = "mistral"
    OLLAMA = "ollama"

    # Cloud Providers
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    DIGITALOCEAN = "digitalocean"
    VERCEL = "vercel"
    NETLIFY = "netlify"

    # CI/CD
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    CIRCLECI = "circleci"
    JENKINS = "jenkins"

    # Databases
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    REDIS = "redis"
    SUPABASE = "supabase"
    PLANETSCALE = "planetscale"

    # Payments
    STRIPE = "stripe"
    PAYPAL = "paypal"

    # Communication
    SLACK = "slack"
    DISCORD = "discord"
    SENDGRID = "sendgrid"
    TWILIO = "twilio"

    # Monitoring
    DATADOG = "datadog"
    SENTRY = "sentry"
    NEWRELIC = "newrelic"

    # Storage
    S3 = "s3"
    GCS = "gcs"
    CLOUDFLARE_R2 = "cloudflare_r2"


@dataclass
class CredentialSpec:
    """Specification for a credential"""

    provider: CredentialProvider
    required_fields: List[str]
    optional_fields: List[str] = field(default_factory=list)
    env_mapping: Dict[str, str] = field(default_factory=dict)
    validation_url: Optional[str] = None


# Credential specifications for each provider
CREDENTIAL_SPECS: Dict[CredentialProvider, CredentialSpec] = {
    # LLM Providers
    CredentialProvider.OPENAI: CredentialSpec(
        provider=CredentialProvider.OPENAI,
        required_fields=["api_key"],
        optional_fields=["organization"],
        env_mapping={"api_key": "OPENAI_API_KEY", "organization": "OPENAI_ORG_ID"},
    ),
    CredentialProvider.ANTHROPIC: CredentialSpec(
        provider=CredentialProvider.ANTHROPIC,
        required_fields=["api_key"],
        env_mapping={"api_key": "ANTHROPIC_API_KEY"},
    ),
    CredentialProvider.GOOGLE: CredentialSpec(
        provider=CredentialProvider.GOOGLE,
        required_fields=["api_key"],
        env_mapping={"api_key": "GOOGLE_API_KEY"},
    ),
    CredentialProvider.GROQ: CredentialSpec(
        provider=CredentialProvider.GROQ,
        required_fields=["api_key"],
        env_mapping={"api_key": "GROQ_API_KEY"},
    ),
    CredentialProvider.OPENROUTER: CredentialSpec(
        provider=CredentialProvider.OPENROUTER,
        required_fields=["api_key"],
        env_mapping={"api_key": "OPENROUTER_API_KEY"},
    ),
    CredentialProvider.TOGETHER: CredentialSpec(
        provider=CredentialProvider.TOGETHER,
        required_fields=["api_key"],
        env_mapping={"api_key": "TOGETHER_API_KEY"},
    ),
    CredentialProvider.MISTRAL: CredentialSpec(
        provider=CredentialProvider.MISTRAL,
        required_fields=["api_key"],
        env_mapping={"api_key": "MISTRAL_API_KEY"},
    ),
    # Cloud Providers
    CredentialProvider.AWS: CredentialSpec(
        provider=CredentialProvider.AWS,
        required_fields=["access_key_id", "secret_access_key"],
        optional_fields=["region", "session_token"],
        env_mapping={
            "access_key_id": "AWS_ACCESS_KEY_ID",
            "secret_access_key": "AWS_SECRET_ACCESS_KEY",
            "region": "AWS_REGION",
            "session_token": "AWS_SESSION_TOKEN",
        },
    ),
    CredentialProvider.GCP: CredentialSpec(
        provider=CredentialProvider.GCP,
        required_fields=["service_account_json"],
        optional_fields=["project_id"],
        env_mapping={
            "service_account_json": "GOOGLE_APPLICATION_CREDENTIALS",
            "project_id": "GCP_PROJECT_ID",
        },
    ),
    CredentialProvider.AZURE: CredentialSpec(
        provider=CredentialProvider.AZURE,
        required_fields=["subscription_id", "tenant_id", "client_id", "client_secret"],
        env_mapping={
            "subscription_id": "AZURE_SUBSCRIPTION_ID",
            "tenant_id": "AZURE_TENANT_ID",
            "client_id": "AZURE_CLIENT_ID",
            "client_secret": "AZURE_CLIENT_SECRET",
        },
    ),
    CredentialProvider.VERCEL: CredentialSpec(
        provider=CredentialProvider.VERCEL,
        required_fields=["token"],
        optional_fields=["team_id"],
        env_mapping={"token": "VERCEL_TOKEN", "team_id": "VERCEL_TEAM_ID"},
    ),
    # CI/CD
    CredentialProvider.GITHUB: CredentialSpec(
        provider=CredentialProvider.GITHUB,
        required_fields=["token"],
        optional_fields=["username"],
        env_mapping={"token": "GITHUB_TOKEN", "username": "GITHUB_USERNAME"},
    ),
    CredentialProvider.GITLAB: CredentialSpec(
        provider=CredentialProvider.GITLAB,
        required_fields=["token"],
        optional_fields=["url"],
        env_mapping={"token": "GITLAB_TOKEN", "url": "GITLAB_URL"},
    ),
    CredentialProvider.CIRCLECI: CredentialSpec(
        provider=CredentialProvider.CIRCLECI,
        required_fields=["token"],
        env_mapping={"token": "CIRCLECI_TOKEN"},
    ),
    # Databases
    CredentialProvider.POSTGRESQL: CredentialSpec(
        provider=CredentialProvider.POSTGRESQL,
        required_fields=["host", "database", "username", "password"],
        optional_fields=["port", "ssl_mode"],
        env_mapping={"connection_string": "DATABASE_URL"},
    ),
    CredentialProvider.SUPABASE: CredentialSpec(
        provider=CredentialProvider.SUPABASE,
        required_fields=["url", "anon_key"],
        optional_fields=["service_role_key"],
        env_mapping={
            "url": "SUPABASE_URL",
            "anon_key": "SUPABASE_ANON_KEY",
            "service_role_key": "SUPABASE_SERVICE_ROLE_KEY",
        },
    ),
    # Payments
    CredentialProvider.STRIPE: CredentialSpec(
        provider=CredentialProvider.STRIPE,
        required_fields=["secret_key"],
        optional_fields=["publishable_key", "webhook_secret"],
        env_mapping={
            "secret_key": "STRIPE_SECRET_KEY",
            "publishable_key": "STRIPE_PUBLISHABLE_KEY",
            "webhook_secret": "STRIPE_WEBHOOK_SECRET",
        },
    ),
    # Communication
    CredentialProvider.SLACK: CredentialSpec(
        provider=CredentialProvider.SLACK,
        required_fields=["bot_token"],
        optional_fields=["signing_secret"],
        env_mapping={
            "bot_token": "SLACK_BOT_TOKEN",
            "signing_secret": "SLACK_SIGNING_SECRET",
        },
    ),
    CredentialProvider.SENDGRID: CredentialSpec(
        provider=CredentialProvider.SENDGRID,
        required_fields=["api_key"],
        env_mapping={"api_key": "SENDGRID_API_KEY"},
    ),
    # Monitoring
    CredentialProvider.SENTRY: CredentialSpec(
        provider=CredentialProvider.SENTRY,
        required_fields=["dsn"],
        optional_fields=["auth_token"],
        env_mapping={"dsn": "SENTRY_DSN", "auth_token": "SENTRY_AUTH_TOKEN"},
    ),
    CredentialProvider.DATADOG: CredentialSpec(
        provider=CredentialProvider.DATADOG,
        required_fields=["api_key"],
        optional_fields=["app_key"],
        env_mapping={"api_key": "DD_API_KEY", "app_key": "DD_APP_KEY"},
    ),
}


class CredentialsService:
    """
    Centralized credentials management with BYOK support.

    Usage:
        # Get from environment (default)
        creds = CredentialsService()
        openai_key = creds.get_credential(CredentialProvider.OPENAI, "api_key")

        # BYOK - user provides their own key
        creds.set_byok_credential(CredentialProvider.OPENAI, {"api_key": "user-key"})
        openai_key = creds.get_credential(CredentialProvider.OPENAI, "api_key")

        # Get all credentials for a provider
        aws_creds = creds.get_provider_credentials(CredentialProvider.AWS)

        # Validate credentials
        is_valid = await creds.validate_credentials(CredentialProvider.STRIPE)
    """

    def __init__(
        self,
        encryption_key: Optional[str] = None,
        db_session=None,
    ):
        """
        Initialize the credentials service.

        Args:
            encryption_key: Key for encrypting stored credentials
            db_session: Optional database session for persistent storage
        """
        self.db = db_session
        self._byok_credentials: Dict[str, Dict[str, str]] = {}
        self._cached_credentials: Dict[str, Dict[str, str]] = {}

        # Set up encryption if available
        self._fernet = None
        if CRYPTO_AVAILABLE and encryption_key:
            key = self._derive_key(encryption_key)
            self._fernet = Fernet(key)

    def _derive_key(self, password: str) -> bytes:
        """Derive an encryption key from a password"""
        salt = b"navi_creds_salt_v1"  # In production, use a random salt per user
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def set_byok_credential(
        self,
        provider: Union[str, CredentialProvider],
        credentials: Dict[str, str],
    ) -> None:
        """
        Set BYOK (Bring Your Own Key) credentials for a provider.

        These credentials are stored in memory (not persisted) and take
        precedence over environment variables.

        Args:
            provider: The credential provider
            credentials: Dict of credential fields (api_key, etc.)
        """
        if isinstance(provider, str):
            provider = CredentialProvider(provider)

        provider_key = provider.value
        self._byok_credentials[provider_key] = credentials

        logger.info(
            f"BYOK credentials set for {provider_key} (fields: {list(credentials.keys())})"
        )

    def clear_byok_credential(self, provider: Union[str, CredentialProvider]) -> None:
        """Clear BYOK credentials for a provider"""
        if isinstance(provider, str):
            provider = CredentialProvider(provider)

        provider_key = provider.value
        self._byok_credentials.pop(provider_key, None)
        logger.info(f"BYOK credentials cleared for {provider_key}")

    def get_credential(
        self,
        provider: Union[str, CredentialProvider],
        field: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get a specific credential field.

        Priority:
        1. BYOK credentials (user-provided)
        2. Environment variables
        3. Cached/stored credentials
        4. Default value

        Args:
            provider: The credential provider
            field: The field to get (api_key, access_key_id, etc.)
            default: Default value if not found

        Returns:
            The credential value or default
        """
        if isinstance(provider, str):
            provider = CredentialProvider(provider)

        provider_key = provider.value

        # Check BYOK first
        if provider_key in self._byok_credentials:
            byok = self._byok_credentials[provider_key]
            if field in byok:
                return byok[field]

        # Check environment variables
        spec = CREDENTIAL_SPECS.get(provider)
        if spec and field in spec.env_mapping:
            env_var = spec.env_mapping[field]
            env_value = os.environ.get(env_var)
            if env_value:
                return env_value

        # Check cache
        if provider_key in self._cached_credentials:
            cached = self._cached_credentials[provider_key]
            if field in cached:
                return cached[field]

        return default

    def get_provider_credentials(
        self,
        provider: Union[str, CredentialProvider],
    ) -> Dict[str, Optional[str]]:
        """
        Get all credentials for a provider.

        Returns a dict with all required and optional fields.

        Args:
            provider: The credential provider

        Returns:
            Dict of field -> value (None if not found)
        """
        if isinstance(provider, str):
            provider = CredentialProvider(provider)

        spec = CREDENTIAL_SPECS.get(provider)
        if not spec:
            return {}

        result = {}
        all_fields = spec.required_fields + spec.optional_fields

        for field in all_fields:
            result[field] = self.get_credential(provider, field)

        return result

    def has_credentials(
        self,
        provider: Union[str, CredentialProvider],
    ) -> bool:
        """
        Check if all required credentials are available for a provider.

        Args:
            provider: The credential provider

        Returns:
            True if all required fields are present
        """
        if isinstance(provider, str):
            provider = CredentialProvider(provider)

        spec = CREDENTIAL_SPECS.get(provider)
        if not spec:
            return False

        for field in spec.required_fields:
            if not self.get_credential(provider, field):
                return False

        return True

    def list_configured_providers(self) -> List[str]:
        """
        List all providers that have credentials configured.

        Returns:
            List of provider names with valid credentials
        """
        configured = []
        for provider in CredentialProvider:
            if self.has_credentials(provider):
                configured.append(provider.value)
        return configured

    def get_llm_api_key(
        self,
        provider: str,
    ) -> Optional[str]:
        """
        Convenience method to get LLM API key.

        Args:
            provider: LLM provider name (openai, anthropic, etc.)

        Returns:
            The API key or None
        """
        try:
            cred_provider = CredentialProvider(provider.lower())
            return self.get_credential(cred_provider, "api_key")
        except ValueError:
            # Unknown provider, try environment variable
            env_var = f"{provider.upper()}_API_KEY"
            return os.environ.get(env_var)

    def get_cloud_credentials(
        self,
        provider: str,
    ) -> Dict[str, Optional[str]]:
        """
        Get cloud provider credentials.

        Args:
            provider: Cloud provider (aws, gcp, azure)

        Returns:
            Dict of credentials
        """
        try:
            cred_provider = CredentialProvider(provider.lower())
            return self.get_provider_credentials(cred_provider)
        except ValueError:
            return {}

    async def validate_credentials(
        self,
        provider: Union[str, CredentialProvider],
    ) -> bool:
        """
        Validate credentials by making a test API call.

        Args:
            provider: The credential provider

        Returns:
            True if credentials are valid
        """
        import httpx

        if isinstance(provider, str):
            provider = CredentialProvider(provider)

        if not self.has_credentials(provider):
            return False

        try:
            # Provider-specific validation
            if provider == CredentialProvider.OPENAI:
                api_key = self.get_credential(provider, "api_key")
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    return resp.status_code == 200

            elif provider == CredentialProvider.ANTHROPIC:
                api_key = self.get_credential(provider, "api_key")
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "claude-3-haiku-20240307",
                            "max_tokens": 1,
                            "messages": [{"role": "user", "content": "Hi"}],
                        },
                    )
                    # 200 or 429 (rate limit) means key is valid
                    return resp.status_code in (200, 429)

            elif provider == CredentialProvider.GITHUB:
                token = self.get_credential(provider, "token")
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://api.github.com/user",
                        headers={"Authorization": f"token {token}"},
                    )
                    return resp.status_code == 200

            elif provider == CredentialProvider.AWS:
                # AWS validation requires boto3
                import boto3

                creds = self.get_provider_credentials(provider)
                sts = boto3.client(
                    "sts",
                    aws_access_key_id=creds.get("access_key_id"),
                    aws_secret_access_key=creds.get("secret_access_key"),
                    region_name=creds.get("region", "us-east-1"),
                )
                sts.get_caller_identity()
                return True

            # Default: assume valid if credentials exist
            return True

        except Exception as e:
            logger.warning(f"Credential validation failed for {provider.value}: {e}")
            return False


# Global credentials service instance
_credentials_service: Optional[CredentialsService] = None


def get_credentials_service() -> CredentialsService:
    """Get the global credentials service instance"""
    global _credentials_service
    if _credentials_service is None:
        _credentials_service = CredentialsService()
    return _credentials_service


def set_byok(provider: str, credentials: Dict[str, str]) -> None:
    """Convenience function to set BYOK credentials"""
    service = get_credentials_service()
    service.set_byok_credential(provider, credentials)


def get_api_key(provider: str) -> Optional[str]:
    """Convenience function to get an API key"""
    service = get_credentials_service()
    return service.get_llm_api_key(provider)
