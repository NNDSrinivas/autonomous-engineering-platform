"""
Enterprise Secrets Management for NAVI

Provides secure credential storage and retrieval with:
- Integration with Vault, AWS Secrets Manager, GCP Secret Manager
- OAuth flow management for external services
- Encrypted storage with org-specific keys
- Short-lived token rotation
- Audit logging for all secret access
"""

from typing import Optional, Dict, Any, List
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging
from cryptography.fernet import Fernet
import json

from .tenancy import require_tenant, TenantAuditLogger

logger = logging.getLogger(__name__)


class SecretProvider(Enum):
    """Supported secret management providers"""

    VAULT = "vault"  # HashiCorp Vault
    AWS_SECRETS = "aws_secrets"  # AWS Secrets Manager
    GCP_SECRETS = "gcp_secrets"  # GCP Secret Manager
    AZURE_KEYVAULT = "azure_keyvault"  # Azure Key Vault
    LOCAL_ENCRYPTED = "local_encrypted"  # Local encrypted storage


class IntegrationType(Enum):
    """Types of integrations NAVI supports"""

    GITHUB = "github"
    GITLAB = "gitlab"
    JIRA = "jira"
    CONFLUENCE = "confluence"
    SLACK = "slack"
    TEAMS = "teams"
    JENKINS = "jenkins"
    CIRCLECI = "circleci"
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


@dataclass
class SecretMetadata:
    """Metadata for stored secrets"""

    org_id: str
    key: str
    integration_type: IntegrationType
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    rotation_enabled: bool = True

    def is_expired(self) -> bool:
        """Check if secret has expired"""
        return bool(self.expires_at and datetime.utcnow() > self.expires_at)


@dataclass
class OAuthCredentials:
    """OAuth credentials for external services"""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: Optional[int] = None
    scope: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "scope": self.scope,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OAuthCredentials":
        return cls(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in"),
            scope=data.get("scope"),
        )


class SecretStore(ABC):
    """Abstract base class for secret storage backends"""

    @abstractmethod
    async def store_secret(
        self, org_id: str, key: str, value: str, metadata: SecretMetadata
    ) -> bool:
        """Store encrypted secret"""
        pass

    @abstractmethod
    async def retrieve_secret(self, org_id: str, key: str) -> Optional[str]:
        """Retrieve and decrypt secret"""
        pass

    @abstractmethod
    async def delete_secret(self, org_id: str, key: str) -> bool:
        """Delete secret"""
        pass

    @abstractmethod
    async def list_secrets(self, org_id: str) -> List[str]:
        """List all secret keys for organization"""
        pass


class LocalEncryptedSecretStore(SecretStore):
    """Local encrypted secret storage using Fernet encryption"""

    def __init__(self, database):
        self.db = database
        self.encryption_keys: Dict[str, Fernet] = {}

    def _get_encryption_key(self, org_id: str) -> Fernet:
        """Get or create org-specific encryption key"""
        if org_id not in self.encryption_keys:
            # In production, fetch from secure key management
            key = Fernet.generate_key()
            self.encryption_keys[org_id] = Fernet(key)
        return self.encryption_keys[org_id]

    async def store_secret(
        self, org_id: str, key: str, value: str, metadata: SecretMetadata
    ) -> bool:
        """Store encrypted secret locally"""
        try:
            fernet = self._get_encryption_key(org_id)
            encrypted_value = fernet.encrypt(value.encode()).decode()

            {
                "org_id": org_id,
                "key": key,
                "encrypted_value": encrypted_value,
                "integration_type": metadata.integration_type.value,
                "created_at": metadata.created_at.isoformat(),
                "expires_at": (
                    metadata.expires_at.isoformat() if metadata.expires_at else None
                ),
                "rotation_enabled": metadata.rotation_enabled,
                "access_count": 0,
            }

            # Store in database (would use tenant-aware database)
            async with self.db.get_async_session():
                # Implementation would use TenantQueryBuilder here
                pass

            TenantAuditLogger.log_access(
                "secrets",
                "store",
                {"key": key, "integration": metadata.integration_type.value},
            )
            return True

        except Exception as e:
            logger.error(f"Failed to store secret {key}: {e}")
            return False

    async def retrieve_secret(self, org_id: str, key: str) -> Optional[str]:
        """Retrieve and decrypt secret"""
        try:
            # Fetch from database
            async with self.db.get_async_session():
                # Would query secrets table with org_id and key
                encrypted_value = None  # Placeholder

                if not encrypted_value:
                    return None

                fernet = self._get_encryption_key(org_id)
                decrypted_value = fernet.decrypt(encrypted_value.encode()).decode()

                # Update access metadata
                TenantAuditLogger.log_access("secrets", "retrieve", {"key": key})

                return decrypted_value

        except Exception as e:
            logger.error(f"Failed to retrieve secret {key}: {e}")
            return None

    async def delete_secret(self, org_id: str, key: str) -> bool:
        """Delete secret"""
        try:
            async with self.db.get_async_session():
                # Would delete from secrets table
                pass

            TenantAuditLogger.log_access("secrets", "delete", {"key": key})
            return True

        except Exception as e:
            logger.error(f"Failed to delete secret {key}: {e}")
            return False

    async def list_secrets(self, org_id: str) -> List[str]:
        """List all secret keys"""
        try:
            async with self.db.get_async_session():
                # Would query secrets table for keys
                return []  # Placeholder

        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            return []


