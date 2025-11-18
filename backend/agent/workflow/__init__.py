"""
NAVI Autonomous Workflow Engine

The multi-step execution engine that transforms NAVI from a coding assistant
into a full autonomous AI engineer.

This is the layer that coordinates:
- Jira understanding (STEP F)
- Tool execution (STEP E)  
- Intent classification (STEP D)
- Organizational context (STEP C)
- Memory & state (STEP B)

To execute complete end-to-end developer workflows:
Jira → Plan → Code → Test → Commit → PR → Update Jira → Done

This is what Devin, Cursor, and Cline aim for but don't fully achieve.
NAVI does it with organizational intelligence.
"""

from .state import WorkflowState, WorkflowStatus
from .steps import (
    step_analysis,
    step_locate_files,
    step_propose_diffs,
    step_apply_diffs,
    step_run_tests,
    step_commit_changes,
    step_push_branch,
    step_create_pr,
    step_update_jira,
    step_done
)
from .engine import run_workflow_step, create_workflow, resume_workflow
from .runner import WorkflowRunner, start_autonomous_task

__all__ = [
    "WorkflowState",
    "WorkflowStatus",
    "step_analysis",
    "step_locate_files",
    "step_propose_diffs",
    "step_apply_diffs",
    "step_run_tests",
    "step_commit_changes",
    "step_push_branch",
    "step_create_pr",
    "step_update_jira",
    "step_done",
    "run_workflow_step",
    "create_workflow",
    "resume_workflow",
    "WorkflowRunner",
    "start_autonomous_task",
]
