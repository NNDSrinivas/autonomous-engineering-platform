# backend/agent/tool_executor.py

"""
NAVI tool executor

This module is the single place where logical tool names like
  - "repo_inspect"
  - "code_read_files"
  - "code_search"
  - "pm_create_ticket"
are mapped to actual Python implementations.

The goal is to keep this file boring and deterministic, so NAVI
feels powerful but predictable.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

# Import actual tool implementations
from .tools.create_file import create_file
from .tools.edit_file import edit_file
from .tools.apply_diff import apply_diff
from .tools.run_command import (
    run_command,
    run_dangerous_command,
    run_interactive_command,
    run_parallel_commands,
    run_command_with_retry,
    list_backups,
    restore_backup,
)
from .tools.web_tools import fetch_url, search_web

# Credentials management for BYOK support
from backend.services.credentials_service import (
    CredentialsService,
)

logger = logging.getLogger(__name__)

# Global credentials service instance (per-session)
# This can be initialized with BYOK credentials
_credentials_service: Optional[CredentialsService] = None


def get_credentials_service() -> CredentialsService:
    """Get or create the global credentials service."""
    global _credentials_service
    if _credentials_service is None:
        _credentials_service = CredentialsService()
    return _credentials_service


def set_byok_credentials(provider: str, credentials: Dict[str, str]) -> None:
    """Set BYOK credentials for a provider."""
    service = get_credentials_service()
    service.set_byok_credential(provider, credentials)


def get_credential(
    provider: str, field: str, default: Optional[str] = None
) -> Optional[str]:
    """Get a credential from the credentials service."""
    service = get_credentials_service()
    return service.get_credential(provider, field, default)


# Tools that mutate state or filesystem. Used by guardrails and UI.
WRITE_OPERATION_TOOLS = {
    # Code write operations
    "code_apply_diff",
    "code_create_file",
    "code_edit_file",
    "code_run_command",
    "repo_write",
    # Jira write operations
    "jira_add_comment",
    "jira_transition_issue",
    "jira_assign_issue",
    "jira_create_issue",
    # GitHub write operations
    "github_comment",
    "github_set_label",
    "github_rerun_check",
    "github_create_issue",
    "github_create_pr",
    # Linear write operations
    "linear_create_issue",
    "linear_add_comment",
    "linear_update_status",
    # GitLab write operations
    "gitlab_create_merge_request",
    "gitlab_add_comment",
    # Notion write operations
    "notion_create_page",
    # Slack write operations
    "slack_send_message",
    # Asana write operations
    "asana_create_task",
    "asana_complete_task",
    # Bitbucket write operations
    "bitbucket_create_pull_request",
    # Discord write operations
    "discord_send_message",
    # Trello write operations
    "trello_create_card",
    "trello_move_card",
    # ClickUp write operations
    "clickup_create_task",
    "clickup_update_task",
    # Confluence write operations
    "confluence_create_page",
    # Figma write operations
    "figma_add_comment",
    # Sentry write operations
    "sentry_resolve_issue",
    # GitHub Actions write operations
    "github_actions_trigger_workflow",
    # CircleCI write operations
    "circleci_trigger_pipeline",
    # Vercel write operations
    "vercel_redeploy",
    # PagerDuty write operations
    "pagerduty_acknowledge_incident",
    "pagerduty_resolve_incident",
    # Monday.com write operations
    "monday_create_item",
    # Datadog write operations
    "datadog_mute_monitor",
    # Deployment execution operations (real execution)
    "deploy_execute",
    "deploy_confirm",
    "deploy_rollback",
    # Scaffolding write operations
    "scaffold_project",
    "scaffold_add_feature",
    # Test generation write operations
    "test_generate_for_file",
    "test_generate_for_function",
    "test_generate_suite",
    # Documentation write operations
    "docs_generate_readme",
    "docs_generate_api",
    "docs_generate_component",
    "docs_generate_architecture",
    "docs_generate_comments",
    "docs_generate_changelog",
    # Infrastructure write operations (Phase 2)
    "infra_generate_terraform",
    "infra_generate_cloudformation",
    "infra_generate_k8s",
    "infra_generate_docker_compose",
    "infra_generate_helm",
    # Database write operations (Phase 2)
    "db_generate_migration",
    "db_run_migration",
    "db_generate_seed",
    # Database execution operations (real execution)
    "db_execute_migration",
    "db_confirm",
    "db_backup",
    "db_restore",
    # Monitoring write operations (Phase 2)
    "monitor_setup_errors",
    "monitor_setup_apm",
    "monitor_setup_logging",
    "monitor_generate_health_checks",
    # Secrets write operations (Phase 2)
    "secrets_sync_to_platform",
    "secrets_rotate",
    # Architecture write operations (Phase 3)
    "arch_generate_adr",
    # GitLab CI write operations (Phase 3)
    "gitlab_ci_generate",
    "gitlab_ci_add_stage",
    "gitlab_ci_generate_cd",
    "gitlab_ci_generate_templates",
    # Multi-cloud write operations (Phase 3)
    "cloud_multi_region",
    "cloud_landing_zone",
}


def get_available_tools():
    """List supported tool entrypoints for UI/help surfaces."""
    return sorted(
        {
            # Context tools
            "context_present_packet",
            "context_summary",
            # Repository and code tools
            "repo_inspect",
            "code_read_files",
            "code_search",
            "code_explain",
            "code_apply_diff",
            "code_create_file",
            "code_edit_file",
            "code_run_command",
            # Project management
            "project_summary",
            # Jira tools
            "jira_list_assigned_issues_for_user",
            "jira_search_issues",
            "jira_assign_issue",
            "jira_create_issue",
            "jira_add_comment",
            "jira_transition_issue",
            # GitHub tools
            "github_list_my_prs",
            "github_list_my_issues",
            "github_get_pr_details",
            "github_list_repo_issues",
            "github_create_issue",
            "github_create_pr",
            "github_comment",
            "github_set_label",
            "github_rerun_check",
            # Linear tools
            "linear_list_my_issues",
            "linear_search_issues",
            "linear_create_issue",
            "linear_add_comment",
            "linear_update_status",
            "linear_list_teams",
            # GitLab tools
            "gitlab_list_my_merge_requests",
            "gitlab_list_my_issues",
            "gitlab_get_pipeline_status",
            "gitlab_search",
            "gitlab_create_merge_request",
            "gitlab_add_comment",
            # Notion tools
            "notion_search_pages",
            "notion_list_recent_pages",
            "notion_get_page_content",
            "notion_list_databases",
            "notion_create_page",
            # Slack tools
            "slack_search_messages",
            "slack_list_channel_messages",
            "slack_send_message",
            # Asana tools
            "asana_list_my_tasks",
            "asana_search_tasks",
            "asana_list_projects",
            "asana_create_task",
            "asana_complete_task",
            # Bitbucket tools
            "bitbucket_list_my_prs",
            "bitbucket_list_repos",
            "bitbucket_get_pr_details",
            "bitbucket_create_pull_request",
            # Discord tools
            "discord_list_channels",
            "discord_get_messages",
            "discord_send_message",
            # Loom tools
            "loom_list_videos",
            "loom_search_videos",
            "loom_get_video",
            # Trello tools
            "trello_list_boards",
            "trello_list_my_cards",
            "trello_get_card",
            "trello_create_card",
            "trello_move_card",
            # ClickUp tools
            "clickup_list_my_tasks",
            "clickup_list_spaces",
            "clickup_get_task",
            "clickup_create_task",
            "clickup_update_task",
            # SonarQube tools
            "sonarqube_list_projects",
            "sonarqube_list_issues",
            "sonarqube_get_quality_gate",
            "sonarqube_get_metrics",
            # Confluence tools
            "confluence_search_pages",
            "confluence_get_page",
            "confluence_list_pages_in_space",
            # Figma tools
            "figma_list_files",
            "figma_get_file",
            "figma_get_comments",
            "figma_list_projects",
            "figma_add_comment",
            # Sentry tools
            "sentry_list_issues",
            "sentry_get_issue",
            "sentry_list_projects",
            "sentry_resolve_issue",
            # Snyk tools
            "snyk_list_vulnerabilities",
            "snyk_list_projects",
            "snyk_get_security_summary",
            "snyk_get_project_issues",
            # GitHub Actions tools
            "github_actions_list_workflows",
            "github_actions_list_runs",
            "github_actions_get_run_status",
            "github_actions_trigger_workflow",
            # CircleCI tools
            "circleci_list_pipelines",
            "circleci_get_pipeline_status",
            "circleci_trigger_pipeline",
            "circleci_get_job_status",
            # Vercel tools
            "vercel_list_projects",
            "vercel_list_deployments",
            "vercel_get_deployment_status",
            "vercel_redeploy",
            # PagerDuty tools
            "pagerduty_list_incidents",
            "pagerduty_get_oncall",
            "pagerduty_list_services",
            "pagerduty_acknowledge_incident",
            "pagerduty_resolve_incident",
            # Google Drive tools
            "gdrive_list_files",
            "gdrive_search",
            "gdrive_get_content",
            # Zoom tools
            "zoom_list_recordings",
            "zoom_get_transcript",
            "zoom_search_recordings",
            # Google Calendar tools
            "gcalendar_list_events",
            "gcalendar_todays_events",
            "gcalendar_get_event",
            # Monday.com tools
            "monday_list_boards",
            "monday_list_items",
            "monday_get_my_items",
            "monday_get_item",
            "monday_create_item",
            # Datadog tools
            "datadog_list_monitors",
            "datadog_alerting_monitors",
            "datadog_list_incidents",
            "datadog_list_dashboards",
            "datadog_mute_monitor",
            # Deployment tools
            "deploy_detect_project",
            "deploy_check_cli",
            "deploy_get_info",
            "deploy_list_platforms",
            # Deployment execution tools (real execution)
            "deploy_execute",
            "deploy_confirm",
            "deploy_rollback",
            "deploy_status",
            # Scaffolding tools
            "scaffold_project",
            "scaffold_detect_requirements",
            "scaffold_add_feature",
            "scaffold_list_templates",
            # Test generation tools
            "test_generate_for_file",
            "test_generate_for_function",
            "test_generate_suite",
            "test_detect_framework",
            "test_suggest_improvements",
            # Documentation tools
            "docs_generate_readme",
            "docs_generate_api",
            "docs_generate_component",
            "docs_generate_architecture",
            "docs_generate_comments",
            "docs_generate_changelog",
            # Infrastructure tools (Phase 2)
            "infra_generate_terraform",
            "infra_generate_cloudformation",
            "infra_generate_k8s",
            "infra_generate_docker_compose",
            "infra_generate_helm",
            "infra_analyze_needs",
            # Database tools (Phase 2)
            "db_design_schema",
            "db_generate_migration",
            "db_run_migration",
            "db_generate_seed",
            "db_analyze_schema",
            "db_generate_erd",
            # Database execution tools (real execution)
            "db_execute_migration",
            "db_confirm",
            "db_backup",
            "db_restore",
            "db_status",
            # Monitoring tools (Phase 2)
            "monitor_setup_errors",
            "monitor_setup_apm",
            "monitor_setup_logging",
            "monitor_generate_health_checks",
            "monitor_setup_alerting",
            # Secrets tools (Phase 2)
            "secrets_generate_env",
            "secrets_setup_provider",
            "secrets_sync_to_platform",
            "secrets_audit",
            "secrets_rotate",
            # Architecture tools (Phase 3)
            "arch_recommend_stack",
            "arch_design_system",
            "arch_generate_diagram",
            "arch_decompose_microservices",
            "arch_generate_adr",
            "arch_analyze_dependencies",
            # GitLab CI/CD tools (Phase 3)
            "gitlab_ci_generate",
            "gitlab_ci_add_stage",
            "gitlab_ci_setup_runners",
            "gitlab_ci_generate_cd",
            "gitlab_ci_generate_templates",
            # Multi-cloud tools (Phase 3)
            "cloud_compare_services",
            "cloud_multi_region",
            "cloud_migrate",
            "cloud_estimate_costs",
            "cloud_landing_zone",
            "cloud_analyze_spend",
            # Web tools - fetch URLs and search
            "web_fetch_url",
            "web_search",
        }
    )


def is_write_operation(tool_name):
    """Return True if the tool mutates files or external systems."""
    return tool_name in WRITE_OPERATION_TOOLS


@dataclass
class ToolResult:
    """Normalized result from any tool."""

    output: Any
    sources: List[Dict[str, Any]]


def _normalize_tool_result(raw: Any) -> ToolResult:
    """
    Unify different tool return formats into ToolResult.

    Supported patterns:
    - dict with {"issues": ..., "sources": [...]}
    - dict with {"output": ..., "sources": [...]}
    - anything else → output=raw, sources=[]
    """
    if isinstance(raw, dict):
        sources = raw.get("sources") or []
        if "output" in raw:
            output = raw["output"]
        elif "issues" in raw:
            # our Jira tool: {"issues": [...], "sources": [...]}
            output = raw["issues"]
        else:
            # generic dict: treat as output
            output = raw
        return ToolResult(output=output, sources=sources)

    # default
    return ToolResult(output=raw, sources=[])


# Where the repo lives on disk.
# You can override this per machine:
#   export NAVI_WORKSPACE_ROOT=/Users/you/path/to/aep
DEFAULT_WORKSPACE_ROOT = Path(
    os.environ.get("NAVI_WORKSPACE_ROOT", os.getcwd())
).resolve()


async def execute_tool_with_sources(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    db=None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    workspace: Optional[Dict[str, Any]] = None,
    context_packet: Optional[Dict[str, Any]] = None,
) -> ToolResult:
    """
    New entrypoint that returns normalized ToolResult with sources.
    """
    raw_result = await execute_tool(
        user_id,
        tool_name,
        args,
        db=db,
        attachments=attachments,
        workspace=workspace,
        context_packet=context_packet,
    )
    return _normalize_tool_result(raw_result)


async def execute_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    db=None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    workspace: Optional[Dict[str, Any]] = None,
    context_packet: Optional[Dict[str, Any]] = None,
    credentials: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Main entrypoint – dispatch tool calls by name.

    Args:
        user_id: User ID
        tool_name: Name of the tool to execute
        args: Tool arguments
        db: Database session
        attachments: File attachments
        workspace: Workspace configuration
        context_packet: Context packet
        credentials: BYOK credentials dict {provider: {field: value}}

    Returns a dict that always has a 'tool' key and a 'text' field
    that can be fed to the LLM.
    """
    # Apply BYOK credentials if provided
    if credentials:
        for provider, creds in credentials.items():
            set_byok_credentials(provider, creds)
    logger.info(
        "[TOOLS] execute_tool user=%s tool=%s args=%s",
        user_id,
        tool_name,
        json.dumps(args, default=str)[:300],
    )

    # Context packet passthrough -------------------------------------------------
    if tool_name == "context_present_packet":
        packet = context_packet or args.get("context_packet")
        if not packet:
            return {
                "tool": tool_name,
                "text": "No context packet available to present.",
                "sources": [],
            }

        sources = packet.get("sources") or []
        return {
            "tool": tool_name,
            "text": "Here is the live context packet for this task.",
            "packet": packet,
            "sources": sources,
        }

    # Workspace-safe tools ------------------------------------------------------
    if tool_name == "repo_inspect":
        # Enrich args with context for VS Code workspace integration
        # Basic guard: require workspace_root to avoid inspecting the wrong repo
        ws = workspace or {}
        if not ws.get("workspace_root"):
            return {
                "tool": "repo_inspect",
                "text": (
                    "I don’t have your workspace path from the extension. "
                    "Open the folder you want me to inspect in VS Code and retry."
                ),
            }
        enriched_args = {
            **args,
            "user_id": user_id,
            "attachments": attachments,
            "workspace": ws,
        }
        return await _tool_repo_inspect(enriched_args)

    if tool_name == "code_read_files":
        return await _tool_code_read_files(args)

    if tool_name == "code_search":
        return await _tool_code_search(args)

    # Code write operations (require workspace) --------------------------------------
    if tool_name == "code_create_file":
        return await _tool_code_create_file(user_id, args)
    if tool_name == "code_edit_file":
        return await _tool_code_edit_file(user_id, args)
    if tool_name == "code_apply_diff":
        return await _tool_code_apply_diff(user_id, args)
    if tool_name == "code_run_command":
        return await _tool_code_run_command(user_id, args)
    if (
        tool_name == "code_run_dangerous_command"
        or tool_name == "run_dangerous_command"
    ):
        return await _tool_code_run_dangerous_command(user_id, args)
    if (
        tool_name == "code_run_interactive_command"
        or tool_name == "run_interactive_command"
    ):
        return await _tool_code_run_interactive_command(user_id, args)
    if (
        tool_name == "code_run_parallel_commands"
        or tool_name == "run_parallel_commands"
    ):
        return await _tool_code_run_parallel_commands(user_id, args)
    if (
        tool_name == "code_run_command_with_retry"
        or tool_name == "run_command_with_retry"
    ):
        return await _tool_code_run_command_with_retry(user_id, args)
    if tool_name == "list_backups":
        return await _tool_list_backups(user_id, args)
    if tool_name == "restore_backup":
        return await _tool_restore_backup(user_id, args)

    # Jira integration tools --------------------------------------------------------
    if tool_name == "jira_list_assigned_issues_for_user":
        return await _tool_jira_list_assigned_issues(user_id, args, db)
    if tool_name == "jira_add_comment":
        return await _tool_jira_add_comment(user_id, args, db)
    if tool_name == "jira_transition_issue":
        return await _tool_jira_transition_issue(user_id, args, db)
    if tool_name == "jira_assign_issue":
        return await _tool_jira_assign_issue(user_id, args, db)
    # GitHub write operations (approval-gated) --------------------------------------
    if tool_name == "github_comment":
        return await _tool_github_comment(user_id, args, db)
    if tool_name == "github_set_label":
        return await _tool_github_set_label(user_id, args, db)
    if tool_name == "github_rerun_check":
        return await _tool_github_rerun_check(user_id, args, db)

    # Linear integration tools -------------------------------------------------------
    if tool_name.startswith("linear_"):
        return await _dispatch_linear_tool(user_id, tool_name, args, db)

    # GitLab integration tools -------------------------------------------------------
    if tool_name.startswith("gitlab_"):
        return await _dispatch_gitlab_tool(user_id, tool_name, args, db)

    # Notion integration tools -------------------------------------------------------
    if tool_name.startswith("notion_"):
        return await _dispatch_notion_tool(user_id, tool_name, args, db)

    # Slack integration tools -------------------------------------------------------
    if tool_name.startswith("slack_"):
        return await _dispatch_slack_tool(user_id, tool_name, args, db)

    # Asana integration tools -------------------------------------------------------
    if tool_name.startswith("asana_"):
        return await _dispatch_asana_tool(user_id, tool_name, args, db)

    # Bitbucket integration tools ---------------------------------------------------
    if tool_name.startswith("bitbucket_"):
        return await _dispatch_bitbucket_tool(user_id, tool_name, args, db)

    # Discord integration tools -----------------------------------------------------
    if tool_name.startswith("discord_"):
        return await _dispatch_discord_tool(user_id, tool_name, args, db)

    # Loom integration tools --------------------------------------------------------
    if tool_name.startswith("loom_"):
        return await _dispatch_loom_tool(user_id, tool_name, args, db)

    # Trello integration tools ------------------------------------------------------
    if tool_name.startswith("trello_"):
        return await _dispatch_trello_tool(user_id, tool_name, args, db)

    # ClickUp integration tools -----------------------------------------------------
    if tool_name.startswith("clickup_"):
        return await _dispatch_clickup_tool(user_id, tool_name, args, db)

    # SonarQube integration tools ---------------------------------------------------
    if tool_name.startswith("sonarqube_"):
        return await _dispatch_sonarqube_tool(user_id, tool_name, args, db)

    # Confluence integration tools --------------------------------------------------
    if tool_name.startswith("confluence_"):
        return await _dispatch_confluence_tool(user_id, tool_name, args, db)

    # Figma integration tools -------------------------------------------------------
    if tool_name.startswith("figma_"):
        return await _dispatch_figma_tool(user_id, tool_name, args, db)

    # Sentry integration tools ------------------------------------------------------
    if tool_name.startswith("sentry_"):
        return await _dispatch_sentry_tool(user_id, tool_name, args, db)

    # Snyk integration tools --------------------------------------------------------
    if tool_name.startswith("snyk_"):
        return await _dispatch_snyk_tool(user_id, tool_name, args, db)

    # GitHub Actions integration tools ----------------------------------------------
    if tool_name.startswith("github_actions_"):
        return await _dispatch_github_actions_tool(user_id, tool_name, args, db)

    # CircleCI integration tools ----------------------------------------------------
    if tool_name.startswith("circleci_"):
        return await _dispatch_circleci_tool(user_id, tool_name, args, db)

    # Vercel integration tools ------------------------------------------------------
    if tool_name.startswith("vercel_"):
        return await _dispatch_vercel_tool(user_id, tool_name, args, db)

    # PagerDuty integration tools ---------------------------------------------------
    if tool_name.startswith("pagerduty_"):
        return await _dispatch_pagerduty_tool(user_id, tool_name, args, db)

    # Google Drive integration tools ------------------------------------------------
    if tool_name.startswith("gdrive_"):
        return await _dispatch_google_drive_tool(user_id, tool_name, args, db)

    # Zoom integration tools --------------------------------------------------------
    if tool_name.startswith("zoom_"):
        return await _dispatch_zoom_tool(user_id, tool_name, args, db)

    # Google Calendar integration tools ---------------------------------------------
    if tool_name.startswith("gcalendar_"):
        return await _dispatch_google_calendar_tool(user_id, tool_name, args, db)

    # Monday.com integration tools --------------------------------------------------
    if tool_name.startswith("monday_"):
        return await _dispatch_monday_tool(user_id, tool_name, args, db)

    # Datadog integration tools -----------------------------------------------------
    if tool_name.startswith("datadog_"):
        return await _dispatch_datadog_tool(user_id, tool_name, args, db)

    # Deployment tools -------------------------------------------------------------
    if tool_name.startswith("deploy_"):
        return await _dispatch_deployment_tool(user_id, tool_name, args, workspace)

    # Scaffolding tools -------------------------------------------------------------
    if tool_name.startswith("scaffold_"):
        return await _dispatch_scaffolding_tool(user_id, tool_name, args, workspace)

    # Test generation tools ---------------------------------------------------------
    if tool_name.startswith("test_"):
        return await _dispatch_test_generation_tool(user_id, tool_name, args, workspace)

    # Documentation tools -----------------------------------------------------------
    if tool_name.startswith("docs_"):
        return await _dispatch_documentation_tool(user_id, tool_name, args, workspace)

    # Infrastructure tools (Phase 2) ---------------------------------------------
    if tool_name.startswith("infra_"):
        return await _dispatch_infrastructure_tool(user_id, tool_name, args, workspace)

    # Database tools (Phase 2) ---------------------------------------------------
    if tool_name.startswith("db_"):
        return await _dispatch_database_tool(user_id, tool_name, args, workspace)

    # Monitoring tools (Phase 2) -------------------------------------------------
    if tool_name.startswith("monitor_"):
        return await _dispatch_monitoring_tool(user_id, tool_name, args, workspace)

    # Secrets tools (Phase 2) ----------------------------------------------------
    if tool_name.startswith("secrets_"):
        return await _dispatch_secrets_tool(user_id, tool_name, args, workspace)

    # Phase 3 Tools ----------------------------------------------------------------
    if tool_name.startswith("arch_"):
        return await _dispatch_architecture_tool(user_id, tool_name, args, workspace)

    if tool_name.startswith("gitlab_ci_"):
        return await _dispatch_gitlab_ci_tool(user_id, tool_name, args, workspace)

    if tool_name.startswith("cloud_"):
        return await _dispatch_multicloud_tool(user_id, tool_name, args, workspace)

    # Enterprise Tools (Phase 6) -----------------------------------------------
    if tool_name.startswith("compliance_"):
        return await _dispatch_compliance_tool(user_id, tool_name, args, workspace)

    if tool_name.startswith("loadtest_"):
        return await _dispatch_loadtest_tool(user_id, tool_name, args, workspace)

    if tool_name.startswith("k8s_"):
        return await _dispatch_k8s_lifecycle_tool(user_id, tool_name, args, workspace)

    # Web tools - fetch URLs and search the web ----------------------------------
    if tool_name.startswith("web_"):
        return await _dispatch_web_tool(user_id, tool_name, args)

    # Project-management stubs (future expansion) --------------------------------
    if tool_name.startswith("pm_"):
        return {
            "tool": tool_name,
            "text": (
                f"pm-tool '{tool_name}' is not fully implemented yet in this build. "
                "NAVI can still help you reason about tickets and next actions."
            ),
        }

    # Fallback – unknown tool ---------------------------------------------------
    logger.warning("[TOOLS] Unknown tool: %s", tool_name)
    return {
        "tool": tool_name,
        "text": f"Tool '{tool_name}' is not implemented in this NAVI build.",
    }


