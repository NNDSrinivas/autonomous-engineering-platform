"""
Audit payload encryption helpers.
"""

from __future__ import annotations

from typing import Any

from cryptography.fernet import Fernet, InvalidToken

import logging as std_logging

logger = std_logging.getLogger(__name__)


class AuditEncryptionError(Exception):
    """Raised when audit payload encryption/decryption fails."""


def _build_fernet(key: str) -> Fernet:
    try:
        return Fernet(key.encode())
    except Exception as exc:
        raise AuditEncryptionError("Invalid audit encryption key") from exc


def encrypt_payload(payload: dict[str, Any], key: str, key_id: str) -> dict[str, Any]:
    """Encrypt audit payload and return a wrapped payload object."""
    fernet = _build_fernet(key)
    try:
        ciphertext = fernet.encrypt(_serialize_payload(payload))
        return {
            "encrypted": True,
            "key_id": key_id,
            "ciphertext": ciphertext.decode(),
        }
    except Exception as exc:
        logger.error("Audit payload encryption failed: %s", exc)
        raise AuditEncryptionError("Audit payload encryption failed") from exc


def decrypt_payload(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Decrypt audit payload wrapper."""
    if not payload.get("encrypted") or "ciphertext" not in payload:
        raise AuditEncryptionError("Payload is not encrypted")
    fernet = _build_fernet(key)
    try:
        plaintext = fernet.decrypt(payload["ciphertext"].encode())
        return _deserialize_payload(plaintext)
    except InvalidToken as exc:
        raise AuditEncryptionError("Audit payload decryption failed") from exc


def _serialize_payload(payload: dict[str, Any]) -> bytes:
    import json

    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode()


def _deserialize_payload(raw: bytes) -> dict[str, Any]:
    import json

    return json.loads(raw.decode())
