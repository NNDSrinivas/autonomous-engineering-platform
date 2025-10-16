from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, JSON, TIMESTAMP, ForeignKey
from ..core.db import Base

class Task(Base):
    __tablename__ = "task"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    meeting_id: Mapped[str | None] = mapped_column(String)
    action_item_id: Mapped[str | None] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)  # open|in_progress|blocked|done|cancelled
    assignee: Mapped[str | None] = mapped_column(String)
    priority: Mapped[str | None] = mapped_column(String)
    due_date: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True))
    updated_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True))
    org_id: Mapped[str | None] = mapped_column(String)

    events: Mapped[list["TaskEvent"]] = relationship("TaskEvent", back_populates="task", cascade="all,delete")
    links: Mapped[list["TaskLink"]] = relationship("TaskLink", back_populates="task", cascade="all,delete")

class TaskEvent(Base):
    __tablename__ = "task_event"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String)
    data: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True))
    task: Mapped["Task"] = relationship("Task", back_populates="events")

class TaskDependency(Base):
    __tablename__ = "task_dependency"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"))
    depends_on_task_id: Mapped[str] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"))

class TaskLink(Base):
    __tablename__ = "task_link"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("task.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String)
    key: Mapped[str | None] = mapped_column(String)
    url: Mapped[str | None] = mapped_column(String)
    meta: Mapped[dict | None] = mapped_column(JSON)
    task: Mapped["Task"] = relationship("Task", back_populates="links")