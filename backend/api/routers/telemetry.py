"""
Telemetry API Router - Receives frontend telemetry events
"""

import logging
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


class TelemetryEvent(BaseModel):
    """Individual telemetry event from frontend"""

    type: str = Field(
        ..., description="Event type (e.g., 'navi.streaming.performance')"
    )
    timestamp: int = Field(..., description="Unix timestamp in milliseconds")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event data")
    sessionId: str | None = Field(None, description="Frontend session ID")
    userId: str | None = Field(None, description="User ID if available")
    workspaceRoot: str | None = Field(None, description="Workspace root path")


class TelemetryBatch(BaseModel):
    """Batch of telemetry events from frontend"""

    events: List[TelemetryEvent] = Field(..., description="List of telemetry events")
    batchId: str = Field(..., description="Unique batch identifier")
    timestamp: int = Field(..., description="Batch creation timestamp")


@router.post("")
async def receive_telemetry(
    batch: TelemetryBatch,
    request: Request,
    session: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Receive and process telemetry events from frontend.

    Persists events to database for analytics and monitoring.
    Also emits Prometheus metrics for real-time monitoring.

    Returns:
        Success response with received event count
    """
    logger.info(
        f"[Telemetry] Received batch {batch.batchId} with {len(batch.events)} events"
    )

    # Extract request metadata
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # Process and persist events
    persisted_count = 0
    for event in batch.events:
        logger.debug(
            f"[Telemetry] {event.type} | session={event.sessionId} | data={event.data}"
        )

        # Persist to database for v1 analytics
        try:
            _persist_telemetry_event(
                session=session,
                event=event,
                client_ip=client_ip,
                user_agent=user_agent,
            )
            persisted_count += 1
        except Exception as e:
            logger.warning(f"Failed to persist telemetry event: {e}")

        # Emit Prometheus metrics for real-time monitoring
        if event.type == "navi.streaming.performance":
            _emit_streaming_metrics(event.data)
        elif event.type == "navi.llm.generation":
            _emit_llm_metrics(event.data)
        elif event.type == "navi.error":
            logger.warning(
                f"[Telemetry] Frontend error: {event.data.get('error')} | {event.data.get('context', {})}"
            )
            # Persist error events to error_events table
            try:
                await _persist_error_event(
                    session=session,
                    event=event,
                    client_ip=client_ip,
                    user_agent=user_agent,
                )
            except Exception as e:
                logger.warning(f"Failed to persist error event: {e}")

    return {
        "success": True,
        "batchId": batch.batchId,
        "eventsReceived": len(batch.events),
        "eventsPersisted": persisted_count,
        "message": "Telemetry received and persisted successfully",
    }


def _persist_telemetry_event(
    session: Session,
    event: TelemetryEvent,
    client_ip: str | None,
    user_agent: str | None,
) -> None:
    """Persist telemetry event to database."""
    from backend.models.telemetry_events import TelemetryEvent as DBTelemetryEvent

    # Extract event type and category
    event_parts = event.type.split(".")
    event_category = event_parts[0] if len(event_parts) > 0 else None
    event_name = ".".join(event_parts[1:]) if len(event_parts) > 1 else event.type

    # Parse user_id and org_id from event data or userId field
    user_id_int = None
    if event.userId and str(event.userId).isdigit():
        user_id_int = int(event.userId)
    elif event.data.get("userId") and str(event.data.get("userId")).isdigit():
        user_id_int = int(event.data.get("userId"))

    org_id_int = None
    if event.data.get("orgId") and str(event.data.get("orgId")).isdigit():
        org_id_int = int(event.data.get("orgId"))

    db_event = DBTelemetryEvent(
        org_id=org_id_int,
        user_id=user_id_int,
        event_type=event_category or "unknown",
        event_category=event_category,
        event_name=event_name,
        event_data=event.data,
        session_id=event.sessionId,
        user_agent=user_agent,
        ip_address=client_ip,
        source="vscode",  # Assuming frontend events are from VSCode extension
        duration_ms=event.data.get("duration_ms") or event.data.get("latencyMs"),
        error_message=event.data.get("error"),
        error_code=event.data.get("errorCode"),
    )

    session.add(db_event)
    session.commit()
    logger.debug(f"[Telemetry] 💾 Persisted event {event.type} to database")


def _persist_error_event(
    session: Session,
    event: TelemetryEvent,
    client_ip: str | None,
    user_agent: str | None,
) -> None:
    """Persist error event to error_events table for detailed tracking."""
    from backend.models.telemetry_events import ErrorEvent

    # Parse user_id and org_id
    user_id_int = None
    if event.userId and str(event.userId).isdigit():
        user_id_int = int(event.userId)

    org_id_int = None
    if event.data.get("orgId") and str(event.data.get("orgId")).isdigit():
        org_id_int = int(event.data.get("orgId"))

    error_event = ErrorEvent(
        org_id=org_id_int,
        user_id=user_id_int,
        error_type=event.data.get("errorType", "unknown"),
        error_code=event.data.get("errorCode"),
        severity=event.data.get("severity", "error"),
        error_message=event.data.get("error", "Unknown error"),
        stack_trace=event.data.get("stack"),
        component=event.data.get("component"),
        operation=event.data.get("operation"),
        session_id=event.sessionId,
        environment="production",  # Could be extracted from config
        user_visible=1 if event.data.get("userVisible", True) else 0,
    )

    session.add(error_event)
    session.commit()
    logger.debug("[Telemetry] 💾 Persisted error event to database")


def _emit_streaming_metrics(data: Dict[str, Any]) -> None:
    """
    Emit Prometheus metrics for streaming performance.

    TODO: Wire this up to actual Prometheus metrics when ready.
    """
    # Example of what this would look like when wired:
    # from backend.telemetry.metrics import STREAMING_LATENCY, STREAMING_THROUGHPUT
    #
    # if "time_to_first_token_ms" in data:
    #     STREAMING_LATENCY.labels(metric="ttft").observe(data["time_to_first_token_ms"])
    # if "tokens_per_second" in data:
    #     STREAMING_THROUGHPUT.observe(data["tokens_per_second"])

    logger.debug(f"[Telemetry] Streaming metrics: {data}")


def _emit_llm_metrics(data: Dict[str, Any]) -> None:
    """
    Emit Prometheus metrics for LLM generation.

    TODO: Wire this up to actual Prometheus metrics when ready.
    """
    # Example of what this would look like when wired:
    # from backend.telemetry.metrics import LLM_CALLS, LLM_LATENCY
    #
    # LLM_CALLS.labels(
    #     phase="frontend",
    #     model=data.get("model", "unknown"),
    #     status="success" if data.get("success") else "error"
    # ).inc()
    #
    # if "latencyMs" in data:
    #     LLM_LATENCY.labels(
    #         phase="frontend",
    #         model=data.get("model", "unknown")
    #     ).observe(data["latencyMs"])

    logger.debug(f"[Telemetry] LLM metrics: {data}")


@router.get("/health")
async def telemetry_health() -> Dict[str, str]:
    """Health check for telemetry endpoint"""
    return {"status": "healthy", "service": "telemetry"}
