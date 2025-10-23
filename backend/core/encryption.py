"""
Token encryption utilities for secure credential storage.

This module provides encryption/decryption functions for API tokens and credentials
using Fernet (AES-128-CBC with HMAC authentication) from the cryptography library.

Security considerations:
- Encryption key must be 32 URL-safe base64-encoded bytes
- Key should be stored in environment variable, not in code
- In production, key should reference a KMS or HSM service
- Supports key rotation via environment variable updates
"""

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import structlog

logger = structlog.get_logger(__name__)


class EncryptionError(Exception):
    """Base exception for encryption operations"""
    pass


class EncryptionKeyError(EncryptionError):
    """Exception raised when encryption key is invalid or missing"""
    pass


class TokenEncryptor:
    """
    Handles encryption and decryption of API tokens and credentials.
    
    Uses Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256) for
    authenticated encryption of sensitive tokens.
    """
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize the token encryptor.
        
        Args:
            encryption_key: Base64-encoded 32-byte key. If None, reads from
                          environment variable TOKEN_ENCRYPTION_KEY.
        
        Raises:
            EncryptionKeyError: If key is missing or invalid
        """
        key = encryption_key or os.environ.get("TOKEN_ENCRYPTION_KEY")
        
        if not key:
            raise EncryptionKeyError(
                "Encryption key not provided. Set TOKEN_ENCRYPTION_KEY environment variable."
            )
        
        try:
            # Validate key format - Fernet requires 32 URL-safe base64-encoded bytes
            key_bytes = base64.urlsafe_b64decode(key)
            if len(key_bytes) != 32:
                raise EncryptionKeyError(
                    f"Encryption key must be 32 bytes, got {len(key_bytes)} bytes"
                )
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
            logger.info("Token encryptor initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize token encryptor", error=str(e))
            raise EncryptionKeyError(f"Invalid encryption key: {e}")
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext token.
        
        Args:
            plaintext: The plaintext token to encrypt
        
        Returns:
            Base64-encoded encrypted token
        
        Raises:
            EncryptionError: If encryption fails
        """
        if not plaintext:
            return ""
        
        try:
            encrypted_bytes = self._fernet.encrypt(plaintext.encode('utf-8'))
            encrypted_str = encrypted_bytes.decode('utf-8')
            logger.debug("Token encrypted successfully", length=len(plaintext))
            return encrypted_str
        except Exception as e:
            logger.error("Token encryption failed", error=str(e))
            raise EncryptionError(f"Failed to encrypt token: {e}")
    
    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt an encrypted token.
        
        Args:
            encrypted: Base64-encoded encrypted token
        
        Returns:
            Decrypted plaintext token
        
        Raises:
            EncryptionError: If decryption fails (invalid token or wrong key)
        """
        if not encrypted:
            return ""
        
        try:
            decrypted_bytes = self._fernet.decrypt(encrypted.encode('utf-8'))
            plaintext = decrypted_bytes.decode('utf-8')
            logger.debug("Token decrypted successfully")
            return plaintext
        except InvalidToken:
            logger.error("Token decryption failed - invalid token or wrong key")
            raise EncryptionError(
                "Failed to decrypt token: invalid token or wrong encryption key"
            )
        except Exception as e:
            logger.error("Token decryption failed", error=str(e))
            raise EncryptionError(f"Failed to decrypt token: {e}")


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.
    
    Returns:
        Base64-encoded 32-byte encryption key suitable for Fernet
    
    Example:
        >>> key = generate_encryption_key()
        >>> print(f"TOKEN_ENCRYPTION_KEY={key}")
    """
    key = Fernet.generate_key()
    return key.decode('utf-8')


def derive_key_from_password(password: str, salt: Optional[bytes] = None) -> tuple[str, bytes]:
    """
    Derive an encryption key from a password using PBKDF2.
    
    This is useful for development/testing but NOT recommended for production.
    In production, use a proper KMS or secrets management service.
    
    Args:
        password: Password to derive key from
        salt: Optional salt (generated if not provided)
    
    Returns:
        Tuple of (base64-encoded key, salt used)
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,  # OWASP recommendation as of 2023
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode('utf-8')))
    return key.decode('utf-8'), salt


# Global encryptor instance (initialized on first use)
_encryptor: Optional[TokenEncryptor] = None


def get_encryptor() -> TokenEncryptor:
    """
    Get the global token encryptor instance.
    
    Returns:
        Singleton TokenEncryptor instance
    
    Raises:
        EncryptionKeyError: If encryption key is not configured
    """
    global _encryptor
    if _encryptor is None:
        _encryptor = TokenEncryptor()
    return _encryptor


def encrypt_token(plaintext: str) -> str:
    """
    Convenience function to encrypt a token using the global encryptor.
    
    Args:
        plaintext: Plaintext token to encrypt
    
    Returns:
        Encrypted token
    """
    return get_encryptor().encrypt(plaintext)


def decrypt_token(encrypted: str) -> str:
    """
    Convenience function to decrypt a token using the global encryptor.
    
    Args:
        encrypted: Encrypted token to decrypt
    
    Returns:
        Plaintext token
    """
    return get_encryptor().decrypt(encrypted)
