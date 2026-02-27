from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import asyncio
import logging
from datetime import timezone, datetime

from .models import IngestEvent, IngestResponse, IngestBatchRequest, IngestBatchResponse
from ...core.db import get_db
from ...services.navi_memory_service import store_memory

router = APIRouter(prefix="/events", tags=["events"])

logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check(db: Session = Depends(get_db)) -> dict:
    """
    Health check endpoint for memory ingestion service.

    Returns status of database connection and memory service availability.
    Used by monitoring and load balancers to verify service health.
    """
    health_status = {
        "service": "events-ingestion",
        "status": "healthy",
        "checks": []
    }

    # Check database connection
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        health_status["checks"].append({
            "name": "database",
            "status": "ok",
            "message": "Database connection successful"
        })
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"].append({
            "name": "database",
            "status": "error",
            "message": f"Database connection failed: {str(e)}"
        })
        logger.error(f"Database health check failed: {e}")

    # Check OpenAI API key configuration
    import os
    if os.getenv("OPENAI_API_KEY"):
        health_status["checks"].append({
            "name": "openai_config",
            "status": "ok",
            "message": "OpenAI API key configured"
        })
    else:
        health_status["status"] = "degraded"
        health_status["checks"].append({
            "name": "openai_config",
            "status": "warning",
            "message": "OpenAI API key not configured - embeddings will fail"
        })

    return health_status


async def _process_event_in_background(
    event: IngestEvent,
    db: Session,
) -> None:
    """
    Background task to process event ingestion asynchronously.

    This prevents slow OpenAI embedding API calls from blocking the HTTP response.
    Errors are logged but don't propagate to the caller since this runs async.
    """
    try:
        # Determine memory category based on source and event type
        category = _determine_memory_category(event.source, event.event_type)

        # Build comprehensive content for embedding and retrieval
        content_parts = []
        if event.title:
            content_parts.append(f"Title: {event.title}")
        if event.summary:
            content_parts.append(f"Summary: {event.summary}")
        if event.content:
            content_parts.append(f"Content: {event.content}")

        full_content = "\n".join(content_parts) if content_parts else event.external_id

        # Prepare comprehensive tags
        tags = {
            "source": event.source,
            "event_type": event.event_type,
            "external_id": event.external_id,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            **event.tags,
        }

        # Add URL if available
        if event.url:
            tags["url"] = event.url

        # Add occurred_at if available
        if event.occurred_at:
            tags["occurred_at"] = event.occurred_at.isoformat()

        # Store in NAVI memory (this includes slow OpenAI embedding call)
        memory_id = await store_memory(
            db=db,
            user_id=event.user_id,
            category=category,
            content=full_content,
            scope=event.external_id,
            title=event.title,
            tags=tags,
            importance=event.importance or 3,
        )

        logger.info(
            f"Background task: Successfully ingested event {event.source}:{event.event_type}:{event.external_id} as memory #{memory_id} for user {event.user_id}"
        )

    except asyncio.TimeoutError:
        # OpenAI embedding generation timed out (>10s default)
        logger.error(
            f"Background task: OpenAI embedding timeout for event {event.source}:{event.event_type}:{event.external_id} for user {event.user_id}. "
            "Check OpenAI API latency or increase timeout_seconds parameter.",
            exc_info=True
        )
    except Exception as e:
        # Log error but don't re-raise since this is a background task
        # Memory ingestion is best-effort and shouldn't break the application
        logger.error(
            f"Background task: Failed to ingest event {event.source}:{event.event_type}:{event.external_id} for user {event.user_id}: {str(e)}",
            exc_info=True
        )


