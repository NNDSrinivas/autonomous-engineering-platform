"""
Database session management utilities.

Provides dependency injection for FastAPI routes and context managers
for synchronous database operations.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings

# Initialize engine and session factory
settings = get_settings()
database_url = settings.database_url
if not database_url:
    # Construct from components if not explicitly set
    database_url = f"postgresql://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"
engine = create_engine(database_url, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Usage:
        with db_session() as session:
            user = session.query(User).filter_by(id=1).first()
            session.commit()

    Automatically handles commit on success and rollback on error.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
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
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
