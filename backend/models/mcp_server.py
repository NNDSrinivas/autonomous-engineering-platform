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
    # SECURITY CRITICAL: secret_json field requires encryption enforcement
    # Current risk: No enforcement at model/service layer - plaintext secrets could be stored if write path forgets encryption
    #
    # Required implementation (before any CRUD API is built):
    # 1. Rename column: secret_json → secret_ciphertext (explicit intent, prevents accidental plaintext writes)
    # 2. Create service layer: MCP server repository/service that enforces encryption on all writes
    #    - Use backend.core.crypto.encrypt_token() for encryption (Fernet-based, similar to audit logs)
    #    - Reject non-bytes values at write time (validation)
    #    - Auto-decrypt on read (transparent to consumers)
    # 3. Migration strategy: Create Alembic migration to rename column when service layer is ready
    # 4. Documentation: Add docstring explaining this is ciphertext-only, never accepts plaintext
    #
    # Implementation reference: backend/api/routers/audit.py (encrypted payload handling)
    secret_json = Column(
        LargeBinary,
        nullable=True,
        comment="MUST be encrypted ciphertext (Fernet). Use service layer for encryption.",
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
