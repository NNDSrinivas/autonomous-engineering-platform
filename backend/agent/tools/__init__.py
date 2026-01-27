"""
NAVI Agent Tools

Comprehensive toolkit for NAVI agent operations:
- File operations (read, create, edit, apply_diff)
- Code search and navigation
- Terminal command execution (safe, dangerous, interactive, parallel)
- External integrations (Jira, Slack, GitHub, GitLab)
- Infrastructure tools (Terraform, K8s, Docker)
- Database tools (schema design, migrations)
- CI/CD tools (GitLab CI, GitHub Actions)
- Documentation generation
- Test generation
- Monitoring and observability
- Secrets management

This is NAVI's "muscles" - the Intent Engine is the brain, tools are the actions.
"""

# Core file operations
from .read_file import read_file
from .create_file import create_file
from .edit_file import edit_file
from .apply_diff import apply_diff
from .search_repo import search_repo

# Command execution (with all variants)
from .run_command import (
    run_command,
    run_dangerous_command,
    run_interactive_command,
    run_parallel_commands,
    run_command_with_retry,
    list_backups,
    restore_backup,
    SAFE_COMMANDS,
    BLOCKED_COMMANDS,
    CONDITIONAL_COMMANDS,
)

# Dangerous command handling
from .dangerous_commands import (
    is_dangerous_command,
    get_command_info,
    format_permission_request,
    BackupManager,
    DANGEROUS_COMMANDS,
    RiskLevel,
)

# Jira integration
from .jira_tools import (
    list_assigned_issues_for_user,
    create_jira_issue,
    update_jira_issue,
    add_jira_comment,
    search_jira_issues,
    JIRA_TOOLS,
)

# GitHub integration
from .github_tools import (
    github_create_pr,
    github_create_branch,
    github_create_issue,
    github_list_issues,
    github_add_issue_comment,
    github_add_pr_review,
    github_list_prs,
    github_merge_pr,
    GITHUB_TOOLS,
)

# Web tools
from .web_tools import fetch_url, search_web

# Slack integration
from .slack_tools import (
    search_slack_messages,
    list_slack_channel_messages,
    send_slack_message,
    SLACK_TOOLS,
)

# GitLab integration
from .gitlab_tools import (
    list_my_gitlab_merge_requests,
    GITLAB_TOOLS,
)

# Infrastructure tools (Terraform, K8s, Docker, Helm)
from .infrastructure_tools import INFRASTRUCTURE_TOOLS

# Documentation tools
from .documentation_tools import DOCUMENTATION_TOOLS

# Scaffolding tools
from .scaffolding_tools import SCAFFOLDING_TOOLS

# Monitoring tools
from .monitoring_tools import MONITORING_TOOLS

# Secrets tools
from .secrets_tools import SECRETS_TOOLS

# Architecture tools
from .architecture_tools import ARCHITECTURE_TOOLS

# Deployment tools
from .deployment_tools import DEPLOYMENT_TOOLS

# Database tools (schema, migrations)
from .database_tools import DATABASE_TOOLS

# Test generation tools
from .test_generation_tools import TEST_GENERATION_TOOLS

# GitLab CI tools
from .gitlab_ci_tools import GITLAB_CI_TOOLS

# GitHub Actions tools
from .github_actions_tools import GITHUB_ACTIONS_TOOLS

# Linear integration
from .linear_tools import LINEAR_TOOLS

# Notion integration
from .notion_tools import NOTION_TOOLS

# Confluence integration
from .confluence_tools import CONFLUENCE_TOOLS

# Multi-cloud tools
from .multicloud_tools import MULTICLOUD_TOOLS

# Asana integration
from .asana_tools import ASANA_TOOLS

# Trello integration
from .trello_tools import TRELLO_TOOLS

# ClickUp integration
from .clickup_tools import CLICKUP_TOOLS

# Monday.com integration
from .monday_tools import MONDAY_TOOLS

# Bitbucket integration
from .bitbucket_tools import BITBUCKET_TOOLS

# Sentry integration
from .sentry_tools import SENTRY_TOOLS

# Datadog integration
from .datadog_tools import DATADOG_TOOLS

# PagerDuty integration
from .pagerduty_tools import PAGERDUTY_TOOLS

# Snyk integration
from .snyk_tools import SNYK_TOOLS

# SonarQube integration
from .sonarqube_tools import SONARQUBE_TOOLS

# Figma integration
from .figma_tools import FIGMA_TOOLS

# Loom integration
from .loom_tools import LOOM_TOOLS

