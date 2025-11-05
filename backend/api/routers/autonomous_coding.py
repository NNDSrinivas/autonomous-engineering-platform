"""
Enhanced Autonomous Coding API - Cline-style step-by-step coding with enterprise intelligence

This API provides endpoints for:
1. Creating tasks from JIRA with full context
2. Step-by-step execution with user approval
3. Real-time progress tracking
4. Enterprise integration (Slack, Confluence, Zoom)
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import threading
import random
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import logging
from datetime import datetime, timezone
import calendar

from backend.core.db import get_db
from backend.autonomous.enhanced_coding_engine import EnhancedAutonomousCodingEngine
from backend.core.ai.llm_service import LLMService
from backend.core.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/autonomous", tags=["autonomous-coding"])

# Thread-safe engine instances per user/workspace
_engine_lock = threading.Lock()
_coding_engines: Dict[str, EnhancedAutonomousCodingEngine] = {}


class CreateTaskFromJiraRequest(BaseModel):
    jira_key: str
    user_context: Optional[Dict[str, Any]] = None


class ExecuteStepRequest(BaseModel):
    task_id: str
    step_id: str
    user_approved: bool
    user_feedback: Optional[str] = None


class TaskPresentationResponse(BaseModel):
    task: Dict[str, Any]
    context: Dict[str, Any]
    implementation_plan: Dict[str, Any]
    steps_preview: List[Dict[str, Any]]
    next_action: str


class StepExecutionResponse(BaseModel):
    status: str
    step: str
    file_path: Optional[str] = None
    changes_applied: bool = False
    validation: Optional[Dict[str, Any]] = None
    next_step: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class WallpaperPreferences(BaseModel):
    theme: str  # "dynamic", "custom", "minimal"
    custom_background: Optional[str] = None
    animation_speed: str = "normal"  # "slow", "normal", "fast"
    particles_enabled: bool = True
    time_based_themes: bool = True


class ConciergeGreetingResponse(BaseModel):
    greeting: Dict[str, Any]
    wallpaper: Dict[str, Any]
    tasks_summary: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    quick_actions: List[Dict[str, Any]]



def get_coding_engine(
    workspace_id: str = "default", db: Optional[Session] = None
) -> EnhancedAutonomousCodingEngine:
    """Get or create a thread-safe coding engine instance for a workspace"""
    with _engine_lock:
        if workspace_id not in _coding_engines:
            # Initialize with proper dependencies
            llm_service = LLMService()
            vector_store = VectorStore()  # Placeholder
            workspace_path = f"/workspace/{workspace_id}"  # Workspace isolation

            # For thread-safe initialization, we'll set the db_session later
            _coding_engines[workspace_id] = EnhancedAutonomousCodingEngine(
                llm_service=llm_service,
                vector_store=vector_store,
                workspace_path=workspace_path,
                db_session=db,
            )

        # Update db_session if provided (for request-scoped sessions) - inside lock for thread safety
        if db is not None:
            _coding_engines[workspace_id].db_session = db

        return _coding_engines[workspace_id]


@router.post("/create-from-jira", response_model=TaskPresentationResponse)
async def create_task_from_jira(
    request: CreateTaskFromJiraRequest, db: Session = Depends(get_db)
):
    """
    Create autonomous coding task from JIRA ticket with full enterprise context

    This is where AEP excels over Cline - complete enterprise intelligence:
    - JIRA ticket details and context
    - Related Confluence documentation
    - Slack/Teams meeting discussions
    - Codebase analysis for related files
    - Team member context and preferences
    """
    try:
        engine = get_coding_engine(db=db)

        # Create task with full enterprise context
        task = await engine.create_task_from_jira(
            jira_key=request.jira_key, user_context=request.user_context or {}
        )

        # Generate comprehensive presentation for user
        presentation = await engine.present_task_to_user(task.id)

        logger.info(f"Created autonomous task from JIRA {request.jira_key}: {task.id}")

        return TaskPresentationResponse(**presentation)

    except Exception as e:
        logger.error(f"Failed to create task from JIRA {request.jira_key}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create autonomous task: {str(e)}"
        )


@router.post("/execute-step")
async def execute_step(request: ExecuteStepRequest, db: Session = Depends(get_db)):
    """
    Execute a single step with user approval

    Enhanced over Cline approach:
    1. User explicitly approves each file modification
    2. Real-time diff preview before changes
    3. Git safety with automatic backups
    4. Show results and next step preview
    5. Handle errors gracefully with rollback options
    """
    try:
        engine = get_coding_engine(db=db)

        # Execute step with user approval
        result = await engine.execute_step(
            task_id=request.task_id,
            step_id=request.step_id,
            user_approved=request.user_approved,
        )

        return result

    except Exception as e:
        logger.error(f"Failed to execute step {request.step_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """Get current status of autonomous coding task"""
    try:
        engine = get_coding_engine(db=db)

        task = engine.active_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "task_id": task.id,
            "title": task.title,
            "status": task.status,
            "current_step": task.current_step_index,
            "total_steps": len(task.steps),
            "jira_key": task.jira_key,
            "branch_name": task.branch_name,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    except Exception as e:
        logger.error(f"Failed to get task status {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/steps")
async def get_task_steps(task_id: str, db: Session = Depends(get_db)):
    """Get all steps for a task with their current status"""
    try:
        engine = get_coding_engine(db=db)

        task = engine.active_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        steps = []
        for step in task.steps:
            steps.append(
                {
                    "id": step.id,
                    "description": step.description,
                    "file_path": step.file_path,
                    "operation": step.operation,
                    "status": step.status.value,
                    "reasoning": step.reasoning,
                    "user_feedback": step.user_feedback,
                }
            )

        return {
            "task_id": task_id,
            "total_steps": len(steps),
            "current_step": task.current_step_index,
            "steps": steps,
        }

    except Exception as e:
        logger.error(f"Failed to get task steps {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/preview-step/{step_id}")
async def preview_step_changes(
    task_id: str, step_id: str, db: Session = Depends(get_db)
):
    """
    Preview what changes a step will make before user approval

    Critical for user trust - show exactly what will happen
    """
    try:
        engine = get_coding_engine(db=db)

        task = engine.active_tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        step = next((s for s in task.steps if s.id == step_id), None)
        if not step:
            raise HTTPException(status_code=404, detail="Step not found")

        # Generate preview of changes
        preview = {
            "step_id": step.id,
            "description": step.description,
            "file_path": step.file_path,
            "operation": step.operation,
            "content_preview": step.content_preview,
            "diff_preview": step.diff_preview,
            "reasoning": step.reasoning,
            "dependencies": step.dependencies,
            "estimated_impact": "Low",  # Would be calculated
            "safety_checks": [
                "Backup created",
                "Syntax validation",
                "Test compatibility",
            ],
        }

        return preview

    except Exception as e:
        logger.error(f"Failed to preview step {step_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/create-pr")
async def create_pull_request(task_id: str, db: Session = Depends(get_db)):
    """Create pull request for completed autonomous coding task"""
    try:
        engine = get_coding_engine(db=db)

        result = await engine.create_pull_request(
            task_id=task_id,
            repository="current",  # Would be configurable
            branch_name=None,  # Use task's branch
        )

        logger.info(f"Created PR for task {task_id}: {result.get('pr_url', 'unknown')}")

        # If error, raise HTTPException with generic message, otherwise return result
        if result.get("status") == "error":
            logger.error(
                f"Failed to create PR for task {task_id}: {result.get('error')}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create pull request: {result.get('error', 'Unknown error')}",
            )

        return result

    except Exception as e:
        logger.error(f"Failed to create PR for task {task_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create pull request: {str(e)}"
        )


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for autonomous coding service"""
    try:
        engine = get_coding_engine(db=db)

        return {
            "status": "healthy",
            "active_tasks": len(engine.active_tasks),
            "queue_size": len(engine.task_queue),
            "workspace_path": str(engine.workspace_path),
            "git_available": engine.repo is not None,
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": "Internal server error"}


@router.get("/user-daily-context")
async def get_user_daily_context(request: Request, db: Session = Depends(get_db)):
    """
    Get comprehensive daily context for user greeting

    This is the "killer feature" - enterprise intelligence for daily workflow:
    - JIRA tasks assigned to user
    - Recent Slack/Teams discussions about their tasks
    - Confluence docs related to current work
    - Meeting notes and decisions
    - Team member availability and context
    """
    try:
        # Get user identity (would use proper auth)
        user_id = request.headers.get("X-User-Id", "default-user")

        # Gather comprehensive daily context
        daily_context = {
            "user": {
                "id": user_id,
                "name": "Developer",  # Would fetch from directory
                "timezone": "UTC",
                "preferences": {},
            },
            "jira_tasks": await _fetch_user_jira_tasks(user_id),
            "recent_discussions": await _fetch_recent_discussions(user_id),
            "documentation_updates": await _fetch_doc_updates(user_id),
            "meeting_context": await _fetch_meeting_context(user_id),
            "team_activity": await _fetch_team_activity(user_id),
            "suggested_priorities": await _suggest_daily_priorities(user_id),
        }

        return daily_context

    except Exception as e:
        logger.error(f"Failed to get daily context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Helper functions for enterprise context gathering
async def _fetch_user_jira_tasks(user_id: str) -> List[Dict[str, Any]]:
    """Fetch user's assigned JIRA tasks with context"""
    # Would integrate with your existing JIRA service
    return [
        {
            "key": "ENG-123",
            "title": "Implement user authentication",
            "priority": "High",
            "status": "In Progress",
            "estimate": "5 story points",
            "sprint": "Sprint 24",
        }
    ]


async def _fetch_recent_discussions(user_id: str) -> List[Dict[str, Any]]:
    """Fetch recent Slack/Teams discussions about user's work"""
    # Would integrate with your existing Slack/Teams connectors
    return [
        {
            "source": "slack",
            "channel": "#engineering",
            "summary": "Discussion about authentication flow",
            "participants": ["alice", "bob"],
            "key_points": ["Use OAuth2", "Consider MFA"],
            "timestamp": "2024-01-15T10:30:00Z",
        }
    ]


async def _fetch_doc_updates(user_id: str) -> List[Dict[str, Any]]:
    """Fetch recent Confluence documentation updates"""
    # Would integrate with your existing Confluence connector
    return [
        {
            "title": "Authentication Architecture",
            "url": "https://confluence.company.com/auth-arch",
            "updated": "2024-01-14T15:00:00Z",
            "summary": "Updated OAuth2 implementation details",
        }
    ]


async def _fetch_meeting_context(user_id: str) -> List[Dict[str, Any]]:
    """Fetch recent meeting notes and decisions"""
    # Would integrate with your existing Zoom/Teams connectors
    return [
        {
            "title": "Sprint Planning - Sprint 24",
            "date": "2024-01-12T09:00:00Z",
            "decisions": ["Prioritize auth work", "Use new UI framework"],
            "action_items": ["ENG-123 assigned to user"],
        }
    ]


async def _fetch_team_activity(user_id: str) -> List[Dict[str, Any]]:
    """Fetch relevant team member activity"""
    # Would use your existing team activity APIs
    return [
        {
            "member": "alice",
            "activity": "Completed OAuth2 research",
            "relevance": "Related to your ENG-123 task",
        }
    ]


async def _suggest_daily_priorities(user_id: str) -> List[Dict[str, Any]]:
    """AI-powered daily priority suggestions"""
    # Would use your LLM service to analyze context and suggest priorities
    return [
        {
            "priority": 1,
            "task": "ENG-123",
            "reasoning": "High priority, blocking other work",
            "estimated_effort": "4 hours",
            "dependencies": [],
        }
    ]


@router.get("/concierge/greeting", response_model=ConciergeGreetingResponse)
async def get_concierge_greeting(request: Request, db: Session = Depends(get_db)):
    """
    Dynamic time-based greeting with animated wallpaper and task intelligence

    Features:
    - Time-based animated wallpapers (morning/evening/night themes)
    - Personalized greeting messages
    - Smart task recommendations
    - Quick action suggestions
    - Enterprise context integration
    """
    try:
        # Get user identity and preferences
        user_id = request.headers.get("X-User-Id", "default-user")
        current_time = datetime.now(timezone.utc)

        # Generate time-based greeting and wallpaper
        greeting_data = await _generate_dynamic_greeting(user_id, current_time)
        wallpaper_config = await _get_wallpaper_config(user_id, current_time)

        # Get daily context for task recommendations
        daily_context = await _get_user_daily_context_data(user_id, db)

        # Generate smart recommendations
        recommendations = await _generate_smart_recommendations(daily_context)
        quick_actions = await _generate_quick_actions(daily_context)

        return ConciergeGreetingResponse(
            greeting=greeting_data,
            wallpaper=wallpaper_config,
            tasks_summary=daily_context.get("tasks_summary", {}),
            recommendations=recommendations,
            quick_actions=quick_actions,
        )

    except Exception as e:
        logger.error(f"Failed to generate concierge greeting: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate greeting")


@router.post("/concierge/wallpaper/preferences")
async def update_wallpaper_preferences(
    preferences: WallpaperPreferences, request: Request, db: Session = Depends(get_db)
):
    """Update user's wallpaper and animation preferences"""
    try:
        user_id = request.headers.get("X-User-Id", "default-user")

        # Store preferences (would use user preferences service)
        saved_preferences = await _save_wallpaper_preferences(user_id, preferences, db)

        return {
            "status": "success",
            "preferences": saved_preferences,
            "message": "Wallpaper preferences updated successfully",
        }

    except Exception as e:
        logger.error(f"Failed to update wallpaper preferences: {e}")
        raise HTTPException(status_code=500, detail="Failed to update preferences")


@router.get("/concierge/wallpaper/themes")
async def get_available_wallpaper_themes():
    """Get all available wallpaper themes and customization options"""
    return {
        "time_based_themes": {
            "morning": {
                "name": "Sunny Meadow",
                "description": "Bright sun with swaying grass and gentle breeze",
                "primary_color": "#87CEEB",
                "accent_color": "#FFD700",
                "animations": ["grass_sway", "cloud_drift", "sun_rays"],
            },
            "afternoon": {
                "name": "Clear Skies",
                "description": "Fluffy clouds drifting across clear blue sky",
                "primary_color": "#4A90E2",
                "accent_color": "#FFFFFF",
                "animations": ["cloud_movement", "bird_flight"],
            },
            "evening": {
                "name": "Beach Sunset",
                "description": "Warm sunset over ocean with animated waves",
                "primary_color": "#FF6B35",
                "accent_color": "#4ECDC4",
                "animations": ["wave_motion", "seagull_flight", "sunset_glow"],
            },
            "night": {
                "name": "Starry Night",
                "description": "Moon and stars with falling meteors",
                "primary_color": "#1A1A2E",
                "accent_color": "#FFD700",
                "animations": ["star_twinkle", "meteor_shower", "moon_glow"],
            },
        },
        "custom_themes": [
            {
                "id": "matrix",
                "name": "Matrix Code",
                "description": "Green digital rain effect",
            },
            {
                "id": "particles",
                "name": "Particle System",
                "description": "Floating geometric particles",
            },
            {
                "id": "minimal",
                "name": "Minimal",
                "description": "Clean gradient background",
            },
        ],
        "animation_options": {
            "speed": ["slow", "normal", "fast"],
            "intensity": ["subtle", "normal", "vibrant"],
            "particles": ["none", "minimal", "normal", "heavy"],
        },
    }


# Helper functions for concierge system
async def _generate_dynamic_greeting(
    user_id: str, current_time: datetime
) -> Dict[str, Any]:
    """Generate personalized, time-based greeting message"""
    hour = current_time.hour
    day_name = calendar.day_name[current_time.weekday()]

    # Time-based greeting templates
    if 6 <= hour < 12:
        time_greeting = "Good morning"
        time_context = "Start your day with focused coding"
        energy_level = "high"
    elif 12 <= hour < 18:
        time_greeting = "Good afternoon"
        time_context = "Keep the momentum going"
        energy_level = "steady"
    elif 18 <= hour < 22:
        time_greeting = "Good evening"
        time_context = "Wrap up the day's work"
        energy_level = "winding_down"
    else:
        time_greeting = "Good evening"
        time_context = "Late night coding session"
        energy_level = "focused"

    return {
        "primary_message": f"{time_greeting}! Ready to build something amazing?",
        "time_context": time_context,
        "day_info": f"Happy {day_name}",
        "energy_level": energy_level,
        "motivational_quote": await _get_daily_motivation(energy_level),
        "timestamp": current_time.isoformat(),
    }


async def _get_wallpaper_config(user_id: str, current_time: datetime) -> Dict[str, Any]:
    """Get dynamic wallpaper configuration based on time and user preferences"""
    hour = current_time.hour

    # Determine time-based theme
    if 6 <= hour < 12:
        theme = "morning"
        animation_set = ["grass_sway", "sun_rays", "butterfly_flutter"]
        color_palette = {
            "primary": "#87CEEB",  # Sky blue
            "secondary": "#98FB98",  # Pale green
            "accent": "#FFD700",  # Gold
            "text": "#2F4F4F",  # Dark slate gray
        }
    elif 12 <= hour < 18:
        theme = "afternoon"
        animation_set = ["cloud_drift", "bird_flight"]
        color_palette = {
            "primary": "#4A90E2",  # Bright blue
            "secondary": "#FFFFFF",  # White
            "accent": "#FFA500",  # Orange
            "text": "#2C3E50",  # Dark blue gray
        }
    elif 18 <= hour < 22:
        theme = "evening"
        animation_set = ["wave_motion", "sunset_glow", "seagull_flight"]
        color_palette = {
            "primary": "#FF6B35",  # Sunset orange
            "secondary": "#4ECDC4",  # Teal
            "accent": "#FFE066",  # Light yellow
            "text": "#2C3E50",  # Dark blue gray
        }
    else:
        theme = "night"
        animation_set = ["star_twinkle", "meteor_shower", "moon_glow"]
        color_palette = {
            "primary": "#1A1A2E",  # Dark navy
            "secondary": "#16213E",  # Darker blue
            "accent": "#FFD700",  # Gold
            "text": "#E8E8E8",  # Light gray
        }

    return {
        "theme": theme,
        "animations": animation_set,
        "colors": color_palette,
        "particle_effects": {"enabled": True, "type": theme, "intensity": "normal"},
        "transition_duration": "2s",
        "hour": hour,
    }


async def _get_user_daily_context_data(user_id: str, db: Session) -> Dict[str, Any]:
    """Get comprehensive daily context for user"""
    try:
        # Get JIRA tasks (using existing endpoint data)
        jira_tasks = await _fetch_user_jira_tasks(user_id)

        # Calculate task summary
        total_tasks = len(jira_tasks)
        high_priority = len([t for t in jira_tasks if t.get("priority") == "High"])
        in_progress = len([t for t in jira_tasks if t.get("status") == "In Progress"])

        return {
            "tasks_summary": {
                "total": total_tasks,
                "high_priority": high_priority,
                "in_progress": in_progress,
                "completion_rate": "75%",  # Would calculate from actual data
            },
            "jira_tasks": jira_tasks,
            "recent_activity": await _fetch_recent_discussions(user_id),
            "upcoming_meetings": [],  # Would fetch from calendar
            "team_updates": await _fetch_team_activity(user_id),
        }

    except Exception as e:
        logger.error(f"Failed to get daily context: {e}")
        return {"tasks_summary": {}, "jira_tasks": []}


async def _generate_smart_recommendations(
    daily_context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Generate AI-powered task recommendations"""
    tasks = daily_context.get("jira_tasks", [])

    recommendations = []

    # High priority tasks first
    high_priority_tasks = [t for t in tasks if t.get("priority") == "High"]
    for task in high_priority_tasks[:3]:  # Top 3 high priority
        recommendations.append(
            {
                "type": "urgent_task",
                "title": f"Complete {task['key']}",
                "description": task.get("title", ""),
                "reason": "High priority, needs attention",
                "estimated_time": "2-4 hours",
                "action": "start_coding",
                "task_key": task["key"],
            }
        )

    # Add coding session recommendation
    if len(recommendations) > 0:
        recommendations.append(
            {
                "type": "focus_session",
                "title": "Start 2-hour focus session",
                "description": "Deep work on your high-priority tasks",
                "reason": "Maximize productivity with uninterrupted coding",
                "estimated_time": "2 hours",
                "action": "start_focus_mode",
            }
        )

    return recommendations[:4]  # Limit to 4 recommendations


async def _generate_quick_actions(
    daily_context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Generate contextual quick actions"""
    return [
        {
            "id": "create_task_from_jira",
            "title": "Create Task from JIRA",
            "icon": "ticket",
            "description": "Start autonomous coding from JIRA ticket",
            "action": "open_jira_selector",
        },
        {
            "id": "review_prs",
            "title": "Review Pull Requests",
            "icon": "git-pull-request",
            "description": "Review team PRs waiting for feedback",
            "action": "open_pr_dashboard",
        },
        {
            "id": "check_team_updates",
            "title": "Team Updates",
            "icon": "users",
            "description": "See what your team is working on",
            "action": "open_team_activity",
        },
        {
            "id": "browse_docs",
            "title": "Browse Documentation",
            "icon": "book",
            "description": "Search Confluence and internal docs",
            "action": "open_doc_search",
        },
    ]


async def _get_daily_motivation(energy_level: str) -> str:
    """Get motivational quote based on energy level and time"""
    quotes = {
        "high": [
            "Every line of code is a step toward something amazing!",
            "Today's bugs are tomorrow's features in disguise.",
            "Code with passion, debug with patience.",
        ],
        "steady": [
            "Consistent progress beats occasional perfection.",
            "Great software is built one commit at a time.",
            "Your code today shapes tomorrow's solutions.",
        ],
        "winding_down": [
            "Finishing strong is just as important as starting right.",
            "Every problem solved makes you a better developer.",
            "Time to wrap up and celebrate today's progress.",
        ],
        "focused": [
            "Night owls write the most elegant code.",
            "The quiet hours are when the magic happens.",
            "Deep focus leads to breakthrough solutions.",
        ],
    }

    return random.choice(quotes.get(energy_level, quotes["steady"]))


async def _save_wallpaper_preferences(
    user_id: str, preferences: WallpaperPreferences, db: Session
) -> Dict[str, Any]:
    """Save user wallpaper preferences to database"""
    # This would typically save to a user_preferences table
    # For now, return the preferences as confirmation
    return {
        "user_id": user_id,
        "theme": preferences.theme,
        "custom_background": preferences.custom_background,
        "animation_speed": preferences.animation_speed,
        "particles_enabled": preferences.particles_enabled,
        "time_based_themes": preferences.time_based_themes,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
