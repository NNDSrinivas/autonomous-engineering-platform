from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime

from backend.core.db import Base


class CiRun(Base):
    __tablename__ = "ci_runs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50), index=True, nullable=False)
    repo = Column(String(300), index=True, nullable=True)
    workflow = Column(String(200), nullable=True)
    run_id = Column(String(200), index=True, nullable=True)
    status = Column(String(50), nullable=True)
    conclusion = Column(String(50), nullable=True)
    url = Column(String(500), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    meta_json = Column(Text, nullable=True)
    workspace_root = Column(String(500), index=True, nullable=True)
    user_id = Column(String(200), index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