# Discord integration
from .discord_tools import DISCORD_TOOLS

# Zoom integration
from .zoom_tools import ZOOM_TOOLS

# Google Calendar integration
from .google_calendar_tools import GOOGLE_CALENDAR_TOOLS

# Google Drive integration
from .google_drive_tools import GOOGLE_DRIVE_TOOLS

# Vercel integration
from .vercel_tools import VERCEL_TOOLS

# CircleCI integration
from .circleci_tools import CIRCLECI_TOOLS

# Enterprise tools (Phase 6)
from .compliance_tools import COMPLIANCE_TOOLS
from .load_testing_tools import LOAD_TESTING_TOOLS
from .advanced_database_tools import ADVANCED_DATABASE_TOOLS
from .kubernetes_lifecycle_tools import K8S_LIFECYCLE_TOOLS

__all__ = [
    # Core file operations
    "read_file",
    "create_file",
    "edit_file",
    "apply_diff",
    "search_repo",
    # Command execution
    "run_command",
    "run_dangerous_command",
    "run_interactive_command",
    "run_parallel_commands",
    "run_command_with_retry",
    "list_backups",
    "restore_backup",
    "SAFE_COMMANDS",
    "BLOCKED_COMMANDS",
    "CONDITIONAL_COMMANDS",
    # Dangerous command handling
    "is_dangerous_command",
    "get_command_info",
    "format_permission_request",
    "BackupManager",
    "DANGEROUS_COMMANDS",
    "RiskLevel",
    # Jira
    "list_assigned_issues_for_user",
    "create_jira_issue",
    "update_jira_issue",
    "add_jira_comment",
    "search_jira_issues",
    "JIRA_TOOLS",
    # GitHub
    "github_create_pr",
    "github_create_branch",
    "github_create_issue",
    "github_list_issues",
    "github_add_issue_comment",
    "github_add_pr_review",
    "github_list_prs",
    "github_merge_pr",
    "GITHUB_TOOLS",
    # Web
    "fetch_url",
    "search_web",
    # Slack
    "search_slack_messages",
    "list_slack_channel_messages",
    "send_slack_message",
    "SLACK_TOOLS",
    # GitLab
    "list_my_gitlab_merge_requests",
    "GITLAB_TOOLS",
    # Infrastructure
    "INFRASTRUCTURE_TOOLS",
    # Database
    "DATABASE_TOOLS",
    # Test Generation
    "TEST_GENERATION_TOOLS",
    # GitLab CI
    "GITLAB_CI_TOOLS",
    # GitHub Actions
    "GITHUB_ACTIONS_TOOLS",
    # Documentation
    "DOCUMENTATION_TOOLS",
    # Scaffolding
    "SCAFFOLDING_TOOLS",
    # Monitoring
    "MONITORING_TOOLS",
    # Secrets
    "SECRETS_TOOLS",
    # Architecture
    "ARCHITECTURE_TOOLS",
    # Deployment
    "DEPLOYMENT_TOOLS",
    # Linear
    "LINEAR_TOOLS",
    # Notion
    "NOTION_TOOLS",
    # Confluence
    "CONFLUENCE_TOOLS",
    # Multi-cloud
    "MULTICLOUD_TOOLS",
    # Asana
    "ASANA_TOOLS",
    # Trello
    "TRELLO_TOOLS",
    # ClickUp
    "CLICKUP_TOOLS",
    # Monday
    "MONDAY_TOOLS",
    # Bitbucket
    "BITBUCKET_TOOLS",
    # Sentry
    "SENTRY_TOOLS",
    # Datadog
    "DATADOG_TOOLS",
    # PagerDuty
    "PAGERDUTY_TOOLS",
    # Snyk
    "SNYK_TOOLS",
    # SonarQube
    "SONARQUBE_TOOLS",
    # Figma
    "FIGMA_TOOLS",
    # Loom
    "LOOM_TOOLS",
    # Discord
    "DISCORD_TOOLS",
    # Zoom
    "ZOOM_TOOLS",
    # Google Calendar
    "GOOGLE_CALENDAR_TOOLS",
    # Google Drive
    "GOOGLE_DRIVE_TOOLS",
    # Vercel
    "VERCEL_TOOLS",
    # CircleCI
    "CIRCLECI_TOOLS",
    # Enterprise tools (Phase 6)
    "COMPLIANCE_TOOLS",
    "LOAD_TESTING_TOOLS",
    "ADVANCED_DATABASE_TOOLS",
    "K8S_LIFECYCLE_TOOLS",
]
