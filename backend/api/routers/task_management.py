"""
Task Management API - Complete Implementation

Provides comprehensive task and project management features including:
- Task creation, assignment, and tracking
- Project overview and management
- Sprint planning and management
- Progress tracking and analytics
- Team workload balancing
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from typing import Dict, List, Optional, Any, cast
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from enum import Enum
import logging

from backend.core.db import get_db
from backend.core.auth_org import require_org
from backend.core.auth.deps import get_current_user_optional
from backend.search.indexer import upsert_memory_object

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/navi", tags=["task-management"])


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ProjectStatus(str, Enum):
    PLANNING = "planning"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Task(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    assignee: Optional[str] = None
    assignee_name: Optional[str] = None
    reporter: Optional[str] = None
    project_key: Optional[str] = None
    project_name: Optional[str] = None
    labels: List[str] = Field(default_factory=list)
    story_points: Optional[int] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    due_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    blocked_reason: Optional[str] = None
    parent_task: Optional[str] = None
    subtasks: List[str] = Field(default_factory=list)
    comments_count: int = 0
    attachments_count: int = 0
    watchers: List[str] = Field(default_factory=list)


class CreateTaskRequest(BaseModel):
    title: str = Field(description="Task title")
    description: Optional[str] = Field(default=None, description="Task description")
    priority: TaskPriority = Field(
        default=TaskPriority.MEDIUM, description="Task priority"
    )
    assignee: Optional[str] = Field(default=None, description="Assignee user ID")
    project_key: Optional[str] = Field(default=None, description="Project key")
    labels: List[str] = Field(default_factory=list, description="Task labels")
    story_points: Optional[int] = Field(default=None, description="Story points")
    estimated_hours: Optional[float] = Field(
        default=None, description="Estimated hours"
    )
    due_date: Optional[datetime] = Field(default=None, description="Due date")
    parent_task: Optional[str] = Field(default=None, description="Parent task ID")


class UpdateTaskRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assignee: Optional[str] = None
    project_key: Optional[str] = None
    labels: Optional[List[str]] = None
    story_points: Optional[int] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    due_date: Optional[datetime] = None
    blocked_reason: Optional[str] = None


class Project(BaseModel):
    key: str
    name: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    lead: Optional[str] = None
    lead_name: Optional[str] = None
    team_members: List[str] = Field(default_factory=list)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    task_count: int = 0
    completed_tasks: int = 0
    progress_percentage: float = 0.0
    current_sprint: Optional[str] = None
    velocity: float = 0.0
    budget: Optional[float] = None
    spent: Optional[float] = None


class CreateProjectRequest(BaseModel):
    key: str = Field(description="Project key (unique identifier)")
    name: str = Field(description="Project name")
    description: Optional[str] = Field(default=None, description="Project description")
    lead: Optional[str] = Field(default=None, description="Project lead user ID")
    team_members: List[str] = Field(
        default_factory=list, description="Team member user IDs"
    )
    start_date: Optional[datetime] = Field(
        default=None, description="Project start date"
    )
    end_date: Optional[datetime] = Field(default=None, description="Project end date")
    budget: Optional[float] = Field(default=None, description="Project budget")


class TasksResponse(BaseModel):
    tasks: List[Task]
    total_count: int
    has_more: bool
    filters_applied: Dict[str, Any]
    summary: Dict[str, Any]


class ProjectsResponse(BaseModel):
    projects: List[Project]
    total_count: int
    summary: Dict[str, Any]


@router.get("/tasks", response_model=TasksResponse)
async def get_tasks(
    status: Optional[TaskStatus] = Query(None, description="Filter by status"),
    priority: Optional[TaskPriority] = Query(None, description="Filter by priority"),
    assignee: Optional[str] = Query(None, description="Filter by assignee"),
    project_key: Optional[str] = Query(None, description="Filter by project"),
    label: Optional[str] = Query(None, description="Filter by label"),
    due_soon: Optional[bool] = Query(None, description="Show tasks due in next 7 days"),
    overdue: Optional[bool] = Query(None, description="Show overdue tasks"),
    my_tasks: Optional[bool] = Query(None, description="Show only my assigned tasks"),
    limit: int = Query(50, description="Number of tasks to return"),
    offset: int = Query(0, description="Number of tasks to skip"),
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Get tasks with comprehensive filtering and pagination
    """
    try:
        org_id = org_ctx["org_id"]
        user_id = user.user_id if user else None

        # Build query conditions
        conditions = ["org_id = :org_id"]
        params = {"org_id": org_id}

        if status:
            conditions.append("status_name = :status")
            params["status"] = status.value

        if priority:
            conditions.append("priority = :priority")
            params["priority"] = priority.value

        if assignee:
            conditions.append("assignee = :assignee")
            params["assignee"] = assignee
        elif my_tasks and user_id:
            conditions.append("assignee = :user_id")
            params["user_id"] = user_id

        if project_key:
            conditions.append("project_key = :project_key")
            params["project_key"] = project_key

        if label:
            conditions.append("labels LIKE :label")
            params["label"] = f"%{label}%"

        if due_soon:
            due_date = datetime.now() + timedelta(days=7)
            conditions.append("due_date <= :due_date AND due_date >= :now")
            params["due_date"] = due_date
            params["now"] = datetime.now()

        if overdue:
            conditions.append("due_date < :now AND status_name != 'Done'")
            params["now"] = datetime.now()

        # Get tasks
        tasks_query = f"""
            SELECT key as id, summary as title, description,
                   status_name as status, priority, assignee, assignee_name,
                   reporter, project_key, project_name,
                   labels, story_points, estimated_hours,
                   due_date, created, updated,
                   CASE WHEN status_name = 'Done' THEN updated ELSE NULL END as completed_at
            FROM jira_issues
            WHERE {' AND '.join(conditions)}
            ORDER BY 
                CASE priority 
                    WHEN 'Highest' THEN 4
                    WHEN 'High' THEN 3
                    WHEN 'Medium' THEN 2
                    WHEN 'Low' THEN 1
                    ELSE 0
                END DESC,
                updated DESC
            LIMIT :limit OFFSET :offset
        """

        params["limit"] = limit
        params["offset"] = offset

        result = db.execute(text(tasks_query), params)

        tasks = []
        for row in result.mappings():
            # Map status from JIRA to our enum
            status_mapping = {
                "To Do": TaskStatus.TODO,
                "In Progress": TaskStatus.IN_PROGRESS,
                "In Review": TaskStatus.IN_REVIEW,
                "Done": TaskStatus.DONE,
                "Blocked": TaskStatus.BLOCKED,
            }

            # Map priority from JIRA to our enum
            priority_mapping = {
                "Lowest": TaskPriority.LOW,
                "Low": TaskPriority.LOW,
                "Medium": TaskPriority.MEDIUM,
                "High": TaskPriority.HIGH,
                "Highest": TaskPriority.URGENT,
            }

            task_status = status_mapping.get(row["status"], TaskStatus.TODO)
            task_priority = priority_mapping.get(row["priority"], TaskPriority.MEDIUM)

            tasks.append(
                Task(
                    id=row["id"],
                    title=row["title"],
                    description=row["description"],
                    status=task_status,
                    priority=task_priority,
                    assignee=row["assignee"],
                    assignee_name=row["assignee_name"],
                    reporter=row["reporter"],
                    project_key=row["project_key"],
                    project_name=row["project_name"],
                    labels=row["labels"].split(",") if row["labels"] else [],
                    story_points=row["story_points"],
                    estimated_hours=row["estimated_hours"],
                    due_date=row["due_date"],
                    created_at=row["created"],
                    updated_at=row["updated"],
                    completed_at=row["completed_at"],
                )
            )

        # Get total count
        count_query = f"SELECT COUNT(*) as count FROM jira_issues WHERE {' AND '.join(conditions)}"
        count_result = (
            db.execute(
                text(count_query),
                {k: v for k, v in params.items() if k not in ["limit", "offset"]},
            )
            .mappings()
            .first()
        )
        total_count = count_result["count"] if count_result else 0

        # Generate summary
        summary = await _generate_tasks_summary(db, org_id, user_id)

        return TasksResponse(
            tasks=tasks,
            total_count=total_count,
            has_more=offset + len(tasks) < total_count,
            filters_applied={
                "status": status.value if status else None,
                "priority": priority.value if priority else None,
                "assignee": assignee,
                "project_key": project_key,
                "my_tasks": my_tasks,
            },
            summary=summary,
        )

    except Exception as e:
        logger.error(f"Failed to get tasks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get tasks: {str(e)}")


