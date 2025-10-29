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
# Use sqlalchemy_url property which handles URL construction and encoding
engine = create_engine(settings.sqlalchemy_url, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions.

    Usage:
        with db_session() as session:
            user = session.query(User).filter_by(id=1).first()
            session.commit()  # Explicit commit required

    Note: Transaction management is left to the caller.
    Automatically rolls back on exceptions.
    """
    session = SessionLocal()
    try:
        yield session
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
