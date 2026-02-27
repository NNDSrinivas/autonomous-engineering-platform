"""Add metrics, learning, and telemetry tables for v1

Revision ID: 0031_metrics_learning
Revises: 0ab632cc0bcb
Create Date: 2026-02-06

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0031_metrics_learning"
down_revision = "0ab632cc0bcb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Skip for SQLite (CI uses SQLite for unit tests, this is PostgreSQL-specific)
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        import logging

        logging.getLogger(__name__).info(
            "Skipping metrics/learning/telemetry migration for non-PostgreSQL database (%s)",
            bind.dialect.name,
        )
        return

    # =========================================================================
    # LLM Metrics Tables
    # =========================================================================

    # Create llm_metrics table
    op.create_table(
        "llm_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("output_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("ttft_ms", sa.Integer(), nullable=True),
        sa.Column("task_type", sa.String(64), nullable=True),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column(
            "extra_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_llm_metrics_org_time", "llm_metrics", ["org_id", "created_at"])
    op.create_index(
        "idx_llm_metrics_user_time", "llm_metrics", ["user_id", "created_at"]
    )
    op.create_index(
        "idx_llm_metrics_model_time", "llm_metrics", ["model", "created_at"]
    )
    op.create_index(
        "idx_llm_metrics_task_time", "llm_metrics", ["task_type", "created_at"]
    )
    op.create_index(op.f("ix_llm_metrics_org_id"), "llm_metrics", ["org_id"])
    op.create_index(op.f("ix_llm_metrics_user_id"), "llm_metrics", ["user_id"])
    op.create_index(op.f("ix_llm_metrics_model"), "llm_metrics", ["model"])
    op.create_index(op.f("ix_llm_metrics_provider"), "llm_metrics", ["provider"])
    op.create_index(op.f("ix_llm_metrics_task_type"), "llm_metrics", ["task_type"])
    op.create_index(op.f("ix_llm_metrics_session_id"), "llm_metrics", ["session_id"])
    op.create_index(op.f("ix_llm_metrics_status"), "llm_metrics", ["status"])
    op.create_index(op.f("ix_llm_metrics_created_at"), "llm_metrics", ["created_at"])

    # Create rag_metrics table
    op.create_table(
        "rag_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("phase", sa.String(64), nullable=False),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("chunks_retrieved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunks_used", sa.Integer(), nullable=True),
        sa.Column("retrieval_latency_ms", sa.Integer(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("task_id", sa.String(128), nullable=True),
        sa.Column(
            "extra_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_rag_metrics_org_time", "rag_metrics", ["org_id", "created_at"])
    op.create_index(
        "idx_rag_metrics_phase_time", "rag_metrics", ["phase", "created_at"]
    )
    op.create_index(op.f("ix_rag_metrics_org_id"), "rag_metrics", ["org_id"])
    op.create_index(op.f("ix_rag_metrics_user_id"), "rag_metrics", ["user_id"])
    op.create_index(op.f("ix_rag_metrics_phase"), "rag_metrics", ["phase"])
    op.create_index(op.f("ix_rag_metrics_session_id"), "rag_metrics", ["session_id"])
    op.create_index(op.f("ix_rag_metrics_task_id"), "rag_metrics", ["task_id"])
    op.create_index(op.f("ix_rag_metrics_created_at"), "rag_metrics", ["created_at"])

    # Create task_metrics table
    op.create_table(
        "task_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.String(128), nullable=True),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("llm_iterations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rag_retrievals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_time_ms", sa.Integer(), nullable=False),
        sa.Column("llm_time_ms", sa.Integer(), nullable=True),
        sa.Column("rag_time_ms", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("error_type", sa.String(64), nullable=True),
        sa.Column(
            "extra_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_task_metrics_org_time", "task_metrics", ["org_id", "created_at"]
    )
    op.create_index(
        "idx_task_metrics_status_time", "task_metrics", ["status", "created_at"]
    )
    op.create_index(
        "idx_task_metrics_type_status", "task_metrics", ["task_type", "status"]
    )
    op.create_index(op.f("ix_task_metrics_org_id"), "task_metrics", ["org_id"])
    op.create_index(op.f("ix_task_metrics_user_id"), "task_metrics", ["user_id"])
    op.create_index(op.f("ix_task_metrics_task_id"), "task_metrics", ["task_id"])
    op.create_index(op.f("ix_task_metrics_task_type"), "task_metrics", ["task_type"])
    op.create_index(op.f("ix_task_metrics_status"), "task_metrics", ["status"])
    op.create_index(op.f("ix_task_metrics_error_type"), "task_metrics", ["error_type"])
    op.create_index(op.f("ix_task_metrics_created_at"), "task_metrics", ["created_at"])

    # =========================================================================
    # Learning Data Tables
    # =========================================================================

    # Create learning_suggestions table
    op.create_table(
        "learning_suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("suggestion_text", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("feedback_type", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(256), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "pattern_tags", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("similar_count", sa.Integer(), server_default="0"),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("task_id", sa.String(128), nullable=True),
        sa.Column("model_used", sa.String(128), nullable=True),
        sa.Column("gen_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_learning_sug_org_time", "learning_suggestions", ["org_id", "created_at"]
    )
    op.create_index(
        "idx_learning_sug_category_feedback",
        "learning_suggestions",
        ["category", "feedback_type"],
    )
    op.create_index(
        "idx_learning_sug_user_feedback",
        "learning_suggestions",
        ["user_id", "feedback_type"],
    )
    op.create_index(
        op.f("ix_learning_suggestions_org_id"), "learning_suggestions", ["org_id"]
    )
    op.create_index(
        op.f("ix_learning_suggestions_user_id"), "learning_suggestions", ["user_id"]
    )
    op.create_index(
        op.f("ix_learning_suggestions_category"), "learning_suggestions", ["category"]
    )
    op.create_index(
        op.f("ix_learning_suggestions_feedback_type"),
        "learning_suggestions",
        ["feedback_type"],
    )
    op.create_index(
        op.f("ix_learning_suggestions_session_id"),
        "learning_suggestions",
        ["session_id"],
    )
    op.create_index(
        op.f("ix_learning_suggestions_gen_id"), "learning_suggestions", ["gen_id"]
    )
    op.create_index(
        op.f("ix_learning_suggestions_created_at"),
        "learning_suggestions",
        ["created_at"],
    )

    # Create learning_insights table
    op.create_table(
        "learning_insights",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("insight_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "pattern_data", postgresql.JSON(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("examples", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("times_applied", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("tags", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_updated",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
        ),
        sa.Column("last_applied", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_learning_ins_org_active", "learning_insights", ["org_id", "is_active"]
    )
    op.create_index(
        "idx_learning_ins_type_active",
        "learning_insights",
        ["insight_type", "is_active"],
    )
    op.create_index("idx_learning_ins_confidence", "learning_insights", ["confidence"])
    op.create_index(
        op.f("ix_learning_insights_org_id"), "learning_insights", ["org_id"]
    )
    op.create_index(
        op.f("ix_learning_insights_insight_type"), "learning_insights", ["insight_type"]
    )
    op.create_index(
        op.f("ix_learning_insights_is_active"), "learning_insights", ["is_active"]
    )
    op.create_index(
        op.f("ix_learning_insights_category"), "learning_insights", ["category"]
    )

    # Create learning_patterns table
    op.create_table(
        "learning_patterns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("pattern_key", sa.String(255), nullable=False),
        sa.Column("pattern_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("occurrences", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("positive_feedback", sa.Integer(), server_default="0"),
        sa.Column("negative_feedback", sa.Integer(), server_default="0"),
        sa.Column(
            "context_data", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            onupdate=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_learning_pat_org_type", "learning_patterns", ["org_id", "pattern_type"]
    )
    op.create_index(
        "idx_learning_pat_user_type", "learning_patterns", ["user_id", "pattern_type"]
    )
    op.create_index("idx_learning_pat_key", "learning_patterns", ["pattern_key"])
    op.create_index(
        op.f("ix_learning_patterns_org_id"), "learning_patterns", ["org_id"]
    )
    op.create_index(
        op.f("ix_learning_patterns_user_id"), "learning_patterns", ["user_id"]
    )
    op.create_index(
        op.f("ix_learning_patterns_pattern_type"), "learning_patterns", ["pattern_type"]
    )

    # =========================================================================
    # Telemetry Events Tables
    # =========================================================================

    # Create telemetry_events table
    op.create_table(
        "telemetry_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_category", sa.String(64), nullable=True),
        sa.Column("event_name", sa.String(255), nullable=False),
        sa.Column("event_data", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("source", sa.String(64), nullable=True),
        sa.Column("source_version", sa.String(64), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_stack", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column(
            "extra_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_telemetry_org_time", "telemetry_events", ["org_id", "created_at"]
    )
    op.create_index(
        "idx_telemetry_user_time", "telemetry_events", ["user_id", "created_at"]
    )
    op.create_index(
        "idx_telemetry_type_time", "telemetry_events", ["event_type", "created_at"]
    )
    op.create_index(
        "idx_telemetry_name_time", "telemetry_events", ["event_name", "created_at"]
    )
    op.create_index(
        "idx_telemetry_source_time", "telemetry_events", ["source", "created_at"]
    )
    op.create_index(op.f("ix_telemetry_events_org_id"), "telemetry_events", ["org_id"])
    op.create_index(
        op.f("ix_telemetry_events_user_id"), "telemetry_events", ["user_id"]
    )
    op.create_index(
        op.f("ix_telemetry_events_event_type"), "telemetry_events", ["event_type"]
    )
    op.create_index(
        op.f("ix_telemetry_events_event_category"),
        "telemetry_events",
        ["event_category"],
    )
    op.create_index(
        op.f("ix_telemetry_events_event_name"), "telemetry_events", ["event_name"]
    )
    op.create_index(
        op.f("ix_telemetry_events_session_id"), "telemetry_events", ["session_id"]
    )
    op.create_index(op.f("ix_telemetry_events_source"), "telemetry_events", ["source"])
    op.create_index(
        op.f("ix_telemetry_events_created_at"), "telemetry_events", ["created_at"]
    )

    # Create performance_metrics table
    op.create_table(
        "performance_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("metric_name", sa.String(255), nullable=False),
        sa.Column("metric_type", sa.String(64), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("p50", sa.Integer(), nullable=True),
        sa.Column("p95", sa.Integer(), nullable=True),
        sa.Column("p99", sa.Integer(), nullable=True),
        sa.Column("min_value", sa.Integer(), nullable=True),
        sa.Column("max_value", sa.Integer(), nullable=True),
        sa.Column("avg_value", sa.Integer(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=True),
        sa.Column("operation", sa.String(255), nullable=True),
        sa.Column("component", sa.String(128), nullable=True),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column(
            "extra_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "idx_perf_metric_org_time", "performance_metrics", ["org_id", "created_at"]
    )
    op.create_index(
        "idx_perf_metric_name_time",
        "performance_metrics",
        ["metric_name", "created_at"],
    )
    op.create_index(
        "idx_perf_metric_type_time",
        "performance_metrics",
        ["metric_type", "created_at"],
    )
    op.create_index(
        "idx_perf_metric_op_time", "performance_metrics", ["operation", "created_at"]
    )
    op.create_index(
        op.f("ix_performance_metrics_org_id"), "performance_metrics", ["org_id"]
    )
    op.create_index(
        op.f("ix_performance_metrics_user_id"), "performance_metrics", ["user_id"]
    )
    op.create_index(
        op.f("ix_performance_metrics_metric_name"),
        "performance_metrics",
        ["metric_name"],
    )
    op.create_index(
        op.f("ix_performance_metrics_metric_type"),
        "performance_metrics",
        ["metric_type"],
    )
    op.create_index(
        op.f("ix_performance_metrics_operation"), "performance_metrics", ["operation"]
    )
    op.create_index(
        op.f("ix_performance_metrics_component"), "performance_metrics", ["component"]
    )
    op.create_index(
        op.f("ix_performance_metrics_session_id"), "performance_metrics", ["session_id"]
    )
    op.create_index(
        op.f("ix_performance_metrics_created_at"), "performance_metrics", ["created_at"]
    )

    # Create error_events table
    op.create_table(
        "error_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(128), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("component", sa.String(128), nullable=True),
        sa.Column("operation", sa.String(255), nullable=True),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("environment", sa.String(64), nullable=True),
        sa.Column("version", sa.String(64), nullable=True),
        sa.Column("user_visible", sa.Integer(), server_default="1"),
        sa.Column("recovery_attempted", sa.Integer(), server_default="0"),
        sa.Column("resolved", sa.Integer(), server_default="0"),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column(
            "extra_metadata", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_error_org_time", "error_events", ["org_id", "created_at"])
    op.create_index("idx_error_type_time", "error_events", ["error_type", "created_at"])
    op.create_index(
        "idx_error_severity_time", "error_events", ["severity", "created_at"]
    )
    op.create_index("idx_error_resolved", "error_events", ["resolved", "created_at"])
    op.create_index(op.f("ix_error_events_org_id"), "error_events", ["org_id"])
    op.create_index(op.f("ix_error_events_user_id"), "error_events", ["user_id"])
    op.create_index(op.f("ix_error_events_error_type"), "error_events", ["error_type"])
    op.create_index(op.f("ix_error_events_error_code"), "error_events", ["error_code"])
    op.create_index(op.f("ix_error_events_severity"), "error_events", ["severity"])
    op.create_index(op.f("ix_error_events_component"), "error_events", ["component"])
    op.create_index(op.f("ix_error_events_session_id"), "error_events", ["session_id"])
    op.create_index(op.f("ix_error_events_resolved"), "error_events", ["resolved"])
    op.create_index(op.f("ix_error_events_created_at"), "error_events", ["created_at"])


def downgrade() -> None:
    # Skip for SQLite
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    # Drop tables in reverse order
    op.drop_table("error_events")
    op.drop_table("performance_metrics")
    op.drop_table("telemetry_events")
    op.drop_table("learning_patterns")
    op.drop_table("learning_insights")
    op.drop_table("learning_suggestions")
    op.drop_table("task_metrics")
    op.drop_table("rag_metrics")
    op.drop_table("llm_metrics")
