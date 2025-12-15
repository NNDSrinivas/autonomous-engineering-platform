from datetime import datetime
from sqlalchemy import Column, BigInteger, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from backend.core.db import Base


class ChangeSet(Base):
    __tablename__ = "change_set"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    org_id = Column(String(255), nullable=True, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    summary = Column(String(500), nullable=True)
    details = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False)
