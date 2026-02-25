"""
Autonomous Sprint Planner Agent

This agent creates and manages sprints like a real engineering manager:
- Estimates tasks using historical data
- Assigns priorities based on business value
- Places tasks into sprints with proper capacity planning
- Projects timelines and monitors burn-down
- Auto-adjusts backlog when tasks spill over
"""

import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

try:
    from ..services.llm_router import LLMRouter
    from ..services.database_service import DatabaseService
    from ..core.config import get_settings
except ImportError:
    from backend.services.llm_router import LLMRouter
    from backend.services.database_service import DatabaseService
    from backend.core.config import get_settings


@dataclass
class BacklogItem:
    """Represents a single backlog item."""

    id: str
    title: str
    description: str
    story_points: Optional[int] = None
    priority: int = 1
    tags: Optional[List[str]] = None
    dependencies: Optional[List[str]] = None
    assigned_to: Optional[str] = None
    estimated_hours: Optional[float] = None
    complexity: str = "medium"  # low, medium, high
    business_value: int = 5  # 1-10 scale
    technical_risk: int = 3  # 1-10 scale
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.dependencies is None:
            self.dependencies = []
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class Sprint:
    """Represents a sprint with all its metadata."""

    id: str
    name: str
    goal: str
    duration_days: int
    start_date: datetime
    end_date: datetime
    capacity_points: int
    items: List[BacklogItem]
    status: str = "planned"  # planned, active, completed
    velocity_target: float = 0.0
    burn_down_data: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.burn_down_data is None:
            self.burn_down_data = {"daily_progress": []}


@dataclass
class SprintPlan:
    """Complete sprint planning result."""

    sprint: Sprint
    reasoning: str
    risks: List[str]
    recommendations: List[str]
    timeline: Dict[str, Any]
    success_criteria: List[str]


