"""
API endpoints for the Intelligent Context Agent.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.core.db import get_db
from backend.core.intelligence.agent import IntelligentContextAgent, ask_agent, get_task_context_auto
from backend.core.intelligence.models import (
    ContextQuery, 
    ContextResponse, 
    TaskContext, 
    SourceType
)
from backend.core.intelligence.search import ContextIndexer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intelligence", tags=["intelligent-context"])


class AskQuestionRequest(BaseModel):
    question: str
    context: Optional[Dict[str, Any]] = None
    source_types: Optional[List[SourceType]] = None


class TaskContextRequest(BaseModel):
    task_id: str
    task_title: str
    task_type: SourceType = SourceType.JIRA


class IndexContentRequest(BaseModel):
    source_type: SourceType
    content: Dict[str, Any]


@router.post("/ask", response_model=ContextResponse)
async def ask_question(
    request: AskQuestionRequest,
    org_key: str = "default",  # TODO: Extract from JWT token
    user_id: Optional[str] = None,  # TODO: Extract from JWT token
    db: Session = Depends(get_db)
):
    """
    Ask the intelligent agent a question and get contextual answers
    from all integrated platforms.
    
    Example questions:
    - "What is the dev environment link?"
    - "Are there any useful wikis for task ABC-123?"
    - "What was discussed about the authentication feature?"
    - "Who was assigned to work on the user management module?"
    """
    try:
        response = await ask_agent(
            question=request.question,
            org_key=org_key,
            user_id=user_id,
            context=request.context
        )
        return response
        
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(status_code=500, detail="Failed to process question")


@router.post("/task-context", response_model=TaskContext)
async def get_task_context(
    request: TaskContextRequest,
    org_key: str = "default",  # TODO: Extract from JWT token
    db: Session = Depends(get_db)
):
    """
    Get automatic context for a specific task.
    
    This endpoint is called when a user selects/opens a task to work on.
    It automatically gathers all relevant information from all sources:
    - Related Slack discussions
    - Confluence documentation
    - Meeting notes mentioning the task
    - Similar tasks and their solutions
    - Code repositories and pull requests
    """
    try:
        task_context = await get_task_context_auto(
            task_id=request.task_id,
            task_title=request.task_title,
            org_key=org_key
        )
        return task_context
        
    except Exception as e:
        logger.error(f"Error getting task context: {e}")
        raise HTTPException(status_code=500, detail="Failed to get task context")


@router.get("/suggestions")
async def get_question_suggestions(
    task_id: Optional[str] = None,
    context: Optional[str] = None,
    org_key: str = "default"
):
    """
    Get suggested questions based on current context.
    
    This can be used to show users what kinds of questions they can ask.
    """
    suggestions = [
        "What is the dev environment link?",
        "Are there any useful wikis related to this task?",
        "What documentation exists for this feature?",
        "Who else has worked on similar tasks?",
        "What was discussed about this in recent meetings?",
        "Are there any blockers or dependencies for this task?",
        "What is the testing strategy for this feature?",
        "Where can I find the API documentation?",
        "How do I deploy this to staging?",
        "What are the acceptance criteria for this task?"
    ]
    
    if task_id:
        suggestions.extend([
            f"What is the status of task {task_id}?",
            f"Who is assigned to task {task_id}?",
            f"Are there any subtasks for {task_id}?",
            f"What is the priority of task {task_id}?"
        ])
    
    return {"suggestions": suggestions}


@router.post("/index")
async def index_content(
    request: IndexContentRequest,
    background_tasks: BackgroundTasks,
    org_key: str = "default",
    db: Session = Depends(get_db)
):
    """
    Index new content into the context search database.
    
    This endpoint can be called by integration webhooks to keep
    the context database up to date.
    """
    try:
        indexer = ContextIndexer()
        
        if request.source_type == SourceType.JIRA:
            result = indexer.index_jira_issue(request.content, org_key, db)
        elif request.source_type == SourceType.SLACK:
            result = indexer.index_slack_message(request.content, org_key, db)
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"Indexing not yet implemented for {request.source_type}"
            )
        
        return {
            "status": "indexed",
            "source_id": result.source_id,
            "source_type": result.source_type
        }
        
    except Exception as e:
        logger.error(f"Error indexing content: {e}")
        raise HTTPException(status_code=500, detail="Failed to index content")


@router.get("/stats")
async def get_intelligence_stats(
    org_key: str = "default",
    db: Session = Depends(get_db)
):
    """
    Get statistics about the intelligent context system.
    """
    try:
        from backend.core.intelligence.models import ContextSource, UserQuestion
        from sqlalchemy import func
        
        # Count sources by type
        source_counts = db.query(
            ContextSource.source_type,
            func.count(ContextSource.id).label("count")
        ).filter(
            ContextSource.org_key == org_key
        ).group_by(ContextSource.source_type).all()
        
        # Count recent questions
        recent_questions = db.query(func.count(UserQuestion.id)).filter(
            UserQuestion.org_key == org_key
        ).scalar() or 0
        
        # Calculate average results per question
        avg_results = db.query(func.avg(UserQuestion.results_found)).filter(
            UserQuestion.org_key == org_key
        ).scalar() or 0
        
        return {
            "sources_by_type": {row[0]: row[1] for row in source_counts},
            "total_questions_asked": recent_questions,
            "average_results_per_question": float(avg_results),
            "available_source_types": [st.value for st in SourceType]
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")


# Webhook endpoints for real-time indexing

@router.post("/webhooks/jira")
async def jira_webhook(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Webhook for JIRA updates to automatically index new/updated issues.
    """
    try:
        # Extract issue data from JIRA webhook payload
        if "issue" in payload:
            issue_data = payload["issue"]
            org_key = "default"  # TODO: Extract from webhook or issue data
            
            background_tasks.add_task(
                _index_jira_issue_background,
                issue_data,
                org_key
            )
            
            return {"status": "webhook_received", "issue_id": issue_data.get("id")}
        
        return {"status": "ignored", "reason": "no_issue_data"}
        
    except Exception as e:
        logger.error(f"Error processing JIRA webhook: {e}")
        return {"status": "error", "error": str(e)}


