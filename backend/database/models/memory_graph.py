"""Memory Graph models for temporal reasoning and relationship tracking

This module defines the data models for the Memory Graph system introduced in PR-17.
The graph consists of nodes (entities like JIRA issues, PRs, meetings) and edges
(relationships like 'fixes', 'discusses', 'derived_from') that enable temporal
reasoning and causality chains.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    Index,
    func,
)
from sqlalchemy.orm import relationship, Mapped
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class NodeKind(str, Enum):
    """Types of entities in the memory graph"""

    JIRA_ISSUE = "jira_issue"
    SLACK_THREAD = "slack_thread"
    MEETING = "meeting"
    CODE_FILE = "code_file"
    PR = "pr"
    DOC = "doc"
    WIKI = "wiki"
    RUN = "run"  # CI/CD run, deployment
    INCIDENT = "incident"


class EdgeRelation(str, Enum):
    """Types of relationships between memory nodes"""

    DISCUSSES = "discusses"  # Slack thread discusses JIRA issue
    REFERENCES = "references"  # PR references JIRA issue
    IMPLEMENTS = "implements"  # PR implements feature from issue
    FIXES = "fixes"  # PR fixes bug/issue
    DUPLICATES = "duplicates"  # Issue duplicates another issue
    DERIVED_FROM = "derived_from"  # PR derived from meeting discussion
    CAUSED_BY = "caused_by"  # Incident caused by deployment/PR
    NEXT = "next"  # Temporal successor in timeline
    PREVIOUS = "previous"  # Temporal predecessor in timeline


class MemoryNode(Base):
    """Represents an entity in the memory graph

    Nodes can be JIRA issues, Slack threads, meetings, PRs, code files, docs,
    deployments, incidents, etc. Each node has an embedding vector for semantic
    search and metadata for rich context.
    """

    __tablename__ = "memory_node"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = Column(String(255), nullable=False, index=True)
    kind: Mapped[str] = Column(
        String(50),
        nullable=False,
        comment="Entity type: jira_issue|slack_thread|meeting|code_file|pr|doc|wiki|run|incident",
    )
    foreign_id: Mapped[str] = Column(
        String(255),
        nullable=False,
        comment="External identifier (e.g., JIRA-123, PR#456)",
    )
    title: Mapped[Optional[str]] = Column(Text, nullable=True)
    summary: Mapped[Optional[str]] = Column(
        Text, nullable=True, comment="AI-generated summary of content"
    )
    # embedding_vec: vector column added via migration (pgvector type)
    meta_json: Mapped[Optional[Dict[str, Any]]] = Column(
        JSON, nullable=True, comment="Metadata: url, assignee, status, etc."
    )
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Updated automatically by SQLAlchemy ORM on update",
    )

    # Relationships
    outbound_edges: Mapped[List["MemoryEdge"]] = relationship(
        "MemoryEdge",
        foreign_keys="MemoryEdge.src_id",
        back_populates="source_node",
        cascade="all, delete-orphan",
    )
    inbound_edges: Mapped[List["MemoryEdge"]] = relationship(
        "MemoryEdge",
        foreign_keys="MemoryEdge.dst_id",
        back_populates="destination_node",
        cascade="all, delete-orphan",
    )

    # Indexes defined in migration
    __table_args__ = (
        Index("idx_memory_node_org_kind", "org_id", "kind"),
        Index("idx_memory_node_org_foreign", "org_id", "foreign_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<MemoryNode(id={self.id}, kind={self.kind}, foreign_id={self.foreign_id})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to dictionary for API responses"""
        return {
            "id": self.id,
            "org_id": self.org_id,
            "kind": self.kind,
            "foreign_id": self.foreign_id,
            "title": self.title,
            "summary": self.summary,
            "meta": self.meta_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MemoryEdge(Base):
    """Represents a relationship between two memory nodes

    Edges encode relationships like 'fixes', 'discusses', 'derived_from' with
    confidence scores and weights for path-finding algorithms. Metadata captures
    the heuristic source and supporting evidence.
    """

    __tablename__ = "memory_edge"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = Column(String(255), nullable=False, index=True)
    src_id: Mapped[int] = Column(
        Integer,
        ForeignKey("memory_node.id", ondelete="CASCADE"),
        nullable=False,
        comment="Source node ID",
    )
    dst_id: Mapped[int] = Column(
        Integer,
        ForeignKey("memory_node.id", ondelete="CASCADE"),
        nullable=False,
        comment="Destination node ID",
    )
    relation: Mapped[str] = Column(
        String(50),
        nullable=False,
        comment="Edge type: discusses|references|implements|fixes|duplicates|derived_from|caused_by|next|previous",
    )
    weight: Mapped[float] = Column(
        Float,
        nullable=False,
        default=1.0,
        comment="Edge importance weight [0, 1]",
    )
    confidence: Mapped[float] = Column(
        Float,
        nullable=False,
        default=1.0,
        comment="Confidence in relationship [0, 1]",
    )
    meta_json: Mapped[Optional[Dict[str, Any]]] = Column(
        JSON,
        nullable=True,
        comment="Edge metadata: source_heuristic, timestamp_diff, etc.",
    )
    created_at: Mapped[datetime] = Column(
        DateTime(timezone=True), nullable=False, server_default="CURRENT_TIMESTAMP"
    )

    # Relationships
    source_node: Mapped["MemoryNode"] = relationship(
        "MemoryNode", foreign_keys=[src_id], back_populates="outbound_edges"
    )
    destination_node: Mapped["MemoryNode"] = relationship(
        "MemoryNode", foreign_keys=[dst_id], back_populates="inbound_edges"
    )

    # Indexes defined in migration
    __table_args__ = (
        Index("idx_memory_edge_org_rel", "org_id", "relation"),
        Index("idx_memory_edge_src", "src_id"),
        Index("idx_memory_edge_dst", "dst_id"),
    )

    def __repr__(self) -> str:
        return f"<MemoryEdge(id={self.id}, relation={self.relation}, {self.src_id}->{self.dst_id})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert edge to dictionary for API responses"""
        return {
            "id": self.id,
            "org_id": self.org_id,
            "src_id": self.src_id,
            "dst_id": self.dst_id,
            "relation": self.relation,
            "weight": self.weight,
            "confidence": self.confidence,
            "meta": self.meta_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @property
    def combined_score(self) -> float:
        """Combined score for path-finding (weight * confidence)"""
        return self.weight * self.confidence
