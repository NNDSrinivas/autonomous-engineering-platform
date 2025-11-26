from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import logging
from datetime import datetime

from .models import IngestEvent, IngestResponse, IngestBatchRequest, IngestBatchResponse
from ...core.db import get_db
from ...services.navi_memory_service import store_memory

router = APIRouter(prefix="/events", tags=["events"])

logger = logging.getLogger(__name__)

@router.post("/ingest", response_model=IngestResponse)
async def ingest_event(
    event: IngestEvent, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> IngestResponse:
    """
    Ingest a single event from any connector (Jira, Slack, GitHub, etc.) into NAVI memory.
    
    This is the universal ingestion endpoint that normalizes events from different
    sources into consistent NAVI memory entries.
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
            "ingested_at": datetime.utcnow().isoformat(),
            **event.tags
        }
        
        # Add URL if available
        if event.url:
            tags["url"] = event.url
            
        # Add occurred_at if available
        if event.occurred_at:
            tags["occurred_at"] = event.occurred_at.isoformat()

        # Store in NAVI memory
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
            f"Successfully ingested event {event.source}:{event.event_type}:{event.external_id} as memory #{memory_id} for user {event.user_id}"
        )
        
        return IngestResponse(
            status="success",
            memory_id=str(memory_id),
            message=f"Ingested {event.source} {event.event_type} as memory #{memory_id}"
        )

    except Exception as e:
        logger.error(
            f"Failed to ingest event {event.source}:{event.event_type}:{event.external_id} for user {event.user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to ingest {event.source} event: {str(e)}"
        )

@router.post("/ingest/batch", response_model=IngestBatchResponse)
async def ingest_events_batch(
    batch_request: IngestBatchRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
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
                
            full_content = "\n".join(content_parts) if content_parts else event.external_id
            
            tags = {
                "source": event.source,
                "event_type": event.event_type,
                "external_id": event.external_id,
                "ingested_at": datetime.utcnow().isoformat(),
                **event.tags
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
        errors=errors
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
    if source in ["jira", "linear", "asana", "trello", "azure"] or "issue" in event_type or "task" in event_type:
        return "task"
    
    # Communication/interaction sources
    if source in ["slack", "teams", "zoom", "discord", "email"] or any(x in event_type for x in ["message", "call", "meeting", "chat"]):
        return "interaction"
    
    # Workspace/code-related sources  
    if source in ["github", "gitlab", "bitbucket", "jenkins", "ci"] or any(x in event_type for x in ["commit", "pr", "build", "deploy"]):
        return "workspace"
    
    # Documentation/knowledge sources
    if source in ["confluence", "notion", "wiki", "docs"]:
        return "workspace"
    
    # Default to interaction for unknown sources
    return "interaction"