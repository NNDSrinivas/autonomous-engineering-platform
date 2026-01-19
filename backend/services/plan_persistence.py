"""
Plan Persistence - Database-backed Plan Storage with Checkpoint/Resume

Provides:
1. SQLite-based persistent storage for plans
2. Checkpoint creation during execution
3. Resume from checkpoints after failures
4. Plan history and versioning
5. Multi-session support

This enables NAVI to handle long-running workflows that survive
restarts, crashes, or session changes.
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


# ============================================================
# DATABASE SETUP
# ============================================================

# Default database path
DEFAULT_DB_PATH = os.environ.get(
    "NAVI_PLANS_DB",
    os.path.expanduser("~/.navi/plans.db")
)


def get_db_path() -> str:
    """Get the database path, creating directory if needed"""
    db_path = DEFAULT_DB_PATH
    db_dir = os.path.dirname(db_path)

    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    return db_path


def init_database(db_path: Optional[str] = None) -> None:
    """Initialize the database schema"""
    db_path = db_path or get_db_path()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Plans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                original_request TEXT,
                workspace_path TEXT,
                project_type TEXT,
                detected_technologies TEXT,  -- JSON array
                relevant_files TEXT,  -- JSON array
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                current_task_index INTEGER DEFAULT 0,
                estimated_files INTEGER DEFAULT 0,
                estimated_lines INTEGER DEFAULT 0,
                risk_level TEXT DEFAULT 'low'
            )
        """)

        # Questions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plan_questions (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                category TEXT NOT NULL,
                question TEXT NOT NULL,
                why_asking TEXT,
                options TEXT,  -- JSON array
                default_answer TEXT,
                answer TEXT,
                answered INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
            )
        """)

        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plan_tasks (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                task_type TEXT NOT NULL,
                files TEXT,  -- JSON array
                commands TEXT,  -- JSON array
                dependencies TEXT,  -- JSON array
                status TEXT DEFAULT 'pending',
                result TEXT,  -- JSON object
                error TEXT,
                task_order INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
            )
        """)

        # Checkpoints table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plan_checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id TEXT NOT NULL,
                task_id TEXT,
                checkpoint_type TEXT NOT NULL,  -- before_task, after_task, manual
                state TEXT NOT NULL,  -- JSON serialized plan state
                created_at TEXT NOT NULL,
                FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
            )
        """)

        # Images table (for UI screenshots)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plan_images (
                id TEXT PRIMARY KEY,
                plan_id TEXT NOT NULL,
                filename TEXT,
                mime_type TEXT,
                description TEXT,
                analysis TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
            )
        """)

        # Execution logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id TEXT NOT NULL,
                task_id TEXT,
                log_type TEXT NOT NULL,  -- info, warning, error, output
                message TEXT NOT NULL,
                details TEXT,  -- JSON
                created_at TEXT NOT NULL,
                FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plans_workspace ON plans(workspace_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plans_status ON plans(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_questions_plan ON plan_questions(plan_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_plan ON plan_tasks(plan_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_plan ON plan_checkpoints(plan_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_plan ON execution_logs(plan_id)")

        conn.commit()

    logger.info(f"Database initialized at {db_path}")


@contextmanager
def get_connection(db_path: Optional[str] = None):
    """Get a database connection"""
    db_path = db_path or get_db_path()

    # Initialize if needed
    if not os.path.exists(db_path):
        init_database(db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ============================================================
# PLAN STORAGE
# ============================================================

class PlanStore:
    """Persistent storage for execution plans"""

    @classmethod
    def save_plan(cls, plan: Dict[str, Any], db_path: Optional[str] = None) -> None:
        """Save a plan to the database"""
        with get_connection(db_path) as conn:
            cursor = conn.cursor()

            # Insert or update plan
            cursor.execute("""
                INSERT OR REPLACE INTO plans (
                    id, title, summary, status, original_request,
                    workspace_path, project_type, detected_technologies,
                    relevant_files, created_at, updated_at,
                    current_task_index, estimated_files, estimated_lines, risk_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan["id"],
                plan.get("title", ""),
                plan.get("summary", ""),
                plan.get("status", "draft"),
                plan.get("original_request", ""),
                plan.get("workspace_path"),
                plan.get("project_type"),
                json.dumps(plan.get("detected_technologies", [])),
                json.dumps(plan.get("relevant_files", [])),
                plan.get("created_at", datetime.utcnow().isoformat()),
                datetime.utcnow().isoformat(),
                plan.get("current_task_index", 0),
                plan.get("estimated_files", 0),
                plan.get("estimated_lines", 0),
                plan.get("risk_level", "low"),
            ))

            # Save questions
            for q in plan.get("questions", []):
                cursor.execute("""
                    INSERT OR REPLACE INTO plan_questions (
                        id, plan_id, category, question, why_asking,
                        options, default_answer, answer, answered, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    q["id"],
                    plan["id"],
                    q.get("category", ""),
                    q["question"],
                    q.get("why_asking", ""),
                    json.dumps(q.get("options", [])),
                    q.get("default"),
                    q.get("answer"),
                    1 if q.get("answered") else 0,
                    datetime.utcnow().isoformat(),
                ))

            # Save tasks
            for i, task in enumerate(plan.get("tasks", [])):
                cursor.execute("""
                    INSERT OR REPLACE INTO plan_tasks (
                        id, plan_id, title, description, task_type,
                        files, commands, dependencies, status,
                        result, error, task_order, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    task["id"],
                    plan["id"],
                    task["title"],
                    task.get("description", ""),
                    task.get("task_type", "generic"),
                    json.dumps(task.get("files", [])),
                    json.dumps(task.get("commands", [])),
                    json.dumps(task.get("dependencies", [])),
                    task.get("status", "pending"),
                    json.dumps(task.get("result")) if task.get("result") else None,
                    task.get("error"),
                    i,
                    datetime.utcnow().isoformat(),
                ))

            conn.commit()

    @classmethod
    def load_plan(cls, plan_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Load a plan from the database"""
        with get_connection(db_path) as conn:
            cursor = conn.cursor()

            # Load plan
            cursor.execute("SELECT * FROM plans WHERE id = ?", (plan_id,))
            row = cursor.fetchone()

            if not row:
                return None

            plan = {
                "id": row["id"],
                "title": row["title"],
                "summary": row["summary"],
                "status": row["status"],
                "original_request": row["original_request"],
                "workspace_path": row["workspace_path"],
                "project_type": row["project_type"],
                "detected_technologies": json.loads(row["detected_technologies"] or "[]"),
                "relevant_files": json.loads(row["relevant_files"] or "[]"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "current_task_index": row["current_task_index"],
                "estimated_files": row["estimated_files"],
                "estimated_lines": row["estimated_lines"],
                "risk_level": row["risk_level"],
            }

            # Load questions
            cursor.execute(
                "SELECT * FROM plan_questions WHERE plan_id = ? ORDER BY created_at",
                (plan_id,)
            )
            plan["questions"] = [
                {
                    "id": q["id"],
                    "category": q["category"],
                    "question": q["question"],
                    "why_asking": q["why_asking"],
                    "options": json.loads(q["options"] or "[]"),
                    "default": q["default_answer"],
                    "answer": q["answer"],
                    "answered": bool(q["answered"]),
                }
                for q in cursor.fetchall()
            ]

            # Load tasks
            cursor.execute(
                "SELECT * FROM plan_tasks WHERE plan_id = ? ORDER BY task_order",
                (plan_id,)
            )
            plan["tasks"] = [
                {
                    "id": t["id"],
                    "title": t["title"],
                    "description": t["description"],
                    "task_type": t["task_type"],
                    "files": json.loads(t["files"] or "[]"),
                    "commands": json.loads(t["commands"] or "[]"),
                    "dependencies": json.loads(t["dependencies"] or "[]"),
                    "status": t["status"],
                    "result": json.loads(t["result"]) if t["result"] else None,
                    "error": t["error"],
                }
                for t in cursor.fetchall()
            ]

            # Load images
            cursor.execute(
                "SELECT * FROM plan_images WHERE plan_id = ?",
                (plan_id,)
            )
            plan["images"] = [
                {
                    "id": img["id"],
                    "filename": img["filename"],
                    "mime_type": img["mime_type"],
                    "description": img["description"],
                    "analysis": img["analysis"],
                }
                for img in cursor.fetchall()
            ]

            # Calculate derived fields
            plan["unanswered_questions"] = len([q for q in plan["questions"] if not q["answered"]])
            plan["completed_tasks"] = len([t for t in plan["tasks"] if t["status"] == "completed"])
            plan["total_tasks"] = len(plan["tasks"])

            return plan

    @classmethod
    def list_plans(
        cls,
        workspace_path: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        db_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List plans with optional filters"""
        with get_connection(db_path) as conn:
            cursor = conn.cursor()

            query = "SELECT id, title, status, workspace_path, created_at, updated_at FROM plans"
            params = []

            conditions = []
            if workspace_path:
                conditions.append("workspace_path = ?")
                params.append(workspace_path)
            if status:
                conditions.append("status = ?")
                params.append(status)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def delete_plan(cls, plan_id: str, db_path: Optional[str] = None) -> bool:
        """Delete a plan and all associated data"""
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
            conn.commit()
            return cursor.rowcount > 0

    @classmethod
    def update_plan_status(
        cls,
        plan_id: str,
        status: str,
        db_path: Optional[str] = None,
    ) -> None:
        """Update plan status"""
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE plans SET status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.utcnow().isoformat(), plan_id)
            )
            conn.commit()

    @classmethod
    def update_task_status(
        cls,
        plan_id: str,
        task_id: str,
        status: str,
        result: Optional[Dict] = None,
        error: Optional[str] = None,
        db_path: Optional[str] = None,
    ) -> None:
        """Update a task's status"""
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE plan_tasks SET
                    status = ?,
                    result = ?,
                    error = ?,
                    completed_at = ?
                WHERE plan_id = ? AND id = ?
            """, (
                status,
                json.dumps(result) if result else None,
                error,
                datetime.utcnow().isoformat() if status in ["completed", "failed"] else None,
                plan_id,
                task_id,
            ))
            conn.commit()


# ============================================================
# CHECKPOINT MANAGEMENT
# ============================================================

class CheckpointManager:
    """Manage execution checkpoints for resume capability"""

    @classmethod
    def create_checkpoint(
        cls,
        plan_id: str,
        task_id: Optional[str] = None,
        checkpoint_type: str = "manual",
        db_path: Optional[str] = None,
    ) -> int:
        """
        Create a checkpoint of the current plan state.

        Returns the checkpoint ID.
        """
        # Load current plan state
        plan = PlanStore.load_plan(plan_id, db_path)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO plan_checkpoints (
                    plan_id, task_id, checkpoint_type, state, created_at
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                plan_id,
                task_id,
                checkpoint_type,
                json.dumps(plan),
                datetime.utcnow().isoformat(),
            ))
            conn.commit()
            return cursor.lastrowid

    @classmethod
    def get_latest_checkpoint(
        cls,
        plan_id: str,
        db_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent checkpoint for a plan"""
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM plan_checkpoints
                WHERE plan_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (plan_id,))

            row = cursor.fetchone()
            if not row:
                return None

            return {
                "id": row["id"],
                "plan_id": row["plan_id"],
                "task_id": row["task_id"],
                "checkpoint_type": row["checkpoint_type"],
                "state": json.loads(row["state"]),
                "created_at": row["created_at"],
            }

    @classmethod
    def list_checkpoints(
        cls,
        plan_id: str,
        db_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all checkpoints for a plan"""
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, plan_id, task_id, checkpoint_type, created_at
                FROM plan_checkpoints
                WHERE plan_id = ?
                ORDER BY created_at DESC
            """, (plan_id,))

            return [dict(row) for row in cursor.fetchall()]

    @classmethod
    def restore_from_checkpoint(
        cls,
        checkpoint_id: int,
        db_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Restore a plan from a checkpoint.

        Returns the restored plan.
        """
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT state FROM plan_checkpoints WHERE id = ?",
                (checkpoint_id,)
            )

            row = cursor.fetchone()
            if not row:
                return None

            plan = json.loads(row["state"])

            # Save the restored plan as current
            PlanStore.save_plan(plan, db_path)

            return plan


# ============================================================
# EXECUTION LOGGING
# ============================================================

class ExecutionLogger:
    """Log execution events for debugging and auditing"""

    @classmethod
    def log(
        cls,
        plan_id: str,
        log_type: str,
        message: str,
        task_id: Optional[str] = None,
        details: Optional[Dict] = None,
        db_path: Optional[str] = None,
    ) -> None:
        """Log an execution event"""
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO execution_logs (
                    plan_id, task_id, log_type, message, details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                plan_id,
                task_id,
                log_type,
                message,
                json.dumps(details) if details else None,
                datetime.utcnow().isoformat(),
            ))
            conn.commit()

    @classmethod
    def get_logs(
        cls,
        plan_id: str,
        task_id: Optional[str] = None,
        log_type: Optional[str] = None,
        limit: int = 100,
        db_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get execution logs"""
        with get_connection(db_path) as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM execution_logs WHERE plan_id = ?"
            params = [plan_id]

            if task_id:
                query += " AND task_id = ?"
                params.append(task_id)

            if log_type:
                query += " AND log_type = ?"
                params.append(log_type)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            return [
                {
                    **dict(row),
                    "details": json.loads(row["details"]) if row["details"] else None,
                }
                for row in cursor.fetchall()
            ]


# ============================================================
# PUBLIC API
# ============================================================

def save_plan(plan: Dict[str, Any]) -> None:
    """Save a plan to persistent storage"""
    PlanStore.save_plan(plan)


def load_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    """Load a plan from persistent storage"""
    return PlanStore.load_plan(plan_id)


def list_plans(
    workspace_path: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List plans with optional filters"""
    return PlanStore.list_plans(workspace_path, status)


def delete_plan(plan_id: str) -> bool:
    """Delete a plan"""
    return PlanStore.delete_plan(plan_id)


def create_checkpoint(
    plan_id: str,
    task_id: Optional[str] = None,
    checkpoint_type: str = "auto",
) -> int:
    """Create a checkpoint"""
    return CheckpointManager.create_checkpoint(plan_id, task_id, checkpoint_type)


def get_latest_checkpoint(plan_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest checkpoint for a plan"""
    return CheckpointManager.get_latest_checkpoint(plan_id)


def restore_checkpoint(checkpoint_id: int) -> Optional[Dict[str, Any]]:
    """Restore a plan from a checkpoint"""
    return CheckpointManager.restore_from_checkpoint(checkpoint_id)


def list_checkpoints(plan_id: str) -> List[Dict[str, Any]]:
    """List all checkpoints for a plan"""
    return CheckpointManager.list_checkpoints(plan_id)


def log_execution(
    plan_id: str,
    log_type: str,
    message: str,
    task_id: Optional[str] = None,
    details: Optional[Dict] = None,
) -> None:
    """Log an execution event"""
    ExecutionLogger.log(plan_id, log_type, message, task_id, details)


def get_execution_logs(
    plan_id: str,
    task_id: Optional[str] = None,
    log_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get execution logs"""
    return ExecutionLogger.get_logs(plan_id, task_id, log_type)


# Initialize database on module load
try:
    init_database()
except Exception as e:
    logger.warning(f"Failed to initialize database: {e}")
