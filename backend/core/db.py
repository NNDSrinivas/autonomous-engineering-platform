from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
import logging
from typing import Optional

from .config import settings


def _create_engine() -> Engine:
    """
    Create the SQLAlchemy engine, ensuring SQLite file paths are ready beforehand.

    GitHub Actions configures `DATABASE_URL` to point at a SQLite file under `./data/`.
    On a clean checkout that directory may not exist yet, which would cause an
    OperationalError during engine initialization. We proactively create the
    directory when we detect a SQLite URL so imports succeed in test environments.
    """
    try:
        database_url = settings.sqlalchemy_url
        url = make_url(database_url)
        if url.get_backend_name() == "sqlite":
            database = url.database
            if database and database != ":memory:":
                db_path = Path(database).expanduser()
                if not db_path.is_absolute():
                    # Resolve relative to project root
                    # This file is at backend/core/db.py, so parent.parent.parent gives us the project root
                    project_root = Path(__file__).parent.parent.parent
                    db_path = project_root / db_path
                db_path.parent.mkdir(parents=True, exist_ok=True)
            # Allow usage across threads when FastAPI spins up multiple workers
            return create_engine(
                database_url,
                pool_pre_ping=True,
                connect_args={"check_same_thread": False},
            )

        return create_engine(database_url, pool_pre_ping=True)
    except Exception as e:
        # Log error but don't prevent module import - let the actual usage fail with a clear error
        logging.error(f"Failed to create database engine: {e}", exc_info=True)
        raise


# Lazy initialization - create engine on first access to avoid import-time failures
_engine: Optional[Engine] = None
_SessionLocal = None


def get_engine() -> Engine:
    """Get or create the database engine (lazy initialization)."""
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def _get_session_local():
    """Get or create SessionLocal (lazy initialization)."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autoflush=False, autocommit=False
        )
    return _SessionLocal


# Reusable lazy proxy for backward compatibility
class LazyProxy:
    """Generic lazy proxy that defers initialization until first access."""

    def __init__(self, getter):
        self._getter = getter

    def __getattr__(self, name):
        return getattr(self._getter(), name)

    def __call__(self, *args, **kwargs):
        return self._getter()(*args, **kwargs)

    def __repr__(self):
        return repr(self._getter())

    def __str__(self):
        return str(self._getter())


# For backward compatibility - create module-level lazy proxies
engine = LazyProxy(get_engine)
SessionLocal = LazyProxy(_get_session_local)


class Base(DeclarativeBase):
    pass


def get_db():
    SessionLocal = _get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def safe_commit_with_rollback(
    db: Session,
    logger: Optional[logging.Logger] = None,
    operation_name: str = "database operation",
) -> bool:
    """
    Safely commit a database transaction with automatic rollback on error.

    Args:
        db: SQLAlchemy database session
        logger: Optional logger for error reporting
        operation_name: Description of the operation for logging context

    Returns:
        True if commit succeeded, False if rollback was required
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    try:
        db.commit()
        return True
    except Exception as commit_error:
        logger.error(f"Failed to commit {operation_name}: {commit_error}")
        try:
            db.rollback()
            logger.info(f"Successfully rolled back {operation_name}")
        except Exception as rollback_error:
            logger.error(f"Failed to rollback {operation_name}: {rollback_error}")
        return False


def safe_rollback(
    db: Session,
    logger: Optional[logging.Logger] = None,
    operation_name: str = "database operation",
) -> bool:
    """
    Safely rollback a database transaction with error handling.

    Args:
        db: SQLAlchemy database session
        logger: Optional logger for error reporting
        operation_name: Description of the operation for logging context

    Returns:
        True if rollback succeeded, False if rollback failed
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    try:
        db.rollback()
        logger.info(f"Successfully rolled back {operation_name}")
        return True
    except Exception as rollback_error:
        logger.error(f"Failed to rollback {operation_name}: {rollback_error}")
        return False
