"""
Database configuration and models for autonomous engineering platform
Using SQLAlchemy 2.0 with async support
"""

from datetime import datetime
from typing import List
from typing import Optional

import structlog
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import JSON
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import relationship

from backend.core.config import get_settings

from sqlalchemy.orm import DeclarativeBase

logger = structlog.get_logger(__name__)


# Use modern SQLAlchemy 2.0 declarative base
class Base(DeclarativeBase):
    pass


# Database Models
class Project(Base):
    """Project/repository information"""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    repository_url = Column(String(512), nullable=True)
    description = Column(Text, nullable=True)
    tech_stack = Column(JSON, nullable=True)  # List of technologies
    team_members = Column(JSON, nullable=True)  # List of team member IDs
    settings = Column(JSON, nullable=True)  # Project-specific settings
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    knowledge_entries = relationship("KnowledgeEntry", back_populates="project")
    team_sessions = relationship("TeamSession", back_populates="project")


class TeamMember(Base):
    """Team member information"""

    __tablename__ = "team_members"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    github_username = Column(String(255), nullable=True)
    role = Column(String(100), nullable=True)  # developer, lead, architect, etc.
    expertise = Column(JSON, nullable=True)  # List of skills/technologies
    preferences = Column(JSON, nullable=True)  # Working preferences
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    authored_sessions = relationship("TeamSession", back_populates="author")


class KnowledgeEntry(Base):
    """Knowledge base entries for team context"""

    __tablename__ = "knowledge_entries"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    type = Column(String(50), nullable=False)  # code, discussion, documentation, etc.
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    entry_metadata = Column(
        JSON, nullable=True
    )  # Renamed from metadata to avoid conflict
    author_id = Column(Integer, ForeignKey("team_members.id"), nullable=True)
    tags = Column(JSON, nullable=True)  # List of tags
    vector_id = Column(String(255), nullable=True)  # ChromaDB vector ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="knowledge_entries")
    author = relationship("TeamMember")


class TeamSession(Base):
    """Team collaboration sessions"""

    __tablename__ = "team_sessions"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("team_members.id"), nullable=False)
    session_type = Column(String(50), nullable=False)  # coding, review, planning, etc.
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    context = Column(JSON, nullable=True)  # Session context data
    outcomes = Column(JSON, nullable=True)  # Session outcomes/decisions
    duration_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="team_sessions")
    author = relationship("TeamMember", back_populates="authored_sessions")
    interactions = relationship("AIInteraction", back_populates="session")


class AIInteraction(Base):
    """AI assistant interactions"""

    __tablename__ = "ai_interactions"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("team_sessions.id"), nullable=True)
    user_query = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    context = Column(JSON, nullable=True)  # Request context
    feedback = Column(JSON, nullable=True)  # User feedback on response
    response_time_ms = Column(Integer, nullable=True)
    confidence_score = Column(String(10), nullable=True)  # AI confidence
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("TeamSession", back_populates="interactions")


class AutonomousTask(Base):
    """Autonomous coding tasks"""

    __tablename__ = "autonomous_tasks"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    task_type = Column(
        String(50), nullable=False
    )  # coding, testing, documentation, etc.
    status = Column(
        String(50), default="pending"
    )  # pending, in_progress, completed, failed
    priority = Column(String(10), default="medium")  # low, medium, high, critical

    # Task execution details
    assigned_files = Column(JSON, nullable=True)  # List of files to work on
    generated_code = Column(Text, nullable=True)
    test_results = Column(JSON, nullable=True)
    approval_status = Column(
        String(50), default="pending"
    )  # pending, approved, rejected

    # Metadata
    estimated_effort = Column(String(50), nullable=True)  # small, medium, large
    dependencies = Column(JSON, nullable=True)  # Task dependencies
    execution_log = Column(JSON, nullable=True)  # Detailed execution steps

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    project = relationship("Project")


# Database configuration
class DatabaseManager:
    """Database manager for the engineering platform"""

    def __init__(self):
        self.settings = get_settings()
        self.engine = None
        self.async_session = None

    async def initialize(self):
        """Initialize database connection and create tables"""
        try:
            # Create async engine
            if not self.settings.database_url:
                raise ValueError("Database URL is not configured")
            self.engine = create_async_engine(
                self.settings.database_url, echo=self.settings.debug, future=True
            )

            # Create session factory
            self.async_session = async_sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )

            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            raise

    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")

    def get_session(self) -> AsyncSession:
        """Get database session"""
        if not self.async_session:
            raise RuntimeError("Database not initialized")
        return self.async_session()


# Global database manager instance
db_manager = DatabaseManager()


async def init_database():
    """Initialize database for the application"""
    await db_manager.initialize()


async def close_database():
    """Close database connections"""
    await db_manager.close()


def get_db_session() -> AsyncSession:
    """Get database session for dependency injection"""
    return db_manager.get_session()


# Database utility functions
async def create_project(
    name: str,
    repository_url: Optional[str] = None,
    description: Optional[str] = None,
    tech_stack: Optional[List[str]] = None,
    team_members: Optional[List[int]] = None,
) -> Project:
    """Create a new project"""
    async with get_db_session() as session:
        project = Project(
            name=name,
            repository_url=repository_url,
            description=description,
            tech_stack=tech_stack or [],
            team_members=team_members or [],
        )

        session.add(project)
        await session.commit()
        await session.refresh(project)

        logger.info("Created new project", project_id=project.id, name=name)
        return project


async def create_team_member(
    name: str,
    email: str,
    github_username: Optional[str] = None,
    role: Optional[str] = None,
    expertise: Optional[List[str]] = None,
) -> TeamMember:
    """Create a new team member"""
    async with get_db_session() as session:
        member = TeamMember(
            name=name,
            email=email,
            github_username=github_username,
            role=role,
            expertise=expertise or [],
        )

        session.add(member)
        await session.commit()
        await session.refresh(member)

        logger.info("Created new team member", member_id=member.id, email=email)
        return member


async def log_ai_interaction(
    user_query: str,
    ai_response: str,
    session_id: Optional[int] = None,
    context: Optional[dict] = None,
    response_time_ms: Optional[int] = None,
    confidence_score: Optional[str] = None,
) -> AIInteraction:
    """Log AI interaction for analytics"""
    async with get_db_session() as session:
        interaction = AIInteraction(
            session_id=session_id,
            user_query=user_query,
            ai_response=ai_response,
            context=context,
            response_time_ms=response_time_ms,
            confidence_score=confidence_score,
        )

        session.add(interaction)
        await session.commit()
        await session.refresh(interaction)

        return interaction
