import re, uuid, datetime as dt
from typing import Iterable
from sqlalchemy.orm import Session
from sqlalchemy import text, select
from ..models.tasks import Task, TaskEvent, TaskLink

def _id(): return str(uuid.uuid4())

JIRA_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
PR_RE = re.compile(r"\bPR\s*#?(\d+)\b", re.IGNORECASE)

def create_task(db: Session, title: str, description: str | None = None,
                assignee: str | None = None, priority: str | None = None,
                due_date: object | None = None, meeting_id: str | None = None,
                action_item_id: str | None = None, org_id: str | None = None) -> Task:
    now = dt.datetime.utcnow()
    t = Task(id=_id(), title=title, description=description or "",
             status="open", assignee=assignee, priority=priority, due_date=due_date,
             created_at=now, updated_at=now, meeting_id=meeting_id,
             action_item_id=action_item_id, org_id=org_id)
    db.add(t); db.commit(); db.refresh(t)
    _add_event(db, t.id, "created", {"title": title})
    _auto_links_from_text(db, t.id, title + " " + (description or ""))
    return t

def _add_event(db: Session, task_id: str, type_: str, data: dict | None):
    ev = TaskEvent(id=_id(), task_id=task_id, type=type_, data=data, created_at=dt.datetime.utcnow())
    db.add(ev); db.commit()

def update_task(db: Session, task_id: str, **fields) -> Task | None:
    t = db.get(Task, task_id)
    if not t: return None
    for k,v in fields.items():
        if v is not None: setattr(t, k, v)
    t.updated_at = dt.datetime.utcnow()
    db.commit(); db.refresh(t)
    if "status" in fields:
        _add_event(db, t.id, "status_changed", {"status": t.status})
    if "assignee" in fields:
        _add_event(db, t.id, "assignee_changed", {"assignee": t.assignee})
    return t

def _auto_links_from_text(db: Session, task_id: str, text_: str):
    for m in JIRA_RE.findall(text_ or ""):
        db.add(TaskLink(id=_id(), task_id=task_id, type="jira", key=m, url=None, meta={}))
    for m in PR_RE.findall(text_ or ""):
        db.add(TaskLink(id=_id(), task_id=task_id, type="github_pr", key=str(m), url=None, meta={}))
    db.commit()

def list_tasks(db: Session, q: str | None = None, status: str | None = None,
               assignee: str | None = None, org_id: str | None = None, limit: int = 50) -> list[dict]:
    clauses, params = ["1=1"], {}
    if q:
        clauses.append("(title LIKE :q OR description LIKE :q)"); params["q"]=f"%{q}%"
    if status:
        clauses.append("status=:s"); params["s"]=status
    if assignee:
        clauses.append("assignee LIKE :a"); params["a"]=f"%{assignee}%"
    if org_id:
        clauses.append("org_id=:o"); params["o"]=org_id
    sql = f"""SELECT id,title,status,assignee,priority,due_date,created_at,updated_at
              FROM task WHERE {' AND '.join(clauses)}
              ORDER BY created_at DESC LIMIT :lim"""
    params["lim"]=limit
    return [dict(r) for r in db.execute(text(sql), params).mappings().all()]

def get_task(db: Session, task_id: str) -> dict | None:
    t = db.get(Task, task_id)
    if not t: return None
    links = db.execute(text("SELECT type,key,url FROM task_link WHERE task_id=:id"), {"id": t.id}).mappings().all()
    return {
        "id": t.id, "title": t.title, "description": t.description, "status": t.status,
        "assignee": t.assignee, "priority": t.priority, "due_date": t.due_date,
        "created_at": t.created_at, "updated_at": t.updated_at,
        "links": [dict(r) for r in links],
        "meeting_id": t.meeting_id, "action_item_id": t.action_item_id
    }

def stats(db: Session, org_id: str | None = None) -> dict:
    where = "WHERE 1=1" + (" AND org_id=:o" if org_id else "")
    rows = db.execute(text(
        f"SELECT status, count(*) FROM task {where} GROUP BY status"
    ), {"o": org_id}).all()
    counts = {r[0]: r[1] for r in rows}
    total = sum(counts.values()) or 1
    ratio = float(counts.get("done", 0)) / float(total)
    # Simple latency calculation (simplified for MVP)
    return {"counts": counts, "completion_ratio": ratio, "avg_latency_seconds": 0}

# Hooks: from meeting action_item → task
def ensure_tasks_for_actions(db: Session, meeting_id: str):
    rows = db.execute(text(
        "SELECT id, title, assignee, source_segment FROM action_item WHERE meeting_id = :mid"
    ), {"mid": meeting_id}).mappings().all()
    for r in rows:
        exists = db.execute(text("SELECT 1 FROM task WHERE action_item_id=:aid"), {"aid": r["id"]}).first()
        if exists: continue
        create_task(db,
            title=r["title"],
            description="Auto-created from meeting action item",
            assignee=r["assignee"],
            priority="P1",
            meeting_id=meeting_id,
            action_item_id=r["id"]
        )