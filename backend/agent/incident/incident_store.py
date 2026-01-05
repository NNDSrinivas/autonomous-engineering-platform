"""
IncidentStore — Persistent Failure Memory

Enterprise-grade organizational memory for failures. Unlike logs, this is
structured incident data that enables pattern recognition across days,
sprints, and engineering teams.

This is what separates NAVI from reactive assistants — it learns and remembers
systemic issues to predict and prevent future failures.
"""

import sqlite3
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class IncidentType(Enum):
    """Types of engineering incidents that NAVI tracks"""

    CI_FAILURE = "CI_FAILURE"
    DEPLOYMENT_FAILURE = "DEPLOYMENT_FAILURE"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TEST_FAILURE = "TEST_FAILURE"
    BUILD_FAILURE = "BUILD_FAILURE"
    SECURITY_INCIDENT = "SECURITY_INCIDENT"
    PERFORMANCE_REGRESSION = "PERFORMANCE_REGRESSION"
    FLAKY_TEST = "FLAKY_TEST"
    DEPENDENCY_ISSUE = "DEPENDENCY_ISSUE"


@dataclass
class Incident:
    """
    Core incident data structure representing a failure event.
    This is organizational memory that enables pattern recognition.
    """

    id: str
    incident_type: IncidentType
    repo: str
    branch: str
    files: List[str]
    failure_type: str
    timestamp: datetime
    resolved: bool
    resolution_commit: Optional[str] = None
    author: Optional[str] = None
    error_message: Optional[str] = None
    failure_context: Optional[Dict[str, Any]] = None
    related_incidents: Optional[List[str]] = None
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    tags: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert incident to dictionary for storage"""
        data = asdict(self)
        data["incident_type"] = self.incident_type.value
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Incident":
        """Create incident from dictionary"""
        # Convert string timestamp back to datetime
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])

        # Convert incident_type back to enum
        if isinstance(data.get("incident_type"), str):
            data["incident_type"] = IncidentType(data["incident_type"])

        return cls(**data)


class IncidentStore:
    """
    Persistent storage and retrieval system for engineering incidents.
    Provides organizational memory that enables incident-level intelligence.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize incident store with SQLite backend"""
        if db_path is None:
            db_path = Path.cwd() / "data" / "incidents.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._init_database()
        logger.info(f"IncidentStore initialized with database: {self.db_path}")

    def _init_database(self) -> None:
        """Initialize database schema for incident storage"""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    incident_type TEXT NOT NULL,
                    repo TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    files TEXT NOT NULL,  -- JSON array
                    failure_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,  -- ISO format
                    resolved BOOLEAN NOT NULL,
                    resolution_commit TEXT,
                    author TEXT,
                    error_message TEXT,
                    failure_context TEXT,  -- JSON
                    related_incidents TEXT,  -- JSON array
                    severity TEXT DEFAULT 'MEDIUM',
                    tags TEXT  -- JSON array
                )
            """
            )

            # Create indices for common queries
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_repo_timestamp ON incidents(repo, timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_incident_type ON incidents(incident_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resolved ON incidents(resolved)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_files ON incidents(files)")

            conn.commit()

    def record_incident(self, incident: Incident) -> None:
        """Record a new incident in persistent storage"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # Convert incident to storage format
                data = incident.to_dict()

                conn.execute(
                    """
                    INSERT OR REPLACE INTO incidents (
                        id, incident_type, repo, branch, files, failure_type,
                        timestamp, resolved, resolution_commit, author, error_message,
                        failure_context, related_incidents, severity, tags
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["id"],
                        data["incident_type"],
                        data["repo"],
                        data["branch"],
                        json.dumps(data["files"]),
                        data["failure_type"],
                        data["timestamp"],
                        data["resolved"],
                        data.get("resolution_commit"),
                        data.get("author"),
                        data.get("error_message"),
                        (
                            json.dumps(data.get("failure_context"))
                            if data.get("failure_context")
                            else None
                        ),
                        (
                            json.dumps(data.get("related_incidents"))
                            if data.get("related_incidents")
                            else None
                        ),
                        data["severity"],
                        json.dumps(data.get("tags")) if data.get("tags") else None,
                    ),
                )

                conn.commit()
                logger.info(
                    f"Recorded incident: {incident.id} ({incident.incident_type.value}) in {incident.repo}"
                )

        except Exception as e:
            logger.error(f"Failed to record incident {incident.id}: {e}")
            raise

    def get_recent_incidents(self, repo: str, limit: int = 50) -> List[Incident]:
        """Get recent incidents for a repository, ordered by timestamp"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row

                cursor = conn.execute(
                    """
                    SELECT * FROM incidents 
                    WHERE repo = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """,
                    (repo, limit),
                )

                incidents = []
                for row in cursor.fetchall():
                    incident_data = dict(row)

                    # Parse JSON fields
                    incident_data["files"] = json.loads(incident_data["files"])
                    if incident_data["failure_context"]:
                        incident_data["failure_context"] = json.loads(
                            incident_data["failure_context"]
                        )
                    if incident_data["related_incidents"]:
                        incident_data["related_incidents"] = json.loads(
                            incident_data["related_incidents"]
                        )
                    if incident_data["tags"]:
                        incident_data["tags"] = json.loads(incident_data["tags"])

                    incidents.append(Incident.from_dict(incident_data))

                logger.debug(f"Retrieved {len(incidents)} recent incidents for {repo}")
                return incidents

        except Exception as e:
            logger.error(f"Failed to get recent incidents for {repo}: {e}")
            return []

    def get_incidents_by_type(
        self, incident_type: IncidentType, repo: Optional[str] = None, limit: int = 100
    ) -> List[Incident]:
        """Get incidents by type, optionally filtered by repository"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row

                if repo:
                    cursor = conn.execute(
                        """
                        SELECT * FROM incidents 
                        WHERE incident_type = ? AND repo = ?
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """,
                        (incident_type.value, repo, limit),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT * FROM incidents 
                        WHERE incident_type = ?
                        ORDER BY timestamp DESC 
                        LIMIT ?
                    """,
                        (incident_type.value, limit),
                    )

                incidents = []
                for row in cursor.fetchall():
                    incident_data = dict(row)

                    # Parse JSON fields
                    incident_data["files"] = json.loads(incident_data["files"])
                    if incident_data["failure_context"]:
                        incident_data["failure_context"] = json.loads(
                            incident_data["failure_context"]
                        )
                    if incident_data["related_incidents"]:
                        incident_data["related_incidents"] = json.loads(
                            incident_data["related_incidents"]
                        )
                    if incident_data["tags"]:
                        incident_data["tags"] = json.loads(incident_data["tags"])

                    incidents.append(Incident.from_dict(incident_data))

                return incidents

        except Exception as e:
            logger.error(f"Failed to get incidents by type {incident_type}: {e}")
            return []

    def get_incidents_by_files(
        self, files: List[str], repo: str, limit: int = 50
    ) -> List[Incident]:
        """Get incidents that affected specific files"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row

                # SQLite JSON support for file matching
                file_conditions = []
                params = [repo]

            for file_path in files:
                file_conditions.append("files LIKE ?")
                params.append(f'%"{file_path}"%')

            query = f"""
                SELECT * FROM incidents 
                WHERE repo = ? AND ({' OR '.join(file_conditions)})
                ORDER BY timestamp DESC 
                LIMIT ?
            """

            # Convert limit to string for query parameters
            params.append(str(limit))

            cursor = conn.execute(query, params)
            incidents = []
            for row in cursor.fetchall():
                incident_data = dict(row)

                # Parse JSON fields
                incident_data["files"] = json.loads(incident_data["files"])
                if incident_data["failure_context"]:
                    incident_data["failure_context"] = json.loads(
                        incident_data["failure_context"]
                    )
                if incident_data["related_incidents"]:
                    incident_data["related_incidents"] = json.loads(
                        incident_data["related_incidents"]
                    )
                if incident_data["tags"]:
                    incident_data["tags"] = json.loads(incident_data["tags"])

                incidents.append(Incident.from_dict(incident_data))

            return incidents

        except Exception as e:
            logger.error(f"Failed to get incidents by files {files}: {e}")
            return []

    def get_unresolved_incidents(self, repo: Optional[str] = None) -> List[Incident]:
        """Get all unresolved incidents, optionally filtered by repository"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row

                if repo:
                    cursor = conn.execute(
                        """
                        SELECT * FROM incidents 
                        WHERE resolved = 0 AND repo = ?
                        ORDER BY timestamp DESC
                    """,
                        (repo,),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT * FROM incidents 
                        WHERE resolved = 0
                        ORDER BY timestamp DESC
                    """
                    )

                incidents = []
                for row in cursor.fetchall():
                    incident_data = dict(row)

                    # Parse JSON fields
                    incident_data["files"] = json.loads(incident_data["files"])
                    if incident_data["failure_context"]:
                        incident_data["failure_context"] = json.loads(
                            incident_data["failure_context"]
                        )
                    if incident_data["related_incidents"]:
                        incident_data["related_incidents"] = json.loads(
                            incident_data["related_incidents"]
                        )
                    if incident_data["tags"]:
                        incident_data["tags"] = json.loads(incident_data["tags"])

                    incidents.append(Incident.from_dict(incident_data))

                return incidents

        except Exception as e:
            logger.error(f"Failed to get unresolved incidents: {e}")
            return []

    def mark_incident_resolved(self, incident_id: str, resolution_commit: str) -> bool:
        """Mark an incident as resolved with the resolution commit"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    """
                    UPDATE incidents 
                    SET resolved = 1, resolution_commit = ?
                    WHERE id = ?
                """,
                    (resolution_commit, incident_id),
                )

                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(
                        f"Marked incident {incident_id} as resolved with commit {resolution_commit}"
                    )
                    return True
                else:
                    logger.warning(f"No incident found with id {incident_id}")
                    return False

        except Exception as e:
            logger.error(f"Failed to mark incident {incident_id} as resolved: {e}")
            return False

    def get_incident_statistics(self, repo: Optional[str] = None) -> Dict[str, Any]:
        """Get statistical overview of incidents for analysis"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row

                # Base conditions
                where_clause = ""
                params = []

                if repo:
                    where_clause = "WHERE repo = ?"
                    params.append(repo)

                # Total incidents
                cursor = conn.execute(
                    f"SELECT COUNT(*) as total FROM incidents {where_clause}", params
                )
                total_incidents = cursor.fetchone()["total"]

                # Incidents by type
                cursor = conn.execute(
                    f"""
                    SELECT incident_type, COUNT(*) as count 
                    FROM incidents {where_clause}
                    GROUP BY incident_type
                    ORDER BY count DESC
                """,
                    params,
                )
                by_type = {
                    row["incident_type"]: row["count"] for row in cursor.fetchall()
                }

                # Resolution rate
                cursor = conn.execute(
                    f"""
                    SELECT 
                        SUM(CASE WHEN resolved = 1 THEN 1 ELSE 0 END) as resolved,
                        COUNT(*) as total
                    FROM incidents {where_clause}
                """,
                    params,
                )
                resolution_data = cursor.fetchone()
                resolution_rate = (
                    resolution_data["resolved"] / resolution_data["total"]
                    if resolution_data["total"] > 0
                    else 0
                )

                # Recent activity (last 7 days)
                cursor = conn.execute(
                    f"""
                    SELECT COUNT(*) as recent
                    FROM incidents 
                    {where_clause} {'AND' if where_clause else 'WHERE'} 
                    timestamp > datetime('now', '-7 days')
                """,
                    params,
                )
                recent_activity = cursor.fetchone()["recent"]

                return {
                    "total_incidents": total_incidents,
                    "by_type": by_type,
                    "resolution_rate": resolution_rate,
                    "recent_activity": recent_activity,
                    "repository": repo,
                }

        except Exception as e:
            logger.error(f"Failed to get incident statistics: {e}")
            return {
                "total_incidents": 0,
                "by_type": {},
                "resolution_rate": 0.0,
                "recent_activity": 0,
                "repository": repo,
            }

    def cleanup_old_incidents(self, days_to_keep: int = 90) -> int:
        """Clean up old resolved incidents to manage storage"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM incidents 
                    WHERE resolved = 1 AND timestamp < datetime('now', '-{} days')
                """.format(
                        days_to_keep
                    )
                )

                deleted_count = cursor.rowcount
                conn.commit()

                logger.info(
                    f"Cleaned up {deleted_count} old incidents (older than {days_to_keep} days)"
                )
                return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old incidents: {e}")
            return 0
