from __future__ import annotations

import datetime as dt
import re
import uuid
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..models.tasks import Task, TaskEvent, TaskLink

try:  # pragma: no cover - optional metrics wiring
    from ..core.middleware import TASK_CREATED, TASK_DONE, TASK_LATENCY
except Exception:  # noqa: BLE001 - best-effort metrics import
    TASK_CREATED = TASK_DONE = TASK_LATENCY = None

JIRA_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
PR_RE = re.compile(r"\bPR\s*#?(\d+)\b", re.IGNORECASE)


def _new_id() -> str:
    return str(uuid.uuid4())


def _parse_due_date(value: Any) -> Optional[dt.datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, (int, float)):
        return dt.datetime.fromtimestamp(float(value), tz=dt.timezone.utc)
    if isinstance(value, str):
        try:
            d = dt.datetime.fromisoformat(value)
            return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            return None
    return None


def _observe_latency(task: Task) -> None:
    if TASK_LATENCY and task.updated_at and task.created_at:
        try:
            delta = task.updated_at - task.created_at
            TASK_LATENCY.observe(max(delta.total_seconds(), 0))
        except Exception:  # pragma: no cover - metrics failures ignored
            pass


def _record_status_metrics(task: Task, previous_status: Optional[str]) -> None:
    if TASK_CREATED and previous_status is None:
        TASK_CREATED.inc()
    if TASK_DONE and previous_status != "done" and task.status == "done":
        TASK_DONE.inc()
    _observe_latency(task)


def create_task(
    db: Session,
    title: str,
    description: Optional[str] = None,
    assignee: Optional[str] = None,
    priority: Optional[str] = None,
    due_date: Any | None = None,
    meeting_id: Optional[str] = None,
    action_item_id: Optional[str] = None,
    org_id: Optional[str] = None,
    *,
    commit: bool = True,
) -> Task:
    """
    Create a new task and persist it to the database.

    Parameters:
        db (Session): SQLAlchemy database session.
        title (str): Title of the task.
        description (Optional[str]): Description of the task.
        assignee (Optional[str]): User ID of the assignee.
        priority (Optional[str]): Priority of the task (P0, P1, P2, P3).
        due_date (Any | None): Due date for the task. Accepts:
            - datetime.datetime (with or without tzinfo)
            - int or float (interpreted as Unix timestamp, seconds)
            - str (ISO 8601 format, e.g. "2024-06-01T12:00:00+00:00")
            - None or empty string for no due date
        meeting_id (Optional[str]): Associated meeting ID.
        action_item_id (Optional[str]): Associated action item ID.
        org_id (Optional[str]): Organization ID.
        commit (bool): Whether to commit the transaction (default: True).

    Side Effects:
        - Persists the new task to the database.
        - Emits a "created" TaskEvent.
        - Auto-links related entities from the task text.
        - Emits metrics/events if metrics wiring is enabled (TASK_CREATED, TASK_LATENCY).

    Returns:
        Task: The created Task object.

    Raises:
        ValueError: If due_date is provided but not in a recognized format.
    """
    # Validate due_date consistently with update_task
    parsed_due_date = _parse_due_date(due_date)
    if parsed_due_date is None and due_date is not None and str(due_date).strip() != "":
        raise ValueError(f"Invalid due_date string: {due_date!r}")

    now = dt.datetime.now(dt.timezone.utc)
    task = Task(
        id=_new_id(),
        title=title,
        description=(description or "").strip() or None,
        status="open",
        assignee=assignee,
        priority=priority,
        due_date=parsed_due_date,
        created_at=now,
        updated_at=now,
        meeting_id=meeting_id,
        action_item_id=action_item_id,
        org_id=org_id,
    )
    db.add(task)

    # Batch all related operations before committing
    _add_event(db, task.id, "created", {"title": title}, commit=False)
    _auto_links_from_text(db, task.id, f"{title} {description or ''}", commit=False)

    # Commit only if requested
    if commit:
        db.commit()
        db.refresh(task)
        _record_status_metrics(task, previous_status=None)

    return task


