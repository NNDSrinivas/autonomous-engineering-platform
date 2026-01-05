from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, LargeBinary

from backend.core.db import Base


class Connector(Base):
    __tablename__ = "connectors"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), index=True, nullable=False)
    name = Column(String(100), nullable=False)
    config_json = Column(Text, nullable=True)
    secret_json = Column(LargeBinary, nullable=True)
    workspace_root = Column(String(500), index=True, nullable=True)
    user_id = Column(String(200), index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
