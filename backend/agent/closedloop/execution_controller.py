"""
Phase 5.0 — Execution Controller (End-to-End Autonomous Operation)

Integrates with existing Phases 4.3-4.9 execution systems to perform autonomous actions.
Handles action queuing, parallel execution, retries, timeouts, and rollback procedures.
Core principle: Execute planned actions safely with proper monitoring and error handling.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor
import traceback

from backend.agent.closedloop.auto_planner import ExecutionPlan, PlannedAction, ActionType, SafetyLevel
from backend.agent.closedloop.context_resolver import ResolvedContext
from backend.autonomous.enhanced_coding_engine import EnhancedAutonomousCodingEngine
from backend.agent.planning.long_horizon_orchestrator import LongHorizonOrchestrator
from backend.core.ai.llm_service import LLMService
from backend.core.memory_system.vector_store import VectorStore
from backend.services.slack_service import _get_client as _get_slack_client
from backend.services.jira import JiraService
from backend.services import connectors as connectors_service
from backend.services.github_write import GitHubWriteService


logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Status of action execution"""
    PENDING = "pending"           # Action queued but not started
    RUNNING = "running"           # Action currently executing
    COMPLETED = "completed"       # Action completed successfully
    FAILED = "failed"            # Action failed permanently
    CANCELLED = "cancelled"       # Action was cancelled
    TIMEOUT = "timeout"          # Action timed out
    RETRYING = "retrying"        # Action failed, retrying
    WAITING_APPROVAL = "waiting_approval"  # Waiting for human approval
    BLOCKED = "blocked"          # Action blocked by prerequisites or safety checks
    PENDING_APPROVAL = "waiting_approval"  # Backwards compatibility alias


@dataclass
class ExecutionResult:
    """Result of executing an action"""
    action: PlannedAction
    status: ExecutionStatus
    
    # Execution details
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Results
    success: bool = False
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None

    # Compatibility fields for legacy callers
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    # Execution metadata
    retry_count: int = 0
    execution_logs: List[str] = field(default_factory=list)
    safety_checks_passed: bool = True
    rollback_performed: bool = False
    rollback_available: bool = False
    
    # Quality metrics
    confidence_post_execution: Optional[float] = None
    verification_passed: bool = False
    verification_results: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionContext:
    """Context for executing an action"""
    action: PlannedAction
    resolved_context: Any
    plan: Optional[ExecutionPlan]
    
    # Execution state
    executor_id: str
    execution_id: str
    started_at: datetime
    
    # Dependencies and prerequisites
    dependent_actions: List[str] = field(default_factory=list)
    prerequisite_results: Dict[str, ExecutionResult] = field(default_factory=dict)
    
    # Safety and monitoring
    safety_override: bool = False
    human_approved: bool = False
    monitoring_active: bool = True
    
    # Execution environment
    workspace_path: Optional[str] = None
    environment_vars: Dict[str, str] = field(default_factory=dict)
    resource_limits: Dict[str, Any] = field(default_factory=dict)


