"""
Portable SQLAlchemy column types used across database backends.

Provides JSONB semantics on Postgres while remaining SQLite-friendly
in local/unit-test runs (falls back to JSON for non-Postgres dialects).
"""

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator

try:
    from sqlalchemy.dialects.postgresql import JSONB as PGJSONB  # type: ignore
except Exception:  # pragma: no cover - only when postgres driver missing
    PGJSONB = None


class PortableJSONB(TypeDecorator):
    """Use native JSONB on Postgres, JSON elsewhere."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if PGJSONB and dialect.name == "postgresql":
            return dialect.type_descriptor(PGJSONB())
        return dialect.type_descriptor(JSON())
