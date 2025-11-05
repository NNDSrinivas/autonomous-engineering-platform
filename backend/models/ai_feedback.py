"""Database models for AI feedback and generation logging."""

from enum import Enum
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    JSON,
    func,
    CheckConstraint,
)
from sqlalchemy.orm import relationship

from backend.core.db import Base


class TaskType(str, Enum):
    """Valid task types for AI generation."""

    CODEGEN = "codegen"
    SUMMARIZE = "summarize"
    CHAT = "chat"
    ANALYSIS = "analysis"


class AiGenerationLog(Base):
    """Log of AI generation requests and their parameters."""

    __tablename__ = "ai_generation_log"

    id = Column(Integer, primary_key=True)
    org_key = Column(String(64), index=True)
    user_sub = Column(String(128), index=True)
    task_type = Column(String(48), nullable=False)  # Validated at application level
    input_fingerprint = Column(String(64), nullable=True)
    model = Column(String(64), nullable=False)
    temperature = Column(Float, nullable=False)
    params = Column(JSON, nullable=False)
    prompt_hash = Column(String(64), nullable=False)
    result_ref = Column(String(128), nullable=True)  # e.g., diff sha
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    result_ref = Column(String(128), nullable=True)  # e.g., diff sha
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationship to feedback
    feedback = relationship(
        "AiFeedback", back_populates="generation", cascade="all, delete-orphan"
    )


class AiFeedback(Base):
    """User feedback on AI generations."""

    __tablename__ = "ai_feedback"

    id = Column(Integer, primary_key=True)
    gen_id = Column(
        Integer, ForeignKey("ai_generation_log.id", ondelete="CASCADE"), index=True
    )
    org_key = Column(String(64), index=True)
    user_sub = Column(String(128), index=True)
    rating = Column(
        SmallInteger, nullable=False
    )  # +1 thumbs-up, 0 neutral, -1 thumbs-down
    reason = Column(
        String(64), nullable=True
    )  # correctness, style, performance, security, other
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationship to generation log
    generation = relationship("AiGenerationLog", back_populates="feedback")
