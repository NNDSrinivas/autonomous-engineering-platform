"""
Purge audit logs older than retention window.

Intended for scheduled execution (cron or task runner).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.core.db import get_db
from backend.core.eventstore.models import AuditLog
from backend.core.settings import settings
from sqlalchemy import delete


def main() -> int:
    if not settings.AUDIT_RETENTION_ENABLED:
        print("Audit retention disabled; skipping purge.")
        return 0

    cutoff_dt = datetime.now(timezone.utc) - timedelta(
        days=settings.AUDIT_RETENTION_DAYS
    )

    db_gen = get_db()
    db = next(db_gen)
    try:
        result = db.execute(delete(AuditLog).where(AuditLog.created_at < cutoff_dt))
        db.commit()
        deleted = result.rowcount or 0
        print(f"Purged {deleted} audit rows older than {cutoff_dt.isoformat()}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Audit purge failed: {exc}")
        return 1
    finally:
        db.close()
        next(db_gen, None)


if __name__ == "__main__":
    raise SystemExit(main())
