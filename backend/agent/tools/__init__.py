"""
NAVI Agent Tools

Real operations that NAVI can perform in the workspace.
Each tool maps to concrete actions like:
- File creation/modification
- Code search and navigation
- Terminal command execution
- External API calls (Jira, Slack, GitHub)

This is NAVI's "muscles" - the Intent Engine is the brain, tools are the actions.
"""

from .read_file import read_file
from .create_file import create_file
from .edit_file import edit_file
from .apply_diff import apply_diff
from .search_repo import search_repo
from .run_command import run_command
from .jira_tools import jira_comment, jira_transition, jira_fetch_issue
from .github_tools import github_create_pr, github_create_branch

__all__ = [
    "read_file",
    "create_file",
    "edit_file",
    "apply_diff",
    "search_repo",
    "run_command",
    "jira_comment",
    "jira_transition",
    "jira_fetch_issue",
    "github_create_pr",
    "github_create_branch",
]
