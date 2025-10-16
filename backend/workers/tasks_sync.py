import datetime as dt
import dramatiq, httpx
from dramatiq.brokers.redis import RedisBroker
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..core.config import settings
from ..core.db import SessionLocal
from ..services.tasks import update_task

broker = RedisBroker(url=settings.redis_url)
dramatiq.set_broker(broker)

@dramatiq.actor(max_retries=0)
def refresh_task_links():
    db: Session = SessionLocal()
    try:
        # For each task that has links, fetch latest statuses (best-effort)
        tasks = db.execute(text("""
            SELECT DISTINCT t.id
            FROM task t JOIN task_link l ON l.task_id = t.id
            WHERE t.status != 'done'
            ORDER BY t.updated_at DESC LIMIT 100
        """)).fetchall()
        for (task_id,) in tasks:
            links = db.execute(text("SELECT type,key,url FROM task_link WHERE task_id=:id"), {"id": task_id}).mappings().all()
            status = None
            for l in links:
                if l["type"] == "jira":
                    # Heuristic: if we had stored URLs, we could fetch; for MVP mark in_progress if linked
                    status = status or "in_progress"
                elif l["type"] in ("github_pr","github_issue"):
                    status = status or "in_progress"
            if status:
                update_task(db, task_id, status=status)
    finally:
        db.close()