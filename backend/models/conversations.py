"""
Conversation models for Slack/Teams ingestion.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, BigInteger, String, Text, TIMESTAMP, ForeignKey
from backend.database.types import PortableJSONB as JSONB
from sqlalchemy.orm import relationship

from backend.core.db import Base


class ConversationMessage(Base):
    __tablename__ = "conversation_message"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(String(255), nullable=False, index=True)
    platform = Column(String(50), nullable=False)  # slack, teams
    channel = Column(String(255), nullable=True)
    thread_ts = Column(String(255), nullable=True)
    message_ts = Column(String(255), nullable=True, index=True)
    user = Column(String(255), nullable=True)
    text = Column(Text, nullable=False)
    meta_json = Column(JSONB, default={}, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    replies = relationship(
        "ConversationReply", back_populates="parent", cascade="all, delete-orphan"
    )


class ConversationReply(Base):
    __tablename__ = "conversation_reply"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(String(255), nullable=False, index=True)
    parent_id = Column(
        BigInteger,
        ForeignKey("conversation_message.id", ondelete="CASCADE"),
        nullable=False,
    )
    message_ts = Column(String(255), nullable=True, index=True)
    user = Column(String(255), nullable=True)
    text = Column(Text, nullable=False)
    meta_json = Column(JSONB, default={}, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    parent = relationship("ConversationMessage", back_populates="replies")
