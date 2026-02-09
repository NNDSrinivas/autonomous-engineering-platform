"""
Import all models to ensure they are registered with SQLAlchemy Base.metadata
This allows Base.metadata.create_all() to create tables for all models.
"""

# Import existing models
from backend.models.ai_feedback import (
    AiFeedback,
    AiGenerationLog,
    TaskType,
)  # noqa: F401
from backend.models.plan import Plan, PlanStep  # noqa: F401
from backend.models.tasks import Task  # noqa: F401
from backend.models.chat_session import ChatSession  # noqa: F401

# Import NEW models for v1
from backend.models.llm_metrics import LlmMetric, RagMetric, TaskMetric  # noqa: F401
from backend.models.learning_data import (  # noqa: F401
    LearningSuggestion,
    LearningInsight,
    LearningPattern,
    FeedbackTypeEnum,
    SuggestionCategoryEnum,
)
from backend.models.telemetry_events import (  # noqa: F401
    TelemetryEvent,
    PerformanceMetric,
    ErrorEvent,
)
from backend.models.mcp_server import McpServer  # noqa: F401

__all__ = [
    # Existing models
    "AiFeedback",
    "AiGenerationLog",
    "TaskType",
    "Plan",
    "PlanStep",
    "Task",
    "ChatSession",
    # New v1 models - Metrics
    "LlmMetric",
    "RagMetric",
    "TaskMetric",
    # New v1 models - Learning
    "LearningSuggestion",
    "LearningInsight",
    "LearningPattern",
    "FeedbackTypeEnum",
    "SuggestionCategoryEnum",
    # New v1 models - Telemetry
    "TelemetryEvent",
    "PerformanceMetric",
    "ErrorEvent",
    "McpServer",
]