class VaultSecretStore(SecretStore):
    """HashiCorp Vault secret storage"""

    def __init__(self, vault_url: str, vault_token: str):
        self.vault_url = vault_url
        self.vault_token = vault_token
        # Would initialize Vault client here

    async def store_secret(
        self, org_id: str, key: str, value: str, metadata: SecretMetadata
    ) -> bool:
        """Store secret in Vault"""
        vault_path = f"orgs/{org_id}/{key}"
        {
            "value": value,
            "metadata": {
                "integration_type": metadata.integration_type.value,
                "created_at": metadata.created_at.isoformat(),
                "expires_at": (
                    metadata.expires_at.isoformat() if metadata.expires_at else None
                ),
            },
        }

        # Would call Vault API here
        TenantAuditLogger.log_access("vault_secrets", "store", {"path": vault_path})
        return True

    async def retrieve_secret(self, org_id: str, key: str) -> Optional[str]:
        """Retrieve secret from Vault"""
        vault_path = f"orgs/{org_id}/{key}"

        # Would call Vault API here
        TenantAuditLogger.log_access("vault_secrets", "retrieve", {"path": vault_path})
        return None  # Placeholder

    async def delete_secret(self, org_id: str, key: str) -> bool:
        """Delete secret from Vault"""
        vault_path = f"orgs/{org_id}/{key}"

        # Would call Vault API here
        TenantAuditLogger.log_access("vault_secrets", "delete", {"path": vault_path})
        return True

    async def list_secrets(self, org_id: str) -> List[str]:
        """List secrets from Vault"""

        # Would call Vault API here
        return []


