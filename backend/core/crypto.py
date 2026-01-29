import base64
import json
import os
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.fernet import Fernet

# Import boto3 only when needed for production
try:
    import boto3

    HAS_BOTO3 = True
except ImportError:
    boto3 = None
    HAS_BOTO3 = False


class TokenEncryptionError(Exception):
    pass


class AuditEncryptionError(Exception):
    pass


def _is_dev_mode() -> bool:
    """Check if running in development mode."""
    app_env = os.environ.get("APP_ENV", "dev").lower()
    return app_env in ["dev", "development", "local"]


def _get_dev_key() -> str:
    """Get or generate a development encryption key for Fernet."""
    # Use a consistent dev key for development
    # In production, this should never be used
    dev_key = os.environ.get("DEV_ENCRYPTION_KEY")
    if dev_key:
        return dev_key

    # Generate a fixed URL-safe base64 key for development (not secure, but consistent)
    # This is a proper 32-byte key encoded in URL-safe base64 format for Fernet
    return "Uqktv94Z9tHa5WsVKJVtBsc-QylZWQ4wTg3_sXekPaA="  # Fixed Fernet-compatible key


def _encode_parts(parts: Tuple[bytes, ...]) -> str:
    # Combine parts with a separator then base64 the whole payload to keep DB-safe string
    payload = b"|".join(parts)
    return base64.b64encode(payload).decode()


def _decode_parts(payload_b64: str) -> Tuple[bytes, ...]:
    try:
        payload = base64.b64decode(payload_b64)
        return tuple(payload.split(b"|"))
    except Exception as e:
        raise TokenEncryptionError("Invalid encrypted token format") from e


def encrypt_token(plaintext_token: str) -> str:
    """Envelope-encrypt a token using AWS KMS to protect the data key and AES-GCM for content.
    In development mode, uses simple Fernet encryption.

    Returns a base64 string safe to store in DB. Format (base64 of):
    version|encrypted_data_key|nonce|ciphertext (production)
    OR dev|encrypted_token (development)
    """
    # Development mode: use simple encryption
    if _is_dev_mode():
        try:
            key = _get_dev_key()
            f = Fernet(key.encode())
            encrypted = f.encrypt(plaintext_token.encode())
            # Format: dev|encrypted_token
            return _encode_parts((b"dev", encrypted))
        except Exception as e:
            raise TokenEncryptionError(f"Development encryption failed: {e}") from e

    # Production mode: use AWS KMS
    key_id = os.environ.get("TOKEN_ENCRYPTION_KEY_ID")
    if not key_id:
        raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY_ID is not set")

    if not HAS_BOTO3:
        raise TokenEncryptionError(
            "boto3 is required for production encryption but not installed"
        )

    kms = boto3.client("kms")
    try:
        resp = kms.generate_data_key(KeyId=key_id, KeySpec="AES_256")
        data_key_plain = resp["Plaintext"]
        data_key_encrypted = resp["CiphertextBlob"]

        aesgcm = AESGCM(data_key_plain)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext_token.encode(), None)

        return _encode_parts(
            (
                b"v1",
                base64.b64encode(data_key_encrypted),
                base64.b64encode(nonce),
                base64.b64encode(ciphertext),
            )
        )
    except Exception as e:
        raise TokenEncryptionError("encryption failed") from e


def decrypt_token(encrypted_blob: str) -> str:
    """Decrypt token previously encrypted with encrypt_token.
    Handles both development and production encryption formats.
    """
    try:
        parts = _decode_parts(encrypted_blob)

        # Check if it's a development token
        if len(parts) == 2 and parts[0] == b"dev":
            if not _is_dev_mode():
                raise TokenEncryptionError("Development token used in production mode")

            key = _get_dev_key()
            f = Fernet(key.encode())
            encrypted_token = parts[1]
            plaintext = f.decrypt(encrypted_token)
            return plaintext.decode()

        # Production mode KMS decryption
        if len(parts) != 4:
            raise TokenEncryptionError("unexpected encrypted token parts")

        key_id = os.environ.get("TOKEN_ENCRYPTION_KEY_ID")
        if not key_id:
            raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY_ID is not set")

        if not HAS_BOTO3:
            raise TokenEncryptionError(
                "boto3 is required for production encryption but not installed"
            )

        kms = boto3.client("kms")

        # version = parts[0]
        encrypted_data_key = base64.b64decode(parts[1])
        nonce = base64.b64decode(parts[2])
        ciphertext = base64.b64decode(parts[3])

        dec = kms.decrypt(CiphertextBlob=encrypted_data_key)
        data_key_plain = dec["Plaintext"]

        aesgcm = AESGCM(data_key_plain)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode()
    except TokenEncryptionError:
        raise
    except Exception as e:
        raise TokenEncryptionError("decryption failed") from e


def _get_audit_fernet() -> Fernet:
    key = os.environ.get("AUDIT_ENCRYPTION_KEY")
    if not key:
        raise AuditEncryptionError("AUDIT_ENCRYPTION_KEY is not set")
    return Fernet(key.encode())


def encrypt_audit_payload(payload: dict) -> dict:
    """Encrypt audit payload for at-rest protection."""
    f = _get_audit_fernet()
    token = f.encrypt(json.dumps(payload).encode()).decode()
    wrapper: dict = {"encrypted": True, "ciphertext": token}
    key_id = os.environ.get("AUDIT_ENCRYPTION_KEY_ID")
    if key_id:
        wrapper["key_id"] = key_id
    return wrapper


def decrypt_audit_payload(wrapper: dict) -> dict:
    """Decrypt audit payload wrapper back to plaintext dict."""
    if not wrapper or not isinstance(wrapper, dict) or not wrapper.get("encrypted"):
        return wrapper
    token = wrapper.get("ciphertext")
    if not token:
        raise AuditEncryptionError("Missing ciphertext")
    f = _get_audit_fernet()
    plaintext = f.decrypt(token.encode()).decode()
    return json.loads(plaintext)
