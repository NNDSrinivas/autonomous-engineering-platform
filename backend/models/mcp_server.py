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
    # TODO: Encrypt secret_json at rest using envelope encryption (backend.core.crypto.encrypt_token)
    # to prevent plaintext credential persistence. Consider:
    # 1. Renaming to secret_ciphertext/encrypted_secret to make intent explicit
    # 2. Adding service-layer helper that always encrypts/decrypts via crypto.encrypt_token()
    # 3. Validating at write time (reject non-bytes or unexpected format) to prevent plaintext
    # 4. Using Fernet encryption similar to audit payload encryption
    secret_json = Column(LargeBinary, nullable=True)
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