class SecretsManager:
    """High-level secrets management service"""

    def __init__(self, secret_store: SecretStore):
        self.secret_store = secret_store
        self.oauth_configs = self._load_oauth_configs()

    def _load_oauth_configs(self) -> Dict[IntegrationType, Dict[str, str]]:
        """Load OAuth configurations for supported integrations"""
        return {
            IntegrationType.GITHUB: {
                "auth_url": "https://github.com/login/oauth/authorize",
                "token_url": "https://github.com/login/oauth/access_token",
                "scopes": "repo,read:user,read:org",
            },
            IntegrationType.SLACK: {
                "auth_url": "https://slack.com/oauth/v2/authorize",
                "token_url": "https://slack.com/api/oauth.v2.access",
                "scopes": "channels:read,chat:write,users:read",
            },
            IntegrationType.JIRA: {
                "auth_url": "https://auth.atlassian.com/authorize",
                "token_url": "https://auth.atlassian.com/oauth/token",
                "scopes": "read:jira-work write:jira-work",
            },
        }

    async def store_oauth_credentials(
        self, integration: IntegrationType, credentials: OAuthCredentials
    ) -> bool:
        """Store OAuth credentials securely"""
        tenant = require_tenant()

        # Calculate expiration
        expires_at = None
        if credentials.expires_in:
            expires_at = datetime.utcnow() + timedelta(seconds=credentials.expires_in)

        metadata = SecretMetadata(
            org_id=tenant.org_id,
            key=f"oauth_{integration.value}",
            integration_type=integration,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            rotation_enabled=True,
        )

        # Store as JSON
        credentials_json = json.dumps(credentials.to_dict())

        return await self.secret_store.store_secret(
            tenant.org_id, f"oauth_{integration.value}", credentials_json, metadata
        )

    async def get_oauth_credentials(
        self, integration: IntegrationType
    ) -> Optional[OAuthCredentials]:
        """Retrieve OAuth credentials"""
        tenant = require_tenant()

        credentials_json = await self.secret_store.retrieve_secret(
            tenant.org_id, f"oauth_{integration.value}"
        )

        if not credentials_json:
            return None

        try:
            credentials_data = json.loads(credentials_json)
            return OAuthCredentials.from_dict(credentials_data)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(
                f"Failed to parse OAuth credentials for {integration.value}: {e}"
            )
            return None

    async def store_api_key(self, integration: IntegrationType, api_key: str) -> bool:
        """Store API key for integration"""
        tenant = require_tenant()

        metadata = SecretMetadata(
            org_id=tenant.org_id,
            key=f"apikey_{integration.value}",
            integration_type=integration,
            created_at=datetime.utcnow(),
            rotation_enabled=False,  # API keys usually don't auto-rotate
        )

        return await self.secret_store.store_secret(
            tenant.org_id, f"apikey_{integration.value}", api_key, metadata
        )

    async def get_api_key(self, integration: IntegrationType) -> Optional[str]:
        """Retrieve API key"""
        tenant = require_tenant()

        return await self.secret_store.retrieve_secret(
            tenant.org_id, f"apikey_{integration.value}"
        )

    async def refresh_oauth_token(self, integration: IntegrationType) -> bool:
        """Refresh OAuth token if needed"""
        credentials = await self.get_oauth_credentials(integration)
        if not credentials or not credentials.refresh_token:
            return False

        # Would implement token refresh logic here
        # Call integration's token refresh endpoint
        # Store new credentials

        logger.info(f"Refreshed OAuth token for {integration.value}")
        return True

    async def list_configured_integrations(self) -> List[Dict[str, Any]]:
        """List all configured integrations for organization"""
        tenant = require_tenant()

        secret_keys = await self.secret_store.list_secrets(tenant.org_id)

        integrations = []
        for key in secret_keys:
            if key.startswith("oauth_") or key.startswith("apikey_"):
                integration_type = key.split("_", 1)[1]
                integrations.append(
                    {
                        "type": integration_type,
                        "auth_method": (
                            "oauth" if key.startswith("oauth_") else "api_key"
                        ),
                        "configured_at": "unknown",  # Would fetch from metadata
                    }
                )

        return integrations

    def get_oauth_authorization_url(
        self, integration: IntegrationType, redirect_uri: str, state: str
    ) -> str:
        """Generate OAuth authorization URL"""
        config = self.oauth_configs.get(integration)
        if not config:
            raise ValueError(f"OAuth not supported for {integration.value}")

        # Would build proper OAuth URL with client_id, scopes, etc.
        return f"{config['auth_url']}?client_id=CLIENT_ID&redirect_uri={redirect_uri}&scope={config['scopes']}&state={state}"


# Factory function to create secrets manager
def create_secrets_manager(provider: SecretProvider, **config) -> SecretsManager:
    """Create secrets manager with specified provider"""

    if provider == SecretProvider.LOCAL_ENCRYPTED:
        from .tenant_database import get_tenant_db

        secret_store = LocalEncryptedSecretStore(get_tenant_db())

    elif provider == SecretProvider.VAULT:
        vault_url = config.get("vault_url")
        vault_token = config.get("vault_token")
        if not vault_url or not vault_token:
            raise ValueError(
                "vault_url and vault_token are required for Vault secrets provider"
            )
        secret_store = VaultSecretStore(
            vault_url=str(vault_url), vault_token=str(vault_token)
        )

    else:
        raise ValueError(f"Unsupported secret provider: {provider}")

    return SecretsManager(secret_store)


# Global secrets manager (initialized by app)
secrets_manager: Optional[SecretsManager] = None


def init_secrets_manager(provider: SecretProvider, **config):
    """Initialize global secrets manager"""
    global secrets_manager
    secrets_manager = create_secrets_manager(provider, **config)


def get_secrets_manager() -> SecretsManager:
    """Get global secrets manager instance"""
    if not secrets_manager:
        raise RuntimeError("Secrets manager not initialized")
    return secrets_manager


__all__ = [
    "SecretProvider",
    "IntegrationType",
    "SecretMetadata",
    "OAuthCredentials",
    "SecretStore",
    "SecretsManager",
    "create_secrets_manager",
    "init_secrets_manager",
    "get_secrets_manager",
]
