"""
NAVI Jira Autonomy Engine

This module enables NAVI to understand, enrich, plan, and execute Jira tasks
with full organizational context integration.

Features:
- Parse Jira issues into structured format
- Enrich with Slack/Confluence/Zoom/GitHub context
- Generate engineering execution plans
- Execute Jira workflow operations
- Resolve which Jira issue user refers to

This is what makes NAVI better than Devin/Cursor/Cline - true organizational intelligence.
"""

from .parser import parse_jira_issue
from .enricher import enrich_jira_context
from .planner import generate_jira_plan
from .executor import (
    start_jira_work,
    complete_jira_work,
    add_jira_comment,
    transition_jira,
)
from .resolver import resolve_jira_target

__all__ = [
    "parse_jira_issue",
    "enrich_jira_context",
    "generate_jira_plan",
    "start_jira_work",
    "complete_jira_work",
    "add_jira_comment",
    "transition_jira",
    "resolve_jira_target",
]
