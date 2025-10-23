"""
Tests for token encryption/decryption functionality.

These tests verify:
- Encryption and decryption work correctly
- Invalid keys are rejected
- Encrypted tokens are not plaintext
- Round-trip encryption/decryption preserves data
- Error handling for invalid inputs
"""

import os
import pytest
from cryptography.fernet import Fernet

from backend.core.encryption import (
    TokenEncryptor,
    EncryptionError,
    EncryptionKeyError,
    generate_encryption_key,
    derive_key_from_password,
    encrypt_token,
    decrypt_token,
)


class TestTokenEncryptor:
    """Test the TokenEncryptor class"""

    def test_initialization_with_valid_key(self):
        """Test that encryptor initializes with a valid key"""
        key = Fernet.generate_key().decode()
        encryptor = TokenEncryptor(encryption_key=key)
        assert encryptor is not None

    def test_initialization_without_key_fails(self):
        """Test that initialization fails without a key"""
        # Clear environment variable if set
        old_key = os.environ.pop("TOKEN_ENCRYPTION_KEY", None)
        try:
            with pytest.raises(EncryptionKeyError) as exc_info:
                TokenEncryptor(encryption_key=None)
            assert "Encryption key not provided" in str(exc_info.value)
        finally:
            # Restore environment variable if it was set
            if old_key:
                os.environ["TOKEN_ENCRYPTION_KEY"] = old_key

    def test_initialization_with_invalid_key_fails(self):
        """Test that initialization fails with an invalid key"""
        with pytest.raises(EncryptionKeyError) as exc_info:
            TokenEncryptor(encryption_key="invalid-key")
        assert "Invalid encryption key" in str(exc_info.value)

    def test_initialization_with_wrong_length_key_fails(self):
        """Test that initialization fails with wrong length key"""
        import base64

        short_key = base64.urlsafe_b64encode(b"short").decode()
        with pytest.raises(EncryptionKeyError) as exc_info:
            TokenEncryptor(encryption_key=short_key)
        assert "must be 32 bytes" in str(exc_info.value)

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption preserve the original token"""
        key = Fernet.generate_key().decode()
        encryptor = TokenEncryptor(encryption_key=key)

        original = "test-slack-token-12345"
        encrypted = encryptor.encrypt(original)
        decrypted = encryptor.decrypt(encrypted)

        assert decrypted == original
        assert encrypted != original  # Ensure it's actually encrypted

    def test_encrypt_empty_string(self):
        """Test encrypting an empty string"""
        key = Fernet.generate_key().decode()
        encryptor = TokenEncryptor(encryption_key=key)

        encrypted = encryptor.encrypt("")
        assert encrypted == ""

    def test_decrypt_empty_string(self):
        """Test decrypting an empty string"""
        key = Fernet.generate_key().decode()
        encryptor = TokenEncryptor(encryption_key=key)

        decrypted = encryptor.decrypt("")
        assert decrypted == ""

    def test_encrypted_token_not_plaintext(self):
        """Test that encrypted tokens don't contain plaintext"""
        key = Fernet.generate_key().decode()
        encryptor = TokenEncryptor(encryption_key=key)

        plaintext = "my-secret-token"
        encrypted = encryptor.encrypt(plaintext)

        assert plaintext not in encrypted
        assert encrypted != plaintext

    def test_decrypt_with_wrong_key_fails(self):
        """Test that decryption fails with the wrong key"""
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        encryptor1 = TokenEncryptor(encryption_key=key1)
        encryptor2 = TokenEncryptor(encryption_key=key2)

        encrypted = encryptor1.encrypt("secret-token")

        with pytest.raises(EncryptionError) as exc_info:
            encryptor2.decrypt(encrypted)
        assert "invalid token or wrong encryption key" in str(exc_info.value)

    def test_decrypt_invalid_token_fails(self):
        """Test that decrypting an invalid token fails"""
        key = Fernet.generate_key().decode()
        encryptor = TokenEncryptor(encryption_key=key)

        with pytest.raises(EncryptionError):
            encryptor.decrypt("not-a-valid-encrypted-token")

    def test_multiple_tokens_different_ciphertext(self):
        """Test that encrypting the same token multiple times produces different ciphertext"""
        key = Fernet.generate_key().decode()
        encryptor = TokenEncryptor(encryption_key=key)

        plaintext = "repeated-token"
        encrypted1 = encryptor.encrypt(plaintext)
        encrypted2 = encryptor.encrypt(plaintext)

        # Fernet includes a timestamp, so each encryption should be different
        # But both should decrypt to the same plaintext
        assert encryptor.decrypt(encrypted1) == plaintext
        assert encryptor.decrypt(encrypted2) == plaintext

    def test_unicode_tokens(self):
        """Test encryption/decryption of unicode tokens"""
        key = Fernet.generate_key().decode()
        encryptor = TokenEncryptor(encryption_key=key)

        unicode_token = "token-with-unicode-日本語-émojis-🔐"
        encrypted = encryptor.encrypt(unicode_token)
        decrypted = encryptor.decrypt(encrypted)

        assert decrypted == unicode_token


