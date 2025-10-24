import base64
import os
from typing import Tuple

import boto3
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class TokenEncryptionError(Exception):
    pass


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

    Returns a base64 string safe to store in DB. Format (base64 of):
    version|encrypted_data_key|nonce|ciphertext
    """
    key_id = os.environ.get("TOKEN_ENCRYPTION_KEY_ID")
    if not key_id:
        raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY_ID is not set")

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

    Expects the same envelope format and will call KMS.decrypt on the encrypted data key.
    """
    key_id = os.environ.get("TOKEN_ENCRYPTION_KEY_ID")
    if not key_id:
        raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY_ID is not set")

    kms = boto3.client("kms")
    try:
        parts = _decode_parts(encrypted_blob)
        # parts: version, encrypted_data_key_b64, nonce_b64, ciphertext_b64
        if len(parts) != 4:
            raise TokenEncryptionError("unexpected encrypted token parts")

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
