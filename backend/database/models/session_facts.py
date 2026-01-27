"""
Session Facts Database Models.

Persistent storage for session facts extracted from NAVI conversations.
Unlike in-memory session storage, these persist across restarts and are
linked by workspace path for continuity.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, relationship

from backend.core.db import Base


class WorkspaceSession(Base):
    """
    Workspace-based session tracking.

    Links sessions to workspaces so NAVI can remember context
    when returning to the same project.
    """

    __tablename__ = "navi_workspace_sessions"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[int] = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Workspace identification
    workspace_path: Mapped[str] = Column(
        Text,
        nullable=False,
        comment="Absolute path to the workspace/project",
    )
    workspace_name: Mapped[Optional[str]] = Column(
        String(255),
        nullable=True,
        comment="Project name (from package.json, etc.)",
    )

    # Current session info
    current_session_id: Mapped[Optional[str]] = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Active conversation session ID",
    )

    # Workspace state
    last_known_state: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        default={},
        comment="Last known project state (servers, ports, etc.)",
    )

    # Timestamps
    first_seen: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_active: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    facts = relationship(
        "SessionFact",
        back_populates="workspace_session",
        cascade="all, delete-orphan",
    )
    error_resolutions = relationship(
        "ErrorResolution",
        back_populates="workspace_session",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "workspace_path", name="uq_user_workspace"),
        Index("idx_workspace_session_user", "user_id"),
        Index("idx_workspace_session_path", "workspace_path"),
    )

    def __repr__(self) -> str:
        return f"<WorkspaceSession(id={self.id}, path={self.workspace_path})>"


class SessionFact(Base):
    """
    Persistent session facts extracted from conversations.

    Stores key information like server ports, file paths, decisions,
    errors encountered, etc. Persists across session restarts.
    """

    __tablename__ = "navi_session_facts"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    workspace_session_id: Mapped[str] = Column(
        UUID(as_uuid=True),
        ForeignKey("navi_workspace_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Fact categorization
    category: Mapped[str] = Column(
        String(50),
        nullable=False,
        comment="Category: server, file, decision, error, task, discovery, dependency",
    )
    fact_key: Mapped[str] = Column(
        String(255),
        nullable=False,
        comment="Unique key within category (e.g., 'port_3000', 'primary_port')",
    )
    fact_value: Mapped[str] = Column(
        Text,
        nullable=False,
        comment="The fact value",
    )

    # Metadata
    source_message_id: Mapped[Optional[str]] = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Message ID where fact was extracted",
    )
    confidence: Mapped[float] = Column(
        Float,
        default=1.0,
        nullable=False,
        comment="Confidence score [0.0, 1.0]",
    )

    # Validity
    is_current: Mapped[bool] = Column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether this fact is still valid/current",
    )
    superseded_by_id: Mapped[Optional[str]] = Column(
        UUID(as_uuid=True),
        ForeignKey("navi_session_facts.id", ondelete="SET NULL"),
        nullable=True,
        comment="Newer fact that supersedes this one",
    )

    # Timestamps
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_verified: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="When this fact was last confirmed true",
    )

    # Relationship
    workspace_session = relationship(
        "WorkspaceSession",
        back_populates="facts",
    )

    __table_args__ = (
        # Only one current fact per category:key per workspace
        Index(
            "idx_session_fact_unique_current",
            "workspace_session_id",
            "category",
            "fact_key",
            unique=True,
            postgresql_where=Column("is_current") == True,
        ),
        Index("idx_session_fact_category", "category"),
        Index("idx_session_fact_current", "is_current"),
    )

    def __repr__(self) -> str:
        return f"<SessionFact(category={self.category}, key={self.fact_key}, value={self.fact_value[:30]})>"


class ErrorResolution(Base):
    """
    Tracks errors encountered and their resolutions.

    When NAVI encounters an error and successfully resolves it,
    the resolution is stored so it can be applied faster next time.
    """

    __tablename__ = "navi_error_resolutions"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    workspace_session_id: Mapped[str] = Column(
        UUID(as_uuid=True),
        ForeignKey("navi_workspace_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Error identification
    error_type: Mapped[str] = Column(
        String(100),
        nullable=False,
        comment="Error type: build_error, runtime_error, command_failed, dependency_error",
    )
    error_signature: Mapped[str] = Column(
        Text,
        nullable=False,
        comment="Normalized error signature for matching",
    )
    error_message: Mapped[str] = Column(
        Text,
        nullable=False,
        comment="Original error message",
    )

    # Resolution
    resolution_steps: Mapped[List[Dict[str, Any]]] = Column(
        JSONB,
        nullable=False,
        comment="Steps taken to resolve the error",
    )
    resolution_summary: Mapped[str] = Column(
        Text,
        nullable=False,
        comment="Human-readable summary of the fix",
    )

    # Effectiveness tracking
    times_applied: Mapped[int] = Column(
        Integer,
        default=1,
        nullable=False,
        comment="Number of times this resolution was applied",
    )
    times_successful: Mapped[int] = Column(
        Integer,
        default=1,
        nullable=False,
        comment="Number of times it successfully resolved the error",
    )

    # Context
    context_data: Mapped[Optional[Dict[str, Any]]] = Column(
        JSONB,
        default={},
        comment="Additional context (file paths, versions, etc.)",
    )

    # Timestamps
    first_seen: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_applied: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship
    workspace_session = relationship(
        "WorkspaceSession",
        back_populates="error_resolutions",
    )

    __table_args__ = (
        Index("idx_error_resolution_type", "error_type"),
        Index("idx_error_resolution_workspace", "workspace_session_id"),
    )

    def __repr__(self) -> str:
        return f"<ErrorResolution(type={self.error_type}, success_rate={self.times_successful}/{self.times_applied})>"


class InstalledDependency(Base):
    """
    Tracks dependencies installed in a workspace.

    When NAVI installs a package, it's recorded here so we know
    what's already available without re-checking every time.
    """

    __tablename__ = "navi_installed_dependencies"

    id: Mapped[str] = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    workspace_session_id: Mapped[str] = Column(
        UUID(as_uuid=True),
        ForeignKey("navi_workspace_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Dependency info
    package_manager: Mapped[str] = Column(
        String(50),
        nullable=False,
        comment="Package manager: npm, pip, cargo, etc.",
    )
    package_name: Mapped[str] = Column(
        String(255),
        nullable=False,
    )
    package_version: Mapped[Optional[str]] = Column(
        String(100),
        nullable=True,
        comment="Installed version",
    )

    # Installation status
    is_dev_dependency: Mapped[bool] = Column(
        Boolean,
        default=False,
        nullable=False,
    )
    install_command: Mapped[Optional[str]] = Column(
        Text,
        nullable=True,
        comment="Command used to install",
    )

    # Timestamps
    installed_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_verified: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "workspace_session_id",
            "package_manager",
            "package_name",
            name="uq_workspace_package",
        ),
        Index("idx_installed_dep_workspace", "workspace_session_id"),
    )

    def __repr__(self) -> str:
        return f"<InstalledDependency({self.package_manager}:{self.package_name}@{self.package_version})>"
