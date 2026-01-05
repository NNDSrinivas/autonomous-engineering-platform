"""
Checkpoint Engine — Pause/Resume with Full State Recovery

Provides robust checkpointing for long-horizon initiatives with full state persistence,
allowing seamless pause/resume across sessions, reboots, and context switches.
"""

import json
import pickle
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import logging
from pathlib import Path

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    JSON,
    LargeBinary,
    Boolean,
    Integer,
)
from sqlalchemy.sql import func

from backend.core.db import Base
from backend.agent.planning.plan_graph import PlanGraph, TaskStatus
from backend.agent.planning.execution_scheduler import ExecutionContext


logger = logging.getLogger(__name__)


class CheckpointType(Enum):
    """Types of checkpoints"""

    AUTO = "AUTO"  # Automatic periodic checkpoint
    MANUAL = "MANUAL"  # User-requested checkpoint
    MILESTONE = "MILESTONE"  # Major milestone checkpoint
    ERROR = "ERROR"  # Checkpoint before error handling
    PAUSE = "PAUSE"  # Checkpoint when pausing execution


@dataclass
class CheckpointMetadata:
    """Metadata for a checkpoint"""

    checkpoint_id: str
    initiative_id: str
    checkpoint_type: CheckpointType
    created_at: datetime
    created_by: str
    description: str
    tags: List[str]
    execution_context: Dict[str, Any]
    progress_summary: Dict[str, Any]
    validation_hash: str


class CheckpointModel(Base):
    """Database model for checkpoints"""

    __tablename__ = "execution_checkpoints"

    checkpoint_id = Column(String, primary_key=True)
    initiative_id = Column(String, nullable=False, index=True)
    checkpoint_type = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    created_by = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    tags = Column(JSON, default=lambda: [])

    # Execution state
    execution_context = Column(JSON, nullable=False)
    progress_summary = Column(JSON, nullable=False)
    validation_hash = Column(String, nullable=False)

    # Serialized state data (pickled for complex objects)
    plan_graph_data = Column(LargeBinary, nullable=False)
    metadata_json = Column(JSON, nullable=False)

    # Status
    is_valid = Column(Boolean, default=True, nullable=False)
    restored_count = Column(Integer, default=0, nullable=False)
    last_restored_at = Column(DateTime(timezone=True), nullable=True)

    def to_metadata(self) -> CheckpointMetadata:
        """Convert to checkpoint metadata"""
        tags_val = self.tags
        execution_context_val = self.execution_context
        progress_summary_val = self.progress_summary

        return CheckpointMetadata(
            checkpoint_id=str(self.checkpoint_id),
            initiative_id=str(self.initiative_id),
            checkpoint_type=CheckpointType(str(self.checkpoint_type)),
            created_at=self.created_at,  # type: ignore  # SQLAlchemy attribute access
            created_by=str(self.created_by),
            description=str(self.description),
            tags=tags_val if isinstance(tags_val, list) else [],
            execution_context=(
                execution_context_val if isinstance(execution_context_val, dict) else {}
            ),
            progress_summary=(
                progress_summary_val if isinstance(progress_summary_val, dict) else {}
            ),
            validation_hash=str(self.validation_hash),
        )