# ---------------------------------------------------------------------------
# Workspace helpers
# ---------------------------------------------------------------------------


def _resolve_root(args: Dict[str, Any]) -> Path:
    """
    Decide which workspace root to use for this tool call.

    Priority:
      1) args["root"] if provided
      2) NAVI_WORKSPACE_ROOT env
      3) current working directory
    """
    root_arg = args.get("root")
    if root_arg:
        root = Path(root_arg).expanduser().resolve()
        try:
            root.relative_to(DEFAULT_WORKSPACE_ROOT)
        except ValueError:
            raise ValueError(
                f"Provided root path '{root_arg}' is not allowed; must be inside {DEFAULT_WORKSPACE_ROOT}."
            )
    else:
        root = DEFAULT_WORKSPACE_ROOT

    return root


async def _tool_repo_inspect(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Safe tool: inspect current repository structure and produce a natural-language overview.

    Uses VS Code attachments when available, falls back to filesystem scan.
    """
    from backend.services.llm import call_llm

    args.get("user_id", "default_user")
    workspace = args.get("workspace", {})
    attachments = args.get("attachments")
    message = args.get("message", "Explain this repository and its structure.")
    model = args.get("model", "gpt-4o-mini")
    mode = args.get("mode", "agent-full")

    logger.info(
        "[TOOLS] repo.inspect workspace=%s attachments=%d",
        workspace,
        len(attachments or []),
    )

    # Get workspace context using perfect workspace retriever
    from backend.agent.perfect_workspace_retriever import (
        retrieve_workspace_sync,
    )

    workspace_ctx = retrieve_workspace_sync(workspace.get("workspace_root", ""))

    # Build system context for the LLM
    system_context = (
        "You are NAVI, an autonomous engineering assistant inspecting the user's repo.\n"
        "You are given:\n"
        f"- Project root identifier: {workspace_ctx.get('project_root')}\n"
        f"- Active file: {workspace_ctx.get('active_file')}\n"
        "- Recent files and a shallow file tree.\n"
        "- Small file contents when available.\n\n"
        "Based on this, explain:\n"
        "1) What this project appears to be about (in plain language).\n"
        "2) The main components / layers (e.g. api, backend, frontend, infra).\n"
        "3) How you would onboard: what files to read first, how to run it.\n"
        "If data is incomplete, be honest, but use whatever structure is visible "
        "instead of generic boilerplate."
    )

    # Build compact context from workspace data
    tree_lines = []
    for node in workspace_ctx.get("file_tree") or []:
        if isinstance(node, dict):
            tree_lines.append(f"- {node.get('path', node)}")
        else:
            tree_lines.append(f"- {node}")

    files_blob = "\n".join(
        f"# {f['path']}\n{f.get('content','')[:2000]}\n"
        for f in (workspace_ctx.get("small_files") or [])[:5]
    )

    context_text = (
        "FILE TREE (from VS Code attachments):\n"
        + "\n".join(tree_lines[:20])  # Limit to prevent token overflow
        + "\n\nSAMPLED FILE CONTENTS:\n"
        + files_blob
    )

    # Use LLM to generate intelligent repository overview
    try:
        reply = await call_llm(
            message=message,
            context={"combined": system_context + "\n\n" + context_text},
            model=model,
            mode=mode,
        )
    except Exception as e:
        logger.error("[TOOLS] repo.inspect LLM call failed: %s", e)
        # Fallback to basic structure description
        reply = (
            f"Repository at {workspace_ctx.get('project_root')}\n\nFiles detected:\n"
            + "\n".join(tree_lines[:10])
        )

    return {
        "tool": "repo_inspect",
        "text": reply,
        "workspace_root": workspace_ctx.get("workspace_root"),
        "files_count": len(workspace_ctx.get("small_files") or []),
    }


async def _tool_code_read_files(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Read one or more files relative to the workspace root.

    Args:
      - files: List[str] of relative paths
      - max_chars: overall char limit
    """
    root = _resolve_root(args)
    files = args.get("files") or args.get("paths") or []
    max_chars = int(args.get("max_chars", 120_000))

    if isinstance(files, str):
        files = [files]

    results: List[Dict[str, Any]] = []
    total = 0

    for rel in files:
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts or rel_path == Path(""):
            results.append({"path": rel, "error": "invalid_path"})
            continue

        path = (root / rel_path).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            results.append({"path": rel, "error": "path_outside_workspace"})
            continue

        if not path.exists() or not path.is_file():
            results.append(
                {
                    "path": rel,
                    "error": "not_found",
                }
            )
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            results.append(
                {
                    "path": rel,
                    "error": f"read_error: {e}",
                }
            )
            continue

        if total + len(text) > max_chars:
            # clip last file if needed
            remaining = max_chars - total
            if remaining <= 0:
                break
            text = text[:remaining] + "\n… (truncated for length)"
            total = max_chars
        else:
            total += len(text)

        results.append(
            {
                "path": rel,
                "content": text,
            }
        )

        if total >= max_chars:
            break

    combined = []
    for f in results:
        if "content" in f:
            combined.append(f"\n\n# File: {f['path']}\n\n{f['content']}")

    combined_text = (
        "".join(combined) if combined else "No readable files were returned."
    )

    return {
        "tool": "code_read_files",
        "root": str(root),
        "files": results,
        "text": combined_text,
    }


async def _tool_code_search(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simple text search in the workspace.

    Args:
      - pattern: regex or plain text
      - globs: list of globs like ['**/*.py', '**/*.ts']
      - max_results: int
    """
    root = _resolve_root(args)
    pattern = str(args.get("pattern") or args.get("query") or "").strip()
    max_results = int(args.get("max_results", 50))
    globs = args.get("globs") or [
        "**/*.py",
        "**/*.ts",
        "**/*.tsx",
        "**/*.js",
        "**/*.jsx",
        "**/*.md",
    ]

    if not pattern:
        return {
            "tool": "code_search",
            "root": str(root),
            "matches": [],
            "text": "No search pattern provided.",
        }

    # Safely compile regex pattern to prevent injection attacks
    def _safe_compile_regex(pattern: str) -> Optional[re.Pattern]:
        """Safely compile regex pattern with validation and size limits."""
        # Limit pattern length to prevent ReDoS attacks
        if len(pattern) > 1000:
            return None

        # Check for dangerous regex constructs
        dangerous_patterns = [
            r"\(\?\#",  # Comments that could hide malicious code
            r"\(\?\=.*\)",  # Complex lookaheads
            r"\(\?\!.*\)",  # Complex lookbehinds
            r"\*\*+",  # Nested quantifiers
            r"\+\++",  # Nested quantifiers
            r"\{\d+,\}",  # Unbounded quantifiers
        ]

        for dangerous in dangerous_patterns:
            if re.search(dangerous, pattern):
                return None

        try:
            # Set reasonable timeout for compilation
            return re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        except (re.error, OverflowError, MemoryError):
            return None

    regex = _safe_compile_regex(pattern)

    matches: List[Dict[str, Any]] = []

    for g in globs:
        for path in root.glob(g):
            if len(matches) >= max_results:
                break
            if not path.is_file():
                continue

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for i, line in enumerate(text.splitlines()):
                if len(matches) >= max_results:
                    break
                if (regex and regex.search(line)) or (not regex and pattern in line):
                    matches.append(
                        {
                            "path": str(path.relative_to(root)),
                            "line": i + 1,
                            "snippet": line.strip()[:200],
                        }
                    )

        if len(matches) >= max_results:
            break

    if not matches:
        summary = f"No matches for '{pattern}' were found under {root}."
    else:
        summary_lines = [f"- {m['path']}:{m['line']} — {m['snippet']}" for m in matches]
        summary = (
            f"Found {len(matches)} match(es) for '{pattern}' under {root}:\n"
            + "\n".join(summary_lines)
        )

    return {
        "tool": "code_search",
        "root": str(root),
        "pattern": pattern,
        "matches": matches,
        "text": summary,
    }


# ---------------------------------------------------------------------------
# Jira tools
# ---------------------------------------------------------------------------


async def _tool_jira_list_assigned_issues(
    user_id: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """List Jira issues assigned to the current user"""
    from backend.agent.tools.jira_tools import list_assigned_issues_for_user
    from backend.core.db import get_db
    from sqlalchemy import text

    try:
        # Prepare context for the tool
        context = {
            "user_id": user_id,
            "user_name": args.get("assignee") or user_id,
            "jira_assignee": args.get("assignee"),
        }
        org_id = args.get("org_id")

        max_results = args.get("max_results", 20)
        local_db = db or next(get_db())

        # Guard: if Jira not connected or no issues ingested for this org, return a clear message
        count_sql = """
            SELECT COUNT(*) 
            FROM jira_issue ji 
            JOIN jira_connection jc ON jc.id = ji.connection_id
        """
        params = {}
        if org_id:
            count_sql += " WHERE jc.org_id = :org_id"
            params["org_id"] = org_id
        count = local_db.execute(text(count_sql), params).scalar() or 0
        if count == 0:
            return {
                "tool": "jira_list_assigned_issues_for_user",
                "text": (
                    "Jira is not connected or no issues are synced for this org. "
                    "Please connect Jira in the Connectors panel and run a sync."
                ),
                "sources": [],
            }

        # Call the Jira tool with unified sources output
        result = await list_assigned_issues_for_user(context, max_results)

        # Check for errors - handle both dict and ToolResult
        if isinstance(result, dict):
            if "error" in result:
                return {
                    "tool": "jira_list_assigned_issues_for_user",
                    "text": f"Error retrieving Jira issues: {result['error']}",
                }
            issues = result.get("issues", [])
            sources = result.get("sources", [])
        else:
            # Handle ToolResult
            issues = result.output if hasattr(result, "output") else []
            sources = result.sources if hasattr(result, "sources") else []

        # Format for LLM consumption
        if not issues:
            return {
                "tool": "jira_list_assigned_issues_for_user",
                "text": f"No Jira issues found assigned to user {user_id}",
                "sources": sources,
            }

        # Build a nice summary table
        issue_lines = []
        for issue in issues:
            status = issue.get("status", "Unknown")
            summary = issue.get("summary", "No summary")
            issue_key = issue.get("issue_key", "No key")
            issue_lines.append(f"• **{issue_key}** - {summary}\n  Status: {status}")

        text_summary = (
            f"Found {len(issues)} Jira issues assigned to you:\n\n"
            + "\n\n".join(issue_lines)
        )

        return {
            "tool": "jira_list_assigned_issues_for_user",
            "issues": issues,
            "sources": sources,  # Unified sources for UI
            "count": len(issues),
            "text": text_summary,
        }

    except Exception as e:
        logger.error("Jira list assigned issues error: %s", e)
        return {
            "tool": "jira_list_assigned_issues_for_user",
            "text": "Failed to fetch Jira issues - check your connection and credentials",
        }


async def _tool_jira_add_comment(
    user_id: str,
    args: Dict[str, Any],
    db=None,
) -> Dict[str, Any]:
    """Add a comment to a Jira issue."""
    from backend.services.jira import JiraService
    from backend.core.db import get_db

    issue_key = args.get("issue_key") or args.get("key")
    comment = args.get("comment")
    org_id = args.get("org_id")
    approved = args.get("approve") is True

    if not issue_key or not comment:
        return {
            "tool": "jira_add_comment",
            "text": "issue_key and comment are required to add a Jira comment.",
        }
    if not approved:
        return {
            "tool": "jira_add_comment",
            "text": "Approval required to post a Jira comment. Pass approve=true to proceed.",
        }

    local_db = db or next(get_db())

    try:
        await JiraService.add_comment(
            local_db,
            issue_key=issue_key,
            comment=comment,
            user_id=user_id,
            org_id=org_id,
        )

        return {
            "tool": "jira_add_comment",
            "text": f"Added comment to {issue_key}",
            "sources": [
                {
                    "name": issue_key,
                    "type": "jira",
                    "connector": "jira",
                }
            ],
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Jira add_comment error: %s", exc)
        return {
            "tool": "jira_add_comment",
            "text": f"Failed to add comment to {issue_key}: {exc}",
        }


async def _tool_jira_transition_issue(
    user_id: str,
    args: Dict[str, Any],
    db=None,
) -> Dict[str, Any]:
    """Transition a Jira issue to a new status."""
    from backend.services.jira import JiraService
    from backend.core.db import get_db

    issue_key = args.get("issue_key") or args.get("key")
    transition_id = args.get("transition_id")
    org_id = args.get("org_id")
    approved = args.get("approve") is True

    if not issue_key or not transition_id:
        return {
            "tool": "jira_transition_issue",
            "text": "issue_key and transition_id are required to transition a Jira issue.",
        }
    if not approved:
        return {
            "tool": "jira_transition_issue",
            "text": "Approval required to transition a Jira issue. Pass approve=true to proceed.",
        }

    local_db = db or next(get_db())

    try:
        await JiraService.transition_issue(
            local_db,
            issue_key=issue_key,
            transition_id=transition_id,
            user_id=user_id,
            org_id=org_id,
        )
        return {
            "tool": "jira_transition_issue",
            "text": f"Transitioned {issue_key} using transition {transition_id}",
            "sources": [
                {
                    "name": issue_key,
                    "type": "jira",
                    "connector": "jira",
                }
            ],
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("Jira transition_issue error: %s", exc)
        return {
            "tool": "jira_transition_issue",
            "text": f"Failed to transition {issue_key}: {exc}",
        }


async def _tool_jira_assign_issue(
    user_id: str,
    args: Dict[str, Any],
    db=None,
) -> Dict[str, Any]:
    """Assign a Jira issue to a user."""
    from backend.services.jira import JiraService
    from backend.core.db import get_db

    issue_key = args.get("issue_key") or args.get("key")
    org_id = args.get("org_id")
    assignee_account_id = args.get("assignee_account_id")
    assignee_name = args.get("assignee_name")
    approved = args.get("approve") is True

    if not issue_key or not assignee_account_id:
        return {
            "tool": "jira_assign_issue",
            "text": "issue_key and assignee_account_id are required to assign a Jira issue.",
        }
    if not approved:
        return {
            "tool": "jira_assign_issue",
            "text": "Approval required to assign a Jira issue. Pass approve=true to proceed.",
        }

    local_db = db or next(get_db())

    try:
        await JiraService.assign_issue(
            local_db,
            issue_key=issue_key,
            assignee_account_id=assignee_account_id,
            assignee_name=assignee_name,
            user_id=user_id,
            org_id=org_id,
        )
        return {
            "tool": "jira_assign_issue",
            "text": f"Assigned {issue_key} to {assignee_name or assignee_account_id}",
            "sources": [
                {
                    "name": issue_key,
                    "type": "jira",
                    "connector": "jira",
                }
            ],
        }
    except Exception:
        logger.error("Jira assign_issue error occurred")
        return {
            "tool": "jira_assign_issue",
            "text": "Failed to assign Jira issue due to an error",
        }


# ---------------------------------------------------------------------------
# GitHub tools (write operations)
# ---------------------------------------------------------------------------


async def _tool_github_comment(
    user_id: str,
    args: Dict[str, Any],
    db=None,
) -> Dict[str, Any]:
    """Add a comment to a GitHub issue or PR."""
    from backend.integrations.github.service import GitHubService
    from backend.core.crypto import decrypt_token
    from backend.core.db import get_db
    from backend.models.integrations import GhConnection

    repo_full_name = args.get("repo")
    number = args.get("number")
    comment = args.get("comment")
    org_id = args.get("org_id")
    approved = args.get("approve") is True

    if not (repo_full_name and number and comment):
        return {
            "tool": "github_comment",
            "text": "repo, number, and comment are required",
        }
    if not approved:
        return {
            "tool": "github_comment",
            "text": "Approval required. Pass approve=true to proceed.",
        }

    local_db = db or next(get_db())
    conn_q = local_db.query(GhConnection)
    if org_id:
        conn_q = conn_q.filter(GhConnection.org_id == org_id)
    conn = conn_q.order_by(GhConnection.id.desc()).first()
    if not conn:
        return {"tool": "github_comment", "text": "No GitHub connection found"}

    GitHubService(token=decrypt_token(conn.access_token or ""))
    try:
        # TODO: Implement add_comment method in GitHubService
        # await gh_client.add_comment(repo_full_name, number, comment)
        return {
            "tool": "github_comment",
            "text": f"GitHub comment functionality not yet implemented for {repo_full_name}#{number}",
            "sources": [
                {
                    "name": f"{repo_full_name}#{number}",
                    "type": "github",
                    "connector": "github",
                }
            ],
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("GitHub comment error: %s", exc)
        return {"tool": "github_comment", "text": f"Failed to add comment: {exc}"}


async def _tool_github_set_label(
    user_id: str,
    args: Dict[str, Any],
    db=None,
) -> Dict[str, Any]:
    """Set a label on a GitHub issue/PR."""
    from backend.core.db import get_db
    from backend.models.integrations import GhConnection

    repo_full_name = args.get("repo")
    number = args.get("number")
    labels = args.get("labels") or []
    org_id = args.get("org_id")
    approved = args.get("approve") is True

    if not (repo_full_name and number and labels):
        return {
            "tool": "github_set_label",
            "text": "repo, number, and labels are required",
        }
    if not approved:
        return {
            "tool": "github_set_label",
            "text": "Approval required. Pass approve=true to proceed.",
        }

    local_db = db or next(get_db())
    conn_q = local_db.query(GhConnection)
    if org_id:
        conn_q = conn_q.filter(GhConnection.org_id == org_id)
    conn = conn_q.order_by(GhConnection.id.desc()).first()
    if not conn:
        return {"tool": "github_set_label", "text": "No GitHub connection found"}

    # gh_client = GitHubService(token=decrypt_token(conn.access_token or ""))
    try:
        # TODO: Implement set_labels method in GitHubService
        # await gh_client.set_labels(repo_full_name, number, labels)
        return {
            "tool": "github_set_label",
            "text": f"GitHub label setting functionality not yet implemented for {repo_full_name}#{number}",
            "sources": [
                {
                    "name": f"{repo_full_name}#{number}",
                    "type": "github",
                    "connector": "github",
                }
            ],
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("GitHub set_label error: %s", exc)
        return {"tool": "github_set_label", "text": f"Failed to set labels: {exc}"}


async def _tool_github_rerun_check(
    user_id: str,
    args: Dict[str, Any],
    db=None,
) -> Dict[str, Any]:
    """Re-run a GitHub check suite/workflow for a commit/PR."""
    from backend.core.db import get_db
    from backend.models.integrations import GhConnection

    repo_full_name = args.get("repo")
    check_run_id = args.get("check_run_id")
    org_id = args.get("org_id")
    approved = args.get("approve") is True

    if not (repo_full_name and check_run_id):
        return {
            "tool": "github_rerun_check",
            "text": "repo and check_run_id are required",
        }
    if not approved:
        return {
            "tool": "github_rerun_check",
            "text": "Approval required. Pass approve=true to proceed.",
        }

    local_db = db or next(get_db())
    conn_q = local_db.query(GhConnection)
    if org_id:
        conn_q = conn_q.filter(GhConnection.org_id == org_id)
    conn = conn_q.order_by(GhConnection.id.desc()).first()
    if not conn:
        return {"tool": "github_rerun_check", "text": "No GitHub connection found"}

    # gh_client = GitHubService(token=decrypt_token(conn.access_token or ""))
    try:
        # TODO: Implement rerun_check_run method in GitHubService
        # await gh_client.rerun_check_run(repo_full_name, check_run_id)
        return {
            "tool": "github_rerun_check",
            "text": f"GitHub check run rerun functionality not yet implemented for {repo_full_name}",
            "sources": [
                {"name": f"{repo_full_name}", "type": "github", "connector": "github"}
            ],
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("GitHub rerun_check error: %s", exc)
        return {"tool": "github_rerun_check", "text": f"Failed to rerun check: {exc}"}


# ==============================================================================
# CODE TOOL IMPLEMENTATIONS
# ==============================================================================


async def _tool_code_create_file(user_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Create new file with content."""
    path = args.get("path")
    content = args.get("content", "")

    if not path:
        return {
            "tool": "code_create_file",
            "text": "❌ Path is required",
            "error": "Missing path parameter",
        }

    result = await create_file(user_id=user_id, path=path, content=content)

    return {
        "tool": "code_create_file",
        "text": result["message"],
        "success": result["success"],
        "path": result.get("path"),
        "error": result.get("error"),
    }


async def _tool_code_edit_file(user_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Edit existing file with content."""
    path = args.get("path")
    content = args.get("content", "")

    if not path:
        return {
            "tool": "code_edit_file",
            "text": "❌ Path is required",
            "error": "Missing path parameter",
        }

    result = await edit_file(user_id=user_id, path=path, new_content=content)

    return {
        "tool": "code_edit_file",
        "text": result["message"],
        "success": result["success"],
        "path": result.get("path"),
        "error": result.get("error"),
    }


async def _tool_code_apply_diff(user_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Apply unified diff to existing file."""
    path = args.get("path")
    diff = args.get("diff")
    old_content = args.get("old_content")

    if not path or not diff:
        return {
            "tool": "code_apply_diff",
            "text": "❌ Path and diff are required",
            "error": "Missing path or diff parameter",
        }

    result = await apply_diff(
        user_id=user_id, path=path, diff=diff, old_content=old_content
    )

    return {
        "tool": "code_apply_diff",
        "text": result["message"],
        "success": result["success"],
        "path": result.get("path"),
        "lines_changed": result.get("lines_changed"),
        "error": result.get("error"),
    }


async def _tool_code_run_command(user_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute safe terminal command."""
    command = args.get("command")
    cwd = args.get("cwd")
    timeout = args.get("timeout", 30)

    if not command:
        return {
            "tool": "code_run_command",
            "text": "❌ Command is required",
            "error": "Missing command parameter",
        }

    result = await run_command(
        user_id=user_id, command=command, cwd=cwd, timeout=timeout
    )

    return {
        "tool": "code_run_command",
        "text": result["message"],
        "success": result["success"],
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
        "exit_code": result.get("exit_code"),
        "error": result.get("error"),
    }


async def _tool_code_run_dangerous_command(
    user_id: str, args: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute dangerous command after approval."""
    command = args.get("command")
    approved = args.get("approved", False)
    skip_backup = args.get("skip_backup", False)
    cwd = args.get("cwd")
    timeout = args.get("timeout", 60)

    if not command:
        return {
            "tool": "code_run_dangerous_command",
            "text": "❌ Command is required",
            "error": "Missing command parameter",
        }

    result = await run_dangerous_command(
        user_id=user_id,
        command=command,
        approved=approved,
        skip_backup=skip_backup,
        cwd=cwd,
        timeout=timeout,
    )

    return {
        "tool": "code_run_dangerous_command",
        "text": result["message"],
        "success": result["success"],
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
        "exit_code": result.get("exit_code"),
        "backup": result.get("backup"),
        "rollback_instructions": result.get("rollback_instructions"),
        "error": result.get("error"),
    }


async def _tool_code_run_interactive_command(
    user_id: str, args: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute command with interactive prompt handling."""
    command = args.get("command")
    auto_yes = args.get("auto_yes", True)
    cwd = args.get("cwd")
    timeout = args.get("timeout", 120)

    if not command:
        return {
            "tool": "code_run_interactive_command",
            "text": "❌ Command is required",
            "error": "Missing command parameter",
        }

    result = await run_interactive_command(
        user_id=user_id,
        command=command,
        auto_yes=auto_yes,
        cwd=cwd,
        timeout=timeout,
    )

    return {
        "tool": "code_run_interactive_command",
        "text": result["message"],
        "success": result["success"],
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
        "exit_code": result.get("exit_code"),
        "prompts_answered": result.get("prompts_answered"),
        "error": result.get("error"),
    }


async def _tool_code_run_parallel_commands(
    user_id: str, args: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute multiple commands in parallel."""
    commands = args.get("commands", [])
    max_workers = args.get("max_workers", 4)
    stop_on_failure = args.get("stop_on_failure", False)
    cwd = args.get("cwd")
    timeout = args.get("timeout", 60)

    if not commands:
        return {
            "tool": "code_run_parallel_commands",
            "text": "❌ Commands list is required",
            "error": "Missing commands parameter",
        }

    result = await run_parallel_commands(
        user_id=user_id,
        commands=commands,
        cwd=cwd,
        timeout=timeout,
        max_workers=max_workers,
        stop_on_failure=stop_on_failure,
    )

    return {
        "tool": "code_run_parallel_commands",
        "text": result["message"],
        "success": result["success"],
        "results": result.get("results"),
        "summary": result.get("summary"),
        "error": result.get("error"),
    }


async def _tool_code_run_command_with_retry(
    user_id: str, args: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute command with automatic retry on failure."""
    command = args.get("command")
    max_retries = args.get("max_retries", 3)
    retry_delay = args.get("retry_delay", 1.0)
    cwd = args.get("cwd")
    timeout = args.get("timeout", 30)

    if not command:
        return {
            "tool": "code_run_command_with_retry",
            "text": "❌ Command is required",
            "error": "Missing command parameter",
        }

    result = await run_command_with_retry(
        user_id=user_id,
        command=command,
        max_retries=max_retries,
        retry_delay=retry_delay,
        cwd=cwd,
        timeout=timeout,
    )

    return {
        "tool": "code_run_command_with_retry",
        "text": result["message"],
        "success": result["success"],
        "attempts": result.get("attempts"),
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
        "exit_code": result.get("exit_code"),
        "error": result.get("error"),
    }


async def _tool_list_backups(user_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """List NAVI backups."""
    workspace_path = args.get("workspace_path", ".")

    result = await list_backups(workspace_path)

    return {
        "tool": "list_backups",
        "text": result["message"],
        "success": result["success"],
        "backups": result.get("backups"),
        "backup_directory": result.get("backup_directory"),
    }


async def _tool_restore_backup(user_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Restore a backup."""
    workspace_path = args.get("workspace_path", ".")
    backup_name = args.get("backup_name")
    target_path = args.get("target_path")

    if not backup_name:
        return {
            "tool": "restore_backup",
            "text": "❌ Backup name is required",
            "error": "Missing backup_name parameter",
        }

    result = await restore_backup(workspace_path, backup_name, target_path)

    return {
        "tool": "restore_backup",
        "text": result["message"],
        "success": result["success"],
        "backup_path": result.get("backup_path"),
        "target_path": result.get("target_path"),
        "error": result.get("error"),
    }


# ==============================================================================
# CONNECTOR TOOL DISPATCHERS
# ==============================================================================


async def _dispatch_linear_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Linear tools to their implementations."""
    from backend.agent.tools.linear_tools import LINEAR_TOOLS
    from backend.core.db import get_db

    db or next(get_db())

    # Build context for the tool
    context = {
        "user_id": user_id,
        "user_name": args.get("user_name") or args.get("assignee"),
        "org_id": args.get("org_id"),
        "linear_assignee": args.get("assignee"),
    }

    # Map tool name to function
    tool_func = LINEAR_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Linear tool '{tool_name}' is not implemented.",
        }

    try:
        # Call the tool with context and args
        if tool_name == "linear_list_my_issues":
            result = await tool_func(
                context,
                status=args.get("status"),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "linear_search_issues":
            result = await tool_func(
                context,
                query=args.get("query", ""),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "linear_create_issue":
            result = await tool_func(
                context,
                team_id=args.get("team_id"),
                title=args.get("title"),
                description=args.get("description"),
                priority=args.get("priority"),
                assignee_id=args.get("assignee_id"),
                approve=args.get("approve", False),
            )
        elif tool_name == "linear_update_status":
            result = await tool_func(
                context,
                issue_id=args.get("issue_id"),
                state_id=args.get("state_id"),
                approve=args.get("approve", False),
            )
        elif tool_name == "linear_list_teams":
            result = await tool_func(context)
        else:
            return {
                "tool": tool_name,
                "text": f"Linear tool '{tool_name}' dispatch not configured.",
            }

        # Convert ToolResult to dict for response
        return {
            "tool": tool_name,
            "text": result.output,
            "sources": result.sources,
        }

    except Exception as exc:
        logger.error("Linear tool error: %s - %s", tool_name, exc)
        return {
            "tool": tool_name,
            "text": f"Error executing Linear tool: {exc}",
        }


async def _dispatch_gitlab_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch GitLab tools to their implementations."""
    from backend.agent.tools.gitlab_tools import GITLAB_TOOLS
    from backend.core.db import get_db

    db or next(get_db())

    # Build context for the tool
    context = {
        "user_id": user_id,
        "user_name": args.get("user_name"),
        "org_id": args.get("org_id"),
        "gitlab_username": args.get("gitlab_username"),
    }

    # Map tool name to function
    tool_func = GITLAB_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"GitLab tool '{tool_name}' is not implemented.",
        }

    try:
        # Call the tool with context and args
        if tool_name == "gitlab_list_my_merge_requests":
            result = await tool_func(
                context,
                status=args.get("status"),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "gitlab_list_my_issues":
            result = await tool_func(
                context,
                status=args.get("status"),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "gitlab_get_pipeline_status":
            result = await tool_func(
                context,
                max_results=args.get("max_results", 10),
            )
        elif tool_name == "gitlab_search":
            result = await tool_func(
                context,
                query=args.get("query", ""),
                item_type=args.get("item_type"),
                max_results=args.get("max_results", 20),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"GitLab tool '{tool_name}' dispatch not configured.",
            }

        # Convert ToolResult to dict for response
        return {
            "tool": tool_name,
            "text": result.output,
            "sources": result.sources,
        }

    except Exception as exc:
        logger.error("GitLab tool error: %s - %s", tool_name, exc)
        return {
            "tool": tool_name,
            "text": f"Error executing GitLab tool: {exc}",
        }


async def _dispatch_notion_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Notion tools to their implementations."""
    from backend.agent.tools.notion_tools import NOTION_TOOLS
    from backend.core.db import get_db

    db or next(get_db())

    # Build context for the tool
    context = {
        "user_id": user_id,
        "org_id": args.get("org_id"),
    }

    # Map tool name to function
    tool_func = NOTION_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Notion tool '{tool_name}' is not implemented.",
        }

    try:
        # Call the tool with context and args
        if tool_name == "notion_search_pages":
            result = await tool_func(
                context,
                query=args.get("query", ""),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "notion_list_recent_pages":
            result = await tool_func(
                context,
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "notion_get_page_content":
            result = await tool_func(
                context,
                page_id=args.get("page_id"),
            )
        elif tool_name == "notion_list_databases":
            result = await tool_func(
                context,
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "notion_create_page":
            result = await tool_func(
                context,
                parent_id=args.get("parent_id"),
                title=args.get("title"),
                content=args.get("content"),
                is_database=args.get("is_database", False),
                approve=args.get("approve", False),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Notion tool '{tool_name}' dispatch not configured.",
            }

        # Convert ToolResult to dict for response
        return {
            "tool": tool_name,
            "text": result.output,
            "sources": result.sources,
        }

    except Exception as exc:
        logger.error("Notion tool error: %s - %s", tool_name, exc)
        return {
            "tool": tool_name,
            "text": f"Error executing Notion tool: {exc}",
        }


async def _dispatch_slack_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Slack tools to their implementations."""
    from backend.agent.tools.slack_tools import SLACK_TOOLS
    from backend.core.db import get_db

    db or next(get_db())

    # Build context for the tool
    context = {
        "user_id": user_id,
        "org_id": args.get("org_id"),
    }

    # Map tool name to function
    tool_func = SLACK_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Slack tool '{tool_name}' is not implemented.",
        }

    try:
        # Call the tool with context and args
        if tool_name == "slack_search_messages":
            result = await tool_func(
                context,
                query=args.get("query", ""),
                channel=args.get("channel"),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "slack_list_channel_messages":
            result = await tool_func(
                context,
                channel=args.get("channel"),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "slack_send_message":
            result = await tool_func(
                context,
                channel=args.get("channel"),
                message=args.get("message"),
                thread_ts=args.get("thread_ts"),
                approve=args.get("approve", False),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Slack tool '{tool_name}' dispatch not configured.",
            }

        # Convert ToolResult to dict for response
        return {
            "tool": tool_name,
            "text": result.output,
            "sources": result.sources,
        }

    except Exception as exc:
        logger.error("Slack tool error: %s - %s", tool_name, exc)
        return {
            "tool": tool_name,
            "text": f"Error executing Slack tool: {exc}",
        }


async def _dispatch_asana_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Asana tools to their implementations."""
    from backend.agent.tools.asana_tools import ASANA_TOOLS
    from backend.core.db import get_db

    db or next(get_db())

    # Build context for the tool
    context = {
        "user_id": user_id,
        "user_name": args.get("user_name"),
        "org_id": args.get("org_id"),
    }

    # Map tool name to function
    tool_func = ASANA_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Asana tool '{tool_name}' is not implemented.",
        }

    try:
        # Call the tool with context and args
        if tool_name == "asana_list_my_tasks":
            result = await tool_func(
                context,
                status=args.get("status"),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "asana_search_tasks":
            result = await tool_func(
                context,
                query=args.get("query", ""),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "asana_list_projects":
            result = await tool_func(
                context,
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "asana_create_task":
            result = await tool_func(
                context,
                name=args.get("name"),
                project_gid=args.get("project_gid"),
                workspace_gid=args.get("workspace_gid"),
                notes=args.get("notes"),
                due_on=args.get("due_on"),
                approve=args.get("approve", False),
            )
        elif tool_name == "asana_complete_task":
            result = await tool_func(
                context,
                task_gid=args.get("task_gid"),
                approve=args.get("approve", False),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Asana tool '{tool_name}' dispatch not configured.",
            }

        # Convert ToolResult to dict for response
        return {
            "tool": tool_name,
            "text": result.output,
            "sources": result.sources,
        }

    except Exception as exc:
        logger.error("Asana tool error: %s - %s", tool_name, exc)
        return {
            "tool": tool_name,
            "text": f"Error executing Asana tool: {exc}",
        }


async def _dispatch_bitbucket_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Bitbucket tools to their implementations."""
    from backend.agent.tools.bitbucket_tools import BITBUCKET_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = BITBUCKET_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Bitbucket tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Bitbucket tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Bitbucket tool: {exc}"}


async def _dispatch_discord_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Discord tools to their implementations."""
    from backend.agent.tools.discord_tools import DISCORD_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = DISCORD_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Discord tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Discord tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Discord tool: {exc}"}


async def _dispatch_loom_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Loom tools to their implementations."""
    from backend.agent.tools.loom_tools import LOOM_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = LOOM_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Loom tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Loom tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Loom tool: {exc}"}


async def _dispatch_trello_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Trello tools to their implementations."""
    from backend.agent.tools.trello_tools import TRELLO_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = TRELLO_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Trello tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Trello tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Trello tool: {exc}"}


async def _dispatch_clickup_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch ClickUp tools to their implementations."""
    from backend.agent.tools.clickup_tools import CLICKUP_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = CLICKUP_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"ClickUp tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("ClickUp tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing ClickUp tool: {exc}"}


async def _dispatch_sonarqube_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch SonarQube tools to their implementations."""
    from backend.agent.tools.sonarqube_tools import SONARQUBE_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = SONARQUBE_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"SonarQube tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("SonarQube tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing SonarQube tool: {exc}"}


async def _dispatch_confluence_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Confluence tools to their implementations."""
    from backend.agent.tools.confluence_tools import CONFLUENCE_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = CONFLUENCE_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Confluence tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Confluence tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Confluence tool: {exc}"}


async def _dispatch_figma_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Figma tools to their implementations."""
    from backend.agent.tools.figma_tools import FIGMA_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = FIGMA_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Figma tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Figma tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Figma tool: {exc}"}


async def _dispatch_sentry_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Sentry tools to their implementations."""
    from backend.agent.tools.sentry_tools import SENTRY_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = SENTRY_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Sentry tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Sentry tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Sentry tool: {exc}"}


async def _dispatch_snyk_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Snyk tools to their implementations."""
    from backend.agent.tools.snyk_tools import SNYK_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = SNYK_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Snyk tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Snyk tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Snyk tool: {exc}"}


async def _dispatch_github_actions_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch GitHub Actions tools to their implementations."""
    from backend.agent.tools.github_actions_tools import GITHUB_ACTIONS_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = GITHUB_ACTIONS_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"GitHub Actions tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("GitHub Actions tool error: %s - %s", tool_name, exc)
        return {
            "tool": tool_name,
            "text": f"Error executing GitHub Actions tool: {exc}",
        }


async def _dispatch_circleci_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch CircleCI tools to their implementations."""
    from backend.agent.tools.circleci_tools import CIRCLECI_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = CIRCLECI_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"CircleCI tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("CircleCI tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing CircleCI tool: {exc}"}


async def _dispatch_vercel_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Vercel tools to their implementations."""
    from backend.agent.tools.vercel_tools import VERCEL_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = VERCEL_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Vercel tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Vercel tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Vercel tool: {exc}"}


async def _dispatch_pagerduty_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch PagerDuty tools to their implementations."""
    from backend.agent.tools.pagerduty_tools import PAGERDUTY_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = PAGERDUTY_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"PagerDuty tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("PagerDuty tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing PagerDuty tool: {exc}"}


async def _dispatch_google_drive_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Google Drive tools to their implementations."""
    from backend.agent.tools.google_drive_tools import GOOGLE_DRIVE_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = GOOGLE_DRIVE_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Google Drive tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Google Drive tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Google Drive tool: {exc}"}


async def _dispatch_zoom_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Zoom tools to their implementations."""
    from backend.agent.tools.zoom_tools import ZOOM_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = ZOOM_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Zoom tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Zoom tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Zoom tool: {exc}"}


async def _dispatch_google_calendar_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Google Calendar tools to their implementations."""
    from backend.agent.tools.google_calendar_tools import GOOGLE_CALENDAR_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = GOOGLE_CALENDAR_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Google Calendar tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Google Calendar tool error: %s - %s", tool_name, exc)
        return {
            "tool": tool_name,
            "text": f"Error executing Google Calendar tool: {exc}",
        }


async def _dispatch_monday_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Monday.com tools to their implementations."""
    from backend.agent.tools.monday_tools import MONDAY_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = MONDAY_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Monday.com tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Monday.com tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Monday.com tool: {exc}"}


async def _dispatch_datadog_tool(
    user_id: str, tool_name: str, args: Dict[str, Any], db=None
) -> Dict[str, Any]:
    """Dispatch Datadog tools to their implementations."""
    from backend.agent.tools.datadog_tools import DATADOG_TOOLS

    context = {"user_id": user_id, "org_id": args.get("org_id")}
    tool_func = DATADOG_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Datadog tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(
            context, **{k: v for k, v in args.items() if k not in ["org_id"]}
        )
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Datadog tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Datadog tool: {exc}"}


async def _dispatch_deployment_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch deployment tools to their implementations."""
    from backend.agent.tools.deployment_tools import DEPLOYMENT_TOOLS

    # Include credentials from credentials service
    cred_service = get_credentials_service()
    context = {
        "user_id": user_id,
        "credentials": {
            "vercel": cred_service.get_provider_credentials("vercel"),
            "netlify": cred_service.get_provider_credentials("netlify"),
            "aws": cred_service.get_provider_credentials("aws"),
            "gcp": cred_service.get_provider_credentials("gcp"),
            "azure": cred_service.get_provider_credentials("azure"),
            "github": cred_service.get_provider_credentials("github"),
        },
    }

    # Get workspace path for project detection
    workspace_path = None
    if workspace:
        workspace_path = workspace.get("workspace_root")

    tool_func = DEPLOYMENT_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Deployment tool '{tool_name}' is not implemented.",
        }

    try:
        # Call tools with appropriate arguments
        if tool_name == "deploy_detect_project":
            result = await tool_func(context, workspace_path=workspace_path)
        elif tool_name == "deploy_check_cli":
            platform = args.get("platform", "")
            result = await tool_func(context, platform=platform)
        elif tool_name == "deploy_get_info":
            platform = args.get("platform", "")
            result = await tool_func(context, platform=platform)
        elif tool_name == "deploy_list_platforms":
            result = await tool_func(context)
        elif tool_name == "deploy_execute":
            platform = args.get("platform", "")
            environment = args.get("environment", "production")
            env_vars = args.get("env_vars", {})
            dry_run = args.get("dry_run", False)
            result = await tool_func(
                context,
                platform=platform,
                workspace_path=workspace_path,
                environment=environment,
                env_vars=env_vars,
                dry_run=dry_run,
            )
        elif tool_name == "deploy_confirm":
            request_id = args.get("request_id", "")
            confirmation_phrase = args.get("confirmation_phrase")
            result = await tool_func(
                context,
                request_id=request_id,
                confirmation_phrase=confirmation_phrase,
            )
        elif tool_name == "deploy_rollback":
            platform = args.get("platform", "")
            deployment_id = args.get("deployment_id", "")
            result = await tool_func(
                context,
                platform=platform,
                deployment_id=deployment_id,
                workspace_path=workspace_path,
            )
        elif tool_name == "deploy_status":
            platform = args.get("platform", "")
            deployment_id = args.get("deployment_id", "")
            result = await tool_func(
                context,
                platform=platform,
                deployment_id=deployment_id,
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Deployment tool '{tool_name}' dispatch not configured.",
            }

        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Deployment tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing deployment tool: {exc}"}


async def _dispatch_scaffolding_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch scaffolding tools to their implementations."""
    from backend.agent.tools.scaffolding_tools import SCAFFOLDING_TOOLS

    context = {"user_id": user_id}

    # Get workspace path
    workspace_path = None
    if workspace:
        workspace_path = workspace.get("workspace_root")

    tool_func = SCAFFOLDING_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Scaffolding tool '{tool_name}' is not implemented.",
        }

    try:
        if tool_name == "scaffold_project":
            result = await tool_func(
                context,
                project_name=args.get("project_name", args.get("name", "")),
                project_type=args.get("project_type", args.get("type", "nextjs")),
                parent_directory=args.get("parent_directory", workspace_path or "."),
                description=args.get("description"),
                typescript=args.get("typescript", True),
                git_init=args.get("git_init", True),
                install_dependencies=args.get("install_dependencies", True),
            )
        elif tool_name == "scaffold_detect_requirements":
            result = await tool_func(
                context,
                description=args.get("description", ""),
            )
        elif tool_name == "scaffold_add_feature":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                feature_type=args.get("feature_type", args.get("type", "")),
                feature_name=args.get("feature_name", args.get("name", "")),
            )
        elif tool_name == "scaffold_list_templates":
            result = await tool_func(context)
        else:
            return {
                "tool": tool_name,
                "text": f"Scaffolding tool '{tool_name}' dispatch not configured.",
            }

        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Scaffolding tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing scaffolding tool: {exc}"}


async def _dispatch_test_generation_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch test generation tools to their implementations."""
    from backend.agent.tools.test_generation_tools import TEST_GENERATION_TOOLS

    context = {"user_id": user_id}

    # Get workspace path
    workspace_path = None
    if workspace:
        workspace_path = workspace.get("workspace_root")

    tool_func = TEST_GENERATION_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Test generation tool '{tool_name}' is not implemented.",
        }

    try:
        if tool_name == "test_generate_for_file":
            result = await tool_func(
                context,
                file_path=args.get("file_path", args.get("file", "")),
                test_type=args.get("test_type", "unit"),
                framework=args.get("framework"),
                coverage_target=args.get("coverage_target", 0.8),
                workspace_path=args.get("workspace_path", workspace_path),
            )
        elif tool_name == "test_generate_for_function":
            result = await tool_func(
                context,
                file_path=args.get("file_path", args.get("file", "")),
                function_name=args.get("function_name", args.get("function", "")),
                framework=args.get("framework"),
                workspace_path=args.get("workspace_path", workspace_path),
            )
        elif tool_name == "test_generate_suite":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                scope=args.get("scope", "changed"),
                test_type=args.get("test_type", "unit"),
                framework=args.get("framework"),
            )
        elif tool_name == "test_detect_framework":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
            )
        elif tool_name == "test_suggest_improvements":
            result = await tool_func(
                context,
                test_file_path=args.get("test_file_path", args.get("file", "")),
                workspace_path=args.get("workspace_path", workspace_path),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Test generation tool '{tool_name}' dispatch not configured.",
            }

        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Test generation tool error: %s - %s", tool_name, exc)
        return {
            "tool": tool_name,
            "text": f"Error executing test generation tool: {exc}",
        }


async def _dispatch_documentation_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch documentation tools to their implementations."""
    from backend.agent.tools.documentation_tools import DOCUMENTATION_TOOLS

    context = {"user_id": user_id}

    # Get workspace path
    workspace_path = None
    if workspace:
        workspace_path = workspace.get("workspace_root")

    tool_func = DOCUMENTATION_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Documentation tool '{tool_name}' is not implemented.",
        }

    try:
        if tool_name == "docs_generate_readme":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                include_badges=args.get("include_badges", True),
                include_toc=args.get("include_toc", True),
                style=args.get("style", "standard"),
            )
        elif tool_name == "docs_generate_api":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                format=args.get("format", "markdown"),
                output_path=args.get("output_path"),
            )
        elif tool_name == "docs_generate_component":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                component_path=args.get("component_path"),
            )
        elif tool_name == "docs_generate_architecture":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                include_diagrams=args.get("include_diagrams", True),
            )
        elif tool_name == "docs_generate_comments":
            result = await tool_func(
                context,
                file_path=args.get("file_path", args.get("file", "")),
                workspace_path=args.get("workspace_path", workspace_path),
                style=args.get("style", "jsdoc"),
            )
        elif tool_name == "docs_generate_changelog":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                version=args.get("version"),
                since_tag=args.get("since_tag"),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Documentation tool '{tool_name}' dispatch not configured.",
            }

        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Documentation tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing documentation tool: {exc}"}


async def _dispatch_infrastructure_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch infrastructure tools to their implementations."""
    from backend.agent.tools.infrastructure_tools import INFRASTRUCTURE_TOOLS

    # Include cloud credentials from credentials service
    cred_service = get_credentials_service()
    context = {
        "user_id": user_id,
        "credentials": {
            "aws": cred_service.get_provider_credentials("aws"),
            "gcp": cred_service.get_provider_credentials("gcp"),
            "azure": cred_service.get_provider_credentials("azure"),
            "digitalocean": cred_service.get_provider_credentials("digitalocean"),
        },
    }
    workspace_path = workspace.get("workspace_root") if workspace else None

    tool_func = INFRASTRUCTURE_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Infrastructure tool '{tool_name}' is not implemented.",
        }

    try:
        if tool_name == "infra_generate_terraform":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                cloud_provider=args.get("cloud_provider", args.get("provider", "aws")),
                resources=args.get("resources", []),
                output_dir=args.get("output_dir", "terraform"),
            )
        elif tool_name == "infra_generate_cloudformation":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                resources=args.get("resources", []),
                output_path=args.get("output_path", "cloudformation.yaml"),
            )
        elif tool_name == "infra_generate_k8s":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                app_name=args.get("app_name", args.get("name", "app")),
                image=args.get("image"),
                replicas=args.get("replicas", 2),
                port=args.get("port", 8080),
                env_vars=args.get("env_vars"),
                host=args.get("host"),
            )
        elif tool_name == "infra_generate_docker_compose":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                services=args.get("services"),
            )
        elif tool_name == "infra_generate_helm":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                chart_name=args.get("chart_name", args.get("name", "app")),
                app_version=args.get("app_version", "1.0.0"),
            )
        elif tool_name == "infra_analyze_needs":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
            )
        # Execution tools (require approval)
        elif tool_name == "infra_terraform_plan":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                working_dir=args.get("working_dir", "."),
                var_file=args.get("var_file"),
            )
        elif tool_name == "infra_terraform_apply":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                working_dir=args.get("working_dir", "."),
                var_file=args.get("var_file"),
                approve=args.get("approve", False),
            )
        elif tool_name == "infra_terraform_destroy":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                working_dir=args.get("working_dir", "."),
                approve=args.get("approve", False),
            )
        elif tool_name == "infra_kubectl_apply":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                manifest_path=args.get("manifest_path", ""),
                namespace=args.get("namespace"),
                dry_run=args.get("dry_run", True),
                approve=args.get("approve", False),
            )
        elif tool_name == "infra_helm_install":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                chart_path=args.get("chart_path", "."),
                release_name=args.get("release_name", "release"),
                namespace=args.get("namespace"),
                values_file=args.get("values_file"),
                approve=args.get("approve", False),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Infrastructure tool '{tool_name}' dispatch not configured.",
            }

        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Infrastructure tool error: %s - %s", tool_name, exc)
        return {
            "tool": tool_name,
            "text": f"Error executing infrastructure tool: {exc}",
        }


