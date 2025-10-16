from __future__ import annotations

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import SessionLocal
from ..services.tasks import update_task

broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)


@dramatiq.actor(max_retries=0)
def refresh_task_links() -> None:
    db: Session = SessionLocal()
    try:
        # Fix PostgreSQL DISTINCT ORDER BY issue by using EXISTS
        tasks = db.execute(
            text(
                """
                SELECT t.id, t.org_id
                FROM task t
                WHERE t.status != 'done'
                AND EXISTS (SELECT 1 FROM task_link l WHERE l.task_id = t.id)
                ORDER BY t.updated_at DESC
                LIMIT 100
                """
            )
        ).fetchall()
        
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
            # Multiple tasks - use IN clause with tuple
            placeholders = ",".join(":task_id_" + str(i) for i in range(len(task_ids)))
            params = {f"task_id_{i}": task_id for i, task_id in enumerate(task_ids)}
            links_result = db.execute(
                text(
                    f"SELECT task_id, type, key, url FROM task_link WHERE task_id IN ({placeholders})"
                ),
                params,
            ).mappings()
        
        # Group links by task_id
        from collections import defaultdict
        links_by_task = defaultdict(list)
        for link in links_result:
            links_by_task[link["task_id"]].append(link)
        
        # Process each task
        for task_id, org_id in tasks:
            links = links_by_task.get(task_id, [])
            inferred_status: str | None = None
            for link in links:
                if link["type"] == "jira":
                    inferred_status = inferred_status or "in_progress"
                elif link["type"] in {"github_pr", "github_issue"}:
                    inferred_status = inferred_status or "in_progress"
            if inferred_status and org_id:
                update_task(db, task_id, org_id=org_id, status=inferred_status)
    finally:
        db.close()