class CheckpointEngine:
    """Manages checkpoints for long-horizon execution"""

    def __init__(self, db_session, storage_path: Optional[Path] = None):
        self.db = db_session
        self.storage_path = storage_path or Path("/tmp/aep_checkpoints")
        self.storage_path.mkdir(exist_ok=True)

    def create_checkpoint(
        self,
        initiative_id: str,
        plan_graph: PlanGraph,
        execution_context: ExecutionContext,
        checkpoint_type: CheckpointType = CheckpointType.AUTO,
        description: str = "",
        created_by: str = "system",
        tags: Optional[List[str]] = None,
    ) -> str:
        """Create a new checkpoint"""

        checkpoint_id = self._generate_checkpoint_id(initiative_id)

        try:
            # Serialize plan graph
            plan_data = plan_graph.to_dict()
            plan_binary = pickle.dumps(plan_data)

            # Create validation hash
            validation_data = {
                "initiative_id": initiative_id,
                "plan_graph_hash": hashlib.md5(plan_binary).hexdigest(),
                "execution_context": asdict(execution_context),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            validation_hash = hashlib.sha256(
                json.dumps(validation_data, sort_keys=True).encode()
            ).hexdigest()

            # Get progress summary
            progress_summary = plan_graph.get_progress_summary()

            # Create checkpoint record
            checkpoint = CheckpointModel(
                checkpoint_id=checkpoint_id,
                initiative_id=initiative_id,
                checkpoint_type=checkpoint_type.value,
                created_by=created_by,
                description=description
                or f"Checkpoint at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
                tags=tags or [],
                execution_context=asdict(execution_context),
                progress_summary=progress_summary,
                validation_hash=validation_hash,
                plan_graph_data=plan_binary,
                metadata_json=validation_data,
            )

            self.db.add(checkpoint)
            self.db.commit()

            logger.info(
                f"Created checkpoint {checkpoint_id} for initiative {initiative_id}"
            )
            return checkpoint_id

        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
            self.db.rollback()
            raise

    def restore_checkpoint(
        self, checkpoint_id: str
    ) -> Tuple[PlanGraph, ExecutionContext, CheckpointMetadata]:
        """Restore execution state from a checkpoint"""

        checkpoint = (
            self.db.query(CheckpointModel)
            .filter_by(checkpoint_id=checkpoint_id)
            .first()
        )

        if not checkpoint:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")

        if not checkpoint.is_valid:
            raise ValueError(f"Checkpoint {checkpoint_id} is marked as invalid")

        try:
            # Validate checkpoint integrity
            if not self._validate_checkpoint(checkpoint):
                raise ValueError(f"Checkpoint {checkpoint_id} failed validation")

            # Restore plan graph
            plan_data = pickle.loads(checkpoint.plan_graph_data)
            plan_graph = self._restore_plan_graph(plan_data)

            # Restore execution context
            execution_context = ExecutionContext(**checkpoint.execution_context)

            # Update restore statistics
            checkpoint.restored_count += 1
            checkpoint.last_restored_at = datetime.now(timezone.utc)
            self.db.commit()

            logger.info(
                f"Restored checkpoint {checkpoint_id} for initiative {checkpoint.initiative_id}"
            )

            return plan_graph, execution_context, checkpoint.to_metadata()

        except Exception as e:
            logger.error(f"Failed to restore checkpoint {checkpoint_id}: {e}")
            raise

    def list_checkpoints(
        self,
        initiative_id: Optional[str] = None,
        checkpoint_type: Optional[CheckpointType] = None,
        limit: int = 50,
    ) -> List[CheckpointMetadata]:
        """List available checkpoints"""

        query = self.db.query(CheckpointModel).filter_by(is_valid=True)

        if initiative_id:
            query = query.filter_by(initiative_id=initiative_id)

        if checkpoint_type:
            query = query.filter_by(checkpoint_type=checkpoint_type.value)

        checkpoints = (
            query.order_by(CheckpointModel.created_at.desc()).limit(limit).all()
        )

        return [cp.to_metadata() for cp in checkpoints]

    def get_latest_checkpoint(self, initiative_id: str) -> Optional[CheckpointMetadata]:
        """Get the most recent checkpoint for an initiative"""

        checkpoint = (
            self.db.query(CheckpointModel)
            .filter_by(initiative_id=initiative_id, is_valid=True)
            .order_by(CheckpointModel.created_at.desc())
            .first()
        )

        return checkpoint.to_metadata() if checkpoint else None

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint (mark as invalid)"""

        checkpoint = (
            self.db.query(CheckpointModel)
            .filter_by(checkpoint_id=checkpoint_id)
            .first()
        )

        if not checkpoint:
            return False

        checkpoint.is_valid = False
        self.db.commit()

        logger.info(f"Deleted checkpoint {checkpoint_id}")
        return True

    def auto_checkpoint_needed(
        self,
        plan_graph: PlanGraph,
        last_checkpoint_time: Optional[datetime] = None,
        auto_interval_minutes: int = 30,
    ) -> bool:
        """Check if an automatic checkpoint is needed"""

        now = datetime.now(timezone.utc)

        # Time-based checkpoint
        if last_checkpoint_time:
            time_since_checkpoint = now - last_checkpoint_time
            if time_since_checkpoint > timedelta(minutes=auto_interval_minutes):
                return True
        else:
            # No previous checkpoint
            return True

        # Progress-based checkpoint
        progress = plan_graph.get_progress_summary()
        completed_tasks = progress["status_counts"].get("COMPLETED", 0)

        # Checkpoint every 5 completed tasks
        if completed_tasks > 0 and completed_tasks % 5 == 0:
            return True

        # Milestone-based checkpoint
        if progress["progress_percent"] > 0 and progress["progress_percent"] % 25 == 0:
            return True

        return False

    def create_milestone_checkpoint(
        self,
        initiative_id: str,
        plan_graph: PlanGraph,
        execution_context: ExecutionContext,
        milestone_name: str,
        created_by: str = "system",
    ) -> str:
        """Create a milestone checkpoint"""

        return self.create_checkpoint(
            initiative_id=initiative_id,
            plan_graph=plan_graph,
            execution_context=execution_context,
            checkpoint_type=CheckpointType.MILESTONE,
            description=f"Milestone: {milestone_name}",
            created_by=created_by,
            tags=["milestone", milestone_name.lower().replace(" ", "_")],
        )

    def pause_execution(
        self,
        initiative_id: str,
        plan_graph: PlanGraph,
        execution_context: ExecutionContext,
        reason: str = "Manual pause",
        created_by: str = "user",
    ) -> str:
        """Create a pause checkpoint"""

        return self.create_checkpoint(
            initiative_id=initiative_id,
            plan_graph=plan_graph,
            execution_context=execution_context,
            checkpoint_type=CheckpointType.PAUSE,
            description=f"Paused execution: {reason}",
            created_by=created_by,
            tags=["pause", "manual"],
        )

    def get_checkpoint_analytics(self, initiative_id: str) -> Dict[str, Any]:
        """Get analytics about checkpoints for an initiative"""

        checkpoints = (
            self.db.query(CheckpointModel)
            .filter_by(initiative_id=initiative_id, is_valid=True)
            .all()
        )

        if not checkpoints:
            return {"total_checkpoints": 0}

        # Calculate statistics
        checkpoint_types = {}
        restore_counts = []
        creation_dates = []

        for cp in checkpoints:
            checkpoint_types[cp.checkpoint_type] = (
                checkpoint_types.get(cp.checkpoint_type, 0) + 1
            )
            restore_counts.append(cp.restored_count)
            creation_dates.append(cp.created_at)

        # Calculate timeline
        if creation_dates:
            timeline_days = (max(creation_dates) - min(creation_dates)).days
        else:
            timeline_days = 0

        return {
            "total_checkpoints": len(checkpoints),
            "checkpoint_types": checkpoint_types,
            "total_restores": sum(restore_counts),
            "avg_restores_per_checkpoint": (
                sum(restore_counts) / len(restore_counts) if restore_counts else 0
            ),
            "timeline_days": timeline_days,
            "first_checkpoint": (
                min(creation_dates).isoformat() if creation_dates else None
            ),
            "latest_checkpoint": (
                max(creation_dates).isoformat() if creation_dates else None
            ),
        }

    def _generate_checkpoint_id(self, initiative_id: str) -> str:
        """Generate a unique checkpoint ID"""

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        hash_input = f"{initiative_id}_{timestamp}_{datetime.now().microsecond}"
        hash_suffix = hashlib.md5(hash_input.encode()).hexdigest()[:8]

        return f"checkpoint_{timestamp}_{hash_suffix}"

    def _validate_checkpoint(self, checkpoint: CheckpointModel) -> bool:
        """Validate checkpoint integrity"""

        try:
            # Verify hash
            validation_data = checkpoint.metadata_json
            expected_hash = hashlib.sha256(
                json.dumps(validation_data, sort_keys=True).encode()
            ).hexdigest()

            if expected_hash != checkpoint.validation_hash:
                logger.error(f"Checkpoint {checkpoint.checkpoint_id} hash mismatch")
                return False

            # Verify plan data can be deserialized
            plan_graph_data = getattr(checkpoint, "plan_graph_data", None)
            if plan_graph_data is not None:
                try:
                    plan_data = pickle.loads(plan_graph_data)
                    if not isinstance(plan_data, dict):
                        logger.error(
                            f"Checkpoint {checkpoint.checkpoint_id} plan data corrupted"
                        )
                        return False
                except Exception as e:
                    logger.error(
                        f"Checkpoint {checkpoint.checkpoint_id} pickle load failed: {e}"
                    )
                    return False

            return True

        except Exception as e:
            logger.error(f"Checkpoint validation failed: {e}")
            return False

    def _restore_plan_graph(self, plan_data: Dict[str, Any]) -> PlanGraph:
        """Restore plan graph from serialized data"""

        # Reconstruct tasks from serialized data
        from backend.agent.planning.task_decomposer import (
            DecomposedTask,
            TaskType,
            TaskPriority,
        )

        tasks = []
        node_data = plan_data["nodes"]

        for task_id, node_dict in node_data.items():
            task_dict = node_dict["task"]

            # Reconstruct DecomposedTask
            task = DecomposedTask(
                id=task_dict["id"],
                title=task_dict["title"],
                description=task_dict["description"],
                task_type=TaskType(task_dict["task_type"]),
                priority=TaskPriority(task_dict["priority"]),
                estimated_hours=task_dict["estimated_hours"],
                dependencies=task_dict["dependencies"],
                approval_required=task_dict["approval_required"],
                approvers=task_dict["approvers"],
                success_criteria=task_dict["success_criteria"],
                jira_issue_type=task_dict.get("jira_issue_type", "Task"),
                metadata=task_dict.get("metadata", {}),
            )

            tasks.append(task)

        # Create new plan graph
        plan_graph = PlanGraph(tasks)

        # Restore node states
        for task_id, node_dict in node_data.items():
            if task_id in plan_graph.nodes:
                node = plan_graph.nodes[task_id]
                node.status = TaskStatus(node_dict["status"])

                if node_dict["started_at"]:
                    node.started_at = datetime.fromisoformat(node_dict["started_at"])

                if node_dict["completed_at"]:
                    node.completed_at = datetime.fromisoformat(
                        node_dict["completed_at"]
                    )

                node.assignee = node_dict.get("assignee")
                node.execution_log = node_dict.get("execution_log", [])
                node.failure_reason = node_dict.get("failure_reason")
                node.approval_status = node_dict.get("approval_status")

        # Restore execution history
        plan_graph.execution_history = plan_data.get("execution_history", [])

        return plan_graph
