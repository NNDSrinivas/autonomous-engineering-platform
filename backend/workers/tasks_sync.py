from __future__ import annotations

import datetime as dt
from collections import defaultdict

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import SessionLocal

# Defer broker initialization to avoid import-time side effects
broker = None
refresh_task_links_actor = None


def init_broker():
    """Initialize Dramatiq broker - call this at application startup"""
    global broker, refresh_task_links_actor
    if broker is None:
        broker = RedisBroker(url=settings.redis_url)
        dramatiq.set_broker(broker)
        # Register actors after broker is set
        refresh_task_links_actor = dramatiq.actor(max_retries=0)(refresh_task_links)
    return broker


def get_broker():
    """Get the broker, initializing if needed"""
    if broker is None:
        init_broker()
    return broker


def refresh_task_links() -> None:
    db: Session = SessionLocal()
    try:
        # Get active tasks with links using EXISTS for PostgreSQL compatibility
        tasks = (
            db.execute(
                text(
                    """
                SELECT t.id, t.org_id, t.status
                FROM task t
                WHERE t.status != 'done' AND EXISTS (
                    SELECT 1 FROM task_link l WHERE l.task_id = t.id
                )
                ORDER BY t.updated_at DESC
                LIMIT 100
            """
                )
            )
            .mappings()
            .all()
        )

        if not tasks:
            return

        # Fix N+1 query: fetch all links in one query
        task_ids = [task["id"] for task in tasks]
        if len(task_ids) == 1:
            # Single task case
            links_result = db.execute(
                text(
                    "SELECT task_id, type, key, url FROM task_link WHERE task_id = :task_id"
                ),
                {"task_id": task_ids[0]},
            ).mappings()
        else:
            # Multiple tasks - use bindparam with expanding for proper IN clause handling
            links_result = db.execute(
                text(
                    "SELECT task_id, type, key, url FROM task_link WHERE task_id IN :task_ids"
                ).bindparams(bindparam("task_ids", expanding=True)),
                {"task_ids": task_ids},
            ).mappings()

        # Group links by task_id
        links_by_task = defaultdict(list)
        for link in links_result:
            links_by_task[link["task_id"]].append(link)

        # Prepare status updates - only for tasks where status will actually change
        status_updates = {}
        for task in tasks:
            task_id, org_id, current_status = task["id"], task["org_id"], task["status"]
            links = links_by_task.get(task_id, [])
            inferred_status: str | None = None
            for link in links:
                if link["type"] == "jira":
                    inferred_status = inferred_status or "in_progress"
                elif link["type"] in {"github_pr", "github_issue"}:
                    inferred_status = inferred_status or "in_progress"
            # Only update if status actually changes
            if inferred_status and inferred_status != current_status and org_id:
                status_updates[task_id] = {"status": inferred_status}

        # Bulk update tasks if we have any status changes
        if status_updates:
            # Fetch all tasks to update in one query
            task_ids_to_update = list(status_updates.keys())
            placeholders = ",".join(
                f":task_id_{i}" for i in range(len(task_ids_to_update))
            )
            params = {
                f"task_id_{i}": task_id for i, task_id in enumerate(task_ids_to_update)
            }

            # Bulk update status using raw SQL for efficiency
            db.execute(
                text(
                    f"""
                    UPDATE task SET
                        status = CASE id
                            {" ".join(f"WHEN :task_id_{i} THEN :status_{i}" for i in range(len(task_ids_to_update)))}
                            ELSE status
                        END,
                        updated_at = CASE id
                            {" ".join(f"WHEN :task_id_{i} THEN :now" for i in range(len(task_ids_to_update)))}
                            ELSE updated_at
                        END
                    WHERE id IN ({placeholders})
                """
                ),
                {
                    **params,
                    **{
                        f"status_{i}": status_updates[task_id]["status"]
                        for i, task_id in enumerate(task_ids_to_update)
                    },
                    "now": dt.datetime.now(dt.timezone.utc),
                },
            )

        # Single commit after all updates
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
    finally:
        db.close()
