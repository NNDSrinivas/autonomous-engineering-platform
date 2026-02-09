from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)

from backend.core.db import Base


class McpServer(Base):
    __tablename__ = "mcp_servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(160), nullable=False)
    url = Column(String(600), nullable=False)
    transport = Column(String(40), nullable=False, default="streamable_http")
    auth_type = Column(String(40), nullable=False, default="none")
    config_json = Column(Text, nullable=True)
    # SECURITY CRITICAL: secret_json field requires encryption enforcement at type/system boundary
    # Current risk: No enforcement prevents accidental plaintext writes via ORM or direct scripts
    #
    # RECOMMENDED: Use SQLAlchemy TypeDecorator for automatic encryption/decryption at ORM layer
    # This prevents accidental plaintext persistence and makes encryption transparent:
    #
    #   class EncryptedBinary(TypeDecorator):
    #       impl = LargeBinary
    #       def process_bind_param(self, value, dialect):
    #           if value is None: return None
    #           return encrypt_token(value)  # Auto-encrypt on write
    #       def process_result_value(self, value, dialect):
    #           if value is None: return None
    #           return decrypt_token(value)  # Auto-decrypt on read
    #
    # Alternative: Service layer enforcement (if TypeDecorator not feasible):
    # 1. Repository/service that is the only allowed write path (enforced via linting/code review)
    # 2. Reject non-bytes at write time + validate ciphertext format
    # 3. Consider renaming to secret_ciphertext for clarity
    #
    # Implementation reference: backend.core.crypto.encrypt_token() (Fernet-based, similar to audit logs)
    secret_json = Column(
        LargeBinary,
        nullable=True,
        comment="MUST be encrypted ciphertext (Fernet). TODO: Use TypeDecorator for enforcement.",
    )
    enabled = Column(Boolean, default=True, nullable=False)
    status = Column(String(32), nullable=False, default="unknown")
    tool_count = Column(Integer, nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    user_id = Column(String(200), index=True, nullable=True)
    org_id = Column(String(200), index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
