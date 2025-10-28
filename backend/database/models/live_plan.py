"""
Live Plan - Real-time collaborative planning sessions
"""
from sqlalchemy import Column, String, JSON, DateTime, Boolean, Index
from sqlalchemy.sql import func
from backend.core.db import Base


class LivePlan(Base):
    """Live collaborative plan session"""
    
    __tablename__ = "live_plan"

    id = Column(String, primary_key=True)
    org_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    steps = Column(JSON, default=lambda: [])  # [{"text": "...", "owner": "...", "ts": "..."}]
    participants = Column(JSON, default=lambda: [])  # ["user1", "user2"]
    archived = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index('ix_live_plan_org_archived', 'org_id', 'archived'),
    )

    def to_dict(self):
        """Serialize to dictionary"""
        return {
            "id": self.id,
            "org_id": self.org_id,
            "title": self.title,
            "description": self.description,
            "steps": self.steps or [],
            "participants": self.participants or [],
            "archived": self.archived,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
