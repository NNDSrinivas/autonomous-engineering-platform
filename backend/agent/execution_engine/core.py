"""
Execution Engine Core - Phase 4.3

The foundational execution system that transforms GroundedTasks into
concrete engineering actions.

This provides the generic Executor interface and ExecutionEngine orchestrator
that coordinates the canonical execution loop:

GroundedTask → Analyze → Plan → Propose → Approve → Apply → Verify → Report
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Dict, Any, Optional
import time
import logging

from backend.agent.task_grounder.types import GroundedTask
from .types import (
    AnalysisResult,
    FixPlan,
    DiffProposal,
    ApplyResult,
    VerificationResult,
    ExecutionResult,
    ExecutionStatus,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=GroundedTask)


class Executor(Generic[T], ABC):
    """
    Abstract base class for task executors.

    Each concrete executor (FixProblemsExecutor, DeployExecutor, etc.)
    implements this interface to provide task-specific execution logic.

    This interface enforces the canonical execution loop.
    """

    @abstractmethod
    async def analyze(self, task: T, context: Dict[str, Any]) -> AnalysisResult:
        """
        Analyze the grounded task to understand what needs to be done.

        This step is pure analysis - no modifications are made.
        Returns structured analysis of the problem.
        """
        pass

    @abstractmethod
    async def plan_fix(
        self, task: T, analysis: AnalysisResult, context: Dict[str, Any]
    ) -> FixPlan:
        """
        Create a structured plan for addressing the analyzed issues.

        This step generates the reasoning and approach but doesn't
        create any code changes yet.
        """
        pass

    @abstractmethod
    async def propose_diff(
        self, task: T, plan: FixPlan, context: Dict[str, Any]
    ) -> DiffProposal:
        """
        Generate concrete diffs/changes based on the fix plan.

        This step creates the actual proposed changes but doesn't
        apply them - they're shown to the user for approval first.
        """
        pass

    @abstractmethod
    async def apply_changes(
        self, proposal: DiffProposal, context: Dict[str, Any]
    ) -> ApplyResult:
        """
        Apply the approved changes to the workspace.

        Only called after user approval. Makes the actual file modifications.
        """
        pass

    @abstractmethod
    async def verify_results(
        self, task: T, apply_result: ApplyResult, context: Dict[str, Any]
    ) -> VerificationResult:
        """
        Verify that the applied changes resolved the original issues.

        Re-checks diagnostics, runs tests if needed, confirms success.
        """
        pass

    async def orchestrate_full_workflow(
        self,
        task: T,
        apply_result: ApplyResult,
        verification: VerificationResult,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Optional method for Phase 4.4 Enterprise Autonomy workflow orchestration.

        Default implementation returns success. Executors can override to provide
        advanced workflow capabilities like PR creation, CI monitoring, etc.
        """
        return {"success": True, "final_status": "workflow_not_implemented"}