class SprintPlannerAgent:
    """
    Autonomous Sprint Planner that acts like an experienced engineering manager.
    Handles sprint creation, task estimation, capacity planning, and progress tracking.
    """

    def __init__(self):
        """Initialize the Sprint Planner Agent."""
        self.llm = LLMRouter()
        self.db = DatabaseService()
        self.settings = get_settings()

        # Sprint planning parameters
        self.default_sprint_duration = 14  # days
        self.default_velocity = 20  # story points per sprint
        self.capacity_buffer = 0.8  # 80% capacity to account for overhead

    async def plan_sprint(
        self,
        backlog_items: List[BacklogItem],
        team_capacity: Optional[int] = None,
        sprint_duration_days: Optional[int] = None,
        previous_velocity: Optional[float] = None,
        team_members: Optional[List[str]] = None,
    ) -> SprintPlan:
        """
        Create a complete sprint plan with intelligent task selection and scheduling.

        Args:
            backlog_items: Available backlog items to choose from
            team_capacity: Total team capacity in story points
            sprint_duration_days: Length of sprint in days
            previous_velocity: Historical velocity for planning
            team_members: List of team member identifiers

        Returns:
            Complete sprint plan with selected items and timeline
        """

        # Set defaults
        duration = sprint_duration_days or self.default_sprint_duration
        capacity = team_capacity or (previous_velocity or self.default_velocity)

        # Apply capacity buffer
        adjusted_capacity = int(capacity * self.capacity_buffer)

        # Create sprint planning prompt
        prompt = f"""
        You are Navi-SprintPlanner, an elite autonomous engineering manager with 10+ years of experience.
        
        Plan a complete sprint for the next {duration} days with {adjusted_capacity} story points capacity.
        
        AVAILABLE BACKLOG ITEMS:
        {json.dumps([asdict(item) for item in backlog_items], indent=2, default=str)}
        
        TEAM INFO:
        - Capacity: {adjusted_capacity} story points
        - Duration: {duration} days
        - Team Members: {team_members or ["Default Team"]}
        - Previous Velocity: {previous_velocity or "Unknown"}
        
        CREATE A COMPREHENSIVE SPRINT PLAN:
        
        1. **Sprint Goal**: One clear, achievable goal that ties selected work together
        
        2. **Selected Items**: Choose backlog items that:
           - Fit within capacity ({adjusted_capacity} points)
           - Have logical dependencies resolved
           - Balance high-value with achievable scope
           - Consider technical risks
        
        3. **Story Point Estimation**: For each selected item, provide:
           - Estimated story points (1, 2, 3, 5, 8, 13, 21)
           - Reasoning for the estimate
           - Confidence level (high/medium/low)
        
        4. **Task Breakdown**: Break complex items into smaller engineering tasks
        
        5. **Timeline**: Day-by-day plan showing:
           - When items should start/complete
           - Dependencies and blockers
           - Critical path items
        
        6. **Risk Analysis**: Identify potential risks and mitigation strategies
        
        7. **Success Criteria**: Measurable definitions of sprint success
        
        8. **Burn-down Projection**: Expected daily progress curve
        
        Return your response as valid JSON with this structure:
        {{
            "sprint_goal": "Clear, specific sprint objective",
            "selected_items": [
                {{
                    "id": "item_id",
                    "story_points": 5,
                    "reasoning": "Why this estimate",
                    "confidence": "high|medium|low",
                    "tasks": ["Task 1", "Task 2", ...]
                }}
            ],
            "timeline": {{
                "day_1": ["Start Item A", "Complete Item B setup"],
                "day_2": ["Continue Item A", "Review Item C"],
                ...
            }},
            "risks": [
                {{
                    "risk": "Description of risk",
                    "probability": "high|medium|low", 
                    "impact": "high|medium|low",
                    "mitigation": "How to address it"
                }}
            ],
            "success_criteria": ["Criteria 1", "Criteria 2", ...],
            "burn_down_projection": [
                {{
                    "day": 1,
                    "remaining_points": 18,
                    "completed_points": 2
                }},
                ...
            ],
            "recommendations": ["Recommendation 1", "Recommendation 2", ...]
        }}
        """

        try:
            # Get LLM response
            response = await self.llm.run(prompt=prompt, use_smart_auto=True)
            planning_result = json.loads(response.text)

            # Create sprint object
            sprint_id = f"sprint_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            start_date = datetime.now()
            end_date = start_date + timedelta(days=duration)

            # Select items based on LLM recommendations
            selected_items = []
            total_points = 0

            for selected in planning_result["selected_items"]:
                # Find the original backlog item
                original_item = next(
                    (item for item in backlog_items if item.id == selected["id"]), None
                )
                if original_item:
                    # Update with planning info
                    original_item.story_points = selected["story_points"]
                    selected_items.append(original_item)
                    total_points += selected["story_points"]

            # Create sprint
            sprint = Sprint(
                id=sprint_id,
                name=f"Sprint {datetime.now().strftime('%Y-%m-%d')}",
                goal=planning_result["sprint_goal"],
                duration_days=duration,
                start_date=start_date,
                end_date=end_date,
                capacity_points=adjusted_capacity,
                items=selected_items,
                velocity_target=total_points
                / (duration / 14),  # Normalize to 2-week velocity
                burn_down_data={
                    "daily_progress": planning_result.get("burn_down_projection", [])
                },
            )

            # Create complete plan
            plan = SprintPlan(
                sprint=sprint,
                reasoning=f"Selected {len(selected_items)} items totaling {total_points} points",
                risks=[
                    risk["risk"] + " (" + risk["mitigation"] + ")"
                    for risk in planning_result.get("risks", [])
                ],
                recommendations=planning_result.get("recommendations", []),
                timeline=planning_result.get("timeline", {}),
                success_criteria=planning_result.get("success_criteria", []),
            )

            # Save sprint to database
            await self._save_sprint(sprint)

            return plan

        except Exception:
            # Fallback planning
            return await self._fallback_sprint_planning(
                backlog_items, adjusted_capacity, duration
            )

    async def monitor_sprint_progress(
        self, sprint_id: str, completed_items: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Monitor and analyze sprint progress with burn-down tracking.

        Args:
            sprint_id: ID of the sprint to monitor
            completed_items: List of item IDs that have been completed

        Returns:
            Progress analysis with recommendations
        """

        # Load sprint data
        sprint_data = await self._load_sprint(sprint_id)
        if not sprint_data:
            return {"error": "Sprint not found"}

        # Calculate progress metrics
        total_points = sum(item.get("story_points", 0) for item in sprint_data["items"])
        completed_points = 0

        if completed_items:
            for item in sprint_data["items"]:
                if item["id"] in completed_items:
                    completed_points += item.get("story_points", 0)

        # Calculate days elapsed
        start_date = datetime.fromisoformat(sprint_data["start_date"])
        days_elapsed = (datetime.now() - start_date).days
        total_days = sprint_data["duration_days"]

        # Expected progress (linear burn-down)
        expected_completion = (days_elapsed / total_days) if total_days > 0 else 0
        expected_points = total_points * expected_completion

        # Calculate variance
        progress_variance = completed_points - expected_points

        # Generate analysis
        analysis_prompt = f"""
        Analyze this sprint progress and provide recommendations:
        
        SPRINT METRICS:
        - Total Points: {total_points}
        - Completed Points: {completed_points}
        - Expected Points by now: {expected_points:.1f}
        - Days Elapsed: {days_elapsed}/{total_days}
        - Progress Variance: {progress_variance:.1f} points
        
        ANALYSIS NEEDED:
        1. Is the sprint on track?
        2. What are the risks?
        3. Should scope be adjusted?
        4. What actions should the team take?
        
        Return JSON with analysis and recommendations.
        """

        try:
            response = await self.llm.run(prompt=analysis_prompt, use_smart_auto=True)
            analysis = json.loads(response.text)

            # Add calculated metrics
            analysis.update(
                {
                    "total_points": total_points,
                    "completed_points": completed_points,
                    "expected_points": expected_points,
                    "progress_percentage": (
                        (completed_points / total_points * 100)
                        if total_points > 0
                        else 0
                    ),
                    "days_remaining": max(0, total_days - days_elapsed),
                    "velocity_trend": (
                        completed_points / max(days_elapsed, 1)
                        if days_elapsed > 0
                        else 0
                    ),
                    "on_track": abs(progress_variance)
                    <= (total_points * 0.1),  # Within 10% tolerance
                }
            )

            return analysis

        except Exception as e:
            return {
                "error": f"Analysis failed: {str(e)}",
                "basic_metrics": {
                    "completed_points": completed_points,
                    "total_points": total_points,
                    "progress_percentage": (
                        (completed_points / total_points * 100)
                        if total_points > 0
                        else 0
                    ),
                },
            }

    async def adjust_sprint_scope(
        self,
        sprint_id: str,
        new_items: Optional[List[BacklogItem]] = None,
        remove_items: Optional[List[str]] = None,
        reason: str = "Scope adjustment",
    ) -> Dict[str, Any]:
        """
        Intelligently adjust sprint scope based on progress and new requirements.

        Args:
            sprint_id: ID of the sprint to adjust
            new_items: New items to potentially add
            remove_items: Item IDs to remove
            reason: Reason for the adjustment

        Returns:
            Adjustment analysis and updated sprint plan
        """

        # Load current sprint
        sprint_data = await self._load_sprint(sprint_id)
        if not sprint_data:
            return {"error": "Sprint not found"}

        current_items = sprint_data["items"]
        current_capacity = sprint_data["capacity_points"]

        # Calculate current utilization
        current_points = sum(item.get("story_points", 0) for item in current_items)

        adjustment_prompt = f"""
        You are Navi-SprintManager adjusting sprint scope mid-sprint.
        
        CURRENT SPRINT:
        - Items: {len(current_items)}
        - Current Points: {current_points}
        - Capacity: {current_capacity}
        - Reason for Change: {reason}
        
        PROPOSED CHANGES:
        - Add Items: {len(new_items) if new_items else 0}
        - Remove Items: {len(remove_items) if remove_items else 0}
        
        NEW ITEMS TO CONSIDER:
        {json.dumps([asdict(item) for item in new_items], default=str) if new_items else "None"}
        
        ANALYZE AND RECOMMEND:
        1. Should these changes be made?
        2. What's the impact on sprint goal?
        3. Are there capacity concerns?
        4. What items should be prioritized?
        5. How should timeline be adjusted?
        
        Return JSON with your analysis and final recommendations.
        """

        try:
            response = await self.llm.run(prompt=adjustment_prompt, use_smart_auto=True)
            adjustment_analysis = json.loads(response.text)

            # Apply approved changes
            updated_items = [
                item for item in current_items if item["id"] not in (remove_items or [])
            ]

            # Add approved new items
            if new_items and adjustment_analysis.get("approved_additions"):
                for item in new_items:
                    if item.id in adjustment_analysis["approved_additions"]:
                        updated_items.append(asdict(item))

            # Update sprint in database
            sprint_data["items"] = updated_items
            sprint_data["last_modified"] = datetime.now().isoformat()
            sprint_data["modification_reason"] = reason

            await self._update_sprint(sprint_id, sprint_data)

            return {
                "success": True,
                "analysis": adjustment_analysis,
                "updated_items_count": len(updated_items),
                "new_total_points": sum(
                    item.get("story_points", 0) for item in updated_items
                ),
            }

        except Exception as e:
            return {"error": f"Scope adjustment failed: {str(e)}"}

    async def _save_sprint(self, sprint: Sprint) -> None:
        """Save sprint to database."""
        try:
            query = """
            INSERT INTO sprints (id, name, goal, duration_days, start_date, end_date, 
                               capacity_points, items, status, velocity_target, burn_down_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            await self.db.execute(
                query,
                [
                    sprint.id,
                    sprint.name,
                    sprint.goal,
                    sprint.duration_days,
                    sprint.start_date.isoformat(),
                    sprint.end_date.isoformat(),
                    sprint.capacity_points,
                    json.dumps([asdict(item) for item in sprint.items], default=str),
                    sprint.status,
                    sprint.velocity_target,
                    json.dumps(sprint.burn_down_data),
                    datetime.now().isoformat(),
                ],
            )
        except Exception:
            # Create table if it doesn't exist
            create_query = """
            CREATE TABLE IF NOT EXISTS sprints (
                id TEXT PRIMARY KEY,
                name TEXT,
                goal TEXT,
                duration_days INTEGER,
                start_date TEXT,
                end_date TEXT,
                capacity_points INTEGER,
                items TEXT,
                status TEXT,
                velocity_target REAL,
                burn_down_data TEXT,
                created_at TEXT,
                last_modified TEXT,
                modification_reason TEXT
            )
            """
            await self.db.execute(create_query, [])
            # Retry insert
            await self.db.execute(
                query,
                [
                    sprint.id,
                    sprint.name,
                    sprint.goal,
                    sprint.duration_days,
                    sprint.start_date.isoformat(),
                    sprint.end_date.isoformat(),
                    sprint.capacity_points,
                    json.dumps([asdict(item) for item in sprint.items], default=str),
                    sprint.status,
                    sprint.velocity_target,
                    json.dumps(sprint.burn_down_data),
                    datetime.now().isoformat(),
                ],
            )

    async def _load_sprint(self, sprint_id: str) -> Optional[Dict[str, Any]]:
        """Load sprint from database."""
        try:
            query = "SELECT * FROM sprints WHERE id = ?"
            result = await self.db.fetch_one(query, [sprint_id])

            if result:
                # Parse JSON fields
                result["items"] = json.loads(result["items"])
                result["burn_down_data"] = json.loads(result["burn_down_data"])
                return result
            return None
        except Exception:
            return None

    async def _update_sprint(self, sprint_id: str, sprint_data: Dict[str, Any]) -> None:
        """Update sprint in database."""
        try:
            query = """
            UPDATE sprints 
            SET items = ?, last_modified = ?, modification_reason = ?
            WHERE id = ?
            """
            await self.db.execute(
                query,
                [
                    json.dumps(sprint_data["items"], default=str),
                    sprint_data["last_modified"],
                    sprint_data.get("modification_reason", ""),
                    sprint_id,
                ],
            )
        except Exception:
            pass  # Fail silently for now

    async def _fallback_sprint_planning(
        self, backlog_items: List[BacklogItem], capacity: int, duration: int
    ) -> SprintPlan:
        """Fallback planning when LLM fails."""

        # Simple capacity-based selection
        selected_items = []
        total_points = 0

        # Sort by priority and business value
        sorted_items = sorted(
            backlog_items,
            key=lambda x: (x.priority, -x.business_value, x.technical_risk),
        )

        for item in sorted_items:
            item_points = item.story_points or self._estimate_story_points(item)
            if total_points + item_points <= capacity:
                item.story_points = item_points
                selected_items.append(item)
                total_points += item_points

        # Create basic sprint
        sprint = Sprint(
            id=f"sprint_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            name=f"Sprint {datetime.now().strftime('%Y-%m-%d')}",
            goal="Complete selected high-priority items",
            duration_days=duration,
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=duration),
            capacity_points=capacity,
            items=selected_items,
        )

        return SprintPlan(
            sprint=sprint,
            reasoning="Fallback planning based on priority and capacity",
            risks=["Limited analysis due to planning system unavailability"],
            recommendations=["Review and adjust sprint scope manually"],
            timeline={
                f"day_{i}": ["Continue planned work"] for i in range(1, duration + 1)
            },
            success_criteria=["Complete all selected items", "Maintain team velocity"],
        )

    def _estimate_story_points(self, item: BacklogItem) -> int:
        """Simple story point estimation based on complexity."""
        complexity_map = {"low": 2, "medium": 5, "high": 8}
        return complexity_map.get(item.complexity, 5)