async def _dispatch_database_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch database tools to their implementations."""
    from backend.agent.tools.database_tools import DATABASE_TOOLS
    from backend.agent.tools.advanced_database_tools import ADVANCED_DATABASE_TOOLS

    context = {"user_id": user_id}
    workspace_path = workspace.get("workspace_root") if workspace else None

    # Check basic database tools first
    tool_func = DATABASE_TOOLS.get(tool_name)

    # If not found, check advanced database tools (Phase 6)
    if not tool_func:
        advanced_config = ADVANCED_DATABASE_TOOLS.get(tool_name)
        if advanced_config:
            return await _dispatch_advanced_database_tool(
                user_id, tool_name, args, workspace, advanced_config
            )
        return {
            "tool": tool_name,
            "text": f"Database tool '{tool_name}' is not implemented.",
        }

    try:
        if tool_name == "db_design_schema":
            result = await tool_func(
                context,
                description=args.get("description", ""),
                database_type=args.get("database_type", "postgresql"),
                orm=args.get("orm"),
            )
        elif tool_name == "db_generate_migration":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                changes=args.get("changes", []),
                migration_name=args.get("migration_name", "migration"),
            )
        elif tool_name == "db_run_migration":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                direction=args.get("direction", "up"),
                dry_run=args.get("dry_run", False),
            )
        elif tool_name == "db_generate_seed":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                models=args.get("models", []),
                count=args.get("count", 10),
            )
        elif tool_name == "db_analyze_schema":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
            )
        elif tool_name == "db_generate_erd":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                format=args.get("format", "mermaid"),
            )
        # Real execution tools
        elif tool_name == "db_execute_migration":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                direction=args.get("direction", "up"),
                target=args.get("target"),
                dry_run=args.get("dry_run", False),
            )
        elif tool_name == "db_confirm":
            result = await tool_func(
                context,
                request_id=args.get("request_id", ""),
                confirmation_input=args.get("confirmation_input"),
            )
        elif tool_name == "db_backup":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                database_url=args.get("database_url"),
                output_path=args.get("output_path"),
                compression=args.get("compression", True),
            )
        elif tool_name == "db_restore":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                backup_path=args.get("backup_path", ""),
                database_url=args.get("database_url"),
            )
        elif tool_name == "db_status":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Database tool '{tool_name}' dispatch not configured.",
            }

        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Database tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing database tool: {exc}"}


async def _dispatch_advanced_database_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch advanced database tools (Phase 6) to their implementations."""
    workspace_path = workspace.get("workspace_root") if workspace else "."

    if not tool_config:
        return {
            "tool": tool_name,
            "text": f"Advanced database tool '{tool_name}' has no configuration.",
        }

    tool_func = tool_config.get("function")
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Advanced database tool '{tool_name}' has no function defined.",
        }

    try:
        if tool_name == "db_orchestrate_migration":
            result = await tool_func(
                workspace_path=args.get("workspace_path", workspace_path),
                migration_tool=args.get("migration_tool"),
                direction=args.get("direction", "up"),
                target=args.get("target"),
                dry_run=args.get("dry_run", True),
                backup_first=args.get("backup_first", True),
            )
        elif tool_name == "db_setup_replication":
            result = await tool_func(
                database_type=args.get("database_type", "postgresql"),
                replication_type=args.get("replication_type", "streaming"),
                primary_host=args.get("primary_host", ""),
                replica_hosts=args.get("replica_hosts", []),
                replication_user=args.get("replication_user", "replicator"),
                workspace_path=args.get("workspace_path", workspace_path),
            )
        elif tool_name == "db_configure_sharding":
            result = await tool_func(
                database_type=args.get("database_type", "postgresql"),
                sharding_strategy=args.get("sharding_strategy", "hash"),
                shard_key=args.get("shard_key", ""),
                num_shards=args.get("num_shards", 4),
                tables=args.get("tables", []),
                workspace_path=args.get("workspace_path", workspace_path),
            )
        elif tool_name == "db_backup_restore":
            result = await tool_func(
                database_type=args.get("database_type", "postgresql"),
                action=args.get("action", "backup"),
                connection_string=args.get("connection_string"),
                backup_path=args.get("backup_path"),
                compression=args.get("compression", True),
                include_schema=args.get("include_schema", True),
                include_data=args.get("include_data", True),
                tables=args.get("tables"),
                workspace_path=args.get("workspace_path", workspace_path),
            )
        elif tool_name == "db_analyze_query_performance":
            result = await tool_func(
                database_type=args.get("database_type", "postgresql"),
                connection_string=args.get("connection_string"),
                query=args.get("query"),
                log_path=args.get("log_path"),
                analyze_mode=args.get("analyze_mode", "explain"),
                top_n=args.get("top_n", 10),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Advanced database tool '{tool_name}' dispatch not configured.",
            }

        # Format result for display
        if isinstance(result, dict):
            import json

            text = json.dumps(result, indent=2, default=str)
        else:
            text = str(result)

        return {"tool": tool_name, "text": text}
    except Exception as exc:
        logger.error("Advanced database tool error: %s - %s", tool_name, exc)
        return {
            "tool": tool_name,
            "text": f"Error executing advanced database tool: {exc}",
        }


