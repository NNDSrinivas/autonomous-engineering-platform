"""Database utility functions for specialized session management."""

from contextlib import contextmanager

from backend.core.db import SessionLocal


@contextmanager
def get_short_lived_session():
    """
    Context manager for short-lived database sessions.

    Use this for validation checks before returning long-lived streaming responses
    (e.g., SSE endpoints) to avoid holding database connections indefinitely.

    This bypasses FastAPI's dependency injection system intentionally, as
    dependencies created with yield (like get_db) are only cleaned up after
    the response completes. For infinite SSE streams, this would mean holding
    a DB connection forever.

    Yields:
        Session: SQLAlchemy database session that will be automatically closed

    Example:
        with get_short_lived_session() as db:
            plan = db.query(LivePlan).filter(...).first()
            if not plan:
                raise HTTPException(404)
        # Session is closed here, before returning streaming response
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
