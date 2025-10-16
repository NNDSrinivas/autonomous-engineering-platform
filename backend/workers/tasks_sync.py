from __future__ import annotations

import datetime as dt
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import SessionLocal

broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)


@dramatiq.actor(max_retries=0)
def refresh_task_links() -> None:
    db: Session = SessionLocal()
    try:
        # Get active tasks with links using EXISTS for PostgreSQL compatibility
        tasks = db.execute(
            text(
                """
                SELECT t.id, t.org_id
                FROM task t
                WHERE t.status != 'done' AND EXISTS (
                    SELECT 1 FROM task_link l WHERE l.task_id = t.id
                )
                ORDER BY t.updated_at DESC
                LIMIT 100
            """
            )
        ).all()

        if not tasks:
            return

        # Fix N+1 query: fetch all links in one query
        task_ids = [task_id for task_id, _ in tasks]
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
        from collections import defaultdict

        links_by_task = defaultdict(list)
        for link in links_result:
            links_by_task[link["task_id"]].append(link)

        # Prepare status updates
        status_updates = {}
        for task_id, org_id in tasks:
            links = links_by_task.get(task_id, [])
            inferred_status: str | None = None
            for link in links:
                if link["type"] == "jira":
                    inferred_status = inferred_status or "in_progress"
                elif link["type"] in {"github_pr", "github_issue"}:
                    inferred_status = inferred_status or "in_progress"
            if inferred_status and org_id:
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
                        END,
                        updated_at = :now
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
        db.commit()
    finally:
        db.close()
