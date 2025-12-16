from datetime import datetime, timezone
from sqlalchemy import Column, BigInteger, String, Text, TIMESTAMP
from backend.core.db import Base


class ChatSession(Base):
    __tablename__ = "chat_session"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(String(255), nullable=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    title = Column(Text, nullable=True)
    created_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    archived = Column(
        TIMESTAMP(timezone=True), nullable=True, index=True
    )  # soft archive timestamp
    deleted_at = Column(
        TIMESTAMP(timezone=True), nullable=True, index=True
    )  # soft delete with retention