@router.post("/ingest", response_model=IngestResponse)
async def ingest_event(
    event: IngestEvent, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
) -> IngestResponse:
    """
    Ingest a single event from any connector (Jira, Slack, GitHub, etc.) into NAVI memory.

    This is the universal ingestion endpoint that normalizes events from different
    sources into consistent NAVI memory entries.

    PERFORMANCE: Returns immediately and processes ingestion in the background to avoid
    timeout issues from slow OpenAI embedding API calls (1-3 seconds per event).

    RELIABILITY: Memory ingestion is best-effort - failures are logged but don't block
    the response. This prevents timeout errors in the VS Code extension.
    """
    try:
        # Validate event immediately (fast - no IO)
        if not event.user_id or not event.source or not event.event_type:
            raise HTTPException(
                status_code=422,
                detail="Missing required fields: user_id, source, or event_type"
            )

        # Queue background task for async processing
        # This returns immediately without waiting for OpenAI embedding generation
        background_tasks.add_task(_process_event_in_background, event, db)

        # Return success immediately - actual processing happens in background
        logger.info(
            f"Queued event ingestion: {event.source}:{event.event_type}:{event.external_id} for user {event.user_id}"
        )

        return IngestResponse(
            status="queued",
            memory_id="pending",
            message=f"Event {event.source} {event.event_type} queued for ingestion",
        )

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors)
        raise
    except Exception as e:
        # Log unexpected errors and return HTTP 503 for queueing failures
        logger.error(
            f"Failed to queue event {event.source}:{event.event_type}:{event.external_id} for user {event.user_id}: {str(e)}",
            exc_info=True
        )
        # Return HTTP 503 to signal temporary failure - allows client retry logic
        raise HTTPException(
            status_code=503,
            detail=f"Failed to queue event for ingestion: {str(e)}. Service temporarily unavailable, please retry."
        )


@router.post("/ingest/batch", response_model=IngestBatchResponse)
async def ingest_events_batch(
    batch_request: IngestBatchRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> IngestBatchResponse:
    """
    Batch ingest multiple events at once for efficiency.
    Useful for initial syncs or bulk imports.
    """
    memory_ids = []
    errors = []
    processed = 0

    for i, event in enumerate(batch_request.events):
        try:
            # Use the same logic as single ingest
            category = _determine_memory_category(event.source, event.event_type)

            content_parts = []
            if event.title:
                content_parts.append(f"Title: {event.title}")
            if event.summary:
                content_parts.append(f"Summary: {event.summary}")
            if event.content:
                content_parts.append(f"Content: {event.content}")

            full_content = (
                "\n".join(content_parts) if content_parts else event.external_id
            )

            tags = {
                "source": event.source,
                "event_type": event.event_type,
                "external_id": event.external_id,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                **event.tags,
            }

            if event.url:
                tags["url"] = event.url
            if event.occurred_at:
                tags["occurred_at"] = event.occurred_at.isoformat()

            memory_id = await store_memory(
                db=db,
                user_id=event.user_id,
                category=category,
                content=full_content,
                scope=event.external_id,
                title=event.title,
                tags=tags,
                importance=event.importance or 3,
            )

            memory_ids.append(str(memory_id))
            processed += 1

        except Exception as e:
            error_msg = f"Event {i}: {str(e)}"
            errors.append(error_msg)
            logger.error(f"Batch ingest error for event {i}: {str(e)}")

    failed = len(batch_request.events) - processed

    logger.info(
        f"Batch ingest completed: {processed}/{len(batch_request.events)} successful, {failed} failed"
    )

    return IngestBatchResponse(
        status="completed",
        processed=processed,
        failed=failed,
        memory_ids=memory_ids,
        errors=errors,
    )


def _determine_memory_category(source: str, event_type: str) -> str:
    """
    Determine the appropriate NAVI memory category based on source and event type.

    Categories:
    - profile: User-related information
    - workspace: Project/repo/workspace context
    - task: Work items, issues, todos
    - interaction: Communications, meetings, messages
    """
    # Task-related sources and events
    if (
        source in ["jira", "linear", "asana", "trello", "azure"]
        or "issue" in event_type
        or "task" in event_type
    ):
        return "task"

    # Communication/interaction sources
    if source in ["slack", "teams", "zoom", "discord", "email"] or any(
        x in event_type for x in ["message", "call", "meeting", "chat"]
    ):
        return "interaction"

    # Workspace/code-related sources
    if source in ["github", "gitlab", "bitbucket", "jenkins", "ci"] or any(
        x in event_type for x in ["commit", "pr", "build", "deploy"]
    ):
        return "workspace"

    # Documentation/knowledge sources
    if source in ["confluence", "notion", "wiki", "docs"]:
        return "workspace"

    # Default to interaction for unknown sources
    return "interaction"