def _add_event(
    db: Session,
    task_id: str,
    event_type: str,
    data: Optional[dict],
    *,
    commit: bool = True,
) -> None:
    event = TaskEvent(
        id=_new_id(),
        task_id=task_id,
        type=event_type,
        data=data,
        created_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(event)
    if commit:
        db.commit()


def update_task(
    db: Session,
    task_id: str,
    *,
    org_id: Optional[str] = None,
    commit: bool = True,
    **fields: Any,
) -> Optional[Task]:
    """
    Update an existing task with provided fields.

    Parameters:
        db (Session): SQLAlchemy database session.
        task_id (str): ID of the task to update.
        org_id (Optional[str]): Organization ID for authorization.
        commit (bool): Whether to commit the transaction (default: True).
        **fields: Fields to update (title, description, status, assignee, priority, due_date).

    Side Effects:
        - Updates the task in the database.
        - Emits an "updated" TaskEvent.
        - Validates status and priority values.
        - Emits metrics/events if metrics wiring is enabled.

    Returns:
        Optional[Task]: The updated Task object, or None if not found.

    Raises:
        ValueError: If field values are invalid or due_date format is unrecognized.
    """
    if not org_id:
        return None

    stmt = select(Task).where(Task.id == task_id, Task.org_id == org_id)
    task = db.scalars(stmt).first()
    if not task:
        return None

    previous_status = task.status

    # Whitelist of allowed updatable columns for security
    allowed_fields = {
        "title",
        "description",
        "status",
        "assignee",
        "priority",
        "due_date",
    }
    mutable_fields = {k: v for k, v in fields.items() if k in allowed_fields}

    # Reject request if unknown keys were provided
    unknown_keys = set(fields.keys()) - allowed_fields
    if unknown_keys:
        raise ValueError(
            f"Invalid update fields: {', '.join(unknown_keys)}. Allowed: {', '.join(sorted(allowed_fields))}"
        )

    if "due_date" in mutable_fields:
        # Handle empty strings by converting to None for clearing the field
        if mutable_fields["due_date"] == "":
            mutable_fields["due_date"] = None
        elif mutable_fields["due_date"] is not None:
            parsed_due_date = _parse_due_date(mutable_fields["due_date"])
            if parsed_due_date is None and str(mutable_fields["due_date"]).strip() != "":
                raise ValueError(f"Invalid due_date string: {mutable_fields['due_date']!r}")
            mutable_fields["due_date"] = parsed_due_date

    # Validate field values for data integrity
    if "status" in mutable_fields:
        valid_statuses = {"open", "in_progress", "done"}
        if mutable_fields["status"] not in valid_statuses:
            raise ValueError(
                f"Invalid status: {mutable_fields['status']!r}. Must be one of: {', '.join(sorted(valid_statuses))}"
            )

    if "priority" in mutable_fields and mutable_fields["priority"] is not None:
        valid_priorities = {"P0", "P1", "P2", "P3"}
        if mutable_fields["priority"] not in valid_priorities:
            raise ValueError(
                f"Invalid priority: {mutable_fields['priority']!r}. Must be one of: {', '.join(sorted(valid_priorities))}"
            )

    for key, value in mutable_fields.items():
        setattr(task, key, value)

    task.updated_at = dt.datetime.now(dt.timezone.utc)

    # Add events before committing
    if "status" in mutable_fields:
        _add_event(db, task.id, "status_changed", {"status": task.status}, commit=False)
    if "assignee" in mutable_fields:
        _add_event(db, task.id, "assignee_changed", {"assignee": task.assignee}, commit=False)

    if commit:
        db.commit()
        db.refresh(task)

    _record_status_metrics(task, previous_status=previous_status)
    return task


def _auto_links_from_text(
    db: Session, task_id: str, text_value: str, *, commit: bool = False
) -> None:
    links_to_add: list[TaskLink] = []

    # Deduplicate JIRA keys to avoid unique constraint violations
    jira_keys = set(JIRA_RE.findall(text_value or ""))
    for key in jira_keys:
        links_to_add.append(
            TaskLink(
                id=_new_id(),
                task_id=task_id,
                type="jira",
                key=key,
                url=None,
                meta={},
            )
        )

    # Deduplicate PR numbers to avoid unique constraint violations
    pr_numbers = set(PR_RE.findall(text_value or ""))
    for pr_number in pr_numbers:
        links_to_add.append(
            TaskLink(
                id=_new_id(),
                task_id=task_id,
                type="github_pr",
                key=str(pr_number),
                url=None,
                meta={},
            )
        )

    if links_to_add:
        db.add_all(links_to_add)
        if commit:
            db.commit()


def list_tasks(
    db: Session,
    q: Optional[str] = None,
    status: Optional[str] = None,
    assignee: Optional[str] = None,
    org_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    clauses = ["1=1"]
    params: dict[str, Any] = {}
    if q:
        clauses.append("(title ILIKE :q OR description ILIKE :q)")
        params["q"] = f"%{q}%"
    if status:
        clauses.append("status = :status")
        params["status"] = status
    if assignee:
        clauses.append("assignee ILIKE :assignee")
        params["assignee"] = f"%{assignee}%"
    if org_id:
        clauses.append("org_id = :org")
        params["org"] = org_id
    params["limit"] = limit

    sql = text(
        """
        SELECT id, title, status, assignee, priority, due_date, created_at, updated_at
        FROM task
        WHERE """
        + " AND ".join(clauses)
        + " ORDER BY created_at DESC LIMIT :limit"
    )
    return [dict(row) for row in db.execute(sql, params).mappings().all()]


def get_task(db: Session, task_id: str, org_id: Optional[str] = None) -> Optional[dict]:
    if not org_id:
        return None

    stmt = select(Task).where(Task.id == task_id, Task.org_id == org_id)
    task = db.scalars(stmt).first()
    if not task:
        return None
    links = db.execute(
        text("SELECT type, key, url, meta FROM task_link WHERE task_id = :task_id"),
        {"task_id": task.id},
    ).mappings()
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "assignee": task.assignee,
        "priority": task.priority,
        "due_date": task.due_date,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "meeting_id": task.meeting_id,
        "action_item_id": task.action_item_id,
        "links": [dict(row) for row in links],
    }


def stats(db: Session, org_id: Optional[str] = None) -> dict:
    params: dict[str, Any] = {}
    where = "WHERE 1=1"
    if org_id:
        where += " AND org_id = :org"
        params["org"] = org_id

    rows = db.execute(
        text(f"SELECT status, COUNT(*) FROM task {where} GROUP BY status"), params
    ).all()
    counts = {status: count for status, count in rows}
    total = sum(counts.values()) or 1
    ratio = float(counts.get("done", 0)) / float(total)

    latency = db.execute(
        text(
            "SELECT AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) FROM task "
            + ("WHERE org_id = :org" if org_id else "")
        ),
        params,
    ).scalar()

    return {
        "counts": counts,
        "completion_ratio": ratio,
        "avg_latency_seconds": int(latency or 0),
    }


def ensure_tasks_for_actions(db: Session, meeting_id: str) -> None:
    """
    Create tasks for action items that don't already have associated tasks.

    Parameters:
        db (Session): SQLAlchemy database session.
        meeting_id (str): ID of the meeting to process action items for.

    Side Effects:
        - Creates new tasks for action items without existing tasks.
        - Uses batch operations for efficiency.
        - Commits all task creation in a single transaction.
        - Emits metrics for each created task.

    Returns:
        None
    """
    meeting_row = db.execute(
        text("SELECT org_id FROM meeting WHERE id = :meeting_id"),
        {"meeting_id": meeting_id},
    ).first()
    meeting_org_id = meeting_row[0] if meeting_row else None

    action_rows = db.execute(
        text(
            """
            SELECT id, title, assignee, source_segment
            FROM action_item
            WHERE meeting_id = :meeting_id
            """
        ),
        {"meeting_id": meeting_id},
    ).mappings()

    # Prefetch all existing action_item_id values for the meeting in a single query
    existing_action_item_ids = {
        r[0]
        for r in db.execute(
            text("SELECT action_item_id FROM task WHERE meeting_id = :meeting_id"),
            {"meeting_id": meeting_id},
        )
        if r[0] is not None
    }

    tasks_created = []
    for mapping in action_rows:
        row = dict(mapping)
        if row["id"] in existing_action_item_ids:
            continue
        task = create_task(
            db,
            title=row["title"],
            description=(row.get("source_segment") or "Auto-created from meeting action item"),
            assignee=row.get("assignee"),
            priority="P1",
            meeting_id=meeting_id,
            action_item_id=row["id"],
            org_id=meeting_org_id,
            commit=False,
        )
        tasks_created.append(task)

    # Commit once after all tasks are created
    if tasks_created:
        db.commit()
        for task in tasks_created:
            db.refresh(task)
            _record_status_metrics(task, previous_status=None)
