"""
Tests for integration models with encrypted tokens.

These tests verify:
- Slack and Confluence models encrypt tokens on save
- Tokens are decrypted when accessed
- Database operations work correctly with encrypted fields
"""

import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from cryptography.fernet import Fernet

from backend.core.db import Base
from backend.models.integrations import SlackConnection, ConfluenceConnection


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing"""
    # Set up encryption key
    test_key = Fernet.generate_key().decode()
    old_key = os.environ.get("TOKEN_ENCRYPTION_KEY")
    os.environ["TOKEN_ENCRYPTION_KEY"] = test_key
    
    # Create in-memory database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    # Cleanup
    session.close()
    engine.dispose()
    if old_key:
        os.environ["TOKEN_ENCRYPTION_KEY"] = old_key
    else:
        os.environ.pop("TOKEN_ENCRYPTION_KEY", None)
    
    # Clear global encryptor
    import backend.core.encryption as enc_module
    enc_module._encryptor = None


class TestSlackConnection:
    """Test SlackConnection model with encrypted bot token"""
    
    def test_slack_connection_creates(self, db_session):
        """Test that we can create a Slack connection"""
        conn = SlackConnection(
            id="slack-1",
            org_id="org-1",
            workspace_id="T1234567",
            workspace_name="Test Workspace",
            bot_token="test-token-123456"
        )
        db_session.add(conn)
        db_session.commit()
        
        assert conn.id == "slack-1"
    
    def test_bot_token_encrypted_in_database(self, db_session):
        """Test that bot token is stored encrypted in the database"""
        plaintext_token = "my-secret-bot-token-12345"
        
        conn = SlackConnection(
            id="slack-2",
            org_id="org-1",
            bot_token=plaintext_token
        )
        db_session.add(conn)
        db_session.commit()
        
        # Access the encrypted field directly
        assert conn._bot_token_encrypted is not None
        assert conn._bot_token_encrypted != plaintext_token
        assert plaintext_token not in conn._bot_token_encrypted
    
    def test_bot_token_decrypts_on_access(self, db_session):
        """Test that bot token is decrypted when accessed via property"""
        plaintext_token = "decryption-test-token"
        
        conn = SlackConnection(
            id="slack-3",
            org_id="org-1",
            bot_token=plaintext_token
        )
        db_session.add(conn)
        db_session.commit()
        
        # Access via property should return decrypted token
        assert conn.bot_token == plaintext_token
    
    def test_bot_token_roundtrip(self, db_session):
        """Test that bot token survives save/load roundtrip"""
        plaintext_token = "roundtrip-test-token-xyz"
        
        # Create and save
        conn = SlackConnection(
            id="slack-4",
            org_id="org-1",
            workspace_id="T9999999",
            bot_token=plaintext_token
        )
        db_session.add(conn)
        db_session.commit()
        
        # Clear session and reload
        db_session.expunge_all()
        loaded_conn = db_session.get(SlackConnection, "slack-4")
        
        assert loaded_conn is not None
        assert loaded_conn.bot_token == plaintext_token
    
    def test_bot_token_update(self, db_session):
        """Test that we can update the bot token"""
        conn = SlackConnection(
            id="slack-5",
            org_id="org-1",
            bot_token="original-token"
        )
        db_session.add(conn)
        db_session.commit()
        
        # Update token
        new_token = "updated-token-new"
        conn.bot_token = new_token
        db_session.commit()
        
        # Reload and verify
        db_session.expunge_all()
        loaded_conn = db_session.get(SlackConnection, "slack-5")
        assert loaded_conn.bot_token == new_token
    
    def test_bot_token_none_handling(self, db_session):
        """Test handling of None bot token"""
        conn = SlackConnection(
            id="slack-6",
            org_id="org-1",
            bot_token=None
        )
        db_session.add(conn)
        db_session.commit()
        
        assert conn.bot_token is None
        assert conn._bot_token_encrypted is None
    
    def test_slack_connection_with_scopes(self, db_session):
        """Test Slack connection with scopes"""
        conn = SlackConnection(
            id="slack-7",
            org_id="org-1",
            bot_token="token-with-scopes",
            scopes=["chat:write", "channels:read", "users:read"]
        )
        db_session.add(conn)
        db_session.commit()
        
        db_session.expunge_all()
        loaded_conn = db_session.get(SlackConnection, "slack-7")
        assert loaded_conn.scopes == ["chat:write", "channels:read", "users:read"]


class TestConfluenceConnection:
    """Test ConfluenceConnection model with encrypted access token"""
    
    def test_confluence_connection_creates(self, db_session):
        """Test that we can create a Confluence connection"""
        conn = ConfluenceConnection(
            id="confluence-1",
            org_id="org-1",
            cloud_base_url="https://mycompany.atlassian.net",
            access_token="confluence-test-token-123456"
        )
        db_session.add(conn)
        db_session.commit()
        
        assert conn.id == "confluence-1"
    
    def test_access_token_encrypted_in_database(self, db_session):
        """Test that access token is stored encrypted in the database"""
        plaintext_token = "confluence-my-secret-access-token-12345"
        
        conn = ConfluenceConnection(
            id="confluence-2",
            org_id="org-1",
            cloud_base_url="https://test.atlassian.net",
            access_token=plaintext_token
        )
        db_session.add(conn)
        db_session.commit()
        
        # Access the encrypted field directly
        assert conn._access_token_encrypted is not None
        assert conn._access_token_encrypted != plaintext_token
        assert plaintext_token not in conn._access_token_encrypted
    
    def test_access_token_decrypts_on_access(self, db_session):
        """Test that access token is decrypted when accessed via property"""
        plaintext_token = "confluence-decryption-test-token"
        
        conn = ConfluenceConnection(
            id="confluence-3",
            org_id="org-1",
            cloud_base_url="https://test.atlassian.net",
            access_token=plaintext_token
        )
        db_session.add(conn)
        db_session.commit()
        
        # Access via property should return decrypted token
        assert conn.access_token == plaintext_token
    
    def test_access_token_roundtrip(self, db_session):
        """Test that access token survives save/load roundtrip"""
        plaintext_token = "confluence-roundtrip-test-token-xyz"
        
        # Create and save
        conn = ConfluenceConnection(
            id="confluence-4",
            org_id="org-1",
            cloud_base_url="https://roundtrip.atlassian.net",
            access_token=plaintext_token
        )
        db_session.add(conn)
        db_session.commit()
        
        # Clear session and reload
        db_session.expunge_all()
        loaded_conn = db_session.get(ConfluenceConnection, "confluence-4")
        
        assert loaded_conn is not None
        assert loaded_conn.access_token == plaintext_token
    
    def test_access_token_update(self, db_session):
        """Test that we can update the access token"""
        conn = ConfluenceConnection(
            id="confluence-5",
            org_id="org-1",
            cloud_base_url="https://update.atlassian.net",
            access_token="confluence-original-token"
        )
        db_session.add(conn)
        db_session.commit()
        
        # Update token
        new_token = "confluence-updated-token-new"
        conn.access_token = new_token
        db_session.commit()
        
        # Reload and verify
        db_session.expunge_all()
        loaded_conn = db_session.get(ConfluenceConnection, "confluence-5")
        assert loaded_conn.access_token == new_token
    
    def test_access_token_none_handling(self, db_session):
        """Test handling of None access token"""
        conn = ConfluenceConnection(
            id="confluence-6",
            org_id="org-1",
            cloud_base_url="https://none.atlassian.net",
            access_token=None
        )
        db_session.add(conn)
        db_session.commit()
        
        assert conn.access_token is None
        assert conn._access_token_encrypted is None
    
    def test_confluence_connection_with_refresh_token(self, db_session):
        """Test Confluence connection with refresh token"""
        conn = ConfluenceConnection(
            id="confluence-7",
            org_id="org-1",
            cloud_base_url="https://refresh.atlassian.net",
            access_token="confluence-access-token",
            refresh_token="confluence-refresh-token-not-encrypted",
            scopes=["read:confluence-space.summary", "write:confluence-content"]
        )
        db_session.add(conn)
        db_session.commit()
        
        db_session.expunge_all()
        loaded_conn = db_session.get(ConfluenceConnection, "confluence-7")
        assert loaded_conn.access_token == "confluence-access-token"
        assert loaded_conn.refresh_token == "confluence-refresh-token-not-encrypted"
        assert loaded_conn.scopes == ["read:confluence-space.summary", "write:confluence-content"]


class TestEncryptionKeyMissing:
    """Test behavior when encryption key is not configured"""
    
    def test_slack_connection_fails_without_encryption_key(self):
        """Test that creating Slack connection fails without encryption key"""
        # Clear encryption key
        old_key = os.environ.pop("TOKEN_ENCRYPTION_KEY", None)
        
        try:
            # Clear global encryptor
            import backend.core.encryption as enc_module
            enc_module._encryptor = None
            
            # Create in-memory database
            engine = create_engine("sqlite:///:memory:")
            Base.metadata.create_all(engine)
            Session = sessionmaker(bind=engine)
            session = Session()
            
            # Should fail when trying to set the token (encryption happens in setter)
            from backend.core.encryption import EncryptionKeyError
            with pytest.raises(EncryptionKeyError):
                conn = SlackConnection(
                    id="slack-no-key",
                    org_id="org-1",
                    bot_token="test-token"
                )
            
            session.close()
            engine.dispose()
        finally:
            # Restore environment
            if old_key:
                os.environ["TOKEN_ENCRYPTION_KEY"] = old_key
            # Clear global encryptor
            import backend.core.encryption as enc_module
            enc_module._encryptor = None
