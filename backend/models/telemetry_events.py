"""Database models for telemetry events."""

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    JSON,
    func,
    Index,
)
from backend.core.db import Base


class TelemetryEvent(Base):
    """
    Store telemetry events from frontend and backend.

    Captures user interactions, feature usage, errors, and performance metrics
    for analytics and debugging. Replaces log-only telemetry with persistent storage.
    """

    __tablename__ = "telemetry_events"

    id = Column(Integer, primary_key=True)

    # Organization and user context
    org_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)

    # Event classification
    event_type = Column(
        String(64), nullable=False, index=True
    )  # click, api_call, error, performance, etc.
    event_category = Column(
        String(64), nullable=True, index=True
    )  # ui, backend, integration, etc.
    event_name = Column(
        String(255), nullable=False, index=True
    )  # specific event identifier

    # Event data
    event_data = Column(
        JSON, nullable=True, comment="Event-specific payload and context"
    )

    # Session and context
    session_id = Column(String(128), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)

    # Source information
    source = Column(String(64), nullable=True, index=True)  # vscode, web, api, backend
    source_version = Column(
        String(64), nullable=True, comment="Extension or app version"
    )

    # Performance metrics (if applicable)
    duration_ms = Column(
        Integer, nullable=True, comment="Duration for performance events"
    )

    # Error information (if applicable)
    error_message = Column(Text, nullable=True)
    error_stack = Column(Text, nullable=True)
    error_code = Column(String(64), nullable=True)

    # Additional metadata
    extra_metadata = Column(JSON, nullable=True, comment="Additional context and tags")

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_telemetry_org_time", "org_id", "created_at"),
        Index("idx_telemetry_user_time", "user_id", "created_at"),
        Index("idx_telemetry_type_time", "event_type", "created_at"),
        Index("idx_telemetry_name_time", "event_name", "created_at"),
        Index("idx_telemetry_source_time", "source", "created_at"),
    )


class PerformanceMetric(Base):
    """
    Store detailed performance metrics for critical operations.

    Tracks latency, throughput, and resource usage for performance analysis.
    """

    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True)

    # Organization and user context
    org_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)

    # Metric identification
    metric_name = Column(String(255), nullable=False, index=True)
    metric_type = Column(
        String(64), nullable=False, index=True
    )  # latency, throughput, resource_usage, etc.

    # Metric values
    value = Column(Integer, nullable=False, comment="Primary metric value")
    unit = Column(
        String(32), nullable=False, comment="Measurement unit: ms, bytes, count, etc."
    )

    # Percentiles and statistics (for aggregated metrics)
    p50 = Column(Integer, nullable=True)
    p95 = Column(Integer, nullable=True)
    p99 = Column(Integer, nullable=True)
    min_value = Column(Integer, nullable=True)
    max_value = Column(Integer, nullable=True)
    avg_value = Column(Integer, nullable=True)
    sample_count = Column(Integer, nullable=True)

    # Context
    operation = Column(
        String(255), nullable=True, index=True
    )  # Specific operation being measured
    component = Column(String(128), nullable=True, index=True)  # System component
    session_id = Column(String(128), nullable=True, index=True)

    # Additional metadata
    extra_metadata = Column(JSON, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_perf_metric_org_time", "org_id", "created_at"),
        Index("idx_perf_metric_name_time", "metric_name", "created_at"),
        Index("idx_perf_metric_type_time", "metric_type", "created_at"),
        Index("idx_perf_metric_op_time", "operation", "created_at"),
    )


class ErrorEvent(Base):
    """
    Store detailed error events for debugging and error tracking.

    Provides structured error tracking with context, stack traces, and resolution status.
    """

    __tablename__ = "error_events"

    id = Column(Integer, primary_key=True)

    # Organization and user context
    org_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)

    # Error classification
    error_type = Column(
        String(128), nullable=False, index=True
    )  # exception class or error category
    error_code = Column(String(64), nullable=True, index=True)
    severity = Column(
        String(32), nullable=False, index=True
    )  # critical, error, warning, info

    # Error details
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text, nullable=True)

    # Context
    component = Column(
        String(128), nullable=True, index=True
    )  # Component where error occurred
    operation = Column(String(255), nullable=True)  # Operation being performed
    session_id = Column(String(128), nullable=True, index=True)

    # Environment
    environment = Column(String(64), nullable=True)  # production, staging, development
    version = Column(String(64), nullable=True)

    # User impact
    user_visible = Column(
        Integer, default=1, comment="Whether error was visible to user (0/1)"
    )
    recovery_attempted = Column(
        Integer, default=0, comment="Whether automatic recovery was attempted (0/1)"
    )

    # Resolution tracking
    resolved = Column(
        Integer, default=0, index=True, comment="Whether error has been resolved (0/1)"
    )
    resolution_notes = Column(Text, nullable=True)

    # Additional metadata
    extra_metadata = Column(JSON, nullable=True)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_error_org_time", "org_id", "created_at"),
        Index("idx_error_type_time", "error_type", "created_at"),
        Index("idx_error_severity_time", "severity", "created_at"),
        Index("idx_error_resolved", "resolved", "created_at"),
    )
