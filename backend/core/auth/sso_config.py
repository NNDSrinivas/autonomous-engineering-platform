"""
SSO configuration helpers.

Supports multi-provider OIDC and placeholder SAML configuration.
Primary configuration is via SSO_PROVIDERS_JSON, with a legacy single-provider
fallback for backward compatibility.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_provider(provider: dict[str, Any]) -> dict[str, Any]:
    data = dict(provider)
    data.pop("client_secret", None)
    return data


def _load_providers_from_env() -> list[dict[str, Any]]:
    raw = os.getenv("SSO_PROVIDERS_JSON", "").strip()
    if not raw:
        return []
    try:
        providers = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning(
            f"Failed to parse SSO_PROVIDERS_JSON: {e}. Check environment variable format."
        )
        return []
    if isinstance(providers, dict):
        providers = [providers]
    if not isinstance(providers, list):
        return []
    normalized: list[dict[str, Any]] = []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        if not provider.get("id"):
            continue
        if provider.get("type") not in {"oidc", "saml"}:
            continue
        normalized.append(provider)
    return normalized


def _legacy_oidc_provider() -> dict[str, Any] | None:
    if not _env_bool("SSO_OIDC_ENABLED", False):
        return None

    issuer = os.getenv("SSO_OIDC_ISSUER", "")
    auth_url = os.getenv("SSO_OIDC_AUTH_URL", "")
    client_id = os.getenv("SSO_OIDC_CLIENT_ID", "")
    redirect_uri = os.getenv("SSO_OIDC_REDIRECT_URI", "")

    if not (issuer and auth_url and client_id and redirect_uri):
        return None

    return {
        "id": os.getenv("SSO_OIDC_ID", "oidc-default"),
        "type": "oidc",
        "name": os.getenv("SSO_OIDC_NAME", "OIDC SSO"),
        "issuer": issuer,
        "auth_url": auth_url,
        "token_url": os.getenv("SSO_OIDC_TOKEN_URL", ""),
        "userinfo_url": os.getenv("SSO_OIDC_USERINFO_URL", ""),
        "client_id": client_id,
        "client_secret": os.getenv("SSO_OIDC_CLIENT_SECRET", ""),
        "scope": os.getenv("SSO_OIDC_SCOPE", "openid profile email"),
        "redirect_uri": redirect_uri,
    }


def _legacy_saml_provider() -> dict[str, Any] | None:
    if not _env_bool("SSO_SAML_ENABLED", False):
        return None

    entrypoint = os.getenv("SSO_SAML_ENTRYPOINT", "")
    issuer = os.getenv("SSO_SAML_ISSUER", "")
    callback_url = os.getenv("SSO_SAML_CALLBACK_URL", "")

    if not (entrypoint and issuer and callback_url):
        return None

    return {
        "id": os.getenv("SSO_SAML_ID", "saml-default"),
        "type": "saml",
        "name": os.getenv("SSO_SAML_NAME", "SAML SSO"),
        "entrypoint": entrypoint,
        "issuer": issuer,
        "callback_url": callback_url,
    }


def _load_providers() -> list[dict[str, Any]]:
    providers = _load_providers_from_env()
    if providers:
        return providers

    legacy: list[dict[str, Any]] = []
    oidc = _legacy_oidc_provider()
    if oidc:
        legacy.append(oidc)
    saml = _legacy_saml_provider()
    if saml:
        legacy.append(saml)
    return legacy


def list_sso_providers() -> list[dict[str, Any]]:
    return [_safe_provider(p) for p in _load_providers()]


def get_provider(provider_id: str) -> dict[str, Any] | None:
    for provider in _load_providers():
        if provider.get("id") == provider_id:
            return provider
    return None


def get_oidc_provider(provider_id: str) -> dict[str, Any] | None:
    provider = get_provider(provider_id)
    if provider and provider.get("type") == "oidc":
        return provider
    return None
