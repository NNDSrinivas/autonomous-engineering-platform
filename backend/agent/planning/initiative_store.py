"""
Initiative Store — Durable State (Weeks, Not Minutes)

Manages long-horizon initiatives that span days or weeks.
Provides persistent storage and state management for autonomous execution.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
from sqlalchemy import Column, String, DateTime, Text, JSON, Index
from sqlalchemy.sql import func

from backend.core.db import Base


class InitiativeStatus(Enum):
    """Status of an initiative"""

    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


@dataclass
class Initiative:
    """Represents a long-horizon initiative"""

    id: str
    title: str
    goal: str
    status: InitiativeStatus
    plan_id: str
    checkpoints: List[str]
    owner: str
    org_id: str
    jira_key: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "title": self.title,
            "goal": self.goal,
            "status": self.status.value,
            "plan_id": self.plan_id,
            "checkpoints": self.checkpoints,
            "owner": self.owner,
            "org_id": self.org_id,
            "jira_key": self.jira_key,
            "metadata": self.metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


class InitiativeModel(Base):
    """Database model for initiatives"""

    __tablename__ = "initiatives"

    id = Column(String, primary_key=True)
    org_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    goal = Column(Text, nullable=False)
    status = Column(String, nullable=False, index=True)
    plan_id = Column(String, nullable=False)
    checkpoints = Column(JSON, default=lambda: [])
    owner = Column(String, nullable=False, index=True)
    jira_key = Column(String, nullable=True, index=True)
    initiative_metadata = Column(JSON, default=lambda: {})
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_initiatives_org_status", "org_id", "status"),
        Index("ix_initiatives_owner_status", "owner", "status"),
    )

    def to_initiative(self) -> Initiative:
        """Convert to Initiative dataclass"""
        # Access the actual values from database row
        checkpoints_val = self.checkpoints
        metadata_val = self.initiative_metadata

        return Initiative(
            id=str(self.id),
            title=str(self.title),
            goal=str(self.goal),
            status=InitiativeStatus(str(self.status)),
            plan_id=str(self.plan_id),
            checkpoints=checkpoints_val if isinstance(checkpoints_val, list) else [],
            owner=str(self.owner),
            org_id=str(self.org_id),
            jira_key=str(self.jira_key) if self.jira_key is not None else None,
            metadata=metadata_val if isinstance(metadata_val, dict) else {},
            created_at=self.created_at,  # type: ignore  # SQLAlchemy attribute access
            updated_at=self.updated_at,  # type: ignore  # SQLAlchemy attribute access
            completed_at=self.completed_at,  # type: ignore  # SQLAlchemy attribute access
        )


class InitiativeStore:
    """Store for managing initiatives with database persistence"""

    def __init__(self, db_session):
        self.db = db_session

    def save_initiative(self, initiative: Initiative) -> None:
        """Save or update an initiative"""
        model = self.db.query(InitiativeModel).filter_by(id=initiative.id).first()

        if model:
            # Update existing
            model.title = initiative.title
            model.goal = initiative.goal
            model.status = initiative.status.value
            model.plan_id = initiative.plan_id
            model.checkpoints = initiative.checkpoints
            model.owner = initiative.owner
            model.jira_key = initiative.jira_key
            model.initiative_metadata = initiative.metadata or {}
            if initiative.completed_at:
                model.completed_at = initiative.completed_at
        else:
            # Create new
            model = InitiativeModel(
                id=initiative.id,
                org_id=initiative.org_id,
                title=initiative.title,
                goal=initiative.goal,
                status=initiative.status.value,
                plan_id=initiative.plan_id,
                checkpoints=initiative.checkpoints,
                owner=initiative.owner,
                jira_key=initiative.jira_key,
                initiative_metadata=initiative.metadata or {},
                completed_at=initiative.completed_at,
            )
            self.db.add(model)

        self.db.commit()

    def get_initiative(self, initiative_id: str) -> Optional[Initiative]:
        """Get an initiative by ID"""
        model = self.db.query(InitiativeModel).filter_by(id=initiative_id).first()
        return model.to_initiative() if model else None

    def list_initiatives(
        self,
        org_id: str,
        owner: Optional[str] = None,
        status: Optional[InitiativeStatus] = None,
        limit: int = 50,
    ) -> List[Initiative]:
        """List initiatives with optional filters"""
        query = self.db.query(InitiativeModel).filter_by(org_id=org_id)

        if owner:
            query = query.filter_by(owner=owner)

        if status:
            query = query.filter_by(status=status.value)

        models = query.order_by(InitiativeModel.created_at.desc()).limit(limit).all()
        return [model.to_initiative() for model in models]

    def list_active_initiatives(
        self, org_id: str, owner: Optional[str] = None
    ) -> List[Initiative]:
        """List active (non-completed, non-cancelled) initiatives"""
        active_statuses = [
            InitiativeStatus.PLANNED.value,
            InitiativeStatus.IN_PROGRESS.value,
            InitiativeStatus.PAUSED.value,
            InitiativeStatus.BLOCKED.value,
        ]

        query = self.db.query(InitiativeModel).filter(
            InitiativeModel.org_id == org_id,
            InitiativeModel.status.in_(active_statuses),
        )

        if owner:
            query = query.filter_by(owner=owner)

        models = query.order_by(InitiativeModel.created_at.desc()).all()
        return [model.to_initiative() for model in models]

    def update_initiative_status(
        self,
        initiative_id: str,
        status: InitiativeStatus,
        completed_at: Optional[datetime] = None,
    ) -> bool:
        """Update initiative status"""
        model = self.db.query(InitiativeModel).filter_by(id=initiative_id).first()
        if not model:
            return False

        model.status = status.value
        if completed_at:
            model.completed_at = completed_at

        self.db.commit()
        return True

    def add_checkpoint(self, initiative_id: str, checkpoint_id: str) -> bool:
        """Add a checkpoint to an initiative"""
        model = self.db.query(InitiativeModel).filter_by(id=initiative_id).first()
        if not model:
            return False

        checkpoints = model.checkpoints or []
        if checkpoint_id not in checkpoints:
            checkpoints.append(checkpoint_id)
            model.checkpoints = checkpoints
            self.db.commit()

        return True
