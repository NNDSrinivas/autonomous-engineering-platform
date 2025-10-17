from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session
import logging
from typing import Optional

from .config import settings

engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
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
