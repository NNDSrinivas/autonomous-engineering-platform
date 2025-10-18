"""Audit logging service for LLM calls with explicit transaction management."""

import logging
from dataclasses import dataclass
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

from .queries import INSERT_LLM_CALL_SUCCESS, INSERT_LLM_CALL_ERROR

logger = logging.getLogger(__name__)


@dataclass
class AuditLogEntry:
    """Data structure for LLM audit log entries."""

    phase: str
    model: str
    status: str
    prompt_hash: str
    tokens: int
    cost_usd: float
    latency_ms: int
    org_id: Optional[str] = None
    user_id: Optional[str] = None
    error_message: Optional[str] = None


class AuditService:
    """Centralized service for audit logging with explicit transaction semantics."""

    def log_success(self, db: Session, entry: AuditLogEntry, commit: bool = False) -> bool:
        """
        Log a successful LLM call.

        Args:
            db: Database session
            entry: Audit log entry data
            commit: Whether to commit the transaction immediately

        Returns:
            True if logging succeeded, False otherwise
        """
        try:
            db.execute(
                text(INSERT_LLM_CALL_SUCCESS),
                {
                    "phase": entry.phase,
                    "model": entry.model,
                    "status": entry.status,
                    "prompt_hash": entry.prompt_hash,
                    "tokens": entry.tokens,
                    "cost_usd": entry.cost_usd,
                    "latency_ms": entry.latency_ms,
                    "org_id": entry.org_id,
                    "user_id": entry.user_id,
                },
            )

            if commit:
                db.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to log successful LLM call for {entry.phase}/{entry.model}: {e}")
            if commit:
                try:
                    db.rollback()
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback audit transaction: {rollback_error}")
            return False

    def log_error(self, db: Session, entry: AuditLogEntry, commit: bool = False) -> bool:
        """
        Log a failed LLM call.

        Args:
            db: Database session
            entry: Audit log entry data
            commit: Whether to commit the transaction immediately

        Returns:
            True if logging succeeded, False otherwise
        """
        try:
            db.execute(
                text(INSERT_LLM_CALL_ERROR),
                {
                    "phase": entry.phase,
                    "model": entry.model,
                    "status": entry.status,
                    "prompt_hash": entry.prompt_hash,
                    "tokens": entry.tokens,
                    "cost_usd": entry.cost_usd,
                    "latency_ms": entry.latency_ms,
                    "error_message": entry.error_message,
                    "org_id": entry.org_id,
                    "user_id": entry.user_id,
                },
            )

            if commit:
                db.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to log failed LLM call for {entry.phase}/{entry.model}: {e}")
            if commit:
                try:
                    db.rollback()
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback audit transaction: {rollback_error}")
            return False


# Singleton instance for the audit service
_audit_service_instance = None


def get_audit_service() -> AuditService:
    """Get the audit service singleton instance."""
    global _audit_service_instance
    if _audit_service_instance is None:
        _audit_service_instance = AuditService()
    return _audit_service_instance
