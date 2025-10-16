from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..core.db import get_db
from ..services import tasks as svc

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

class CreateTaskReq(BaseModel):
    title: str
    description: str | None = None
    assignee: str | None = None
    priority: str | None = "P1"
    due_date: str | None = None
    meeting_id: str | None = None
    action_item_id: str | None = None

@router.post("")
def create_task(body: CreateTaskReq, db: Session = Depends(get_db)):
    t = svc.create_task(db, title=body.title, description=body.description,
                        assignee=body.assignee, priority=body.priority,
                        due_date=body.due_date, meeting_id=body.meeting_id,
                        action_item_id=body.action_item_id)
    return {"id": t.id}

class UpdateTaskReq(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    assignee: str | None = None
    priority: str | None = None
    due_date: str | None = None

@router.patch("/{task_id}")
def update_task(task_id: str, body: UpdateTaskReq, db: Session = Depends(get_db)):
    t = svc.update_task(db, task_id, **body.model_dump(exclude_none=True))
    if not t: raise HTTPException(status_code=404, detail="Task not found")
    return {"ok": True}

@router.get("/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    res = svc.get_task(db, task_id)
    if not res: raise HTTPException(status_code=404, detail="Task not found")
    return res

@router.get("")
def search(q: str | None = None, status: str | None = None, assignee: str | None = None,
           limit: int = Query(50, le=100), db: Session = Depends(get_db)):
    return {"items": svc.list_tasks(db, q=q, status=status, assignee=assignee, limit=limit)}

@router.get("/stats/summary")
def stats(db: Session = Depends(get_db)):
    return svc.stats(db)