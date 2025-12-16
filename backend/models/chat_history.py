from datetime import datetime, timezone
from sqlalchemy import Column, BigInteger, String, Text, TIMESTAMP
from backend.core.db import Base


class ChatMessage(Base):
    __tablename__ = "chat_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(255), nullable=False, index=True)
    org_id = Column(String(255), nullable=True, index=True)
    role = Column(String(50), nullable=False)  # user | assistant | system
    message = Column(Text, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
