from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, JSON, TIMESTAMP
from ..core.db import Base


class Meeting(Base):
    __tablename__ = "meeting"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # uuid str
    session_id: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    participants: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    org_id: Mapped[str | None] = mapped_column(String, nullable=True)

    segments: Mapped[list["TranscriptSegment"]] = relationship(
        "TranscriptSegment", back_populates="meeting", cascade="all,delete"
    )
    summary: Mapped["MeetingSummary | None"] = relationship(
        "MeetingSummary", back_populates="meeting", uselist=False
    )
    actions: Mapped[list["ActionItem"]] = relationship(
        "ActionItem", back_populates="meeting", cascade="all,delete"
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segment"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meeting.id", ondelete="CASCADE"))
    ts_start_ms: Mapped[int | None] = mapped_column(Integer)
    ts_end_ms: Mapped[int | None] = mapped_column(Integer)
    speaker: Mapped[str | None] = mapped_column(String)
    text: Mapped[str] = mapped_column(String)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="segments")


class MeetingSummary(Base):
    __tablename__ = "meeting_summary"
    meeting_id: Mapped[str] = mapped_column(
        ForeignKey("meeting.id", ondelete="CASCADE"), primary_key=True
    )
    bullets: Mapped[list[str] | None] = mapped_column(JSON)
    decisions: Mapped[list[str] | None] = mapped_column(JSON)
    risks: Mapped[list[str] | None] = mapped_column(JSON)

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="summary")


class ActionItem(Base):
    __tablename__ = "action_item"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    meeting_id: Mapped[str] = mapped_column(ForeignKey("meeting.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String)
    assignee: Mapped[str | None] = mapped_column(String)
    due_hint: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[float | None] = mapped_column()
    source_segment: Mapped[str | None] = mapped_column(
        ForeignKey("transcript_segment.id", ondelete="SET NULL")
    )

    meeting: Mapped["Meeting"] = relationship("Meeting", back_populates="actions")
