"""
Adaptive Replanner — Intelligent Plan Adjustment

Monitors execution progress and environmental changes to adaptively replan
when reality diverges from expectations. Maintains plan coherence while
adapting to new constraints, opportunities, and failures.
"""

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging

from backend.agent.planning.plan_graph import PlanGraph, TaskStatus
from backend.agent.planning.task_decomposer import TaskDecomposer
from backend.agent.planning.execution_scheduler import ExecutionContext
from backend.agent.planning.initiative_store import Initiative
from backend.agent.planner_v3 import PlannerV3


logger = logging.getLogger(__name__)


class ReplanTrigger(Enum):
    """Triggers that can cause replanning"""
    TASK_FAILURE = "TASK_FAILURE"           # Task failed multiple times
    BLOCKED_TASKS = "BLOCKED_TASKS"         # Tasks blocked for too long
    SCOPE_CHANGE = "SCOPE_CHANGE"           # Goal or requirements changed
    RESOURCE_CHANGE = "RESOURCE_CHANGE"     # Team or resource availability changed
    TIMELINE_PRESSURE = "TIMELINE_PRESSURE" # Behind schedule significantly
    NEW_OPPORTUNITY = "NEW_OPPORTUNITY"     # New info suggests better approach
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE" # External dependency failed
    MANUAL_REQUEST = "MANUAL_REQUEST"       # Human requested replanning


@dataclass
class ReplanContext:
    """Context information for replanning decisions"""
    trigger: ReplanTrigger
    trigger_details: Dict[str, Any]
    current_progress: Dict[str, Any]
    constraints: Dict[str, Any]
    new_information: Dict[str, Any]
    replan_scope: str  # "full", "partial", "minimal"
    preserve_completed: bool = True


@dataclass
class ReplanResult:
    """Result of a replanning operation"""
    success: bool
    new_plan_graph: Optional[PlanGraph]
    changes_summary: Dict[str, Any]
    impact_analysis: Dict[str, Any]
    recommendations: List[str]
    approval_required: bool
    replan_reason: str
    
    
class ReplanAnalyzer:
    """Analyzes when and how to replan"""
    
    def __init__(self):
        self.failure_thresholds = {
            "max_consecutive_failures": 3,
            "max_blocked_duration_hours": 24,
            "max_schedule_delay_percent": 50,
        }
    
    def should_replan(self, plan_graph: PlanGraph, context: ExecutionContext) -> Tuple[bool, Optional[ReplanTrigger], Dict[str, Any]]:
        """Analyze if replanning is needed"""
        
        progress = plan_graph.get_progress_summary()
        
        # Check for persistent failures
        failed_tasks = plan_graph.get_failed_tasks()
        if len(failed_tasks) > self.failure_thresholds["max_consecutive_failures"]:
            return True, ReplanTrigger.TASK_FAILURE, {
                "failed_tasks": len(failed_tasks),
                "failure_rate": len(failed_tasks) / progress["total_tasks"],
                "critical_failures": [
                    task.task.id for task in failed_tasks 
                    if task.task.id in progress["critical_path"]
                ]
            }
        
        # Check for long-term blockages
        blocked_tasks = plan_graph.get_blocked_tasks()
        long_blocked = []
        now = datetime.now(timezone.utc)
        
        for task in blocked_tasks:
            if task.started_at:
                blocked_duration = (now - task.started_at).total_seconds() / 3600
                if blocked_duration > self.failure_thresholds["max_blocked_duration_hours"]:
                    long_blocked.append(task)
        
        if long_blocked:
            return True, ReplanTrigger.BLOCKED_TASKS, {
                "blocked_tasks": len(long_blocked),
                "longest_blocked_hours": max(
                    (now - task.started_at).total_seconds() / 3600 
                    for task in long_blocked if task.started_at
                ),
                "blocked_task_ids": [task.task.id for task in long_blocked]
            }
        
        # Check timeline pressure
        if self._is_behind_schedule(plan_graph, context):
            return True, ReplanTrigger.TIMELINE_PRESSURE, {
                "schedule_delay_percent": self._calculate_schedule_delay(plan_graph, context),
                "critical_path_status": self._analyze_critical_path_status(plan_graph)
            }
        
        return False, None, {}
    
    def _is_behind_schedule(self, plan_graph: PlanGraph, context: ExecutionContext) -> bool:
        """Check if execution is significantly behind schedule"""
        
        # Simple heuristic: if we're past 50% of expected timeline but < 25% complete
        # This would be enhanced with actual timeline tracking
        
        progress = plan_graph.get_progress_summary()
        completion_rate = progress["progress_percent"]
        
        # For now, use a simple rule: if < 25% complete but have many failed/blocked tasks
        failed_and_blocked = (
            progress["status_counts"].get("FAILED", 0) + 
            progress["status_counts"].get("BLOCKED", 0)
        )
        
        return completion_rate < 25 and failed_and_blocked > progress["total_tasks"] * 0.2
    
    def _calculate_schedule_delay(self, plan_graph: PlanGraph, context: ExecutionContext) -> float:
        """Calculate schedule delay percentage"""
        
        # Simplified calculation - would be enhanced with actual timeline tracking
        progress = plan_graph.get_progress_summary()
        completion_rate = progress["progress_percent"]
        
        # Estimate expected completion based on time elapsed
        # This is a placeholder for more sophisticated timeline analysis
        return max(0, 50 - completion_rate)  # Simple heuristic
    
    def _analyze_critical_path_status(self, plan_graph: PlanGraph) -> Dict[str, Any]:
        """Analyze status of critical path tasks"""
        
        critical_path = plan_graph.get_critical_path()
        critical_status = {"total": len(critical_path), "completed": 0, "failed": 0, "blocked": 0}
        
        for task_id in critical_path:
            if task_id in plan_graph.nodes:
                status = plan_graph.nodes[task_id].status
                if status == TaskStatus.COMPLETED:
                    critical_status["completed"] += 1
                elif status == TaskStatus.FAILED:
                    critical_status["failed"] += 1
                elif status == TaskStatus.BLOCKED:
                    critical_status["blocked"] += 1
        
        return critical_status


