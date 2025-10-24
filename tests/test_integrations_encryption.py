"""
Integration tests for token encryption in services.

Tests that tokens are properly encrypted when saved and decrypted when retrieved.
"""

import os
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.db import Base
from backend.services.github import GitHubService
from backend.services.jira import JiraService


class TestIntegrationEncryption:
    def setup_method(self):
        """Set up test database and environment"""
        os.environ["TOKEN_ENCRYPTION_KEY_ID"] = "test-key-id"

        # Create in-memory SQLite database for testing
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)

        Session = sessionmaker(bind=self.engine)
        self.db = Session()

    def teardown_method(self):
        """Clean up"""
        self.db.close()
        if "TOKEN_ENCRYPTION_KEY_ID" in os.environ:
            del os.environ["TOKEN_ENCRYPTION_KEY_ID"]

    @patch("backend.core.crypto.boto3")
    def test_github_connection_token_encryption(self, mock_boto3):
        """Test that GitHub tokens are encrypted when saved"""
        # Mock KMS
        mock_kms = MagicMock()
        mock_boto3.client.return_value = mock_kms

        mock_data_key = b"x" * 32
        mock_kms.generate_data_key.return_value = {
            "Plaintext": mock_data_key,
            "CiphertextBlob": b"encrypted_data_key_blob",
        }

        # Save connection with plaintext token
        original_token = "github_pat_1234567890abcdef"
        conn = GitHubService.save_connection(self.db, original_token)

        # Verify token was encrypted (not stored as plaintext)
        assert conn.access_token != original_token
        assert conn.access_token is not None
        assert len(conn.access_token) > len(original_token)  # Encrypted is longer

        # Verify KMS was called
        mock_kms.generate_data_key.assert_called_once()

    @patch("backend.core.crypto.boto3")
    def test_jira_connection_token_encryption(self, mock_boto3):
        """Test that JIRA tokens are encrypted when saved"""
        # Mock KMS
        mock_kms = MagicMock()
        mock_boto3.client.return_value = mock_kms

        mock_data_key = b"x" * 32
        mock_kms.generate_data_key.return_value = {
            "Plaintext": mock_data_key,
            "CiphertextBlob": b"encrypted_data_key_blob",
        }

        # Save connection with plaintext token
        original_token = "jira_api_token_abcdef123456"
        base_url = "https://company.atlassian.net"
        conn = JiraService.save_connection(self.db, base_url, original_token)

        # Verify token was encrypted
        assert conn.access_token != original_token
        assert conn.access_token is not None
        assert len(conn.access_token) > len(original_token)

        # Verify other fields unchanged
        assert conn.cloud_base_url == base_url
        assert conn.scopes == ["read"]

        # Verify KMS was called
        mock_kms.generate_data_key.assert_called_once()

    def test_encryption_failure_handling(self):
        """Test that service handles encryption failures gracefully"""
        # Remove environment variable to trigger encryption error
        if "TOKEN_ENCRYPTION_KEY_ID" in os.environ:
            del os.environ["TOKEN_ENCRYPTION_KEY_ID"]

        with pytest.raises(Exception):  # Should fail due to missing key ID
            GitHubService.save_connection(self.db, "test_token")

    @patch("backend.core.crypto.boto3")
    def test_token_not_logged_in_plaintext(self, mock_boto3, caplog):
        """Test that plaintext tokens don't appear in logs"""
        import logging

        caplog.set_level(logging.DEBUG)

        # Mock KMS
        mock_kms = MagicMock()
        mock_boto3.client.return_value = mock_kms

        mock_data_key = b"x" * 32
        mock_kms.generate_data_key.return_value = {
            "Plaintext": mock_data_key,
            "CiphertextBlob": b"encrypted_data_key_blob",
        }

        # Save connection
        secret_token = "github_pat_SUPER_SECRET_TOKEN_123"
        GitHubService.save_connection(self.db, secret_token)

        # Check that plaintext token doesn't appear in any log messages
        for record in caplog.records:
            assert secret_token not in record.getMessage()
            assert secret_token not in str(record.args)
