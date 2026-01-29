"""
Database session management utilities.

Provides dependency injection for FastAPI routes and context managers
for synchronous database operations.
"""

import os
import threading
from pathlib import Path
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings

# Lazy initialization to avoid import-time failures (matches pattern in backend/core/db.py)
_engine: Optional[Engine] = None
_SessionLocal = None
_engine_lock = threading.Lock()
_session_lock = threading.Lock()


def _get_engine() -> Engine:
    """Get or create the database engine (lazy initialization, thread-safe)."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                settings = get_settings()
                database_url = settings.sqlalchemy_url
                if os.getenv("PYTEST_CURRENT_TEST") and not os.getenv("DATABASE_URL"):
                    database_url = "sqlite:///./data/aep_test.db"
                url = make_url(database_url)
                if url.get_backend_name() == "sqlite":
                    database = url.database
                    if database and database != ":memory:":
                        db_path = Path(database).expanduser()
                        if not db_path.is_absolute():
                            db_path = Path.cwd() / db_path
                        db_path.parent.mkdir(parents=True, exist_ok=True)
                    _engine = create_engine(
                        database_url,
                        echo=False,
                        connect_args={"check_same_thread": False},
                    )
                else:
                    _engine = create_engine(database_url, echo=False)
    return _engine


def _get_session_local() -> sessionmaker[Session]:
    """Get or create SessionLocal factory (sessionmaker) (lazy initialization, thread-safe)."""
    global _SessionLocal
    if _SessionLocal is None:
        with _session_lock:
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
