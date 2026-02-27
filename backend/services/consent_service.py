"""
Consent Service - Manages command consent preferences and audit logging.

This service provides:
- Auto-allow checking (exact commands and command types)
- Preference storage and management
- Audit trail of all consent decisions
- Settings UI support for user preference management
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.database.models.consent import ConsentPreference, ConsentAuditLog
from backend.database.models.rbac import DBUser, Organization
from backend.core.db import SessionLocal

logger = logging.getLogger(__name__)


class ConsentService:
    """Manages consent preferences and audit logging for command execution."""

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize the consent service.

        Args:
            db: Optional database session. If not provided, creates a new session per operation.
        """
        self._db = db
        self._owns_session = db is None

    def _get_db(self) -> Session:
        """Get database session, creating if needed."""
        if self._db is not None:
            return self._db
        return SessionLocal()

    def _close_db_if_owned(self, db: Session):
        """Close database session if we created it."""
        if self._owns_session and db is not self._db:
            db.close()

    def _resolve_user_org_ids(
        self, db: Session, user_id: str, org_id: str
    ) -> tuple[Optional[int], Optional[int]]:
        """Resolve auth identities to numeric DB IDs used by consent tables."""
        user_id_int: Optional[int] = None
        org_id_int: Optional[int] = None

        try:
            parsed = int(str(org_id))
            if parsed > 0:
                org_id_int = parsed
        except (TypeError, ValueError):
            org_key = (org_id or "").strip()
            if org_key:
                try:
                    org = (
                        db.query(Organization)
                        .filter(Organization.org_key == org_key)
                        .one_or_none()
                    )
                    if org:
                        org_id_int = int(org.id)
                except Exception as exc:
                    logger.debug(
                        "Failed to resolve org key '%s' to numeric org ID: %s",
                        org_key,
                        exc,
                    )

        try:
            parsed = int(str(user_id))
            if parsed > 0:
                user_id_int = parsed
        except (TypeError, ValueError):
            user_sub = (user_id or "").strip()
            if user_sub:
                try:
                    query = db.query(DBUser).filter(DBUser.sub == user_sub)
                    if org_id_int is not None:
                        query = query.filter(DBUser.org_id == org_id_int)
                    db_user = query.one_or_none()
                    if db_user:
                        user_id_int = int(db_user.id)
                        if org_id_int is None:
                            org_id_int = int(db_user.org_id)
                except Exception as exc:
                    logger.debug(
                        "Failed to resolve user sub '%s' to numeric user ID: %s",
                        user_sub,
                        exc,
                    )

        return user_id_int, org_id_int

    def check_auto_allow(
        self, user_id: str, org_id: str, command: str
    ) -> Optional[str]:
        """
        Check if command is auto-allowed by user preferences.

        Args:
            user_id: ID of the user (will be converted to int)
            org_id: ID of the organization (will be converted to int)
            command: Command string to check

        Returns:
            'exact_command' if exact match found
            'command_type' if command type match found
            None if no auto-allow preference exists
        """
        db = self._get_db()
        try:
            user_id_int, org_id_int = self._resolve_user_org_ids(db, user_id, org_id)
            if user_id_int is None or org_id_int is None:
                logger.warning(
                    "Cannot check auto-allow: unresolved user/org IDs (user_id=%s, org_id=%s)",
                    user_id,
                    org_id,
                )
                return None

            # Extract base command (first word)
            base_command = command.split()[0] if command.strip() else ""

            # Check for exact command match first (highest priority)
            exact_pref = db.execute(
                select(ConsentPreference).where(
                    ConsentPreference.user_id == user_id_int,
                    ConsentPreference.org_id == org_id_int,
                    ConsentPreference.preference_type == "exact_command",
                    ConsentPreference.command_pattern == command,
                )
            ).scalar_one_or_none()

            if exact_pref:
                logger.info(f"Auto-allowed '{command}' via exact_command preference")
                return "exact_command"

            # Check for command type match (base command only)
            if base_command:
                type_pref = db.execute(
                    select(ConsentPreference).where(
                        ConsentPreference.user_id == user_id_int,
                        ConsentPreference.org_id == org_id_int,
                        ConsentPreference.preference_type == "command_type",
                        ConsentPreference.command_pattern == base_command,
                    )
                ).scalar_one_or_none()

                if type_pref:
                    logger.info(
                        f"Auto-allowed '{command}' via command_type preference for '{base_command}'"
                    )
                    return "command_type"

            return None

        except Exception as e:
            logger.error(f"Failed to check auto-allow for command '{command}': {e}")
            return None
        finally:
            self._close_db_if_owned(db)

    def save_preference(
        self,
        user_id: str,
        org_id: str,
        preference_type: str,
        command: str,
        task_id: Optional[str] = None,
    ) -> bool:
        """
        Save an always-allow preference to database.

        Args:
            user_id: ID of the user (will be converted to int)
            org_id: ID of the organization (will be converted to int)
            preference_type: 'exact_command' or 'command_type'
            command: Command string (full command for exact_command, base command for command_type)
            task_id: Optional task ID that created this preference

        Returns:
            True if saved successfully, False otherwise
        """
        db = self._get_db()
        try:
            user_id_int, org_id_int = self._resolve_user_org_ids(db, user_id, org_id)
            if user_id_int is None or org_id_int is None:
                logger.warning(
                    "Cannot save consent preference: unresolved user/org IDs (user_id=%s, org_id=%s)",
                    user_id,
                    org_id,
                )
                return False

            # For command_type, extract base command
            if preference_type == "command_type":
                command_pattern = command.split()[0] if command.strip() else command
            else:
                command_pattern = command

            pref = ConsentPreference(
                user_id=user_id_int,
                org_id=org_id_int,
                preference_type=preference_type,
                command_pattern=command_pattern,
                created_by_task_id=task_id,
            )

            db.add(pref)
            db.commit()

            logger.info(
                f"Saved consent preference: {preference_type} for '{command_pattern}'"
            )
            return True

        except IntegrityError:
            # Preference already exists (unique constraint violation)
            db.rollback()
            logger.info(
                f"Consent preference already exists: {preference_type} for '{command}'"
            )
            return True  # Already exists is still "success"
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save consent preference: {e}")
            return False
        finally:
            self._close_db_if_owned(db)

    def log_decision(
        self,
        consent_id: str,
        user_id: str,
        org_id: str,
        command: str,
        decision: str,
        requested_at: datetime,
        responded_at: datetime,
        shell: str = "bash",
        cwd: Optional[str] = None,
        danger_level: Optional[str] = None,
        alternative_command: Optional[str] = None,
        task_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> bool:
        """
        Log a consent decision to the audit trail.

        Args:
            consent_id: Unique ID of the consent request
            user_id: ID of the user (will be converted to int)
            org_id: ID of the organization (will be converted to int)
            command: Original command string
            decision: User's decision ('allow_once', 'allow_always_exact', 'allow_always_type', 'deny', 'alternative')
            requested_at: When consent was requested
            responded_at: When user responded
            shell: Shell type (default: bash)
            cwd: Current working directory
            danger_level: Command danger level
            alternative_command: Alternative command if decision was 'alternative'
            task_id: Associated task ID
            session_id: Associated session ID

        Returns:
            True if logged successfully, False otherwise
        """
        db = self._get_db()
        try:
            user_id_int, org_id_int = self._resolve_user_org_ids(db, user_id, org_id)
            if user_id_int is None or org_id_int is None:
                logger.warning(
                    "Cannot log consent decision: unresolved user/org IDs (user_id=%s, org_id=%s)",
                    user_id,
                    org_id,
                )
                return False

            response_time_ms = int((responded_at - requested_at).total_seconds() * 1000)

            audit_entry = ConsentAuditLog(
                consent_id=consent_id,
                user_id=user_id_int,
                org_id=org_id_int,
                command=command,
                shell=shell,
                cwd=cwd,
                danger_level=danger_level,
                decision=decision,
                alternative_command=alternative_command,
                requested_at=requested_at,
                responded_at=responded_at,
                response_time_ms=response_time_ms,
                task_id=task_id,
                session_id=session_id,
            )

            db.add(audit_entry)
            db.commit()

            logger.info(
                f"Logged consent decision: {decision} for '{command}' (response time: {response_time_ms}ms)"
            )
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to log consent decision: {e}")
            return False
        finally:
            self._close_db_if_owned(db)

    def get_user_preferences(self, user_id: str, org_id: str) -> List[Dict[str, Any]]:
        """
        Get all consent preferences for a user (for settings UI).

        Args:
            user_id: ID of the user (will be converted to int)
            org_id: ID of the organization (will be converted to int)

        Returns:
            List of preference dictionaries
        """
        db = self._get_db()
        try:
            user_id_int, org_id_int = self._resolve_user_org_ids(db, user_id, org_id)
            if user_id_int is None or org_id_int is None:
                logger.warning(
                    "Cannot fetch consent preferences: unresolved user/org IDs (user_id=%s, org_id=%s)",
                    user_id,
                    org_id,
                )
                return []

            prefs = (
                db.execute(
                    select(ConsentPreference)
                    .where(
                        ConsentPreference.user_id == user_id_int,
                        ConsentPreference.org_id == org_id_int,
                    )
                    .order_by(ConsentPreference.created_at.desc())
                )
                .scalars()
                .all()
            )

            return [
                {
                    "id": str(pref.id),
                    "preference_type": pref.preference_type,
                    "command_pattern": pref.command_pattern,
                    "created_at": (
                        pref.created_at.isoformat() if pref.created_at else None
                    ),
                    "created_by_task_id": pref.created_by_task_id,
                }
                for pref in prefs
            ]

        except Exception as e:
            logger.error(f"Failed to get user preferences: {e}")
            return []
        finally:
            self._close_db_if_owned(db)

    def delete_preference(self, preference_id: str, user_id: str, org_id: str) -> bool:
        """
        Remove an always-allow rule.

        Args:
            preference_id: UUID of the preference to delete
            user_id: ID of the user (will be converted to int, for authorization check)
            org_id: ID of the organization (will be converted to int, for authorization check)

        Returns:
            True if deleted successfully, False otherwise
        """
        db = self._get_db()
        try:
            user_id_int, org_id_int = self._resolve_user_org_ids(db, user_id, org_id)
            if user_id_int is None or org_id_int is None:
                logger.warning(
                    "Cannot delete consent preference: unresolved user/org IDs (user_id=%s, org_id=%s)",
                    user_id,
                    org_id,
                )
                return False

            # Delete only if owned by this user/org (security check)
            result = db.execute(
                delete(ConsentPreference).where(
                    ConsentPreference.id == preference_id,
                    ConsentPreference.user_id == user_id_int,
                    ConsentPreference.org_id == org_id_int,
                )
            )
            db.commit()

            deleted = result.rowcount > 0
            if deleted:
                logger.info(f"Deleted consent preference: {preference_id}")
            else:
                logger.warning(
                    f"Consent preference not found or unauthorized: {preference_id}"
                )

            return deleted

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete consent preference: {e}")
            return False
        finally:
            self._close_db_if_owned(db)

    def get_audit_log(
        self, user_id: str, org_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get recent consent decisions for audit/review.

        Args:
            user_id: ID of the user (will be converted to int)
            org_id: ID of the organization (will be converted to int)
            limit: Maximum number of entries to return

        Returns:
            List of audit log entry dictionaries
        """
        db = self._get_db()
        try:
            user_id_int, org_id_int = self._resolve_user_org_ids(db, user_id, org_id)
            if user_id_int is None or org_id_int is None:
                logger.warning(
                    "Cannot fetch consent audit log: unresolved user/org IDs (user_id=%s, org_id=%s)",
                    user_id,
                    org_id,
                )
                return []

            logs = (
                db.execute(
                    select(ConsentAuditLog)
                    .where(
                        ConsentAuditLog.user_id == user_id_int,
                        ConsentAuditLog.org_id == org_id_int,
                    )
                    .order_by(ConsentAuditLog.requested_at.desc())
                    .limit(limit)
                )
                .scalars()
                .all()
            )

            return [
                {
                    "id": str(log.id),
                    "consent_id": log.consent_id,
                    "command": log.command,
                    "shell": log.shell,
                    "cwd": log.cwd,
                    "danger_level": log.danger_level,
                    "decision": log.decision,
                    "alternative_command": log.alternative_command,
                    "requested_at": (
                        log.requested_at.isoformat() if log.requested_at else None
                    ),
                    "responded_at": (
                        log.responded_at.isoformat() if log.responded_at else None
                    ),
                    "response_time_ms": log.response_time_ms,
                    "task_id": log.task_id,
                    "session_id": log.session_id,
                }
                for log in logs
            ]

        except Exception as e:
            logger.error(f"Failed to get audit log: {e}")
            return []
        finally:
            self._close_db_if_owned(db)


# Module-level singleton for easy access
_consent_service: Optional[ConsentService] = None


def get_consent_service(db: Optional[Session] = None) -> ConsentService:
    """
    Get or create the consent service singleton.

    Args:
        db: Optional database session to use

    Returns:
        ConsentService instance
    """
    global _consent_service
    if db is not None:
        # Return a new instance with the provided session
        return ConsentService(db)

    if _consent_service is None:
        _consent_service = ConsentService()

    return _consent_service