@router.post("/webhooks/slack")
async def slack_webhook(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Webhook for Slack events to automatically index relevant messages.
    """
    try:
        # Extract message data from Slack webhook payload
        if "event" in payload and payload["event"]["type"] == "message":
            message_data = payload["event"]
            org_key = "default"  # TODO: Extract from team_id or other identifier
            
            # Only index messages that might be useful (not too short, etc.)
            text = message_data.get("text", "")
            if len(text) > 20 and not text.startswith("<@"):  # Not just mentions
                background_tasks.add_task(
                    _index_slack_message_background,
                    message_data,
                    org_key
                )
            
            return {"status": "webhook_received"}
        
        return {"status": "ignored", "reason": "not_message_event"}
        
    except Exception as e:
        logger.error(f"Error processing Slack webhook: {e}")
        return {"status": "error", "error": str(e)}


# Background tasks for indexing

def _index_jira_issue_background(issue_data: Dict[str, Any], org_key: str):
    """Background task to index a JIRA issue."""
    try:
        db = next(get_db())
        try:
            indexer = ContextIndexer()
            indexer.index_jira_issue(issue_data, org_key, db)
            logger.info(f"Indexed JIRA issue {issue_data.get('id')} for org {org_key}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to index JIRA issue in background: {e}")


def _index_slack_message_background(message_data: Dict[str, Any], org_key: str):
    """Background task to index a Slack message."""
    try:
        db = next(get_db())
        try:
            indexer = ContextIndexer()
            indexer.index_slack_message(message_data, org_key, db)
            logger.info(f"Indexed Slack message {message_data.get('ts')} for org {org_key}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to index Slack message in background: {e}")