async def _dispatch_monitoring_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch monitoring tools to their implementations."""
    from backend.agent.tools.monitoring_tools import MONITORING_TOOLS

    context = {"user_id": user_id}
    workspace_path = workspace.get("workspace_root") if workspace else None

    tool_func = MONITORING_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Monitoring tool '{tool_name}' is not implemented.",
        }

    try:
        if tool_name == "monitor_setup_errors":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                provider=args.get("provider", "sentry"),
                dsn=args.get("dsn"),
            )
        elif tool_name == "monitor_setup_apm":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                provider=args.get("provider", "datadog"),
            )
        elif tool_name == "monitor_setup_logging":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                library=args.get("library"),
            )
        elif tool_name == "monitor_generate_health_checks":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
            )
        elif tool_name == "monitor_setup_alerting":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                provider=args.get("provider", "pagerduty"),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Monitoring tool '{tool_name}' dispatch not configured.",
            }

        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Monitoring tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing monitoring tool: {exc}"}


async def _dispatch_secrets_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch secrets tools to their implementations."""
    from backend.agent.tools.secrets_tools import SECRETS_TOOLS

    context = {"user_id": user_id}
    workspace_path = workspace.get("workspace_root") if workspace else None

    tool_func = SECRETS_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Secrets tool '{tool_name}' is not implemented.",
        }

    try:
        if tool_name == "secrets_generate_env":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
            )
        elif tool_name == "secrets_setup_provider":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                provider=args.get("provider", "vault"),
            )
        elif tool_name == "secrets_sync_to_platform":
            result = await tool_func(
                context,
                env_file=args.get("env_file", ".env"),
                platform=args.get("platform", "vercel"),
                environment=args.get("environment", "production"),
            )
        elif tool_name == "secrets_audit":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
            )
        elif tool_name == "secrets_rotate":
            result = await tool_func(
                context,
                workspace_path=args.get("workspace_path", workspace_path or "."),
                secrets=args.get("secrets", []),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Secrets tool '{tool_name}' dispatch not configured.",
            }

        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Secrets tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing secrets tool: {exc}"}


