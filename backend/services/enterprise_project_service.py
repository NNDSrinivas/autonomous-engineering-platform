"""
Enterprise Project Service.

Central service for managing long-running enterprise projects.
Orchestrates task decomposition, human checkpoints, and progress tracking.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from backend.database.models import (
    EnterpriseProject,
    HumanCheckpointGate,
    ProjectTaskQueue,
    WorkspaceSession,
)

logger = logging.getLogger(__name__)


class EnterpriseProjectService:
    """
    Service for managing enterprise-level projects.

    Handles:
    - Project lifecycle (create, update, complete)
    - Goal decomposition into tasks
    - Human checkpoint gates
    - Progress tracking
    - Architecture decision records
    """

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Project Lifecycle
    # =========================================================================

    def create_project(
        self,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        project_type: str = "general",
        workspace_session_id: Optional[str] = None,
        goals: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> EnterpriseProject:
        """
        Create a new enterprise project.

        Args:
            user_id: User creating the project
            name: Project name
            description: Project description
            project_type: Type (e-commerce, microservices, api, etc.)
            workspace_session_id: Link to workspace session
            goals: Initial project goals
            config: Project configuration

        Returns:
            Created EnterpriseProject
        """
        project = EnterpriseProject(
            user_id=user_id,
            name=name,
            description=description,
            project_type=project_type,
            workspace_session_id=UUID(workspace_session_id) if workspace_session_id else None,
            goals=goals or [],
            config=config or {},
            status="planning",
        )

        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)

        logger.info(
            "Created enterprise project",
            extra={"project_id": str(project.id), "name": name, "user_id": user_id},
        )
        return project

    def get_project(
        self,
        project_id: str,
        user_id: int,
    ) -> Optional[EnterpriseProject]:
        """Get a project by ID for a user."""
        result = self.db.execute(
            select(EnterpriseProject).where(
                and_(
                    EnterpriseProject.id == UUID(project_id),
                    EnterpriseProject.user_id == user_id,
                )
            )
        )
        return result.scalar_one_or_none()

    def get_user_projects(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[EnterpriseProject]:
        """Get all projects for a user."""
        query = select(EnterpriseProject).where(
            EnterpriseProject.user_id == user_id
        )

        if status:
            query = query.where(EnterpriseProject.status == status)

        query = query.order_by(EnterpriseProject.updated_at.desc()).limit(limit)

        result = self.db.execute(query)
        return list(result.scalars().all())

    def update_project(
        self,
        project_id: str,
        user_id: int,
        updates: Dict[str, Any],
    ) -> Optional[EnterpriseProject]:
        """Update project fields."""
        project = self.get_project(project_id, user_id)
        if not project:
            return None

        allowed_fields = {
            "name", "description", "project_type", "goals", "milestones",
            "config", "status", "progress_percentage",
        }

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(project, field, value)

        project.updated_at = datetime.now(timezone.utc)
        project.last_active_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(project)
        return project

    def update_project_status(
        self,
        project_id: str,
        user_id: int,
        status: str,
    ) -> Optional[EnterpriseProject]:
        """Update project status."""
        project = self.get_project(project_id, user_id)
        if not project:
            return None

        project.status = status
        project.updated_at = datetime.now(timezone.utc)

        if status == "completed":
            project.completed_at = datetime.now(timezone.utc)
            project.progress_percentage = 100

        self.db.commit()
        self.db.refresh(project)

        logger.info(
            "Updated project status",
            extra={"project_id": project_id, "status": status},
        )
        return project

    # =========================================================================
    # Task Management
    # =========================================================================

    def add_task(
        self,
        project_id: str,
        task_key: str,
        title: str,
        description: Optional[str] = None,
        task_type: str = "development",
        priority: int = 50,
        dependencies: Optional[List[str]] = None,
        can_parallelize: bool = False,
        verification_criteria: Optional[List[Dict[str, Any]]] = None,
        milestone_id: Optional[str] = None,
        parent_task_id: Optional[str] = None,
    ) -> ProjectTaskQueue:
        """Add a task to the project queue."""
        task = ProjectTaskQueue(
            project_id=UUID(project_id),
            task_key=task_key,
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            dependencies=dependencies or [],
            can_parallelize=can_parallelize,
            verification_criteria=verification_criteria or [],
            milestone_id=milestone_id,
            parent_task_id=UUID(parent_task_id) if parent_task_id else None,
            status="pending",
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        logger.info(
            "Added task to project",
            extra={"project_id": project_id, "task_key": task_key, "title": title},
        )
        return task

    def add_tasks_bulk(
        self,
        project_id: str,
        tasks: List[Dict[str, Any]],
    ) -> List[ProjectTaskQueue]:
        """Add multiple tasks at once."""
        created_tasks = []
        for task_data in tasks:
            task = ProjectTaskQueue(
                project_id=UUID(project_id),
                task_key=task_data["task_key"],
                title=task_data["title"],
                description=task_data.get("description"),
                task_type=task_data.get("task_type", "development"),
                priority=task_data.get("priority", 50),
                dependencies=task_data.get("dependencies", []),
                can_parallelize=task_data.get("can_parallelize", False),
                verification_criteria=task_data.get("verification_criteria", []),
                milestone_id=task_data.get("milestone_id"),
                status="pending",
            )
            self.db.add(task)
            created_tasks.append(task)

        self.db.commit()

        for task in created_tasks:
            self.db.refresh(task)

        logger.info(
            "Added bulk tasks to project",
            extra={"project_id": project_id, "count": len(created_tasks)},
        )
        return created_tasks

    def get_project_tasks(
        self,
        project_id: str,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> List[ProjectTaskQueue]:
        """Get all tasks for a project."""
        query = select(ProjectTaskQueue).where(
            ProjectTaskQueue.project_id == UUID(project_id)
        )

        if status:
            query = query.where(ProjectTaskQueue.status == status)
        if task_type:
            query = query.where(ProjectTaskQueue.task_type == task_type)

        query = query.order_by(
            ProjectTaskQueue.priority.desc(),
            ProjectTaskQueue.created_at.asc(),
        )

        result = self.db.execute(query)
        return list(result.scalars().all())

    def get_ready_tasks(
        self,
        project_id: str,
        max_tasks: int = 5,
    ) -> List[ProjectTaskQueue]:
        """
        Get tasks ready for execution.

        A task is ready if:
        - Status is 'pending' or 'ready'
        - All dependencies are completed
        """
        # Get all tasks for the project
        all_tasks = self.get_project_tasks(project_id)

        # Build set of completed task keys
        completed_keys = {
            task.task_key
            for task in all_tasks
            if task.status == "completed"
        }

        # Find ready tasks
        ready_tasks = []
        for task in all_tasks:
            if task.status not in ("pending", "ready"):
                continue

            # Check if all dependencies are satisfied
            deps = task.dependencies or []
            if all(dep in completed_keys for dep in deps):
                ready_tasks.append(task)

                # Update status to 'ready' if it was 'pending'
                if task.status == "pending":
                    task.status = "ready"

        self.db.commit()

        # Sort by priority and return top N
        ready_tasks.sort(key=lambda t: (-t.priority, t.created_at))
        return ready_tasks[:max_tasks]

    def update_task_status(
        self,
        task_id: str,
        status: str,
        error_message: Optional[str] = None,
        verification_result: Optional[Dict[str, Any]] = None,
        outputs: Optional[List[Dict[str, Any]]] = None,
        modified_files: Optional[List[str]] = None,
    ) -> Optional[ProjectTaskQueue]:
        """Update a task's status."""
        result = self.db.execute(
            select(ProjectTaskQueue).where(
                ProjectTaskQueue.id == UUID(task_id)
            )
        )
        task = result.scalar_one_or_none()

        if not task:
            return None

        task.status = status
        task.updated_at = datetime.now(timezone.utc)

        if status == "in_progress" and not task.started_at:
            task.started_at = datetime.now(timezone.utc)
        elif status == "completed":
            task.completed_at = datetime.now(timezone.utc)
            task.progress_percentage = 100
        elif status == "failed":
            task.error_count += 1
            if error_message:
                task.last_error = error_message

        if verification_result:
            task.verification_result = verification_result
            task.verification_passed = verification_result.get("passed", False)

        if outputs:
            task.outputs = outputs
        if modified_files:
            task.modified_files = modified_files

        self.db.commit()
        self.db.refresh(task)

        # Update project progress
        self._update_project_progress(str(task.project_id))

        return task

    def _update_project_progress(self, project_id: str) -> None:
        """Recalculate and update project progress percentage."""
        tasks = self.get_project_tasks(project_id)
        if not tasks:
            return

        completed = sum(1 for t in tasks if t.status == "completed")
        total = len(tasks)
        progress = int((completed / total) * 100)

        self.db.execute(
            update(EnterpriseProject)
            .where(EnterpriseProject.id == UUID(project_id))
            .values(
                progress_percentage=progress,
                updated_at=datetime.now(timezone.utc),
            )
        )
        self.db.commit()

    # =========================================================================
    # Human Checkpoint Gates
    # =========================================================================

    def create_checkpoint_gate(
        self,
        project_id: str,
        gate_type: str,
        title: str,
        description: Optional[str] = None,
        options: Optional[List[Dict[str, Any]]] = None,
        trigger_context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
        priority: str = "normal",
        blocks_progress: bool = True,
    ) -> HumanCheckpointGate:
        """
        Create a human checkpoint gate.

        Args:
            project_id: Project ID
            gate_type: Type (architecture_review, security_review, cost_approval, etc.)
            title: Title for the decision
            description: Detailed description
            options: List of options with trade-offs
            trigger_context: Context that triggered this gate
            task_id: Associated task if any
            priority: Priority level
            blocks_progress: Whether this blocks further execution

        Returns:
            Created HumanCheckpointGate
        """
        gate = HumanCheckpointGate(
            project_id=UUID(project_id),
            gate_type=gate_type,
            title=title,
            description=description,
            options=options or [],
            trigger_context=trigger_context or {},
            task_id=UUID(task_id) if task_id else None,
            priority=priority,
            blocks_progress=blocks_progress,
            status="pending",
        )

        self.db.add(gate)
        self.db.commit()
        self.db.refresh(gate)

        # Update project status if gate blocks progress
        if blocks_progress:
            self.db.execute(
                update(EnterpriseProject)
                .where(EnterpriseProject.id == UUID(project_id))
                .values(status="blocked")
            )
            self.db.commit()

        logger.info(
            "Created checkpoint gate",
            extra={
                "project_id": project_id,
                "gate_type": gate_type,
                "title": title,
            },
        )
        return gate

    def get_pending_gates(
        self,
        project_id: str,
    ) -> List[HumanCheckpointGate]:
        """Get all pending checkpoint gates for a project."""
        result = self.db.execute(
            select(HumanCheckpointGate)
            .where(
                and_(
                    HumanCheckpointGate.project_id == UUID(project_id),
                    HumanCheckpointGate.status == "pending",
                )
            )
            .order_by(
                HumanCheckpointGate.priority.desc(),
                HumanCheckpointGate.created_at.asc(),
            )
        )
        return list(result.scalars().all())

    def get_gate(
        self,
        gate_id: str,
    ) -> Optional[HumanCheckpointGate]:
        """Get a checkpoint gate by ID."""
        result = self.db.execute(
            select(HumanCheckpointGate).where(
                HumanCheckpointGate.id == UUID(gate_id)
            )
        )
        return result.scalar_one_or_none()

    def process_gate_decision(
        self,
        gate_id: str,
        chosen_option_id: str,
        decision_reason: Optional[str] = None,
        decided_by: Optional[str] = None,
    ) -> Optional[HumanCheckpointGate]:
        """
        Process a human decision on a checkpoint gate.

        Args:
            gate_id: Gate ID
            chosen_option_id: ID of the chosen option
            decision_reason: Human's reasoning
            decided_by: User who made the decision

        Returns:
            Updated gate
        """
        gate = self.get_gate(gate_id)
        if not gate:
            return None

        gate.status = "approved"
        gate.chosen_option_id = chosen_option_id
        gate.decision_reason = decision_reason
        gate.decided_by = decided_by
        gate.decided_at = datetime.now(timezone.utc)

        # Store decision in project's human_decisions
        project = self.db.execute(
            select(EnterpriseProject).where(
                EnterpriseProject.id == gate.project_id
            )
        ).scalar_one()

        decisions = project.human_decisions or []
        decisions.append({
            "gate_id": str(gate.id),
            "gate_type": gate.gate_type,
            "title": gate.title,
            "chosen_option_id": chosen_option_id,
            "decision_reason": decision_reason,
            "decided_by": decided_by,
            "decided_at": datetime.now(timezone.utc).isoformat(),
        })
        project.human_decisions = decisions

        # Check if project can be unblocked
        pending_blocking_gates = self.db.execute(
            select(HumanCheckpointGate)
            .where(
                and_(
                    HumanCheckpointGate.project_id == gate.project_id,
                    HumanCheckpointGate.status == "pending",
                    HumanCheckpointGate.blocks_progress == True,
                )
            )
        ).scalars().all()

        if not pending_blocking_gates:
            project.status = "active"

        self.db.commit()
        self.db.refresh(gate)

        logger.info(
            "Processed gate decision",
            extra={
                "gate_id": gate_id,
                "chosen_option_id": chosen_option_id,
                "decided_by": decided_by,
            },
        )
        return gate

    # =========================================================================
    # Architecture Decision Records
    # =========================================================================

    def add_architecture_decision(
        self,
        project_id: str,
        user_id: int,
        title: str,
        context: str,
        decision: str,
        consequences: List[str],
        alternatives: Optional[List[Dict[str, str]]] = None,
        status: str = "accepted",
    ) -> Optional[EnterpriseProject]:
        """
        Add an Architecture Decision Record (ADR) to the project.

        Args:
            project_id: Project ID
            user_id: User making the decision
            title: ADR title (e.g., "Use PostgreSQL for primary database")
            context: Context and problem statement
            decision: The decision made
            consequences: List of consequences
            alternatives: Alternative options considered
            status: ADR status (proposed, accepted, deprecated, superseded)

        Returns:
            Updated project
        """
        project = self.get_project(project_id, user_id)
        if not project:
            return None

        adr = {
            "id": str(uuid4()),
            "title": title,
            "context": context,
            "decision": decision,
            "consequences": consequences,
            "alternatives": alternatives or [],
            "status": status,
            "date": datetime.now(timezone.utc).isoformat(),
            "author_id": user_id,
        }

        adrs = project.architecture_decisions or []
        adrs.append(adr)
        project.architecture_decisions = adrs

        self.db.commit()
        self.db.refresh(project)

        logger.info(
            "Added ADR to project",
            extra={"project_id": project_id, "adr_title": title},
        )
        return project

    # =========================================================================
    # Memory Context
    # =========================================================================

    def get_project_memory_context(
        self,
        project_id: str,
        user_id: int,
    ) -> str:
        """
        Generate a memory context string for the project.

        This is injected into the agent's context to provide awareness
        of the project state.

        Returns:
            Formatted memory context string
        """
        project = self.get_project(project_id, user_id)
        if not project:
            return ""

        lines = [
            "## Enterprise Project Context",
            f"**Project:** {project.name}",
            f"**Type:** {project.project_type}",
            f"**Status:** {project.status}",
            f"**Progress:** {project.progress_percentage}%",
        ]

        # Goals
        if project.goals:
            lines.append("\n### Goals")
            for goal in project.goals[:5]:  # Top 5 goals
                status = goal.get("status", "pending")
                lines.append(f"- [{status}] {goal.get('description', 'Unknown')}")

        # Recent architecture decisions
        if project.architecture_decisions:
            lines.append("\n### Recent Architecture Decisions")
            for adr in project.architecture_decisions[-3:]:  # Last 3 ADRs
                lines.append(f"- **{adr.get('title')}**: {adr.get('decision', '')[:100]}...")

        # Completed components
        if project.completed_components:
            lines.append("\n### Completed Components")
            for comp in project.completed_components[-5:]:
                lines.append(f"- {comp.get('component', 'Unknown')}")

        # Pending components
        if project.pending_components:
            lines.append("\n### Pending Components")
            for comp in project.pending_components[:5]:
                lines.append(f"- {comp.get('component', 'Unknown')}")

        # Active blockers
        blockers = [b for b in (project.blockers or []) if not b.get("resolved_at")]
        if blockers:
            lines.append("\n### Active Blockers")
            for blocker in blockers[:3]:
                lines.append(f"- {blocker.get('description', 'Unknown')}")

        # Task summary
        tasks = self.get_project_tasks(project_id)
        if tasks:
            completed = sum(1 for t in tasks if t.status == "completed")
            in_progress = sum(1 for t in tasks if t.status == "in_progress")
            pending = sum(1 for t in tasks if t.status in ("pending", "ready"))
            lines.append(f"\n### Task Progress: {completed}/{len(tasks)} completed, {in_progress} in progress, {pending} pending")

        return "\n".join(lines)

    # =========================================================================
    # Iteration Tracking
    # =========================================================================

    def increment_iterations(
        self,
        project_id: str,
        count: int = 1,
    ) -> None:
        """Increment the project's total iteration count."""
        self.db.execute(
            update(EnterpriseProject)
            .where(EnterpriseProject.id == UUID(project_id))
            .values(
                total_iterations=EnterpriseProject.total_iterations + count,
                last_active_at=datetime.now(timezone.utc),
            )
        )
        self.db.commit()

    def update_checkpoint_iteration(
        self,
        project_id: str,
        iteration: int,
    ) -> None:
        """Update the last checkpoint iteration number."""
        self.db.execute(
            update(EnterpriseProject)
            .where(EnterpriseProject.id == UUID(project_id))
            .values(last_checkpoint_iteration=iteration)
        )
        self.db.commit()
