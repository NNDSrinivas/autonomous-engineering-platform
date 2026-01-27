from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, JSON, TIMESTAMP
from ..core.db import Base


class Meeting(Base):
    __tablename__ = "meeting"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid str
    session_id: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    participants: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    org_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    segments: Mapped[List["TranscriptSegment"]] = relationship(
        "TranscriptSegment", back_populates="meeting", cascade="all,delete"
    )
    summary: Mapped[Optional["MeetingSummary"]] = relationship(
        "MeetingSummary", back_populates="meeting", uselist=False
    )
    actions: Mapped[List["ActionItem"]] = relationship(
        "ActionItem", back_populates="meeting", cascade="all,delete"
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segment"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meeting.id", ondelete="CASCADE")
    )
    ts_start_ms: Mapped[Optional[int]] = mapped_column(Integer)
    ts_end_ms: Mapped[Optional[int]] = mapped_column(Integer)
    speaker: Mapped[Optional[str]] = mapped_column(String)
    text: Mapped[str] = mapped_column(String)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="segments")


class MeetingSummary(Base):
    __tablename__ = "meeting_summary"
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meeting.id", ondelete="CASCADE"), primary_key=True
    )
    bullets: Mapped[Optional[List[str]]] = mapped_column(JSON)
    decisions: Mapped[Optional[List[str]]] = mapped_column(JSON)
    risks: Mapped[Optional[List[str]]] = mapped_column(JSON)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="summary")


class ActionItem(Base):
    __tablename__ = "action_item"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meeting.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String)
    assignee: Mapped[Optional[str]] = mapped_column(String)
    due_hint: Mapped[Optional[str]] = mapped_column(String)
    confidence: Mapped[Optional[float]] = mapped_column()
    source_segment: Mapped[Optional[str]] = mapped_column(
        ForeignKey("transcript_segment.id", ondelete="SET NULL")
    )

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="actions")
