from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import JSON, TIMESTAMP, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.db import Base


class Task(Base):
    __tablename__ = "task"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    meeting_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action_item_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    assignee: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    priority: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    org_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    events: Mapped[List["TaskEvent"]] = relationship(
        "TaskEvent", back_populates="task", cascade="all, delete-orphan"
    )
    links: Mapped[List["TaskLink"]] = relationship(
        "TaskLink", back_populates="task", cascade="all, delete-orphan"
    )


class TaskEvent(Base):
    __tablename__ = "task_event"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    task: Mapped[Task] = relationship("Task", back_populates="events")


class TaskDependency(Base):
    __tablename__ = "task_dependency"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    depends_on_task_id: Mapped[str] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )


class TaskLink(Base):
    __tablename__ = "task_link"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        ForeignKey("task.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    task: Mapped[Task] = relationship("Task", back_populates="links")