# ---------------------------------------------------------------------------
# Phase 3: Architecture Tools
# ---------------------------------------------------------------------------


async def _dispatch_architecture_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch architecture tools to their implementations."""
    from backend.agent.tools.architecture_tools import ARCHITECTURE_TOOLS

    context = {"user_id": user_id, **args}
    workspace_path = workspace.get("workspace_root") if workspace else None
    if workspace_path:
        context["workspace_path"] = workspace_path

    tool_func = ARCHITECTURE_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Architecture tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(context)
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Architecture tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing architecture tool: {exc}"}


# ---------------------------------------------------------------------------
# Phase 3: GitLab CI Tools
# ---------------------------------------------------------------------------


async def _dispatch_gitlab_ci_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch GitLab CI tools to their implementations."""
    from backend.agent.tools.gitlab_ci_tools import GITLAB_CI_TOOLS

    context = {"user_id": user_id, **args}
    workspace_path = workspace.get("workspace_root") if workspace else None
    if workspace_path:
        context["workspace_path"] = workspace_path

    tool_func = GITLAB_CI_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"GitLab CI tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(context)
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("GitLab CI tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing GitLab CI tool: {exc}"}


# ---------------------------------------------------------------------------
# Phase 3: Multi-Cloud Tools
# ---------------------------------------------------------------------------


