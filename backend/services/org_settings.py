from __future__ import annotations

from typing import Iterable, Optional
from urllib.parse import urlparse
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.database.models.rbac import Organization

logger = logging.getLogger(__name__)

_SCHEMA_READY = False

_DEFAULT_REDIRECT_PATH = "/settings/connectors"


def _ensure_org_schema(db: Session) -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    if settings.environment.lower() not in {"development", "test"}:
        _SCHEMA_READY = True
        return

    try:
        existing = set()
        try:
            rows = db.execute(text("PRAGMA table_info(organizations)")).fetchall()
            for row in rows:
                existing.add(str(row[1]))
        except Exception:
            rows = db.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name='organizations'"
                )
            ).fetchall()
            for row in rows:
                existing.add(str(row[0]))

        def add_column(sql: str) -> None:
            try:
                db.execute(text(sql))
                db.commit()
            except Exception:
                db.rollback()

        if "ui_base_url" not in existing:
            add_column("ALTER TABLE organizations ADD COLUMN ui_base_url VARCHAR(512)")
        if "ui_allowed_domains" not in existing:
            add_column("ALTER TABLE organizations ADD COLUMN ui_allowed_domains TEXT")
        if "ui_redirect_path" not in existing:
            add_column("ALTER TABLE organizations ADD COLUMN ui_redirect_path VARCHAR(255)")
    finally:
        _SCHEMA_READY = True


def _is_local_host(hostname: str) -> bool:
    return hostname in {"localhost", "127.0.0.1", "::1"} or hostname.endswith(".localhost")


def _normalize_origin(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    scheme = parsed.scheme.lower()
    host = parsed.netloc.lower()
    if scheme == "http" and not _is_local_host(parsed.hostname or ""):
        return None
    if scheme not in {"http", "https"}:
        return None
    return f"{scheme}://{host}"


def _normalize_redirect_path(raw: Optional[str]) -> str:
    if not raw:
        return _DEFAULT_REDIRECT_PATH
    value = raw.strip()
    if not value:
        return _DEFAULT_REDIRECT_PATH
    if value.startswith(("http://", "https://")):
        return _DEFAULT_REDIRECT_PATH
    if "://" in value or " " in value or "?" in value or "#" in value:
        return _DEFAULT_REDIRECT_PATH
    if not value.startswith("/"):
        value = f"/{value}"
    return value


def _normalize_allowed_domains(domains: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen = set()
    for raw in domains:
        origin = _normalize_origin(raw)
        if not origin or origin in seen:
            continue
        normalized.append(origin)
        seen.add(origin)
    return normalized


def _serialize_domains(domains: Iterable[str]) -> Optional[str]:
    normalized = _normalize_allowed_domains(domains)
    return ",".join(normalized) if normalized else None


def _parse_domains(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    parts = [item.strip() for item in raw.split(",") if item.strip()]
    return _normalize_allowed_domains(parts)


def _get_or_create_org(db: Session, org_key: str) -> Optional[Organization]:
    org = db.query(Organization).filter_by(org_key=org_key).one_or_none()
    if org:
        return org
    if settings.environment != "development":
        return None
    org = Organization(org_key=org_key, name=org_key)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def get_org_ui_config(db: Session, org_key: str) -> dict:
    _ensure_org_schema(db)
    org = db.query(Organization).filter_by(org_key=org_key).one_or_none()
    if not org:
        return {
            "base_url": None,
            "allowed_domains": [],
            "redirect_path": _DEFAULT_REDIRECT_PATH,
        }
    return {
        "base_url": _normalize_origin(org.ui_base_url),
        "allowed_domains": _parse_domains(org.ui_allowed_domains),
        "redirect_path": _normalize_redirect_path(org.ui_redirect_path),
    }


def save_org_ui_config(
    db: Session,
    org_key: str,
    base_url: Optional[str],
    allowed_domains: Iterable[str],
    redirect_path: Optional[str],
) -> dict:
    _ensure_org_schema(db)
    org = _get_or_create_org(db, org_key)
    if not org:
        raise ValueError("Organization not found")

    normalized_base = _normalize_origin(base_url)
    if base_url and not normalized_base:
        raise ValueError("Invalid base URL. Use https:// or localhost http URLs.")
    normalized_domains = _normalize_allowed_domains(allowed_domains)
    normalized_path = _normalize_redirect_path(redirect_path)

    org.ui_base_url = normalized_base
    org.ui_allowed_domains = _serialize_domains(normalized_domains)
    org.ui_redirect_path = normalized_path
    db.add(org)
    db.commit()
    db.refresh(org)

    return {
        "base_url": normalized_base,
        "allowed_domains": normalized_domains,
        "redirect_path": normalized_path,
    }


def select_ui_origin(config: dict, requested_origin: Optional[str]) -> Optional[str]:
    base_url = config.get("base_url")
    if not base_url:
        return None
    if requested_origin:
        normalized = _normalize_origin(requested_origin)
        allowed = set(config.get("allowed_domains") or [])
        if normalized and (normalized == base_url or normalized in allowed):
            return normalized
    return base_url
