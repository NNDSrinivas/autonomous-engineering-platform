from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.db import get_db
from ..services import tasks as task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str | None = None
    assignee: str | None = None
    priority: str | None = Field(default="P1")
    due_date: str | None = None
    meeting_id: str | None = None
    action_item_id: str | None = None


@router.post("")
def create_task(
    body: CreateTaskRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    org_id = request.headers.get("X-Org-Id")
    task = task_service.create_task(
        db,
        title=body.title,
        description=body.description,
        assignee=body.assignee,
        priority=body.priority,
        due_date=body.due_date,
        meeting_id=body.meeting_id,
        action_item_id=body.action_item_id,
        org_id=org_id,
    )
    return {"id": task.id}


class UpdateTaskRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    assignee: str | None = None
    priority: str | None = None
    due_date: str | None = None


@router.patch("/{task_id}")
def update_task(
    task_id: str,
    body: UpdateTaskRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    org_id = request.headers.get("X-Org-Id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing organization context")
    task = task_service.update_task(
        db,
        task_id,
        org_id=org_id,
        **body.model_dump(exclude_none=True),
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}


@router.get("/{task_id}")
def get_task(task_id: str, request: Request, db: Session = Depends(get_db)):
    org_id = request.headers.get("X-Org-Id")
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing organization context")
    task = task_service.get_task(db, task_id, org_id=org_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("")
def search_tasks(
    request: Request,
    q: str | None = None,
    status: str | None = None,
    assignee: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    org_id = request.headers.get("X-Org-Id")
    items = task_service.list_tasks(
        db,
        q=q,
        status=status,
        assignee=assignee,
        org_id=org_id,
        limit=limit,
    )
    return {"items": items}


@router.get("/stats/summary")
def task_stats(
    request: Request,
    db: Session = Depends(get_db),
    org_id: str | None = Query(default=None),
):
    effective_org = org_id or request.headers.get("X-Org-Id")
    return task_service.stats(db, effective_org)