class AdaptiveReplanner:
    """Manages adaptive replanning of long-horizon initiatives"""
    
    def __init__(self, task_decomposer: Optional[TaskDecomposer] = None, planner: Optional[PlannerV3] = None):
        self.task_decomposer = task_decomposer or TaskDecomposer()
        self.planner = planner or PlannerV3()
        self.analyzer = ReplanAnalyzer()
        self.replan_history: List[Dict[str, Any]] = []
    
    def evaluate_replan_need(
        self, 
        plan_graph: PlanGraph, 
        context: ExecutionContext,
        additional_triggers: Optional[List[ReplanTrigger]] = None
    ) -> Tuple[bool, Optional[ReplanContext]]:
        """Evaluate if replanning is needed and return context"""
        
        # Check automatic triggers
        should_replan, trigger, details = self.analyzer.should_replan(plan_graph, context)
        
        # Check additional manual triggers
        if not should_replan and additional_triggers:
            should_replan = True
            trigger = additional_triggers[0]  # Use first trigger
            details = {"manual_triggers": [t.value for t in additional_triggers]}
        
        if not should_replan:
            return False, None
        
        # Ensure we have a valid trigger
        if trigger is None:
            logger.warning("Replan needed but no trigger provided, using MANUAL_REQUEST")
            trigger = ReplanTrigger.MANUAL_REQUEST
            details = details or {"reason": "Manual replan requested"}
        
        # Build replan context
        progress = plan_graph.get_progress_summary()
        
        replan_context = ReplanContext(
            trigger=trigger,
            trigger_details=details,
            current_progress=progress,
            constraints={
                "preserve_completed_tasks": True,
                "max_timeline_extension": 0.5,  # 50% extension allowed
                "resource_constraints": context.__dict__,
            },
            new_information={},
            replan_scope=self._determine_replan_scope(trigger, details, progress) if trigger else "task",
        )
        
        return True, replan_context
    
    async def replan(
        self,
        initiative: Initiative,
        current_plan: PlanGraph,
        context: ExecutionContext,
        replan_context: ReplanContext
    ) -> ReplanResult:
        """Perform adaptive replanning"""
        
        logger.info(f"Starting replan for initiative {initiative.id}, trigger: {replan_context.trigger.value}")
        
        try:
            if replan_context.replan_scope == "minimal":
                return self._minimal_replan(current_plan, replan_context)
            elif replan_context.replan_scope == "partial":
                return await self._partial_replan(initiative, current_plan, context, replan_context)
            else:  # full replan
                return await self._full_replan(initiative, current_plan, context, replan_context)
                
        except Exception as e:
            logger.error(f"Replan failed: {e}")
            return ReplanResult(
                success=False,
                new_plan_graph=None,
                changes_summary={"error": str(e)},
                impact_analysis={"replan_failed": True},
                recommendations=["Manual intervention required", "Review replan failure logs"],
                approval_required=True,
                replan_reason=f"Replan failed due to error: {str(e)}"
            )
    
    def _minimal_replan(self, current_plan: PlanGraph, replan_context: ReplanContext) -> ReplanResult:
        """Perform minimal replanning - mostly task status adjustments"""
        
        changes = []
        
        # Retry failed tasks with modified approach
        failed_tasks = current_plan.get_failed_tasks()
        for task in failed_tasks:
            # Simple retry - reset status to planned
            task.status = TaskStatus.PLANNED
            task.failure_reason = None
            task.execution_log.append(f"Reset for retry due to {replan_context.trigger.value}")
            changes.append(f"Reset failed task: {task.task.title}")
        
        # Unblock blocked tasks by removing problematic dependencies
        blocked_tasks = current_plan.get_blocked_tasks()
        for task in blocked_tasks:
            if len(task.task.dependencies) > 0:
                # Remove one dependency to unblock
                removed_dep = task.task.dependencies.pop(0)
                task.status = TaskStatus.PLANNED
                changes.append(f"Removed blocking dependency {removed_dep} from {task.task.title}")
        
        return ReplanResult(
            success=True,
            new_plan_graph=current_plan,
            changes_summary={"changes": changes, "scope": "minimal"},
            impact_analysis={"timeline_impact": "minimal", "risk_level": "low"},
            recommendations=["Monitor retry success", "Consider partial replan if issues persist"],
            approval_required=False,
            replan_reason=f"Minimal replan triggered by {replan_context.trigger.value}"
        )
    
    async def _partial_replan(
        self,
        initiative: Initiative,
        current_plan: PlanGraph,
        context: ExecutionContext,
        replan_context: ReplanContext
    ) -> ReplanResult:
        """Perform partial replanning - adjust remaining tasks"""
        
        # Preserve completed and in-progress tasks
        completed_tasks = [
            node.task for node in current_plan.nodes.values()
            if node.status in [TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS]
        ]
        
        # Identify problematic tasks to replan
        problematic_tasks = []
        for node in current_plan.nodes.values():
            if node.status in [TaskStatus.FAILED, TaskStatus.BLOCKED]:
                problematic_tasks.append(node.task)
        
        # Generate new tasks for the problematic areas
        remaining_goal = self._extract_remaining_goal(initiative, current_plan, replan_context)
        
        # Use task decomposer to generate alternative tasks
        new_decomposition = await self.task_decomposer.decompose_goal(
            goal=remaining_goal,
            context={
                "completed_tasks": [task.title for task in completed_tasks],
                "failed_tasks": [task.title for task in problematic_tasks],
                "trigger": replan_context.trigger.value,
                "repository": context.org_id,
            },
            org_id=context.org_id,
            owner=context.owner
        )
        
        # Create new plan with preserved and new tasks
        all_tasks = completed_tasks + new_decomposition.tasks
        new_plan = PlanGraph(all_tasks)
        
        # Restore status of preserved tasks
        for task in completed_tasks:
            if task.id in new_plan.nodes:
                original_node = current_plan.nodes[task.id]
                new_plan.nodes[task.id].status = original_node.status
                new_plan.nodes[task.id].started_at = original_node.started_at
                new_plan.nodes[task.id].completed_at = original_node.completed_at
                new_plan.nodes[task.id].assignee = original_node.assignee
                new_plan.nodes[task.id].execution_log = original_node.execution_log
        
        # Analyze changes
        changes_summary = {
            "preserved_tasks": len(completed_tasks),
            "new_tasks": len(new_decomposition.tasks),
            "removed_tasks": len(problematic_tasks),
            "total_tasks_before": len(current_plan.nodes),
            "total_tasks_after": len(new_plan.nodes),
        }
        
        impact_analysis = {
            "timeline_impact": "moderate",
            "risk_level": "medium",
            "estimated_additional_hours": sum(task.estimated_hours for task in new_decomposition.tasks),
            "critical_path_changed": True,
        }
        
        return ReplanResult(
            success=True,
            new_plan_graph=new_plan,
            changes_summary=changes_summary,
            impact_analysis=impact_analysis,
            recommendations=[
                "Review new task breakdown with team",
                "Update timeline estimates",
                "Consider additional resources for new tasks"
            ],
            approval_required=True,  # Partial replans need approval
            replan_reason=f"Partial replan due to {replan_context.trigger.value}"
        )
    
    async def _full_replan(
        self,
        initiative: Initiative,
        current_plan: PlanGraph,
        context: ExecutionContext,
        replan_context: ReplanContext
    ) -> ReplanResult:
        """Perform full replanning - complete task redesign"""
        
        logger.info(f"Performing full replan for initiative {initiative.id}")
        
        # Extract lessons learned from current plan
        lessons_learned = self._extract_lessons_learned(current_plan, replan_context)
        
        # Enhanced context with lessons learned
        enhanced_context = {
            "previous_attempt": True,
            "lessons_learned": lessons_learned,
            "failed_approaches": self._extract_failed_approaches(current_plan),
            "successful_approaches": self._extract_successful_approaches(current_plan),
            "trigger": replan_context.trigger.value,
            "constraints": replan_context.constraints,
            "repository": context.org_id,
        }
        
        # Generate completely new decomposition
        new_decomposition = await self.task_decomposer.decompose_goal(
            goal=initiative.goal,
            context=enhanced_context,
            org_id=context.org_id,
            owner=context.owner
        )
        
        # Create new plan graph
        new_plan = PlanGraph(new_decomposition.tasks)
        
        # Analyze impact
        old_progress = current_plan.get_progress_summary()
        
        changes_summary = {
            "complete_redesign": True,
            "old_tasks": old_progress["total_tasks"],
            "new_tasks": len(new_decomposition.tasks),
            "old_estimated_hours": old_progress["total_estimated_hours"],
            "new_estimated_hours": new_decomposition.total_estimated_hours,
            "lessons_applied": len(lessons_learned),
        }
        
        impact_analysis = {
            "timeline_impact": "significant",
            "risk_level": "high",
            "progress_reset": True,
            "estimated_timeline_weeks": new_decomposition.suggested_timeline_weeks,
            "risks": new_decomposition.risks,
            "assumptions": new_decomposition.assumptions,
        }
        
        recommendations = [
            "Full stakeholder review required",
            "Update initiative timeline and expectations",
            "Consider resource reallocation",
            "Implement enhanced monitoring for early issue detection"
        ]
        
        # Add specific recommendations based on trigger
        if replan_context.trigger == ReplanTrigger.TASK_FAILURE:
            recommendations.append("Review team skills and training needs")
        elif replan_context.trigger == ReplanTrigger.TIMELINE_PRESSURE:
            recommendations.append("Consider scope reduction or additional resources")
        
        return ReplanResult(
            success=True,
            new_plan_graph=new_plan,
            changes_summary=changes_summary,
            impact_analysis=impact_analysis,
            recommendations=recommendations,
            approval_required=True,  # Full replans always need approval
            replan_reason=f"Full replan due to {replan_context.trigger.value}: {replan_context.trigger_details}"
        )
    
    def _determine_replan_scope(
        self, 
        trigger: ReplanTrigger, 
        details: Dict[str, Any], 
        progress: Dict[str, Any]
    ) -> str:
        """Determine the appropriate scope of replanning"""
        
        # High-impact triggers usually need full replan
        if trigger in [ReplanTrigger.SCOPE_CHANGE, ReplanTrigger.RESOURCE_CHANGE]:
            return "full"
        
        # Timeline pressure with low progress needs full replan
        if trigger == ReplanTrigger.TIMELINE_PRESSURE and progress["progress_percent"] < 25:
            return "full"
        
        # Multiple failures or critical path issues need partial replan
        failure_rate = details.get("failure_rate", 0)
        if failure_rate > 0.3:  # More than 30% failure rate
            return "partial"
        
        # Critical path failures need partial replan
        if "critical_failures" in details and details["critical_failures"]:
            return "partial"
        
        # Otherwise, try minimal first
        return "minimal"
    
    def _extract_remaining_goal(
        self, 
        initiative: Initiative, 
        current_plan: PlanGraph, 
        replan_context: ReplanContext
    ) -> str:
        """Extract the remaining goal based on completed work"""
        
        completed_tasks = [
            node.task for node in current_plan.nodes.values()
            if node.status == TaskStatus.COMPLETED
        ]
        
        if not completed_tasks:
            return initiative.goal  # Nothing completed, same goal
        
        # Generate description of remaining work
        completed_work = "; ".join([task.title for task in completed_tasks])
        
        remaining_goal = f"""
        Original Goal: {initiative.goal}
        
        Completed Work: {completed_work}
        
        Remaining Work: Complete the original goal considering the work already done.
        Avoid duplicating completed tasks and build upon existing progress.
        
        Replan Trigger: {replan_context.trigger.value}
        Issues to Address: {json.dumps(replan_context.trigger_details, indent=2)}
        """
        
        return remaining_goal.strip()
    
    def _extract_lessons_learned(self, current_plan: PlanGraph, replan_context: ReplanContext) -> List[str]:
        """Extract lessons learned from the current plan execution"""
        
        lessons = []
        
        # Analyze failed tasks
        failed_tasks = current_plan.get_failed_tasks()
        if failed_tasks:
            failure_patterns = {}
            for task in failed_tasks:
                task_type = task.task.task_type.value
                failure_patterns[task_type] = failure_patterns.get(task_type, 0) + 1
            
            for task_type, count in failure_patterns.items():
                lessons.append(f"{task_type} tasks are challenging (failed {count} times)")
        
        # Analyze blocked tasks
        blocked_tasks = current_plan.get_blocked_tasks()
        if blocked_tasks:
            lessons.append(f"Dependency management needs improvement ({len(blocked_tasks)} tasks blocked)")
        
        # Analyze execution history for patterns
        execution_history = current_plan.execution_history
        if execution_history:
            # Simple pattern detection
            events = [event["event_type"] for event in execution_history]
            if events.count("failed") > events.count("completed"):
                lessons.append("Execution success rate is low, consider smaller tasks")
        
        # Trigger-specific lessons
        if replan_context.trigger == ReplanTrigger.TIMELINE_PRESSURE:
            lessons.append("Time estimation was optimistic, add more buffer")
        elif replan_context.trigger == ReplanTrigger.BLOCKED_TASKS:
            lessons.append("Dependencies are more complex than anticipated")
        
        return lessons
    
    def _extract_failed_approaches(self, current_plan: PlanGraph) -> List[str]:
        """Extract approaches that failed"""
        
        failed_approaches = []
        failed_tasks = current_plan.get_failed_tasks()
        
        for task in failed_tasks:
            if task.failure_reason:
                failed_approaches.append(f"Approach '{task.task.title}' failed: {task.failure_reason}")
        
        return failed_approaches
    
    def _extract_successful_approaches(self, current_plan: PlanGraph) -> List[str]:
        """Extract approaches that succeeded"""
        
        successful_approaches = []
        completed_tasks = [
            node for node in current_plan.nodes.values()
            if node.status == TaskStatus.COMPLETED
        ]
        
        for task in completed_tasks:
            execution_time = None
            if task.started_at and task.completed_at:
                execution_time = (task.completed_at - task.started_at).total_seconds() / 3600
            
            approach = f"Successfully completed '{task.task.title}'"
            if execution_time:
                approach += f" in {execution_time:.1f} hours"
            
            successful_approaches.append(approach)
        
        return successful_approaches
    
    def record_replan(self, replan_result: ReplanResult, initiative_id: str) -> None:
        """Record replanning history for analysis"""
        
        replan_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "initiative_id": initiative_id,
            "success": replan_result.success,
            "reason": replan_result.replan_reason,
            "changes": replan_result.changes_summary,
            "impact": replan_result.impact_analysis,
            "approval_required": replan_result.approval_required,
        }
        
        self.replan_history.append(replan_record)
        logger.info(f"Recorded replan for initiative {initiative_id}")
    
    def get_replan_analytics(self, initiative_id: Optional[str] = None) -> Dict[str, Any]:
        """Get analytics about replanning patterns"""
        
        relevant_replans = [
            r for r in self.replan_history
            if not initiative_id or r["initiative_id"] == initiative_id
        ]
        
        if not relevant_replans:
            return {"total_replans": 0}
        
        # Calculate statistics
        total_replans = len(relevant_replans)
        successful_replans = sum(1 for r in relevant_replans if r["success"])
        
        # Most common reasons
        reasons = [r["reason"] for r in relevant_replans]
        reason_counts = {}
        for reason in reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        
        return {
            "total_replans": total_replans,
            "success_rate": successful_replans / total_replans if total_replans > 0 else 0,
            "common_reasons": sorted(reason_counts.items(), key=lambda x: x[1], reverse=True),
            "replans_requiring_approval": sum(1 for r in relevant_replans if r["approval_required"]),
        }