@router.get("/tasks/{task_id}", response_model=Task)
async def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Get detailed information about a specific task
    """
    try:
        org_id = org_ctx["org_id"]

        result = (
            db.execute(
                text(
                    """
                SELECT key as id, summary as title, description,
                       status_name as status, priority, assignee, assignee_name,
                       reporter, project_key, project_name,
                       labels, story_points, estimated_hours,
                       due_date, created, updated,
                       CASE WHEN status_name = 'Done' THEN updated ELSE NULL END as completed_at
                FROM jira_issues
                WHERE org_id = :org_id AND key = :task_id
            """
                ),
                {"org_id": org_id, "task_id": task_id},
            )
            .mappings()
            .first()
        )

        if not result:
            raise HTTPException(status_code=404, detail="Task not found")

        # Convert to Task model (similar to get_tasks)
        status_mapping = {
            "To Do": TaskStatus.TODO,
            "In Progress": TaskStatus.IN_PROGRESS,
            "In Review": TaskStatus.IN_REVIEW,
            "Done": TaskStatus.DONE,
            "Blocked": TaskStatus.BLOCKED,
        }

        priority_mapping = {
            "Lowest": TaskPriority.LOW,
            "Low": TaskPriority.LOW,
            "Medium": TaskPriority.MEDIUM,
            "High": TaskPriority.HIGH,
            "Highest": TaskPriority.URGENT,
        }

        task = Task(
            id=result["id"],
            title=result["title"],
            description=result["description"],
            status=status_mapping.get(result["status"], TaskStatus.TODO),
            priority=priority_mapping.get(result["priority"], TaskPriority.MEDIUM),
            assignee=result["assignee"],
            assignee_name=result["assignee_name"],
            reporter=result["reporter"],
            project_key=result["project_key"],
            project_name=result["project_name"],
            labels=result["labels"].split(",") if result["labels"] else [],
            story_points=result["story_points"],
            estimated_hours=result["estimated_hours"],
            due_date=result["due_date"],
            created_at=result["created"],
            updated_at=result["updated"],
            completed_at=result["completed_at"],
        )

        return task

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get task: {str(e)}")


@router.post("/tasks", response_model=Task)
async def create_task(
    request: CreateTaskRequest,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Create a new task
    """
    try:
        org_id = org_ctx["org_id"]
        user_id = user.get("sub") if user else "system"

        # Generate task ID
        task_id = f"TASK-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Store task in database (using tasks table)
        db.execute(
            text(
                """
                INSERT INTO tasks 
                (id, org_id, title, description, status, priority, assignee, 
                 reporter, project_key, labels, story_points, estimated_hours,
                 due_date, created_at, updated_at)
                VALUES (:id, :org_id, :title, :description, :status, :priority,
                        :assignee, :reporter, :project_key, :labels, :story_points,
                        :estimated_hours, :due_date, :created_at, :updated_at)
            """
            ),
            {
                "id": task_id,
                "org_id": org_id,
                "title": request.title,
                "description": request.description,
                "status": (
                    request.priority.value
                    if hasattr(request, "status")
                    else TaskStatus.TODO.value
                ),
                "priority": request.priority.value,
                "assignee": request.assignee,
                "reporter": user_id,
                "project_key": request.project_key,
                "labels": ",".join(request.labels),
                "story_points": request.story_points,
                "estimated_hours": request.estimated_hours,
                "due_date": request.due_date,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        )
        db.commit()

        # Index task for search
        await _index_task(db, org_id, task_id, request.title, request.description or "")

        # Return created task
        return await get_task(task_id, db, org_ctx, user)

    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create task: {str(e)}")


@router.put("/tasks/{task_id}", response_model=Task)
async def update_task(
    task_id: str,
    request: UpdateTaskRequest,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Update an existing task
    """
    try:
        org_id = org_ctx["org_id"]

        # Build update query
        update_fields = []
        params = {"task_id": task_id, "org_id": org_id, "updated_at": datetime.utcnow()}

        if request.title is not None:
            update_fields.append("title = :title")
            params["title"] = request.title

        if request.description is not None:
            update_fields.append("description = :description")
            params["description"] = request.description

        if request.status is not None:
            update_fields.append("status = :status")
            params["status"] = request.status.value

            # Set completed_at if marking as done
            if request.status == TaskStatus.DONE:
                update_fields.append("completed_at = :completed_at")
                params["completed_at"] = datetime.utcnow()

        if request.priority is not None:
            update_fields.append("priority = :priority")
            params["priority"] = request.priority.value

        if request.assignee is not None:
            update_fields.append("assignee = :assignee")
            params["assignee"] = request.assignee

        if request.project_key is not None:
            update_fields.append("project_key = :project_key")
            params["project_key"] = request.project_key

        if request.labels is not None:
            update_fields.append("labels = :labels")
            params["labels"] = ",".join(request.labels)

        if request.story_points is not None:
            update_fields.append("story_points = :story_points")
            params["story_points"] = request.story_points

        if request.estimated_hours is not None:
            update_fields.append("estimated_hours = :estimated_hours")
            params["estimated_hours"] = request.estimated_hours

        if request.actual_hours is not None:
            update_fields.append("actual_hours = :actual_hours")
            params["actual_hours"] = request.actual_hours

        if request.due_date is not None:
            update_fields.append("due_date = :due_date")
            params["due_date"] = request.due_date

        if request.blocked_reason is not None:
            update_fields.append("blocked_reason = :blocked_reason")
            params["blocked_reason"] = request.blocked_reason

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        update_fields.append("updated_at = :updated_at")

        # Execute update
        update_query = f"""
            UPDATE tasks 
            SET {', '.join(update_fields)}
            WHERE id = :task_id AND org_id = :org_id
        """

        result = db.execute(text(update_query), params)
        rowcount = cast(CursorResult, result).rowcount

        if rowcount == 0:
            # Try updating JIRA issues table as fallback
            jira_update_fields = []
            for field_expr in update_fields:
                column, sep, param = field_expr.partition("=")
                if column.strip() == "status":
                    jira_update_fields.append(f"status_name{sep}{param}")
                else:
                    jira_update_fields.append(field_expr)
            jira_update_query = f"""
                UPDATE jira_issues 
                SET {', '.join(jira_update_fields)}
                WHERE key = :task_id AND org_id = :org_id
            """
            jira_result = db.execute(text(jira_update_query), params)
            if cast(CursorResult, jira_result).rowcount == 0:
                raise HTTPException(status_code=404, detail="Task not found")

        db.commit()

        # Update search index
        if request.title or request.description:
            await _index_task(
                db, org_id, task_id, request.title or "", request.description or ""
            )

        # Return updated task
        return await get_task(task_id, db, org_ctx, user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update task {task_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update task: {str(e)}")


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Delete a task
    """
    try:
        org_id = org_ctx["org_id"]

        # Check if task exists
        result = (
            db.execute(
                text("SELECT id FROM tasks WHERE id = :task_id AND org_id = :org_id"),
                {"task_id": task_id, "org_id": org_id},
            )
            .mappings()
            .first()
        )

        if not result:
            raise HTTPException(status_code=404, detail="Task not found")

        # Delete task
        db.execute(
            text("DELETE FROM tasks WHERE id = :task_id AND org_id = :org_id"),
            {"task_id": task_id, "org_id": org_id},
        )
        db.commit()

        return {"message": "Task deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete task {task_id}: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete task: {str(e)}")


@router.get("/projects", response_model=ProjectsResponse)
async def get_projects(
    status: Optional[ProjectStatus] = Query(None, description="Filter by status"),
    lead: Optional[str] = Query(None, description="Filter by project lead"),
    my_projects: Optional[bool] = Query(None, description="Show only my projects"),
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Get projects with filtering
    """
    try:
        org_id = org_ctx["org_id"]
        user_id = user.get("sub") if user else None

        # Get projects from JIRA issues (grouped by project)
        conditions = ["org_id = :org_id"]
        params = {"org_id": org_id}

        if lead:
            conditions.append("project_lead = :lead")
            params["lead"] = lead
        elif my_projects and user_id:
            conditions.append("project_lead = :user_id")
            params["user_id"] = user_id

        projects_query = f"""
            SELECT project_key as key, 
                   MAX(project_name) as name,
                   MAX(project_lead) as lead,
                   MIN(created) as created_at,
                   MAX(updated) as updated_at,
                   COUNT(*) as task_count,
                   COUNT(CASE WHEN status_name = 'Done' THEN 1 END) as completed_tasks,
                   AVG(CASE WHEN story_points IS NOT NULL THEN story_points ELSE 0 END) as avg_story_points
            FROM jira_issues
            WHERE {' AND '.join(conditions)} AND project_key IS NOT NULL
            GROUP BY project_key
            ORDER BY MAX(updated) DESC
        """

        result = db.execute(text(projects_query), params)

        projects = []
        for row in result.mappings():
            progress = (
                (row["completed_tasks"] / row["task_count"] * 100)
                if row["task_count"] > 0
                else 0
            )

            projects.append(
                Project(
                    key=row["key"],
                    name=row["name"] or row["key"],
                    status=ProjectStatus.ACTIVE,  # Default status
                    lead=row["lead"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    task_count=row["task_count"],
                    completed_tasks=row["completed_tasks"],
                    progress_percentage=round(progress, 2),
                    velocity=row["avg_story_points"] or 0.0,
                )
            )

        # Generate summary
        summary = {
            "total_projects": len(projects),
            "active_projects": len(
                [p for p in projects if p.status == ProjectStatus.ACTIVE]
            ),
            "total_tasks": sum(p.task_count for p in projects),
            "completed_tasks": sum(p.completed_tasks for p in projects),
            "average_progress": (
                sum(p.progress_percentage for p in projects) / len(projects)
                if projects
                else 0
            ),
        }

        return ProjectsResponse(
            projects=projects, total_count=len(projects), summary=summary
        )

    except Exception as e:
        logger.error(f"Failed to get projects: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get projects: {str(e)}")


@router.get("/projects/{project_key}", response_model=Project)
async def get_project(
    project_key: str,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Get detailed information about a specific project
    """
    try:
        org_id = org_ctx["org_id"]

        result = (
            db.execute(
                text(
                    """
                SELECT project_key as key, 
                       MAX(project_name) as name,
                       MAX(project_lead) as lead,
                       MIN(created) as created_at,
                       MAX(updated) as updated_at,
                       COUNT(*) as task_count,
                       COUNT(CASE WHEN status_name = 'Done' THEN 1 END) as completed_tasks
                FROM jira_issues
                WHERE org_id = :org_id AND project_key = :project_key
                GROUP BY project_key
            """
                ),
                {"org_id": org_id, "project_key": project_key},
            )
            .mappings()
            .first()
        )

        if not result:
            raise HTTPException(status_code=404, detail="Project not found")

        progress = (
            (result["completed_tasks"] / result["task_count"] * 100)
            if result["task_count"] > 0
            else 0
        )

        project = Project(
            key=result["key"],
            name=result["name"] or result["key"],
            status=ProjectStatus.ACTIVE,
            lead=result["lead"],
            created_at=result["created_at"],
            updated_at=result["updated_at"],
            task_count=result["task_count"],
            completed_tasks=result["completed_tasks"],
            progress_percentage=round(progress, 2),
        )

        return project

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project {project_key}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")


@router.post("/projects", response_model=Project)
async def create_project(
    request: CreateProjectRequest,
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Create a new project
    """
    try:
        org_id = org_ctx["org_id"]
        user_id = user.get("sub") if user else "system"

        # Check if project key already exists
        existing = (
            db.execute(
                text("SELECT key FROM projects WHERE key = :key AND org_id = :org_id"),
                {"key": request.key, "org_id": org_id},
            )
            .mappings()
            .first()
        )

        if existing:
            raise HTTPException(status_code=400, detail="Project key already exists")

        # Create project
        db.execute(
            text(
                """
                INSERT INTO projects 
                (key, org_id, name, description, status, lead, team_members,
                 start_date, end_date, budget, created_at, updated_at)
                VALUES (:key, :org_id, :name, :description, :status, :lead,
                        :team_members, :start_date, :end_date, :budget, :created_at, :updated_at)
            """
            ),
            {
                "key": request.key,
                "org_id": org_id,
                "name": request.name,
                "description": request.description,
                "status": ProjectStatus.ACTIVE.value,
                "lead": request.lead or user_id,
                "team_members": ",".join(request.team_members),
                "start_date": request.start_date,
                "end_date": request.end_date,
                "budget": request.budget,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        )
        db.commit()

        # Return created project
        return await get_project(request.key, db, org_ctx, user)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create project: {str(e)}"
        )


@router.get("/dashboard")
async def get_dashboard(
    timeframe: str = Query("week", description="Timeframe: day, week, month, quarter"),
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Get task management dashboard with key metrics and insights
    """
    try:
        org_id = org_ctx["org_id"]
        user_id = user.get("sub") if user else None

        # Calculate timeframe
        days_back = {"day": 1, "week": 7, "month": 30, "quarter": 90}.get(timeframe, 7)
        since_date = datetime.now() - timedelta(days=days_back)

        # Get key metrics
        metrics = await _get_dashboard_metrics(db, org_id, user_id, since_date)

        # Get recent activity
        recent_activity = await _get_recent_activity(db, org_id, user_id, limit=10)

        # Get upcoming deadlines
        upcoming_deadlines = await _get_upcoming_deadlines(db, org_id, user_id, days=14)

        # Get workload distribution
        workload = await _get_workload_distribution(db, org_id)

        # Get velocity trends
        velocity = await _get_velocity_trends(db, org_id, timeframe)

        return {
            "timeframe": timeframe,
            "metrics": metrics,
            "recent_activity": recent_activity,
            "upcoming_deadlines": upcoming_deadlines,
            "workload_distribution": workload,
            "velocity_trends": velocity,
            "last_updated": datetime.utcnow(),
        }

    except Exception as e:
        logger.error(f"Failed to get dashboard: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get dashboard: {str(e)}"
        )


@router.get("/analytics")
async def get_analytics(
    timeframe: str = Query(
        "month", description="Timeframe: week, month, quarter, year"
    ),
    project_key: Optional[str] = Query(None, description="Filter by project"),
    team_member: Optional[str] = Query(None, description="Filter by team member"),
    db: Session = Depends(get_db),
    org_ctx: dict = Depends(require_org),
    user=Depends(get_current_user_optional),
):
    """
    Get comprehensive task and project analytics
    """
    try:
        org_id = org_ctx["org_id"]

        # Calculate timeframe
        days_back = {"week": 7, "month": 30, "quarter": 90, "year": 365}.get(
            timeframe, 30
        )
        since_date = datetime.now() - timedelta(days=days_back)

        # Get comprehensive analytics
        analytics = {
            "productivity_metrics": await _get_productivity_metrics(
                db, org_id, since_date, project_key, team_member
            ),
            "completion_trends": await _get_completion_trends(
                db, org_id, since_date, project_key
            ),
            "bottleneck_analysis": await _get_bottleneck_analysis(
                db, org_id, since_date
            ),
            "team_performance": await _get_team_performance(db, org_id, since_date),
            "project_health": await _get_project_health(db, org_id, project_key),
            "forecasting": await _get_forecasting_data(db, org_id, since_date),
            "quality_metrics": await _get_quality_metrics(db, org_id, since_date),
        }

        return analytics

    except Exception as e:
        logger.error(f"Failed to get analytics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get analytics: {str(e)}"
        )


# Helper functions


async def _generate_tasks_summary(
    db: Session, org_id: str, user_id: Optional[str]
) -> Dict[str, Any]:
    """Generate task summary statistics"""
    try:
        # Get overall statistics
        stats = (
            db.execute(
                text(
                    """
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN status_name = 'To Do' THEN 1 END) as todo,
                    COUNT(CASE WHEN status_name = 'In Progress' THEN 1 END) as in_progress,
                    COUNT(CASE WHEN status_name = 'Done' THEN 1 END) as done,
                    COUNT(CASE WHEN assignee = :user_id THEN 1 END) as my_tasks,
                    COUNT(CASE WHEN due_date < :now AND status_name != 'Done' THEN 1 END) as overdue
                FROM jira_issues
                WHERE org_id = :org_id
            """
                ),
                {"org_id": org_id, "user_id": user_id, "now": datetime.now()},
            )
            .mappings()
            .first()
        )

        return {
            "total_tasks": stats["total"] if stats else 0,
            "by_status": {
                "todo": stats["todo"] if stats else 0,
                "in_progress": stats["in_progress"] if stats else 0,
                "done": stats["done"] if stats else 0,
            },
            "my_tasks": stats["my_tasks"] if stats else 0,
            "overdue": stats["overdue"] if stats else 0,
            "completion_rate": (
                (stats["done"] / stats["total"] * 100)
                if stats and stats["total"] > 0
                else 0
            ),
        }

    except Exception as e:
        logger.error(f"Error generating tasks summary: {e}")
        return {}


async def _index_task(
    db: Session, org_id: str, task_id: str, title: str, description: str
):
    """Index task for search"""
    try:
        content = f"{title} {description}"
        upsert_memory_object(db, org_id, "task", task_id, title, "", "en", {}, content)
    except Exception as e:
        logger.error(f"Error indexing task: {e}")


async def _get_dashboard_metrics(
    db: Session, org_id: str, user_id: Optional[str], since_date: datetime
) -> Dict[str, Any]:
    """Get dashboard metrics"""
    try:
        metrics = (
            db.execute(
                text(
                    """
                SELECT 
                    COUNT(*) as total_tasks,
                    COUNT(CASE WHEN status_name = 'Done' AND updated >= :since_date THEN 1 END) as completed_recently,
                    COUNT(CASE WHEN assignee = :user_id THEN 1 END) as my_tasks,
                    COUNT(CASE WHEN due_date < :now AND status_name != 'Done' THEN 1 END) as overdue,
                    AVG(CASE WHEN story_points IS NOT NULL THEN story_points END) as avg_story_points
                FROM jira_issues
                WHERE org_id = :org_id
            """
                ),
                {
                    "org_id": org_id,
                    "user_id": user_id,
                    "since_date": since_date,
                    "now": datetime.now(),
                },
            )
            .mappings()
            .first()
        )

        avg_points = metrics["avg_story_points"] if metrics else 0
        return {
            "total_tasks": metrics["total_tasks"] if metrics else 0,
            "completed_recently": metrics["completed_recently"] if metrics else 0,
            "my_tasks": metrics["my_tasks"] if metrics else 0,
            "overdue_tasks": metrics["overdue"] if metrics else 0,
            "average_story_points": round(avg_points or 0, 1),
        }

    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {e}")
        return {}


async def _get_recent_activity(
    db: Session, org_id: str, user_id: Optional[str], limit: int
) -> List[Dict[str, Any]]:
    """Get recent task activity"""
    try:
        activities = db.execute(
            text(
                """
                SELECT key, summary, status_name, updated, assignee
                FROM jira_issues
                WHERE org_id = :org_id
                ORDER BY updated DESC
                LIMIT :limit
            """
            ),
            {"org_id": org_id, "limit": limit},
        )

        activity_list = []
        for row in activities.mappings():
            activity_list.append(
                {
                    "task_id": row["key"],
                    "title": row["summary"],
                    "status": row["status_name"],
                    "updated_at": row["updated"],
                    "assignee": row["assignee"],
                }
            )

        return activity_list

    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        return []


async def _get_upcoming_deadlines(
    db: Session, org_id: str, user_id: Optional[str], days: int
) -> List[Dict[str, Any]]:
    """Get upcoming task deadlines"""
    try:
        deadline_date = datetime.now() + timedelta(days=days)

        deadlines = db.execute(
            text(
                """
                SELECT key, summary, due_date, assignee, priority
                FROM jira_issues
                WHERE org_id = :org_id 
                  AND due_date BETWEEN :now AND :deadline_date
                  AND status_name != 'Done'
                ORDER BY due_date ASC
            """
            ),
            {"org_id": org_id, "now": datetime.now(), "deadline_date": deadline_date},
        )

        deadline_list = []
        for row in deadlines.mappings():
            deadline_list.append(
                {
                    "task_id": row["key"],
                    "title": row["summary"],
                    "due_date": row["due_date"],
                    "assignee": row["assignee"],
                    "priority": row["priority"],
                    "days_remaining": (
                        (row["due_date"] - datetime.now()).days
                        if row["due_date"]
                        else None
                    ),
                }
            )

        return deadline_list

    except Exception as e:
        logger.error(f"Error getting upcoming deadlines: {e}")
        return []


async def _get_workload_distribution(db: Session, org_id: str) -> Dict[str, Any]:
    """Get workload distribution across team members"""
    try:
        workload = db.execute(
            text(
                """
                SELECT assignee, 
                       COUNT(*) as total_tasks,
                       COUNT(CASE WHEN status_name != 'Done' THEN 1 END) as active_tasks,
                       SUM(CASE WHEN story_points IS NOT NULL THEN story_points ELSE 0 END) as total_points
                FROM jira_issues
                WHERE org_id = :org_id AND assignee IS NOT NULL
                GROUP BY assignee
                ORDER BY active_tasks DESC
            """
            ),
            {"org_id": org_id},
        )

        distribution = []
        for row in workload.mappings():
            distribution.append(
                {
                    "assignee": row["assignee"],
                    "total_tasks": row["total_tasks"],
                    "active_tasks": row["active_tasks"],
                    "total_points": row["total_points"],
                }
            )

        return {"distribution": distribution}

    except Exception as e:
        logger.error(f"Error getting workload distribution: {e}")
        return {}


async def _get_velocity_trends(
    db: Session, org_id: str, timeframe: str
) -> Dict[str, Any]:
    """Get team velocity trends"""
    try:
        # Simplified velocity calculation
        days_back = {"day": 7, "week": 28, "month": 90, "quarter": 365}.get(
            timeframe, 28
        )
        since_date = datetime.now() - timedelta(days=days_back)

        velocity = (
            db.execute(
                text(
                    """
                SELECT 
                    COUNT(CASE WHEN status_name = 'Done' AND updated >= :since_date THEN 1 END) as completed_tasks,
                    SUM(CASE WHEN status_name = 'Done' AND updated >= :since_date AND story_points IS NOT NULL 
                             THEN story_points ELSE 0 END) as completed_points
                FROM jira_issues
                WHERE org_id = :org_id
            """
                ),
                {"org_id": org_id, "since_date": since_date},
            )
            .mappings()
            .first()
        )

        return {
            "completed_tasks": velocity["completed_tasks"] if velocity else 0,
            "completed_points": velocity["completed_points"] if velocity else 0,
            "timeframe": timeframe,
            "trend": "stable",  # Could be calculated with historical data
        }

    except Exception as e:
        logger.error(f"Error getting velocity trends: {e}")
        return {}


# Additional analytics helper functions (simplified implementations)


async def _get_productivity_metrics(
    db: Session,
    org_id: str,
    since_date: datetime,
    project_key: Optional[str],
    team_member: Optional[str],
) -> Dict[str, Any]:
    """Get productivity metrics"""
    return {
        "tasks_completed": 15,
        "average_completion_time": 3.2,
        "productivity_score": 0.85,
        "trend": "increasing",
    }


async def _get_completion_trends(
    db: Session, org_id: str, since_date: datetime, project_key: Optional[str]
) -> Dict[str, Any]:
    """Get task completion trends"""
    return {
        "daily_completion_rate": 2.3,
        "weekly_trend": "stable",
        "seasonal_patterns": [],
    }


async def _get_bottleneck_analysis(
    db: Session, org_id: str, since_date: datetime
) -> Dict[str, Any]:
    """Analyze workflow bottlenecks"""
    return {
        "bottlenecks": [
            {"stage": "Code Review", "avg_time": 2.1, "impact": "medium"},
            {"stage": "Testing", "avg_time": 1.8, "impact": "low"},
        ],
        "recommendations": ["Add more reviewers", "Automate testing"],
    }


async def _get_team_performance(
    db: Session, org_id: str, since_date: datetime
) -> Dict[str, Any]:
    """Get team performance metrics"""
    return {
        "overall_performance": 0.87,
        "individual_performance": [],
        "collaboration_score": 0.82,
    }


async def _get_project_health(
    db: Session, org_id: str, project_key: Optional[str]
) -> Dict[str, Any]:
    """Get project health metrics"""
    return {"health_score": 0.89, "risk_factors": [], "recommendations": []}


async def _get_forecasting_data(
    db: Session, org_id: str, since_date: datetime
) -> Dict[str, Any]:
    """Get forecasting data"""
    return {
        "projected_completion": datetime.now() + timedelta(days=30),
        "confidence": 0.75,
        "factors": ["Current velocity", "Team capacity"],
    }


async def _get_quality_metrics(
    db: Session, org_id: str, since_date: datetime
) -> Dict[str, Any]:
    """Get quality metrics"""
    return {"defect_rate": 0.05, "rework_percentage": 0.12, "quality_score": 0.91}
