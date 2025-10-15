from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, JSON, TIMESTAMP
from ..core.db import Base
from datetime import datetime


class SessionAnswer(Base):
    """SQLAlchemy model for storing AI - generated answers and metadata."""

    __tablename__ = "session_answer"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    answer: Mapped[str] = mapped_column(String)
    citations: Mapped[list[dict]] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column()
    token_count: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