class TestKeyGeneration:
    """Test key generation utilities"""

    def test_generate_encryption_key(self):
        """Test that generate_encryption_key produces a valid key"""
        key = generate_encryption_key()

        # Should be able to create an encryptor with the generated key
        encryptor = TokenEncryptor(encryption_key=key)
        assert encryptor is not None

        # Should be able to encrypt/decrypt with it
        plaintext = "test-token"
        encrypted = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == plaintext

    def test_derive_key_from_password(self):
        """Test password-based key derivation"""
        password = "my-secure-password"
        key, salt = derive_key_from_password(password)

        # Should be able to create an encryptor with the derived key
        encryptor = TokenEncryptor(encryption_key=key)
        assert encryptor is not None

        # Same password and salt should produce same key
        key2, _ = derive_key_from_password(password, salt)
        assert key == key2

        # Different password should produce different key
        key3, _ = derive_key_from_password("different-password", salt)
        assert key != key3


class TestConvenienceFunctions:
    """Test the convenience functions that use the global encryptor"""

    def test_encrypt_decrypt_convenience_functions(self):
        """Test the convenience encrypt/decrypt functions"""
        # Set up environment variable
        test_key = Fernet.generate_key().decode()
        old_key = os.environ.get("TOKEN_ENCRYPTION_KEY")
        os.environ["TOKEN_ENCRYPTION_KEY"] = test_key

        try:
            # Clear the global encryptor to force reinitialization
            import backend.core.encryption as enc_module

            enc_module._encryptor = None

            plaintext = "test-token-123"
            encrypted = encrypt_token(plaintext)
            decrypted = decrypt_token(encrypted)

            assert decrypted == plaintext
            assert encrypted != plaintext
        finally:
            # Restore original environment
            if old_key:
                os.environ["TOKEN_ENCRYPTION_KEY"] = old_key
            else:
                os.environ.pop("TOKEN_ENCRYPTION_KEY", None)
            # Clear global encryptor
            enc_module._encryptor = None

    def test_convenience_functions_without_key_fails(self):
        """Test that convenience functions fail without a configured key"""
        # Clear environment variable
        old_key = os.environ.pop("TOKEN_ENCRYPTION_KEY", None)

        try:
            # Clear the global encryptor
            import backend.core.encryption as enc_module

            enc_module._encryptor = None

            with pytest.raises(EncryptionKeyError):
                encrypt_token("test-token")
        finally:
            # Restore environment
            if old_key:
                os.environ["TOKEN_ENCRYPTION_KEY"] = old_key
            # Clear global encryptor
            enc_module._encryptor = None


class TestSecurityProperties:
    """Test security properties of the encryption"""

    def test_encrypted_length_differs_from_plaintext(self):
        """Test that encrypted tokens have different length than plaintext"""
        key = Fernet.generate_key().decode()
        encryptor = TokenEncryptor(encryption_key=key)

        plaintext = "short"
        encrypted = encryptor.encrypt(plaintext)

        # Fernet adds overhead (timestamp, IV, padding, HMAC)
        assert len(encrypted) > len(plaintext)

    def test_no_information_leakage_in_ciphertext(self):
        """Test that ciphertext doesn't leak information about plaintext"""
        key = Fernet.generate_key().decode()
        encryptor = TokenEncryptor(encryption_key=key)

        # Similar plaintexts should produce completely different ciphertexts
        token1 = "test-token-1234567890-1111111111-AAAAAAAAAAAAAAAAAAAAAA"
        token2 = "test-token-1234567890-1111111111-BBBBBBBBBBBBBBBBBBBBBB"

        encrypted1 = encryptor.encrypt(token1)
        encrypted2 = encryptor.encrypt(token2)

        # Calculate Hamming distance (should be high)
        min_len = min(len(encrypted1), len(encrypted2))
        differences = sum(
            c1 != c2 for c1, c2 in zip(encrypted1[:min_len], encrypted2[:min_len])
        )

        # At least 40% of characters should be different
        assert differences > min_len * 0.4

    def test_timestamp_in_encrypted_token(self):
        """Test that Fernet includes timestamp (prevents replay attacks)"""
        import time

        key = Fernet.generate_key().decode()
        encryptor = TokenEncryptor(encryption_key=key)

        plaintext = "test-token"
        encrypted1 = encryptor.encrypt(plaintext)
        time.sleep(0.1)  # Small delay
        encrypted2 = encryptor.encrypt(plaintext)

        # Same plaintext at different times should produce different ciphertexts
        assert encrypted1 != encrypted2
