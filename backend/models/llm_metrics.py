"""Database models for LLM metrics and performance tracking."""

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    JSON,
    func,
    Index,
)
from backend.core.db import Base


class LlmMetric(Base):
    """
    Store LLM usage metrics for cost tracking and analysis.

    Captures token usage, cost, latency, and other metrics for each LLM call.
    This complements Prometheus metrics by providing persistent historical data.
    """

    __tablename__ = "llm_metrics"

    id = Column(Integer, primary_key=True)

    # Organization and user context
    org_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)

    # LLM call details
    model = Column(String(128), nullable=False, index=True)
    provider = Column(String(64), nullable=False, index=True)  # anthropic, openai, etc.

    # Token usage
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)

    # Cost tracking (in USD)
    input_cost = Column(Float, nullable=False, default=0.0)
    output_cost = Column(Float, nullable=False, default=0.0)
    total_cost = Column(Float, nullable=False, default=0.0)

    # Performance metrics
    latency_ms = Column(
        Integer, nullable=True, comment="Total request latency in milliseconds"
    )
    ttft_ms = Column(
        Integer, nullable=True, comment="Time to first token in milliseconds"
    )

    # Task context
    task_type = Column(
        String(64), nullable=True, index=True
    )  # chat, codegen, analysis, etc.
    session_id = Column(String(128), nullable=True, index=True)

    # Additional metadata
    extra_metadata = Column(
        JSON, nullable=True, comment="Additional context and metadata"
    )

    # Status and error tracking
    status = Column(
        String(32), nullable=False, default="success", index=True
    )  # success, error, timeout
    error_message = Column(Text, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_llm_metrics_org_time", "org_id", "created_at"),
        Index("idx_llm_metrics_user_time", "user_id", "created_at"),
        Index("idx_llm_metrics_model_time", "model", "created_at"),
        Index("idx_llm_metrics_task_time", "task_type", "created_at"),
    )


class RagMetric(Base):
    """
    Store RAG (Retrieval-Augmented Generation) performance metrics.

    Tracks retrieval latency, chunk counts, and relevance for RAG operations.
    """

    __tablename__ = "rag_metrics"

    id = Column(Integer, primary_key=True)

    # Organization and user context
    org_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)

    # RAG operation details
    phase = Column(String(64), nullable=False, index=True)  # planning, execution, etc.
    query = Column(Text, nullable=True, comment="Search query or context request")

    # Retrieval metrics
    chunks_retrieved = Column(Integer, nullable=False, default=0)
    chunks_used = Column(
        Integer, nullable=True, comment="Number of chunks actually used in context"
    )
    retrieval_latency_ms = Column(
        Integer, nullable=False, comment="Retrieval time in milliseconds"
    )

    # Quality metrics (if available)
    relevance_score = Column(
        Float, nullable=True, comment="Average relevance score of retrieved chunks"
    )

    # Context
    session_id = Column(String(128), nullable=True, index=True)
    task_id = Column(String(128), nullable=True, index=True)

    # Additional metadata
    extra_metadata = Column(JSON, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_rag_metrics_org_time", "org_id", "created_at"),
        Index("idx_rag_metrics_phase_time", "phase", "created_at"),
    )


class TaskMetric(Base):
    """
    Store task-level metrics for iteration tracking and completion analysis.

    Tracks number of LLM iterations, total task time, and success/failure rates.
    """

    __tablename__ = "task_metrics"

    id = Column(Integer, primary_key=True)

    # Organization and user context
    org_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)

    # Task details
    task_id = Column(String(128), nullable=True, index=True)
    task_type = Column(String(64), nullable=False, index=True)

    # Iteration metrics
    llm_iterations = Column(Integer, nullable=False, default=0)
    rag_retrievals = Column(Integer, nullable=False, default=0)

    # Time metrics
    completion_time_ms = Column(
        Integer, nullable=False, comment="Total task completion time"
    )
    llm_time_ms = Column(
        Integer, nullable=True, comment="Total time spent in LLM calls"
    )
    rag_time_ms = Column(
        Integer, nullable=True, comment="Total time spent in RAG retrieval"
    )

    # Resource usage
    total_tokens = Column(Integer, nullable=False, default=0)
    total_cost = Column(Float, nullable=False, default=0.0)

    # Status
    status = Column(
        String(32), nullable=False, index=True
    )  # success, error, timeout, cancelled
    error_type = Column(String(64), nullable=True, index=True)

    # Additional metadata
    extra_metadata = Column(JSON, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_task_metrics_org_time", "org_id", "created_at"),
        Index("idx_task_metrics_status_time", "status", "created_at"),
        Index("idx_task_metrics_type_status", "task_type", "status"),
    )
