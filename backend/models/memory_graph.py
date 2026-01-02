"""
Memory Graph Models - Organizational Brain Storage

SQLAlchemy ORM models for the memory graph system that powers NAVI's
organizational intelligence across Jira, Slack, Teams, Zoom, GitHub, and more.
"""

from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Text,
    Float,
    Integer,
    ForeignKey,
    TIMESTAMP,
)
from backend.database.types import PortableJSONB as JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from backend.core.db import Base


class MemoryNode(Base):
    """
    Memory Node - Represents any organizational entity.

    Examples:
    - Jira issues
    - Slack messages
    - Teams conversations
    - Zoom meetings
    - GitHub PRs/issues
    - Confluence pages
    - Code files/functions
    - Team members
    """

    __tablename__ = "memory_node"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    org_id = Column(String(255), nullable=False, index=True)
    node_type = Column(
        String(50), nullable=False, index=True
    )  # jira_issue, slack_msg, pr, code, etc
    title = Column(Text, nullable=True)
    text = Column(Text, nullable=False)
    meta_json = Column(JSONB, default={}, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    chunks = relationship(
        "MemoryChunk", back_populates="node", cascade="all, delete-orphan"
    )
    outgoing_edges = relationship(
        "MemoryEdge",
        foreign_keys="MemoryEdge.from_id",
        back_populates="from_node",
        cascade="all, delete-orphan",
    )
    incoming_edges = relationship(
        "MemoryEdge",
        foreign_keys="MemoryEdge.to_id",
        back_populates="to_node",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<MemoryNode(id={self.id}, type={self.node_type}, title={self.title})>"


class MemoryChunk(Base):
    """
    Memory Chunk - Text chunks with dense vector embeddings for semantic search.

    Each node is broken into chunks (~200 tokens each) for efficient retrieval.
    Uses pgvector HNSW index for fast similarity search.
    """

    __tablename__ = "memory_chunk"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    node_id = Column(
        BigInteger, ForeignKey("memory_node.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Text, nullable=True)  # VECTOR(1536) in PostgreSQL
    created_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    node = relationship("MemoryNode", back_populates="chunks")

    def __repr__(self):
        return f"<MemoryChunk(id={self.id}, node_id={self.node_id}, index={self.chunk_index})>"


class MemoryEdge(Base):
    """
    Memory Edge - Relationships between organizational entities.

    Edge types:
    - mentions: A mentions B (Slack → Person, Jira → PR)
    - documents: A documents B (Confluence → Feature, Meeting → Decision)
    - implements: A implements B (PR → Jira, Code → Feature)
    - relates_to: Generic relationship
    - depends_on: Dependency relationship
    - blocks: Blocking relationship
    - duplicates: Duplicate relationship
    """

    __tablename__ = "memory_edge"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    org_id = Column(String(255), nullable=False)
    from_id = Column(
        BigInteger,
        ForeignKey("memory_node.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_id = Column(
        BigInteger,
        ForeignKey("memory_node.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edge_type = Column(String(50), nullable=False, index=True)
    weight = Column(Float, default=1.0, nullable=False)
    meta_json = Column(JSONB, default={}, nullable=False)
    created_at = Column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    from_node = relationship(
        "MemoryNode", foreign_keys=[from_id], back_populates="outgoing_edges"
    )
    to_node = relationship(
        "MemoryNode", foreign_keys=[to_id], back_populates="incoming_edges"
    )

    def __repr__(self):
        return f"<MemoryEdge(id={self.id}, {self.from_id} --{self.edge_type}--> {self.to_id})>"