class ExecutionEngine:
    """
    Orchestrates the execution of GroundedTasks using appropriate Executors.

    This is the main entry point for Phase 4.3+ autonomous execution.
    It manages the execution loop and coordinates between different
    executor types.
    """

    def __init__(self):
        self._executors: Dict[str, Executor] = {}

    def register_executor(self, intent: str, executor: Executor):
        """Register an executor for a specific intent type"""
        self._executors[intent] = executor
        logger.info(f"Registered executor for intent: {intent}")

    def get_executor(self, intent: str) -> Executor:
        """Get the appropriate executor for an intent"""
        if intent not in self._executors:
            raise ValueError(f"No executor registered for intent: {intent}")
        return self._executors[intent]

    async def execute_task(
        self, task: GroundedTask, context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        Execute a GroundedTask using the canonical execution loop.

        This is the main execution method that orchestrates:
        1. Analysis
        2. Planning
        3. Diff Proposal
        4. (Approval happens in the calling code)
        5. Application (if approved)
        6. Verification
        7. Final reporting
        """
        if context is None:
            context = {}

        task_id = f"exec-{int(time.time())}-{task.intent}"
        start_time = time.time()

        logger.info(f"Starting execution for task {task_id}: {task.intent}")

        try:
            # Get the appropriate executor
            executor = self.get_executor(task.intent)

            # Phase 1: Analyze
            logger.info(f"[{task_id}] Starting analysis phase")
            analysis = await executor.analyze(task, context)
            logger.info(
                f"[{task_id}] Analysis complete: {analysis.total_issues} issues found"
            )
            context["analysis_result"] = analysis
            context["analysis"] = analysis

            # Phase 2: Plan
            logger.info(f"[{task_id}] Starting planning phase")
            plan = await executor.plan_fix(task, analysis, context)
            logger.info(
                f"[{task_id}] Plan complete: {len(plan.steps)} steps, {plan.risk_level} risk"
            )

            # Phase 3: Propose
            logger.info(f"[{task_id}] Starting diff proposal phase")
            proposal = await executor.propose_diff(task, plan, context)
            logger.info(
                f"[{task_id}] Proposal complete: {proposal.total_files} files to change"
            )

            # At this point, we return the ExecutionResult with proposal
            # The calling code handles approval workflow
            # If approved, it calls execute_approved_changes()

            execution_time = int((time.time() - start_time) * 1000)

            return ExecutionResult(
                task_id=task_id,
                status=ExecutionStatus.AWAITING_APPROVAL,
                analysis=analysis,
                plan=plan,
                proposal=proposal,
                execution_time_ms=execution_time,
                user_approved=False,
                final_report=self._generate_proposal_report(analysis, plan, proposal),
                success=True,
            )

        except Exception as e:
            logger.error(f"[{task_id}] Execution failed: {e}", exc_info=True)
            execution_time = int((time.time() - start_time) * 1000)

            return ExecutionResult(
                task_id=task_id,
                status=ExecutionStatus.FAILED,
                execution_time_ms=execution_time,
                user_approved=False,
                final_report=f"Execution failed: {str(e)}",
                success=False,
            )

    async def execute_approved_changes(
        self,
        execution_result: ExecutionResult,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Continue execution after user approval.

        This applies the changes and verifies the results.
        Called only after user approves the proposal.
        """
        if context is None:
            context = {}

        task_id = execution_result.task_id
        start_time = time.time()

        logger.info(f"[{task_id}] Continuing with approved changes")

        try:
            if not execution_result.proposal:
                raise ValueError("No proposal found in execution result")

            # We need to reconstruct the task and executor
            # For now, we'll get it from the proposal or context
            intent = context.get("intent") or execution_result.task_id.split("-")[-1]
            executor = self.get_executor(intent)

            # Phase 4: Apply changes
            logger.info(f"[{task_id}] Applying approved changes")
            apply_result = await executor.apply_changes(
                execution_result.proposal, context
            )
            logger.info(
                f"[{task_id}] Changes applied: {len(apply_result.files_updated)} files updated"
            )

            # Phase 5: Verify results
            logger.info(f"[{task_id}] Verifying results")
            # We need the original task for verification
            original_task = context.get("original_task")
            if original_task:
                verification = await executor.verify_results(
                    original_task, apply_result, context
                )
                logger.info(f"[{task_id}] Verification complete: {verification.status}")
            else:
                # Create a basic verification result if no original task
                verification = VerificationResult(
                    remaining_issues=0,
                    resolved_issues=len(apply_result.files_updated),
                    status="resolved" if apply_result.success else "failed",
                    verification_details=(
                        "Applied changes successfully"
                        if apply_result.success
                        else "Failed to apply some changes"
                    ),
                    success=apply_result.success,
                    message=(
                        "Changes applied and verified"
                        if apply_result.success
                        else "Some changes failed to apply"
                    ),
                )

            # Phase 4.4: Enterprise Autonomy Stack (if enabled and successful)
            workflow_result = None
            if (
                apply_result.success
                and verification.status == "resolved"
                and hasattr(executor, "orchestrate_full_workflow")
                and original_task
            ):
                try:
                    logger.info(
                        f"[{task_id}] Starting Phase 4.4 Enterprise Autonomy workflow"
                    )
                    workflow_result = await executor.orchestrate_full_workflow(
                        original_task, apply_result, verification, context
                    )
                    logger.info(
                        f"[{task_id}] Phase 4.4 workflow: {workflow_result.get('final_status', 'unknown')}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[{task_id}] Phase 4.4 workflow failed (non-critical): {e}"
                    )
                    workflow_result = {
                        "success": False,
                        "error": str(e),
                        "final_status": "workflow_error",
                    }

            execution_time = int((time.time() - start_time) * 1000)
            total_time = execution_result.execution_time_ms + execution_time

            # Update the execution result
            execution_result.apply_result = apply_result
            execution_result.verification = verification
            execution_result.workflow_result = (
                workflow_result  # Store Phase 4.4 results
            )
            execution_result.execution_time_ms = total_time
            execution_result.user_approved = True
            execution_result.status = (
                ExecutionStatus.COMPLETED
                if apply_result.success and verification.status == "resolved"
                else ExecutionStatus.FAILED
            )
            execution_result.final_report = self._generate_final_report(
                execution_result
            )
            execution_result.success = (
                apply_result.success and verification.status == "resolved"
            )

            return execution_result

        except Exception as e:
            logger.error(
                f"[{task_id}] Failed to apply approved changes: {e}", exc_info=True
            )

            execution_result.status = ExecutionStatus.FAILED
            execution_result.final_report = f"Failed to apply changes: {str(e)}"
            execution_result.success = False

            return execution_result

    def _generate_proposal_report(
        self, analysis: AnalysisResult, plan: FixPlan, proposal: DiffProposal
    ) -> str:
        """Generate human-readable report for the proposal stage"""
        report = "## Analysis Complete\n\n"
        report += f"Found **{analysis.total_issues} issues** across {len(analysis.affected_files)} files:\n"
        report += f"• {analysis.error_count} errors\n"
        report += f"• {analysis.warning_count} warnings\n"
        report += f"• {analysis.fixable_count} automatically fixable\n\n"

        report += "## Fix Plan\n\n"
        report += f"{plan.summary}\n\n"
        report += f"**Approach**: {plan.reasoning}\n\n"
        report += f"**Risk Level**: {plan.risk_level}\n"
        report += f"**Files to modify**: {len(plan.files_to_modify)}\n\n"

        report += "## Proposed Changes\n\n"
        report += f"I will modify **{proposal.total_files} files** with:\n"
        report += f"• {proposal.total_additions} lines added\n"
        report += f"• {proposal.total_deletions} lines removed\n\n"

        report += "**Do you want me to apply these changes?**"

        return report

    def _generate_final_report(self, result: ExecutionResult) -> str:
        """Generate human-readable final report"""
        if not result.apply_result or not result.verification:
            return "Execution incomplete"

        if result.success:
            report = "✅ **Task completed successfully**\n\n"
            report += f"• Updated {len(result.apply_result.files_updated)} files\n"
            report += f"• Resolved {result.verification.resolved_issues} issues\n"
            if result.verification.remaining_issues == 0:
                report += "• All diagnostics are now clean\n"
            else:
                report += f"• {result.verification.remaining_issues} issues remain\n"

            # Add Phase 4.4 workflow information if available
            if result.workflow_result:
                workflow = result.workflow_result
                if (
                    workflow.get("success")
                    and workflow.get("final_status") == "completed_successfully"
                ):
                    report += "\n🤖 **Autonomous Workflow Completed**\n"
                    if workflow.get("branch_created"):
                        report += f"• Created branch: `{workflow.get('branch_name', 'unknown')}`\n"
                    if workflow.get("commits_made"):
                        commit_sha = workflow.get("commit_sha", "unknown")[:8]
                        report += f"• Committed changes: `{commit_sha}`\n"
                    if workflow.get("pr_created"):
                        pr_number = workflow.get("pr_number", "unknown")
                        pr_url = workflow.get("pr_url", "#")
                        report += f"• Created [PR #{pr_number}]({pr_url})\n"
                    if workflow.get("ci_monitored"):
                        ci_status = workflow.get("ci_status", "unknown")
                        report += f"• CI pipeline: {ci_status}\n"

                    # Add next action
                    next_action = workflow.get("next_action", {})
                    if next_action.get("staff_level"):
                        report += "\n🏆 **Staff Engineer-level automation achieved**\n"
                        report += f"{next_action.get('message', 'Workflow completed successfully')}\n"

                elif workflow.get("final_status") == "autonomy_disabled":
                    report += "\n📋 **Autonomous workflow available but disabled**\n"
                    report += "Enable full autonomy to have NAVI create branches, PRs, and monitor CI automatically.\n"

        else:
            report = "❌ **Task failed**\n\n"
            if result.apply_result.files_failed:
                report += f"• Failed to update: {', '.join(result.apply_result.files_failed)}\n"
            if result.verification.new_issues > 0:
                report += f"• Introduced {result.verification.new_issues} new issues\n"

        return report


# Global execution engine instance
execution_engine = ExecutionEngine()