async def _dispatch_multicloud_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch multi-cloud tools to their implementations."""
    from backend.agent.tools.multicloud_tools import MULTICLOUD_TOOLS

    context = {"user_id": user_id, **args}
    workspace_path = workspace.get("workspace_root") if workspace else None
    if workspace_path:
        context["workspace_path"] = workspace_path

    tool_func = MULTICLOUD_TOOLS.get(tool_name)
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Multi-cloud tool '{tool_name}' is not implemented.",
        }

    try:
        result = await tool_func(context)
        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Multi-cloud tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing multi-cloud tool: {exc}"}


async def _dispatch_web_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
) -> Dict[str, Any]:
    """Dispatch web tools (fetch URLs, search web) to their implementations."""
    if tool_name == "web_fetch_url":
        url = args.get("url", "")
        extract_text = args.get("extract_text", True)
        max_length = args.get("max_length")

        result = await fetch_url(
            user_id=user_id,
            url=url,
            extract_text=extract_text,
            max_length=max_length,
        )

        if result.get("success"):
            content = result.get("content", "")
            title = result.get("title", "")
            message = result.get("message", "")
            return {
                "tool": tool_name,
                "text": (
                    f"{message}\n\n**Title:** {title}\n\n{content}"
                    if title
                    else f"{message}\n\n{content}"
                ),
                "url": result.get("url"),
                "content_type": result.get("content_type"),
            }
        else:
            return {
                "tool": tool_name,
                "text": f"Failed to fetch URL: {result.get('error', 'Unknown error')}",
            }

    if tool_name == "web_search":
        query = args.get("query", "")
        max_results = args.get("max_results", 5)
        search_depth = args.get("search_depth", "basic")

        result = await search_web(
            user_id=user_id,
            query=query,
            max_results=max_results,
            search_depth=search_depth,
        )

        if result.get("success"):
            results = result.get("results", [])
            answer = result.get("answer", "")
            message = result.get("message", "")

            # Format results for display
            formatted_results = []
            for r in results:
                formatted_results.append(
                    f"**{r.get('title', 'Untitled')}**\n"
                    f"URL: {r.get('url', '')}\n"
                    f"{r.get('content', '')[:500]}..."
                )

            text = f"{message}\n\n"
            if answer:
                text += f"**Summary:** {answer}\n\n"
            text += "**Results:**\n\n" + "\n\n---\n\n".join(formatted_results)

            return {
                "tool": tool_name,
                "text": text,
                "query": query,
                "results": results,
            }
        else:
            return {
                "tool": tool_name,
                "text": f"Web search failed: {result.get('error', 'Unknown error')}",
            }

    return {
        "tool": tool_name,
        "text": f"Web tool '{tool_name}' is not implemented.",
    }


# ---------------------------------------------------------------------------
# Enterprise Tools Dispatch (Phase 6)
# ---------------------------------------------------------------------------


async def _dispatch_compliance_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch compliance tools (PCI-DSS, HIPAA, SOC2) to their implementations."""
    from backend.agent.tools.compliance_tools import COMPLIANCE_TOOLS

    workspace_path = workspace.get("workspace_root") if workspace else "."

    tool_config = COMPLIANCE_TOOLS.get(tool_name)
    if not tool_config:
        return {
            "tool": tool_name,
            "text": f"Compliance tool '{tool_name}' is not implemented.",
        }

    tool_func = tool_config.get("function")
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Compliance tool '{tool_name}' has no function defined.",
        }

    try:
        if tool_name == "compliance_check_pci_dss":
            result = await tool_func(
                workspace_path=args.get("workspace_path", workspace_path),
                scan_depth=args.get("scan_depth", "full"),
            )
        elif tool_name == "compliance_check_hipaa":
            result = await tool_func(
                workspace_path=args.get("workspace_path", workspace_path),
                scan_depth=args.get("scan_depth", "full"),
            )
        elif tool_name == "compliance_check_soc2":
            result = await tool_func(
                workspace_path=args.get("workspace_path", workspace_path),
                scan_depth=args.get("scan_depth", "full"),
            )
        elif tool_name == "compliance_audit_dependencies":
            result = await tool_func(
                workspace_path=args.get("workspace_path", workspace_path),
                include_dev=args.get("include_dev", False),
            )
        elif tool_name == "compliance_generate_report":
            result = await tool_func(
                workspace_path=args.get("workspace_path", workspace_path),
                frameworks=args.get("frameworks", ["pci-dss", "hipaa", "soc2"]),
                output_format=args.get("output_format", "markdown"),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Compliance tool '{tool_name}' dispatch not configured.",
            }

        # Format result for display
        if isinstance(result, dict):
            import json

            text = json.dumps(result, indent=2, default=str)
        else:
            text = str(result)

        return {"tool": tool_name, "text": text}
    except Exception as exc:
        logger.error("Compliance tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing compliance tool: {exc}"}