class ExecutionController:
    """
    Orchestrates the execution of planned actions with safety, monitoring, and integration
    
    Key responsibilities:
    1. Execute planned actions using appropriate Phase 4.x systems
    2. Handle parallel execution, dependencies, and sequencing
    3. Implement retry logic, timeouts, and error handling
    4. Perform safety checks and rollback procedures
    5. Monitor execution progress and report status
    6. Integrate with existing autonomous systems (Enhanced Coding Engine, etc.)
    """
    
    def __init__(self, db_session, workspace_path: Optional[str] = None):
        self.db = db_session
        self.workspace_path = workspace_path
        
        # Execution state
        self.active_executions: Dict[str, ExecutionContext] = {}
        self.execution_history: Dict[str, ExecutionResult] = {}
        self.execution_queue: asyncio.Queue = asyncio.Queue()
        
        # Integration with existing systems
        self.coding_engine: Optional[EnhancedAutonomousCodingEngine] = None
        self._llm_service: Optional[LLMService] = None
        self._vector_store: Optional[VectorStore] = None
        self.orchestrator = LongHorizonOrchestrator(db_session)
        self.slack_client = _get_slack_client()
        
        # Execution configuration
        self.max_concurrent_executions = 5
        self.default_timeout_minutes = 60
        self.max_retries_default = 2
        self.safety_check_timeout = 30
        
        # Thread pool for I/O bound operations
        self.thread_pool = ThreadPoolExecutor(max_workers=10)
        
        # Action executors - map action types to execution functions
        self.action_executors: Dict[ActionType, Callable] = {
            # Jira actions
            ActionType.ASSIGN_ISSUE: self._execute_assign_issue,
            ActionType.UPDATE_STATUS: self._execute_update_status,
            ActionType.ADD_COMMENT: self._execute_add_comment,
            ActionType.CREATE_SUBTASK: self._execute_create_subtask,
            ActionType.LINK_ISSUES: self._execute_link_issues,
            
            # GitHub actions
            ActionType.CREATE_PR: self._execute_create_pr,
            ActionType.REVIEW_PR: self._execute_review_pr,
            ActionType.MERGE_PR: self._execute_merge_pr,
            ActionType.CREATE_ISSUE: self._execute_create_github_issue,
            
            # Code actions
            ActionType.FIX_BUG: self._execute_fix_bug,
            ActionType.IMPLEMENT_FEATURE: self._execute_implement_feature,
            ActionType.REFACTOR_CODE: self._execute_refactor_code,
            ActionType.UPDATE_DOCUMENTATION: self._execute_update_documentation,
            ActionType.WRITE_TESTS: self._execute_write_tests,
            
            # Communication actions
            ActionType.NOTIFY_TEAM: self._execute_notify_team,
            ActionType.ESCALATE_ISSUE: self._execute_escalate_issue,
            ActionType.REQUEST_CLARIFICATION: self._execute_request_clarification,
            
            # System actions
            ActionType.RESTART_SERVICE: self._execute_restart_service,
            ActionType.ROLLBACK_DEPLOYMENT: self._execute_rollback_deployment,
            ActionType.SCALE_RESOURCES: self._execute_scale_resources,
            
            # Meta actions
            ActionType.GATHER_MORE_CONTEXT: self._execute_gather_context,
            ActionType.WAIT_FOR_HUMAN: self._execute_wait_for_human,
            ActionType.NO_ACTION_NEEDED: self._execute_no_action,
        }
        
        # Safety checkers
        self.safety_checkers: Dict[ActionType, Callable] = {
            ActionType.FIX_BUG: self._safety_check_code_changes,
            ActionType.IMPLEMENT_FEATURE: self._safety_check_code_changes,
            ActionType.MERGE_PR: self._safety_check_merge,
            ActionType.ROLLBACK_DEPLOYMENT: self._safety_check_rollback,
            ActionType.RESTART_SERVICE: self._safety_check_service_restart,
        }
        
        # Rollback procedures
        self.rollback_procedures: Dict[ActionType, Callable] = {
            ActionType.FIX_BUG: self._rollback_code_changes,
            ActionType.IMPLEMENT_FEATURE: self._rollback_code_changes,
            ActionType.MERGE_PR: self._rollback_merge,
            ActionType.UPDATE_STATUS: self._rollback_status_change,
            ActionType.ADD_COMMENT: self._rollback_comment,
        }

    def _ensure_coding_engine(self, workspace_path: Optional[str]) -> EnhancedAutonomousCodingEngine:
        if self.coding_engine:
            return self.coding_engine
        if not workspace_path:
            raise ValueError("workspace_path is required for autonomous code execution")
        if not self._llm_service:
            self._llm_service = LLMService()
        if not self._vector_store:
            self._vector_store = VectorStore()
        self.coding_engine = EnhancedAutonomousCodingEngine(
            llm_service=self._llm_service,
            vector_store=self._vector_store,
            workspace_path=workspace_path,
            db_session=self.db,
        )
        return self.coding_engine

    def _resolve_actor_context(self, exec_context: ExecutionContext) -> Tuple[Optional[str], Optional[str]]:
        action = exec_context.action
        resolved = exec_context.resolved_context
        user_id = action.parameters.get("user_id") or getattr(resolved, "user_id", None)
        org_id = action.parameters.get("org_id") or getattr(resolved, "org_id", None)
        return (str(user_id) if user_id else None, str(org_id) if org_id else None)

    def _get_github_write_service(self, exec_context: ExecutionContext) -> GitHubWriteService:
        user_id, org_id = self._resolve_actor_context(exec_context)
        connector = connectors_service.get_connector_for_context(
            self.db,
            user_id=user_id,
            org_id=org_id,
            provider="github",
        )
        if not connector:
            raise RuntimeError("GitHub connector not configured for this context")
        secrets = connector.get("secrets") or {}
        token = secrets.get("token") or secrets.get("access_token")
        if not token:
            raise RuntimeError("GitHub connector token missing")
        return GitHubWriteService(token=token)

    @staticmethod
    def _parse_repo_target(target: Optional[str]) -> Tuple[Optional[str], Optional[int]]:
        if not target:
            return None, None
        if "#" in target:
            repo, pr_part = target.split("#", 1)
            try:
                return repo, int(pr_part)
            except ValueError:
                return repo, None
        return target, None
    
    async def execute_plan(self, plan: ExecutionPlan) -> List[ExecutionResult]:
        """
        Execute a complete execution plan
        
        This is the main entry point for plan execution
        """
        
        logger.info(f"Starting execution of plan {plan.plan_id} with {len(plan.primary_actions)} actions")
        
        results = []
        
        try:
            # Check if human approval is needed
            if plan.human_approval_needed:
                approval_granted = await self._request_human_approval(plan)
                if not approval_granted:
                    logger.info(f"Human approval denied for plan {plan.plan_id}")
                    return [ExecutionResult(
                        action=action,
                        status=ExecutionStatus.CANCELLED,
                        error_message="Human approval denied"
                    ) for action in plan.primary_actions]
            
            # Check execution window
            if plan.execution_window:
                if not self._is_within_execution_window(plan.execution_window):
                    logger.info(f"Plan {plan.plan_id} outside execution window, queuing for later")
                    await self._schedule_for_execution_window(plan)
                    return results
            
            # Check prerequisites
            if not plan.prerequisites_met:
                logger.warning(f"Prerequisites not met for plan {plan.plan_id}")
                # Try to resolve prerequisites
                prereq_met = await self._resolve_prerequisites(plan)
                if not prereq_met:
                    return [ExecutionResult(
                        action=action,
                        status=ExecutionStatus.BLOCKED,
                        error_message="Prerequisites not satisfied"
                    ) for action in plan.primary_actions]
            
            # Execute primary actions
            primary_results = await self._execute_actions_parallel(
                plan.primary_actions,
                plan.context,
                plan
            )
            results.extend(primary_results)
            
            # Check if primary actions succeeded
            primary_success = all(r.success for r in primary_results)
            
            if not primary_success:
                logger.warning(f"Primary actions failed for plan {plan.plan_id}, executing contingencies")
                
                # Execute contingency actions
                contingency_results = await self._execute_actions_parallel(
                    plan.contingency_actions,
                    plan.context,
                    plan
                )
                results.extend(contingency_results)
            
            # Start monitoring actions (don't wait for them)
            if plan.monitoring_actions:
                asyncio.create_task(self._execute_monitoring_actions(
                    plan.monitoring_actions,
                    plan.context,
                    plan
                ))
            
            logger.info(f"Completed execution of plan {plan.plan_id}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to execute plan {plan.plan_id}: {e}")
            logger.error(traceback.format_exc())
            
            return [ExecutionResult(
                action=action,
                status=ExecutionStatus.FAILED,
                error_message=f"Plan execution failed: {str(e)}",
                error_traceback=traceback.format_exc()
            ) for action in plan.primary_actions]
    
    async def execute_action(
        self,
        action: PlannedAction,
        context: Any,
        plan: Optional[ExecutionPlan] = None,
    ) -> ExecutionResult:
        """
        Execute a single planned action
        
        This handles the complete lifecycle of action execution
        """
        
        execution_id = f"exec_{action.action_type.value}_{int(datetime.now().timestamp())}"
        
        logger.info(f"Starting execution of action {action.action_type.value} (ID: {execution_id})")
        
        # Create execution context
        exec_context = ExecutionContext(
            action=action,
            resolved_context=context,
            plan=plan,
            executor_id="autonomous_controller",
            execution_id=execution_id,
            started_at=datetime.now(timezone.utc),
            workspace_path=self.workspace_path,
        )
        
        # Track active execution
        self.active_executions[execution_id] = exec_context
        
        # Create execution result
        result = ExecutionResult(
            action=action,
            status=ExecutionStatus.PENDING,
            started_at=datetime.now(timezone.utc)
        )
        
        try:
            # Perform pre-execution safety checks
            if not await self._perform_safety_checks(exec_context, result):
                result.status = ExecutionStatus.FAILED
                result.error_message = "Safety checks failed"
                result.safety_checks_passed = False
                return result
            
            # Check for human approval if required
            if action.human_approval_required and not exec_context.human_approved:
                approval_granted = await self._request_action_approval(action, context)
                if not approval_granted:
                    result.status = ExecutionStatus.CANCELLED
                    result.error_message = "Human approval denied"
                    return result
                exec_context.human_approved = True
            
            # Execute with retries
            max_retries = action.max_retries if action.max_retries >= 0 else self.max_retries_default
            
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    result.status = ExecutionStatus.RETRYING
                    result.retry_count = attempt
                    logger.info(f"Retrying action {action.action_type.value}, attempt {attempt + 1}/{max_retries + 1}")
                
                result.status = ExecutionStatus.RUNNING
                
                try:
                    # Execute the action
                    execution_result = await self._execute_single_action(exec_context, result)
                    
                    if execution_result:
                        result.status = ExecutionStatus.COMPLETED
                        result.success = True
                        result.result_data = execution_result
                        break
                    else:
                        # Execution returned False/None indicating failure
                        if attempt < max_retries:
                            continue  # Retry
                        else:
                            result.status = ExecutionStatus.FAILED
                            result.error_message = "Action execution returned failure"
                
                except asyncio.TimeoutError:
                    result.status = ExecutionStatus.TIMEOUT
                    result.error_message = f"Action timed out after {action.timeout_minutes} minutes"
                    if attempt < max_retries:
                        continue  # Retry
                    else:
                        break
                
                except Exception as e:
                    error_msg = str(e)
                    result.error_message = error_msg
                    result.error_traceback = traceback.format_exc()
                    logger.error(f"Action execution failed: {error_msg}")
                    
                    if attempt < max_retries:
                        continue  # Retry
                    else:
                        result.status = ExecutionStatus.FAILED
                        break
            
            # Perform rollback if action failed and rollback is defined
            if not result.success and action.rollback_plan:
                logger.info(f"Performing rollback for failed action {action.action_type.value}")
                try:
                    await self._perform_rollback(exec_context, result)
                    result.rollback_performed = True
                except Exception as e:
                    logger.error(f"Rollback failed: {e}")
                    result.execution_logs.append(f"Rollback failed: {str(e)}")
        
        finally:
            # Clean up
            result.completed_at = datetime.now(timezone.utc)
            if result.started_at:
                result.duration_seconds = (result.completed_at - result.started_at).total_seconds()
            
            # Remove from active executions
            self.active_executions.pop(execution_id, None)
            
            # Store in history
            self.execution_history[execution_id] = result
            
            logger.info(f"Completed execution of action {action.action_type.value} with status {result.status.value}")
        
        return result
    
    async def _execute_actions_parallel(
        self, 
        actions: List[PlannedAction], 
        context: ResolvedContext, 
        plan: ExecutionPlan
    ) -> List[ExecutionResult]:
        """Execute multiple actions in parallel with concurrency control"""
        
        if not actions:
            return []
        
        # Group actions by dependencies
        independent_actions = [a for a in actions if not a.prerequisites]
        dependent_actions = [a for a in actions if a.prerequisites]
        
        results = []
        
        # Execute independent actions in parallel
        if independent_actions:
            semaphore = asyncio.Semaphore(self.max_concurrent_executions)
            
            async def execute_with_semaphore(action):
                async with semaphore:
                    return await self.execute_action(action, context, plan)
            
            tasks = [execute_with_semaphore(action) for action in independent_actions]
            independent_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions
            for i, result in enumerate(independent_results):
                if isinstance(result, Exception):
                    results.append(ExecutionResult(
                        action=independent_actions[i],
                        status=ExecutionStatus.FAILED,
                        error_message=str(result),
                        error_traceback=traceback.format_exc()
                    ))
                else:
                    results.append(result)
        
        # Execute dependent actions sequentially (simplified dependency resolution)
        for action in dependent_actions:
            result = await self.execute_action(action, context, plan)
            results.append(result)
        
        return results
    
    async def _execute_monitoring_actions(
        self,
        actions: List[PlannedAction],
        context: ResolvedContext,
        plan: ExecutionPlan
    ):
        """Execute monitoring actions in the background"""
        
        try:
            for action in actions:
                # Execute monitoring action
                await self.execute_action(action, context, plan)
                
                # Wait before next monitoring cycle
                if action.parameters.get("check_frequency") == "every_30_minutes":
                    await asyncio.sleep(30 * 60)  # 30 minutes
                elif action.parameters.get("check_frequency") == "every_15_minutes":
                    await asyncio.sleep(15 * 60)  # 15 minutes
                else:
                    await asyncio.sleep(plan.monitoring_frequency * 60)  # Default frequency
                
        except Exception as e:
            logger.error(f"Monitoring actions failed: {e}")
    
    async def _execute_single_action(self, exec_context: ExecutionContext, result: ExecutionResult) -> Any:
        """Execute a single action using the appropriate executor"""
        
        action = exec_context.action
        executor = self.action_executors.get(action.action_type)
        
        if not executor:
            raise NotImplementedError(f"No executor found for action type {action.action_type}")
        
        # Set timeout
        timeout = action.timeout_minutes * 60 if action.timeout_minutes > 0 else self.default_timeout_minutes * 60
        
        try:
            # Execute with timeout
            return await asyncio.wait_for(
                executor(exec_context, result),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Action {action.action_type.value} timed out after {timeout} seconds")
            raise
    
    # Action Executors
    
    async def _execute_assign_issue(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute issue assignment"""
        
        action = exec_context.action
        issue_key = action.target
        assignee = action.parameters.get("assignee")
        
        logger.info(f"Assigning issue {issue_key} to {assignee}")
        
        try:
            assignee_account_id = action.parameters.get("assignee_account_id")
            await JiraService.assign_issue(
                self.db,
                issue_key=issue_key,
                assignee_account_id=assignee_account_id,
                assignee_name=assignee if not assignee_account_id else None,
            )
            result.execution_logs.append(f"Successfully assigned {issue_key} to {assignee}")
            return {"issue_key": issue_key, "assignee": assignee, "assigned": True}
                
        except Exception as e:
            logger.error(f"Failed to assign issue {issue_key}: {e}")
            raise
    
    async def _execute_update_status(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute status update"""
        
        action = exec_context.action
        issue_key = action.target
        transition_id = action.parameters.get("transition_id") or action.parameters.get("status")
        
        logger.info(f"Updating status of {issue_key} to {transition_id}")
        
        try:
            if not transition_id:
                raise ValueError("transition_id or status is required to update Jira status")
            await JiraService.transition_issue(self.db, issue_key, transition_id)
            result.execution_logs.append(f"Successfully updated {issue_key} status to {transition_id}")
            return {"issue_key": issue_key, "new_status": transition_id, "updated": True}
                
        except Exception as e:
            logger.error(f"Failed to update status of {issue_key}: {e}")
            raise
    
    async def _execute_add_comment(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute comment addition"""
        
        action = exec_context.action
        target = action.target
        comment_text = action.parameters.get("comment", "")
        
        logger.info(f"Adding comment to {target}")
        
        try:
            # Handle different target types
            if target.startswith("slack:"):
                # Slack comment/message
                channel = action.parameters.get("channel")
                if not channel:
                    target_parts = target.split(":")
                    if len(target_parts) >= 2:
                        channel = target_parts[1]
                if not channel:
                    raise ValueError("Slack channel is required for Slack comments")
                thread_ts = action.parameters.get("thread_ts")
                if not self.slack_client:
                    raise RuntimeError("Slack client is not configured")
                message_result = await self.slack_client.post_message(
                    channel=channel,
                    text=comment_text,
                    thread_ts=thread_ts,
                )
                return {
                    "target": target,
                    "message_sent": True,
                    "message_ts": message_result.get("ts"),
                }
            
            else:
                # Jira comment
                await JiraService.add_comment(self.db, target, comment_text)
                result.execution_logs.append(f"Successfully added comment to {target}")
                return {"target": target, "comment_added": True}
                    
        except Exception as e:
            logger.error(f"Failed to add comment to {target}: {e}")
            raise
    
    async def _execute_create_subtask(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute subtask creation"""
        
        action = exec_context.action
        parent_key = action.target
        subtask_title = action.parameters.get("title", "Autonomous Subtask")
        subtask_description = action.parameters.get("description", "")
        
        logger.info(f"Creating subtask for {parent_key}")
        
        try:
            subtask_result = await JiraService.create_subtask(
                self.db,
                parent_key=parent_key,
                summary=subtask_title,
                description=subtask_description,
            )
            subtask_key = subtask_result.get("key") or subtask_result.get("id")
            result.execution_logs.append(f"Successfully created subtask {subtask_key or 'unknown'}")
            return {"parent_key": parent_key, "subtask_key": subtask_key, "created": True}
                
        except Exception as e:
            logger.error(f"Failed to create subtask for {parent_key}: {e}")
            raise
    
    async def _execute_link_issues(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute issue linking"""
        
        action = exec_context.action
        source_key = action.target
        target_issues = action.parameters.get("target_issues", [])
        link_type = action.parameters.get("link_type", "relates to")
        
        logger.info(f"Linking {source_key} to {len(target_issues)} issues")
        
        try:
            linked_count = 0
            
            for target_key in target_issues:
                await JiraService.link_issues(self.db, source_key, target_key, link_type)
                linked_count += 1
            
            result.execution_logs.append(f"Successfully linked {linked_count}/{len(target_issues)} issues")
            return {"source_key": source_key, "linked_count": linked_count, "total_targets": len(target_issues)}
            
        except Exception as e:
            logger.error(f"Failed to link issues for {source_key}: {e}")
            raise
    
    async def _execute_implement_feature(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute feature implementation using Enhanced Coding Engine"""
        
        action = exec_context.action
        issue_key = action.parameters.get("issue_key") or action.target
        
        logger.info(f"Implementing feature for {issue_key}")
        
        try:
            engine = self._ensure_coding_engine(exec_context.workspace_path)
            task = await engine.create_task_from_jira(issue_key, user_context={})
            presentation = await engine.present_task_to_user(task.id)
            result.execution_logs.append(f"Prepared implementation plan for {issue_key}")
            return {
                "issue_key": issue_key,
                "task_id": task.id,
                "presentation": presentation,
                "requires_approval": True,
            }
                
        except Exception as e:
            logger.error(f"Failed to implement feature for {issue_key}: {e}")
            raise
    
    async def _execute_fix_bug(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute bug fix using Enhanced Coding Engine"""
        
        action = exec_context.action
        issue_key = action.parameters.get("issue_key") or action.target
        
        logger.info(f"Fixing bug for {issue_key}")
        
        try:
            engine = self._ensure_coding_engine(exec_context.workspace_path)
            task = await engine.create_task_from_jira(issue_key, user_context={})
            presentation = await engine.present_task_to_user(task.id)
            result.execution_logs.append(f"Prepared bug fix plan for {issue_key}")
            return {
                "issue_key": issue_key,
                "task_id": task.id,
                "presentation": presentation,
                "requires_approval": True,
            }
                
        except Exception as e:
            logger.error(f"Failed to fix bug for {issue_key}: {e}")
            raise
    
    async def _execute_review_pr(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute PR review"""
        
        action = exec_context.action
        pr_target = action.target  # Format: "repo#number"
        
        logger.info(f"Reviewing PR {pr_target}")
        
        try:
            # Parse PR target
            repo, pr_number = pr_target.split("#")
            
            # Perform automated code review
            review_result = await self._perform_automated_pr_review(repo, pr_number, action.parameters)
            
            result.execution_logs.append(f"Successfully reviewed PR {pr_target}")
            
            return {
                "pr_target": pr_target,
                "review_completed": True,
                "review_comments": review_result.get("comments", []),
                "approval_status": review_result.get("status", "commented")
            }
            
        except Exception as e:
            logger.error(f"Failed to review PR {pr_target}: {e}")
            raise
    
    async def _execute_notify_team(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute team notification"""
        
        action = exec_context.action
        message = action.parameters.get("response", action.parameters.get("message", ""))
        channel = action.parameters.get("channel", action.target)
        
        logger.info(f"Sending notification to {channel}")
        
        try:
            # Send Slack notification
            if not self.slack_client:
                raise RuntimeError("Slack client is not configured")
            message_result = await self.slack_client.post_message(
                channel=channel,
                text=message,
                thread_ts=action.parameters.get("thread_ts"),
            )
            
            result.execution_logs.append(f"Successfully sent notification to {channel}")
            
            return {
                "channel": channel,
                "message_sent": True,
                "message_ts": message_result.get("ts")
            }
            
        except Exception as e:
            logger.error(f"Failed to send notification to {channel}: {e}")
            raise
    
    async def _execute_escalate_issue(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute issue escalation"""
        
        action = exec_context.action
        target = action.target
        escalation_type = action.parameters.get("escalation_type", "general")
        
        logger.info(f"Escalating {target} ({escalation_type})")
        
        try:
            # Send escalation notifications
            notifications_sent = []
            
            # Notify recipients
            for recipient in action.notification_recipients:
                try:
                    # Would send email, Slack, or other notification
                    notification_sent = await self._send_escalation_notification(
                        recipient, target, escalation_type, action.parameters
                    )
                    notifications_sent.append({
                        "recipient": recipient,
                        "sent": notification_sent
                    })
                except Exception as e:
                    logger.error(f"Failed to notify {recipient}: {e}")
                    notifications_sent.append({
                        "recipient": recipient,
                        "sent": False,
                        "error": str(e)
                    })
            
            result.execution_logs.append(f"Escalation sent to {len(notifications_sent)} recipients")
            
            return {
                "target": target,
                "escalation_type": escalation_type,
                "notifications_sent": notifications_sent,
                "escalated": True
            }
            
        except Exception as e:
            logger.error(f"Failed to escalate {target}: {e}")
            raise
    
    async def _execute_gather_context(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute context gathering"""
        
        action = exec_context.action
        target = action.target
        context_types = action.parameters.get("gather_types", ["all"])
        
        logger.info(f"Gathering additional context for {target}")
        
        try:
            # This would integrate with the ContextResolver to gather more information
            additional_context = {}
            
            for context_type in context_types:
                if context_type == "related_issues":
                    # Find more related issues
                    related_issues = await self._find_additional_related_issues(target)
                    additional_context["related_issues"] = related_issues
                
                elif context_type == "code_examples":
                    # Find code examples
                    code_examples = await self._find_code_examples(target)
                    additional_context["code_examples"] = code_examples
                
                elif context_type == "test_cases":
                    # Find test cases
                    test_cases = await self._find_test_cases(target)
                    additional_context["test_cases"] = test_cases
            
            result.execution_logs.append(f"Successfully gathered additional context for {target}")
            
            return {
                "target": target,
                "context_gathered": True,
                "additional_context": additional_context,
                "context_types": context_types
            }
            
        except Exception as e:
            logger.error(f"Failed to gather context for {target}: {e}")
            raise
    
    async def _execute_wait_for_human(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute wait for human action (essentially a no-op with notification)"""
        
        action = exec_context.action
        wait_reason = action.parameters.get("wait_reason", "human_intervention_needed")
        
        logger.info(f"Waiting for human intervention: {wait_reason}")
        
        try:
            # Send notification about waiting
            if action.parameters.get("notify_team"):
                for recipient in action.notification_recipients:
                    await self._send_wait_notification(recipient, action.target, wait_reason)
            
            result.execution_logs.append("Notified team about waiting for human intervention")
            
            return {
                "target": action.target,
                "wait_reason": wait_reason,
                "human_notified": True,
                "waiting": True
            }
            
        except Exception as e:
            logger.error(f"Failed to notify about waiting: {e}")
            raise
    
    async def _execute_no_action(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute no-action (placeholder)"""
        
        logger.info("No action needed")
        
        return {
            "action_taken": "none",
            "reason": "no_action_needed"
        }
    
    async def _execute_create_pr(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute PR creation via GitHub connector"""
        action = exec_context.action
        repo_full_name = (
            action.parameters.get("repo_full_name")
            or action.parameters.get("repo")
            or self._parse_repo_target(action.target)[0]
        )
        base = (
            action.parameters.get("base")
            or action.parameters.get("base_branch")
            or "main"
        )
        head = action.parameters.get("head") or action.parameters.get("head_branch")
        title = (
            action.parameters.get("title")
            or action.parameters.get("summary")
            or action.description
            or "Automated PR"
        )
        body = (
            action.parameters.get("body")
            or action.parameters.get("description")
            or action.reasoning
            or ""
        )
        if not repo_full_name or not head:
            raise ValueError("repo_full_name and head branch are required for PR creation")

        ticket_key = action.parameters.get("ticket_key") or action.parameters.get("issue_key")
        draft = bool(action.parameters.get("draft", True))
        dry_run = bool(action.parameters.get("dry_run", False))

        logger.info(
            "Creating PR repo=%s base=%s head=%s draft=%s",
            repo_full_name,
            base,
            head,
            draft,
        )

        svc = self._get_github_write_service(exec_context)
        pr_result = await svc.draft_pr(
            repo_full_name=repo_full_name,
            base=base,
            head=head,
            title=title,
            body=body,
            ticket_key=ticket_key,
            draft=draft,
            dry_run=dry_run,
        )
        result.execution_logs.append(f"GitHub PR request executed for {repo_full_name}")
        return {
            "repo": repo_full_name,
            "base": base,
            "head": head,
            "draft": draft,
            "dry_run": dry_run,
            **pr_result,
        }
    
    async def _execute_merge_pr(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute PR merge via GitHub connector"""
        action = exec_context.action
        repo_full_name, pr_number = self._parse_repo_target(action.target)
        if not repo_full_name:
            repo_full_name = action.parameters.get("repo_full_name") or action.parameters.get("repo")
        if not pr_number:
            pr_number_raw = action.parameters.get("pr_number") or action.parameters.get("number")
            if pr_number_raw is not None:
                pr_number = int(pr_number_raw)

        if not repo_full_name or not pr_number:
            raise ValueError("repo_full_name and pr_number are required for merge")

        merge_method = action.parameters.get("merge_method") or "merge"
        commit_title = action.parameters.get("commit_title")
        commit_message = action.parameters.get("commit_message")
        dry_run = bool(action.parameters.get("dry_run", False))

        logger.info(
            "Merging PR repo=%s pr_number=%s method=%s",
            repo_full_name,
            pr_number,
            merge_method,
        )

        svc = self._get_github_write_service(exec_context)
        merge_result = await svc.merge_pr(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            merge_method=merge_method,
            commit_title=commit_title,
            commit_message=commit_message,
            dry_run=dry_run,
        )
        result.execution_logs.append(f"GitHub PR merge executed for {repo_full_name}#{pr_number}")
        return {
            "repo": repo_full_name,
            "pr_number": pr_number,
            "merge_method": merge_method,
            "dry_run": dry_run,
            **merge_result,
        }
    
    async def _execute_create_github_issue(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute GitHub issue creation via connector"""
        action = exec_context.action
        repo_full_name = (
            action.parameters.get("repo_full_name")
            or action.parameters.get("repo")
            or self._parse_repo_target(action.target)[0]
        )
        title = (
            action.parameters.get("title")
            or action.description
            or action.parameters.get("summary")
            or action.target
        )
        body = (
            action.parameters.get("body")
            or action.parameters.get("description")
            or action.reasoning
            or ""
        )
        if not repo_full_name or not title:
            raise ValueError("repo_full_name and title are required for issue creation")

        labels = action.parameters.get("labels")
        assignees = action.parameters.get("assignees")
        ticket_key = action.parameters.get("ticket_key") or action.parameters.get("issue_key")
        dry_run = bool(action.parameters.get("dry_run", False))

        logger.info("Creating GitHub issue repo=%s title=%s", repo_full_name, title)

        svc = self._get_github_write_service(exec_context)
        issue_result = await svc.create_issue(
            repo_full_name=repo_full_name,
            title=title,
            body=body,
            labels=labels,
            assignees=assignees,
            ticket_key=ticket_key,
            dry_run=dry_run,
        )
        result.execution_logs.append(f"GitHub issue request executed for {repo_full_name}")
        return {
            "repo": repo_full_name,
            "title": title,
            "dry_run": dry_run,
            **issue_result,
        }
    
    async def _execute_refactor_code(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute code refactoring"""
        # Would integrate with Enhanced Coding Engine
        logger.info("Refactoring code (placeholder)")
        return {"code_refactored": True}
    
    async def _execute_update_documentation(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute documentation update"""
        # Would integrate with documentation systems
        logger.info("Updating documentation (placeholder)")
        return {"documentation_updated": True}
    
    async def _execute_write_tests(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute test writing"""
        # Would integrate with Enhanced Coding Engine
        logger.info("Writing tests (placeholder)")
        return {"tests_written": True}
    
    async def _execute_request_clarification(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute clarification request"""
        # Would add comment or send message asking for clarification
        logger.info("Requesting clarification (placeholder)")
        return {"clarification_requested": True}
    
    async def _execute_restart_service(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute service restart"""
        # Would integrate with deployment/orchestration systems
        logger.info("Restarting service (placeholder)")
        return {"service_restarted": True}
    
    async def _execute_rollback_deployment(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute deployment rollback"""
        # Would integrate with deployment systems
        logger.info("Rolling back deployment (placeholder)")
        return {"deployment_rolled_back": True}
    
    async def _execute_scale_resources(self, exec_context: ExecutionContext, result: ExecutionResult) -> Dict[str, Any]:
        """Execute resource scaling"""
        # Would integrate with cloud platforms
        logger.info("Scaling resources (placeholder)")
        return {"resources_scaled": True}
    
    # Safety checks and validation
    
    async def _perform_safety_checks(self, exec_context: ExecutionContext, result: ExecutionResult) -> bool:
        """Perform pre-execution safety checks"""
        
        action = exec_context.action
        
        # Get safety checker for this action type
        safety_checker = self.safety_checkers.get(action.action_type)
        
        if not safety_checker:
            # No specific safety checker, perform general checks
            return await self._general_safety_check(exec_context, result)
        
        try:
            # Perform action-specific safety check
            return await asyncio.wait_for(
                safety_checker(exec_context, result),
                timeout=self.safety_check_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Safety check timed out for {action.action_type.value}")
            return False
        except Exception as e:
            logger.error(f"Safety check failed for {action.action_type.value}: {e}")
            return False
    
    async def _general_safety_check(self, exec_context: ExecutionContext, result: ExecutionResult) -> bool:
        """Perform general safety checks"""
        
        action = exec_context.action
        
        # Check confidence thresholds
        if action.confidence_score < 0.5:  # Minimum confidence for any action
            logger.warning(f"Action {action.action_type.value} has low confidence: {action.confidence_score}")
            return False
        
        # Check safety level
        if action.safety_level == SafetyLevel.DANGEROUS:
            logger.warning(f"Action {action.action_type.value} marked as dangerous")
            return False
        
        # Check for safety override
        if exec_context.safety_override:
            logger.info(f"Safety check overridden for {action.action_type.value}")
            return True
        
        return True
    
    async def _safety_check_code_changes(self, exec_context: ExecutionContext, result: ExecutionResult) -> bool:
        """Safety check for code modification actions"""
        
        # Check if workspace is clean
        if exec_context.workspace_path:
            # Would check git status, ensure no uncommitted changes
            pass
        
        # Check if tests exist
        # Would verify test coverage before making changes
        
        # Check if changes affect critical paths
        # Would analyze code impact
        
        return True  # Placeholder
    
    async def _safety_check_merge(self, exec_context: ExecutionContext, result: ExecutionResult) -> bool:
        """Safety check for PR merge"""
        
        # Check if PR has approvals
        # Check if CI is passing
        # Check if PR is mergeable
        
        return True  # Placeholder
    
    async def _safety_check_rollback(self, exec_context: ExecutionContext, result: ExecutionResult) -> bool:
        """Safety check for deployment rollback"""
        
        # Check if rollback target exists
        # Check if rollback is safe
        # Check service dependencies
        
        return True  # Placeholder
    
    async def _safety_check_service_restart(self, exec_context: ExecutionContext, result: ExecutionResult) -> bool:
        """Safety check for service restart"""
        
        # Check service health
        # Check if restart is during acceptable window
        # Check dependencies
        
        return True  # Placeholder
    
    # Rollback procedures
    
    async def _perform_rollback(self, exec_context: ExecutionContext, result: ExecutionResult):
        """Perform rollback after failed action"""
        
        action = exec_context.action
        rollback_procedure = self.rollback_procedures.get(action.action_type)
        
        if rollback_procedure:
            await rollback_procedure(exec_context, result)
        else:
            logger.info(f"No rollback procedure defined for {action.action_type.value}")
    
    async def _rollback_code_changes(self, exec_context: ExecutionContext, result: ExecutionResult):
        """Rollback code changes"""
        # Would revert git changes, close PR, etc.
        logger.info("Rolling back code changes")
    
    async def _rollback_merge(self, exec_context: ExecutionContext, result: ExecutionResult):
        """Rollback PR merge"""
        # Would revert the merge commit
        logger.info("Rolling back PR merge")
    
    async def _rollback_status_change(self, exec_context: ExecutionContext, result: ExecutionResult):
        """Rollback status change"""
        # Would revert Jira status
        logger.info("Rolling back status change")
    
    async def _rollback_comment(self, exec_context: ExecutionContext, result: ExecutionResult):
        """Rollback comment addition"""
        # Would delete the comment if possible
        logger.info("Rolling back comment")
    
    # Helper methods
    
    async def _request_human_approval(self, plan: ExecutionPlan) -> bool:
        """Request human approval for a plan"""
        
        logger.info(f"Requesting human approval for plan {plan.plan_id}")
        
        # Would integrate with approval system (Slack, email, etc.)
        # For now, return True for non-dangerous actions
        
        has_dangerous = any(action.safety_level == SafetyLevel.DANGEROUS for action in plan.primary_actions)
        
        if has_dangerous:
            logger.warning("Plan contains dangerous actions, approval denied by default")
            return False
        
        return True  # Placeholder
    
    async def _request_action_approval(self, action: PlannedAction, context: Any) -> bool:
        """Request human approval for a specific action"""
        
        logger.info(f"Requesting human approval for action {action.action_type.value}")
        
        # Would integrate with approval system
        # For now, auto-approve safe actions
        
        return action.safety_level in [SafetyLevel.SAFE, SafetyLevel.CAUTIOUS]
    
    def _is_within_execution_window(self, window: Tuple[datetime, datetime]) -> bool:
        """Check if current time is within execution window"""
        
        now = datetime.now(timezone.utc)
        start, end = window
        
        return start <= now <= end
    
    async def _schedule_for_execution_window(self, plan: ExecutionPlan):
        """Schedule plan for execution within its window"""
        
        # Would integrate with scheduling system
        logger.info(f"Scheduling plan {plan.plan_id} for execution window")
    
    async def _resolve_prerequisites(self, plan: ExecutionPlan) -> bool:
        """Attempt to resolve prerequisites for a plan"""
        
        # Would attempt to satisfy prerequisites
        # For now, just return current state
        return plan.prerequisites_met
    
    # Placeholder helper methods
    
    async def _perform_automated_pr_review(self, repo: str, pr_number: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Perform automated PR review"""
        return {"comments": [], "status": "commented"}
    
    async def _send_escalation_notification(self, recipient: str, target: str, escalation_type: str, parameters: Dict[str, Any]) -> bool:
        """Send escalation notification"""
        return True
    
    async def _send_wait_notification(self, recipient: str, target: str, reason: str) -> bool:
        """Send notification about waiting for human intervention"""
        return True
    
    async def _find_additional_related_issues(self, target: str) -> List[Dict[str, Any]]:
        """Find additional related issues"""
        return []
    
    async def _find_code_examples(self, target: str) -> List[Dict[str, Any]]:
        """Find code examples"""
        return []
    
    async def _find_test_cases(self, target: str) -> List[Dict[str, Any]]:
        """Find test cases"""
        return []
