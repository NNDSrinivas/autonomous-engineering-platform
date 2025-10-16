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
        tasks = db.execute(
            text(
                """
                SELECT DISTINCT t.id
                FROM task t
                JOIN task_link l ON l.task_id = t.id
                WHERE t.status != 'done'
                ORDER BY t.updated_at DESC
                LIMIT 100
                """
            )
        ).fetchall()
        for (task_id,) in tasks:
            links = db.execute(
                text(
                    "SELECT type, key, url FROM task_link WHERE task_id = :task_id"
                ),
                {"task_id": task_id},
            ).mappings()
            inferred_status: str | None = None
            for link in links:
                if link["type"] == "jira":
                    inferred_status = inferred_status or "in_progress"
                elif link["type"] in {"github_pr", "github_issue"}:
                    inferred_status = inferred_status or "in_progress"
            if inferred_status:
                update_task(db, task_id, status=inferred_status)
    finally:
        db.close()