async def _dispatch_loadtest_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch load testing tools (k6, Locust) to their implementations."""
    from backend.agent.tools.load_testing_tools import LOAD_TESTING_TOOLS

    workspace_path = workspace.get("workspace_root") if workspace else "."

    tool_config = LOAD_TESTING_TOOLS.get(tool_name)
    if not tool_config:
        return {
            "tool": tool_name,
            "text": f"Load testing tool '{tool_name}' is not implemented.",
        }

    tool_func = tool_config.get("function")
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Load testing tool '{tool_name}' has no function defined.",
        }

    try:
        if tool_name == "loadtest_generate_k6":
            result = await tool_func(
                workspace_path=args.get("workspace_path", workspace_path),
                target_url=args.get("target_url", ""),
                test_type=args.get("test_type", "load"),
                duration=args.get("duration", "5m"),
                vus=args.get("vus", 10),
                endpoints=args.get("endpoints", []),
                thresholds=args.get("thresholds"),
            )
        elif tool_name == "loadtest_generate_locust":
            result = await tool_func(
                workspace_path=args.get("workspace_path", workspace_path),
                target_url=args.get("target_url", ""),
                test_type=args.get("test_type", "load"),
                users=args.get("users", 10),
                spawn_rate=args.get("spawn_rate", 1),
                endpoints=args.get("endpoints", []),
            )
        elif tool_name == "loadtest_run":
            result = await tool_func(
                workspace_path=args.get("workspace_path", workspace_path),
                tool=args.get("tool", "k6"),
                script_path=args.get("script_path", ""),
                output_format=args.get("output_format", "json"),
                env_vars=args.get("env_vars", {}),
            )
        elif tool_name == "loadtest_analyze_results":
            result = await tool_func(
                results_path=args.get("results_path", ""),
                baseline_path=args.get("baseline_path"),
                thresholds=args.get("thresholds"),
            )
        elif tool_name == "loadtest_establish_baseline":
            result = await tool_func(
                workspace_path=args.get("workspace_path", workspace_path),
                target_url=args.get("target_url", ""),
                duration=args.get("duration", "2m"),
                vus=args.get("vus", 5),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Load testing tool '{tool_name}' dispatch not configured.",
            }

        # Format result for display
        if isinstance(result, dict):
            import json

            text = json.dumps(result, indent=2, default=str)
        else:
            text = str(result)

        return {"tool": tool_name, "text": text}
    except Exception as exc:
        logger.error("Load testing tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing load testing tool: {exc}"}


async def _dispatch_k8s_lifecycle_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch Kubernetes lifecycle tools to their implementations."""
    from backend.agent.tools.kubernetes_lifecycle_tools import K8S_LIFECYCLE_TOOLS

    # Include cloud credentials for K8s cluster operations
    cred_service = get_credentials_service()

    # Set cloud credentials as environment variables for CLI tools
    aws_creds = cred_service.get_provider_credentials("aws")
    gcp_creds = cred_service.get_provider_credentials("gcp")
    cred_service.get_provider_credentials("azure")

    # Export credentials to environment for eksctl/gcloud/az CLI
    if aws_creds.get("access_key_id"):
        os.environ["AWS_ACCESS_KEY_ID"] = aws_creds["access_key_id"]
    if aws_creds.get("secret_access_key"):
        os.environ["AWS_SECRET_ACCESS_KEY"] = aws_creds["secret_access_key"]
    if aws_creds.get("region"):
        os.environ["AWS_DEFAULT_REGION"] = aws_creds["region"]

    if gcp_creds.get("service_account_key"):
        # Write service account key to temp file for gcloud
        import tempfile

        key_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        key_file.write(gcp_creds["service_account_key"])
        key_file.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_file.name

    workspace_path = workspace.get("workspace_root") if workspace else "."

    tool_config = K8S_LIFECYCLE_TOOLS.get(tool_name)
    if not tool_config:
        return {
            "tool": tool_name,
            "text": f"Kubernetes tool '{tool_name}' is not implemented.",
        }

    tool_func = tool_config.get("function")
    if not tool_func:
        return {
            "tool": tool_name,
            "text": f"Kubernetes tool '{tool_name}' has no function defined.",
        }

    try:
        if tool_name == "k8s_cluster_create":
            result = await tool_func(
                provider=args.get("provider", ""),
                cluster_name=args.get("cluster_name", ""),
                region=args.get("region", ""),
                node_count=args.get("node_count", 3),
                node_type=args.get("node_type", "standard"),
                kubernetes_version=args.get("kubernetes_version", "latest"),
                vpc_config=args.get("vpc_config"),
                enable_private_cluster=args.get("enable_private_cluster", False),
                enable_workload_identity=args.get("enable_workload_identity", True),
                tags=args.get("tags"),
                workspace_path=args.get("workspace_path", workspace_path),
            )
        elif tool_name == "k8s_cluster_upgrade":
            result = await tool_func(
                provider=args.get("provider", ""),
                cluster_name=args.get("cluster_name", ""),
                region=args.get("region", ""),
                target_version=args.get("target_version", ""),
                upgrade_strategy=args.get("upgrade_strategy", "rolling"),
                drain_timeout=args.get("drain_timeout", 300),
                node_pool=args.get("node_pool"),
                workspace_path=args.get("workspace_path", workspace_path),
            )
        elif tool_name == "k8s_node_pool_manage":
            result = await tool_func(
                provider=args.get("provider", ""),
                cluster_name=args.get("cluster_name", ""),
                region=args.get("region", ""),
                action=args.get("action", ""),
                node_pool_name=args.get("node_pool_name", ""),
                node_count=args.get("node_count"),
                node_type=args.get("node_type"),
                taints=args.get("taints"),
                labels=args.get("labels"),
                enable_autoscaling=args.get("enable_autoscaling", False),
                min_nodes=args.get("min_nodes", 1),
                max_nodes=args.get("max_nodes", 10),
            )
        elif tool_name == "k8s_install_addons":
            result = await tool_func(
                addons=args.get("addons", []),
                cluster_name=args.get("cluster_name", ""),
                provider=args.get("provider"),
                namespace=args.get("namespace", "kube-system"),
                helm_values=args.get("helm_values"),
                workspace_path=args.get("workspace_path", workspace_path),
            )
        elif tool_name == "k8s_cluster_health_check":
            result = await tool_func(
                checks=args.get("checks"),
                namespace=args.get("namespace"),
                verbose=args.get("verbose", False),
            )
        else:
            return {
                "tool": tool_name,
                "text": f"Kubernetes tool '{tool_name}' dispatch not configured.",
            }

        # Format result for display
        if isinstance(result, dict):
            import json

            text = json.dumps(result, indent=2, default=str)
        else:
            text = str(result)

        return {"tool": tool_name, "text": text}
    except Exception as exc:
        logger.error("Kubernetes tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing Kubernetes tool: {exc}"}
