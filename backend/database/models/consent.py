"""
Consent System Models

Database models for command consent preferences and audit logging.
- ConsentPreference: Stores user's always-allow rules (exact commands or command types)
- ConsentAuditLog: Audit trail of all consent decisions
"""

from sqlalchemy import (
    Column,
    String,
    Text,
    ForeignKey,
    Integer,
    DateTime,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from backend.core.db import Base
import uuid


class ConsentPreference(Base):
    """
    User consent preferences for auto-allowing commands.

    Supports two types:
    - 'exact_command': Auto-allow this specific command string
    - 'command_type': Auto-allow all commands of this type (e.g., all 'rm' commands)
    """

    __tablename__ = "consent_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    org_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    preference_type = Column(
        String(20), nullable=False
    )  # 'exact_command' or 'command_type'
    command_pattern = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by_task_id = Column(String(50), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "org_id",
            "preference_type",
            "command_pattern",
            name="consent_preferences_unique",
        ),
        Index("idx_consent_prefs_user_org", "user_id", "org_id"),
        Index("idx_consent_prefs_pattern", "command_pattern"),
    )


class ConsentAuditLog(Base):
    """
    Audit trail of all consent decisions.

    Records every consent request and user's decision for compliance and debugging.
    """

    __tablename__ = "consent_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consent_id = Column(String(50), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    command = Column(Text, nullable=False)
    shell = Column(String(20), default="bash")
    cwd = Column(Text, nullable=True)
    danger_level = Column(String(20), nullable=True)
    decision = Column(
        String(20), nullable=False
    )  # 'allow_once', 'allow_always_exact', 'allow_always_type', 'deny', 'alternative'
    alternative_command = Column(Text, nullable=True)
    requested_at = Column(DateTime(timezone=True), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=False)
    response_time_ms = Column(Integer, nullable=True)
    task_id = Column(String(50), nullable=True)
    session_id = Column(String(100), nullable=True)

    __table_args__ = (
        Index(
            "idx_consent_audit_user",
            "user_id",
            "requested_at",
            postgresql_using="btree",
        ),
    )
