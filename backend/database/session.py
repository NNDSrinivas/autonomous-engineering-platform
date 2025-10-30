"""
Database session management utilities.

Provides dependency injection for FastAPI routes and context managers
for synchronous database operations.
"""

import threading
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings

# Lazy initialization to avoid import-time failures (matches pattern in backend/core/db.py)
_engine: Optional[Engine] = None
_SessionLocal = None
_lock = threading.Lock()


def _get_engine() -> Engine:
    """Get or create the database engine (lazy initialization, thread-safe)."""
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                settings = get_settings()
                _engine = create_engine(settings.sqlalchemy_url, echo=False)
    return _engine


def _get_session_local() -> sessionmaker[Session]:
    """Get or create SessionLocal factory (sessionmaker) (lazy initialization, thread-safe)."""
    global _SessionLocal
    if _SessionLocal is None:
        with _lock:
            if _SessionLocal is None:
                engine = _get_engine()
                _SessionLocal = sessionmaker(
                    autocommit=False, autoflush=False, bind=engine
                )
    return _SessionLocal


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Usage:
        with db_session() as session:
            user = session.query(User).filter_by(id=1).first()
            session.commit()  # Explicit commit required

    Note: Transaction commits are left to the caller. Automatic rollback occurs on SQLAlchemyError exceptions only.
    """
    from sqlalchemy.exc import SQLAlchemyError

    SessionLocal = _get_session_local()
    session = SessionLocal()
    try:
        yield session
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.

    Usage:
        @router.get("/users")
        def list_users(db: Session = Depends(get_db)):
            return db.query(User).all()

    The session is automatically closed after the request.
    """
    SessionLocal = _get_session_local()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
