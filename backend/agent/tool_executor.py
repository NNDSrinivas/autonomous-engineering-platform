# backend/agent/tool_executor.py

"""
NAVI tool executor

This module is the single place where logical tool names like
  - "repo.inspect"
  - "code.read_files"
  - "code.search"
  - "pm.create_ticket"
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
from .tools.run_command import run_command

logger = logging.getLogger(__name__)

# Tools that mutate state or filesystem. Used by guardrails and UI.
WRITE_OPERATION_TOOLS = {
    # Code write operations
    "code.apply_diff",
    "code.create_file",
    "code.edit_file",
    "code.run_command",
    "repo.write",
    # Jira write operations
    "jira.add_comment",
    "jira.transition_issue",
    "jira.assign_issue",
    "jira.create_issue",
    # GitHub write operations
    "github.comment",
    "github.set_label",
    "github.rerun_check",
    "github.create_issue",
    "github.create_pr",
    # Linear write operations
    "linear.create_issue",
    "linear.add_comment",
    "linear.update_status",
    # GitLab write operations
    "gitlab.create_merge_request",
    "gitlab.add_comment",
    # Notion write operations
    "notion.create_page",
    # Slack write operations
    "slack.send_message",
    # Asana write operations
    "asana.create_task",
    "asana.complete_task",
    # Bitbucket write operations
    "bitbucket.create_pull_request",
    # Discord write operations
    "discord.send_message",
    # Trello write operations
    "trello.create_card",
    "trello.move_card",
    # ClickUp write operations
    "clickup.create_task",
    "clickup.update_task",
    # Confluence write operations
    "confluence.create_page",
    # Figma write operations
    "figma.add_comment",
    # Sentry write operations
    "sentry.resolve_issue",
    # GitHub Actions write operations
    "github_actions.trigger_workflow",
    # CircleCI write operations
    "circleci.trigger_pipeline",
    # Vercel write operations
    "vercel.redeploy",
    # PagerDuty write operations
    "pagerduty.acknowledge_incident",
    "pagerduty.resolve_incident",
    # Monday.com write operations
    "monday.create_item",
    # Datadog write operations
    "datadog.mute_monitor",
}


def get_available_tools():
    """List supported tool entrypoints for UI/help surfaces."""
    return sorted(
        {
            # Context tools
            "context.present_packet",
            "context.summary",
            # Repository and code tools
            "repo.inspect",
            "code.read_files",
            "code.search",
            "code.explain",
            "code.apply_diff",
            "code.create_file",
            "code.edit_file",
            "code.run_command",
            # Project management
            "project.summary",
            # Jira tools
            "jira.list_assigned_issues_for_user",
            "jira.search_issues",
            "jira.assign_issue",
            "jira.create_issue",
            "jira.add_comment",
            "jira.transition_issue",
            # GitHub tools
            "github.list_my_prs",
            "github.list_my_issues",
            "github.get_pr_details",
            "github.list_repo_issues",
            "github.create_issue",
            "github.create_pr",
            "github.comment",
            "github.set_label",
            "github.rerun_check",
            # Linear tools
            "linear.list_my_issues",
            "linear.search_issues",
            "linear.create_issue",
            "linear.add_comment",
            "linear.update_status",
            "linear.list_teams",
            # GitLab tools
            "gitlab.list_my_merge_requests",
            "gitlab.list_my_issues",
            "gitlab.get_pipeline_status",
            "gitlab.search",
            "gitlab.create_merge_request",
            "gitlab.add_comment",
            # Notion tools
            "notion.search_pages",
            "notion.list_recent_pages",
            "notion.get_page_content",
            "notion.list_databases",
            "notion.create_page",
            # Slack tools
            "slack.search_messages",
            "slack.list_channel_messages",
            "slack.send_message",
            # Asana tools
            "asana.list_my_tasks",
            "asana.search_tasks",
            "asana.list_projects",
            "asana.create_task",
            "asana.complete_task",
            # Bitbucket tools
            "bitbucket.list_my_prs",
            "bitbucket.list_repos",
            "bitbucket.get_pr_details",
            "bitbucket.create_pull_request",
            # Discord tools
            "discord.list_channels",
            "discord.get_messages",
            "discord.send_message",
            # Loom tools
            "loom.list_videos",
            "loom.search_videos",
            "loom.get_video",
            # Trello tools
            "trello.list_boards",
            "trello.list_my_cards",
            "trello.get_card",
            "trello.create_card",
            "trello.move_card",
            # ClickUp tools
            "clickup.list_my_tasks",
            "clickup.list_spaces",
            "clickup.get_task",
            "clickup.create_task",
            "clickup.update_task",
            # SonarQube tools
            "sonarqube.list_projects",
            "sonarqube.list_issues",
            "sonarqube.get_quality_gate",
            "sonarqube.get_metrics",
            # Confluence tools
            "confluence.search_pages",
            "confluence.get_page",
            "confluence.list_pages_in_space",
            # Figma tools
            "figma.list_files",
            "figma.get_file",
            "figma.get_comments",
            "figma.list_projects",
            "figma.add_comment",
            # Sentry tools
            "sentry.list_issues",
            "sentry.get_issue",
            "sentry.list_projects",
            "sentry.resolve_issue",
            # Snyk tools
            "snyk.list_vulnerabilities",
            "snyk.list_projects",
            "snyk.get_security_summary",
            "snyk.get_project_issues",
            # GitHub Actions tools
            "github_actions.list_workflows",
            "github_actions.list_runs",
            "github_actions.get_run_status",
            "github_actions.trigger_workflow",
            # CircleCI tools
            "circleci.list_pipelines",
            "circleci.get_pipeline_status",
            "circleci.trigger_pipeline",
            "circleci.get_job_status",
            # Vercel tools
            "vercel.list_projects",
            "vercel.list_deployments",
            "vercel.get_deployment_status",
            "vercel.redeploy",
            # PagerDuty tools
            "pagerduty.list_incidents",
            "pagerduty.get_oncall",
            "pagerduty.list_services",
            "pagerduty.acknowledge_incident",
            "pagerduty.resolve_incident",
            # Google Drive tools
            "gdrive.list_files",
            "gdrive.search",
            "gdrive.get_content",
            # Zoom tools
            "zoom.list_recordings",
            "zoom.get_transcript",
            "zoom.search_recordings",
            # Google Calendar tools
            "gcalendar.list_events",
            "gcalendar.todays_events",
            "gcalendar.get_event",
            # Monday.com tools
            "monday.list_boards",
            "monday.list_items",
            "monday.get_my_items",
            "monday.get_item",
            "monday.create_item",
            # Datadog tools
            "datadog.list_monitors",
            "datadog.alerting_monitors",
            "datadog.list_incidents",
            "datadog.list_dashboards",
            "datadog.mute_monitor",
            # Deployment tools
            "deploy.detect_project",
            "deploy.check_cli",
            "deploy.get_info",
            "deploy.list_platforms",
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
) -> Dict[str, Any]:
    """
    Main entrypoint – dispatch tool calls by name.

    Returns a dict that always has a 'tool' key and a 'text' field
    that can be fed to the LLM.
    """
    logger.info(
        "[TOOLS] execute_tool user=%s tool=%s args=%s",
        user_id,
        tool_name,
        json.dumps(args, default=str)[:300],
    )

    # Context packet passthrough -------------------------------------------------
    if tool_name == "context.present_packet":
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
    if tool_name == "repo.inspect":
        # Enrich args with context for VS Code workspace integration
        # Basic guard: require workspace_root to avoid inspecting the wrong repo
        ws = workspace or {}
        if not ws.get("workspace_root"):
            return {
                "tool": "repo.inspect",
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

    if tool_name == "code.read_files":
        return await _tool_code_read_files(args)

    if tool_name == "code.search":
        return await _tool_code_search(args)

    # Code write operations (require workspace) --------------------------------------
    if tool_name == "code.create_file":
        return await _tool_code_create_file(user_id, args)
    if tool_name == "code.edit_file":
        return await _tool_code_edit_file(user_id, args)
    if tool_name == "code.apply_diff":
        return await _tool_code_apply_diff(user_id, args)
    if tool_name == "code.run_command":
        return await _tool_code_run_command(user_id, args)

    # Jira integration tools --------------------------------------------------------
    if tool_name == "jira.list_assigned_issues_for_user":
        return await _tool_jira_list_assigned_issues(user_id, args, db)
    if tool_name == "jira.add_comment":
        return await _tool_jira_add_comment(user_id, args, db)
    if tool_name == "jira.transition_issue":
        return await _tool_jira_transition_issue(user_id, args, db)
    if tool_name == "jira.assign_issue":
        return await _tool_jira_assign_issue(user_id, args, db)
    # GitHub write operations (approval-gated) --------------------------------------
    if tool_name == "github.comment":
        return await _tool_github_comment(user_id, args, db)
    if tool_name == "github.set_label":
        return await _tool_github_set_label(user_id, args, db)
    if tool_name == "github.rerun_check":
        return await _tool_github_rerun_check(user_id, args, db)

    # Linear integration tools -------------------------------------------------------
    if tool_name.startswith("linear."):
        return await _dispatch_linear_tool(user_id, tool_name, args, db)

    # GitLab integration tools -------------------------------------------------------
    if tool_name.startswith("gitlab."):
        return await _dispatch_gitlab_tool(user_id, tool_name, args, db)

    # Notion integration tools -------------------------------------------------------
    if tool_name.startswith("notion."):
        return await _dispatch_notion_tool(user_id, tool_name, args, db)

    # Slack integration tools -------------------------------------------------------
    if tool_name.startswith("slack."):
        return await _dispatch_slack_tool(user_id, tool_name, args, db)

    # Asana integration tools -------------------------------------------------------
    if tool_name.startswith("asana."):
        return await _dispatch_asana_tool(user_id, tool_name, args, db)

    # Bitbucket integration tools ---------------------------------------------------
    if tool_name.startswith("bitbucket."):
        return await _dispatch_bitbucket_tool(user_id, tool_name, args, db)

    # Discord integration tools -----------------------------------------------------
    if tool_name.startswith("discord."):
        return await _dispatch_discord_tool(user_id, tool_name, args, db)

    # Loom integration tools --------------------------------------------------------
    if tool_name.startswith("loom."):
        return await _dispatch_loom_tool(user_id, tool_name, args, db)

    # Trello integration tools ------------------------------------------------------
    if tool_name.startswith("trello."):
        return await _dispatch_trello_tool(user_id, tool_name, args, db)

    # ClickUp integration tools -----------------------------------------------------
    if tool_name.startswith("clickup."):
        return await _dispatch_clickup_tool(user_id, tool_name, args, db)

    # SonarQube integration tools ---------------------------------------------------
    if tool_name.startswith("sonarqube."):
        return await _dispatch_sonarqube_tool(user_id, tool_name, args, db)

    # Confluence integration tools --------------------------------------------------
    if tool_name.startswith("confluence."):
        return await _dispatch_confluence_tool(user_id, tool_name, args, db)

    # Figma integration tools -------------------------------------------------------
    if tool_name.startswith("figma."):
        return await _dispatch_figma_tool(user_id, tool_name, args, db)

    # Sentry integration tools ------------------------------------------------------
    if tool_name.startswith("sentry."):
        return await _dispatch_sentry_tool(user_id, tool_name, args, db)

    # Snyk integration tools --------------------------------------------------------
    if tool_name.startswith("snyk."):
        return await _dispatch_snyk_tool(user_id, tool_name, args, db)

    # GitHub Actions integration tools ----------------------------------------------
    if tool_name.startswith("github_actions."):
        return await _dispatch_github_actions_tool(user_id, tool_name, args, db)

    # CircleCI integration tools ----------------------------------------------------
    if tool_name.startswith("circleci."):
        return await _dispatch_circleci_tool(user_id, tool_name, args, db)

    # Vercel integration tools ------------------------------------------------------
    if tool_name.startswith("vercel."):
        return await _dispatch_vercel_tool(user_id, tool_name, args, db)

    # PagerDuty integration tools ---------------------------------------------------
    if tool_name.startswith("pagerduty."):
        return await _dispatch_pagerduty_tool(user_id, tool_name, args, db)

    # Google Drive integration tools ------------------------------------------------
    if tool_name.startswith("gdrive."):
        return await _dispatch_google_drive_tool(user_id, tool_name, args, db)

    # Zoom integration tools --------------------------------------------------------
    if tool_name.startswith("zoom."):
        return await _dispatch_zoom_tool(user_id, tool_name, args, db)

    # Google Calendar integration tools ---------------------------------------------
    if tool_name.startswith("gcalendar."):
        return await _dispatch_google_calendar_tool(user_id, tool_name, args, db)

    # Monday.com integration tools --------------------------------------------------
    if tool_name.startswith("monday."):
        return await _dispatch_monday_tool(user_id, tool_name, args, db)

    # Datadog integration tools -----------------------------------------------------
    if tool_name.startswith("datadog."):
        return await _dispatch_datadog_tool(user_id, tool_name, args, db)

    # Deployment tools -------------------------------------------------------------
    if tool_name.startswith("deploy."):
        return await _dispatch_deployment_tool(user_id, tool_name, args, workspace)

    # Project-management stubs (future expansion) --------------------------------
    if tool_name.startswith("pm."):
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
        "tool": "repo.inspect",
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
        "tool": "code.read_files",
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
            "tool": "code.search",
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
        "tool": "code.search",
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
                "tool": "jira.list_assigned_issues_for_user",
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
                    "tool": "jira.list_assigned_issues_for_user",
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
                "tool": "jira.list_assigned_issues_for_user",
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
            "tool": "jira.list_assigned_issues_for_user",
            "issues": issues,
            "sources": sources,  # Unified sources for UI
            "count": len(issues),
            "text": text_summary,
        }

    except Exception as e:
        logger.error("Jira list assigned issues error: %s", e)
        return {
            "tool": "jira.list_assigned_issues_for_user",
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
            "tool": "jira.add_comment",
            "text": "issue_key and comment are required to add a Jira comment.",
        }
    if not approved:
        return {
            "tool": "jira.add_comment",
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
            "tool": "jira.add_comment",
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
            "tool": "jira.add_comment",
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
            "tool": "jira.transition_issue",
            "text": "issue_key and transition_id are required to transition a Jira issue.",
        }
    if not approved:
        return {
            "tool": "jira.transition_issue",
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
            "tool": "jira.transition_issue",
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
            "tool": "jira.transition_issue",
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
            "tool": "jira.assign_issue",
            "text": "issue_key and assignee_account_id are required to assign a Jira issue.",
        }
    if not approved:
        return {
            "tool": "jira.assign_issue",
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
            "tool": "jira.assign_issue",
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
            "tool": "jira.assign_issue",
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
            "tool": "github.comment",
            "text": "repo, number, and comment are required",
        }
    if not approved:
        return {
            "tool": "github.comment",
            "text": "Approval required. Pass approve=true to proceed.",
        }

    local_db = db or next(get_db())
    conn_q = local_db.query(GhConnection)
    if org_id:
        conn_q = conn_q.filter(GhConnection.org_id == org_id)
    conn = conn_q.order_by(GhConnection.id.desc()).first()
    if not conn:
        return {"tool": "github.comment", "text": "No GitHub connection found"}

    GitHubService(token=decrypt_token(conn.access_token or ""))
    try:
        # TODO: Implement add_comment method in GitHubService
        # await gh_client.add_comment(repo_full_name, number, comment)
        return {
            "tool": "github.comment",
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
        return {"tool": "github.comment", "text": f"Failed to add comment: {exc}"}


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
            "tool": "github.set_label",
            "text": "repo, number, and labels are required",
        }
    if not approved:
        return {
            "tool": "github.set_label",
            "text": "Approval required. Pass approve=true to proceed.",
        }

    local_db = db or next(get_db())
    conn_q = local_db.query(GhConnection)
    if org_id:
        conn_q = conn_q.filter(GhConnection.org_id == org_id)
    conn = conn_q.order_by(GhConnection.id.desc()).first()
    if not conn:
        return {"tool": "github.set_label", "text": "No GitHub connection found"}

    # gh_client = GitHubService(token=decrypt_token(conn.access_token or ""))
    try:
        # TODO: Implement set_labels method in GitHubService
        # await gh_client.set_labels(repo_full_name, number, labels)
        return {
            "tool": "github.set_label",
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
        return {"tool": "github.set_label", "text": f"Failed to set labels: {exc}"}


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
            "tool": "github.rerun_check",
            "text": "repo and check_run_id are required",
        }
    if not approved:
        return {
            "tool": "github.rerun_check",
            "text": "Approval required. Pass approve=true to proceed.",
        }

    local_db = db or next(get_db())
    conn_q = local_db.query(GhConnection)
    if org_id:
        conn_q = conn_q.filter(GhConnection.org_id == org_id)
    conn = conn_q.order_by(GhConnection.id.desc()).first()
    if not conn:
        return {"tool": "github.rerun_check", "text": "No GitHub connection found"}

    # gh_client = GitHubService(token=decrypt_token(conn.access_token or ""))
    try:
        # TODO: Implement rerun_check_run method in GitHubService
        # await gh_client.rerun_check_run(repo_full_name, check_run_id)
        return {
            "tool": "github.rerun_check",
            "text": f"GitHub check run rerun functionality not yet implemented for {repo_full_name}",
            "sources": [
                {"name": f"{repo_full_name}", "type": "github", "connector": "github"}
            ],
        }
    except Exception as exc:  # noqa: BLE001
        logger.error("GitHub rerun_check error: %s", exc)
        return {"tool": "github.rerun_check", "text": f"Failed to rerun check: {exc}"}


# ==============================================================================
# CODE TOOL IMPLEMENTATIONS
# ==============================================================================


async def _tool_code_create_file(user_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Create new file with content."""
    path = args.get("path")
    content = args.get("content", "")

    if not path:
        return {
            "tool": "code.create_file",
            "text": "❌ Path is required",
            "error": "Missing path parameter",
        }

    result = await create_file(user_id=user_id, path=path, content=content)

    return {
        "tool": "code.create_file",
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
            "tool": "code.edit_file",
            "text": "❌ Path is required",
            "error": "Missing path parameter",
        }

    result = await edit_file(user_id=user_id, path=path, new_content=content)

    return {
        "tool": "code.edit_file",
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
            "tool": "code.apply_diff",
            "text": "❌ Path and diff are required",
            "error": "Missing path or diff parameter",
        }

    result = await apply_diff(
        user_id=user_id, path=path, diff=diff, old_content=old_content
    )

    return {
        "tool": "code.apply_diff",
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
            "tool": "code.run_command",
            "text": "❌ Command is required",
            "error": "Missing command parameter",
        }

    result = await run_command(
        user_id=user_id, command=command, cwd=cwd, timeout=timeout
    )

    return {
        "tool": "code.run_command",
        "text": result["message"],
        "success": result["success"],
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
        "exit_code": result.get("exit_code"),
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
        if tool_name == "linear.list_my_issues":
            result = await tool_func(
                context,
                status=args.get("status"),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "linear.search_issues":
            result = await tool_func(
                context,
                query=args.get("query", ""),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "linear.create_issue":
            result = await tool_func(
                context,
                team_id=args.get("team_id"),
                title=args.get("title"),
                description=args.get("description"),
                priority=args.get("priority"),
                assignee_id=args.get("assignee_id"),
                approve=args.get("approve", False),
            )
        elif tool_name == "linear.update_status":
            result = await tool_func(
                context,
                issue_id=args.get("issue_id"),
                state_id=args.get("state_id"),
                approve=args.get("approve", False),
            )
        elif tool_name == "linear.list_teams":
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
        if tool_name == "gitlab.list_my_merge_requests":
            result = await tool_func(
                context,
                status=args.get("status"),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "gitlab.list_my_issues":
            result = await tool_func(
                context,
                status=args.get("status"),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "gitlab.get_pipeline_status":
            result = await tool_func(
                context,
                max_results=args.get("max_results", 10),
            )
        elif tool_name == "gitlab.search":
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
        if tool_name == "notion.search_pages":
            result = await tool_func(
                context,
                query=args.get("query", ""),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "notion.list_recent_pages":
            result = await tool_func(
                context,
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "notion.get_page_content":
            result = await tool_func(
                context,
                page_id=args.get("page_id"),
            )
        elif tool_name == "notion.list_databases":
            result = await tool_func(
                context,
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "notion.create_page":
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
        if tool_name == "slack.search_messages":
            result = await tool_func(
                context,
                query=args.get("query", ""),
                channel=args.get("channel"),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "slack.list_channel_messages":
            result = await tool_func(
                context,
                channel=args.get("channel"),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "slack.send_message":
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
        if tool_name == "asana.list_my_tasks":
            result = await tool_func(
                context,
                status=args.get("status"),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "asana.search_tasks":
            result = await tool_func(
                context,
                query=args.get("query", ""),
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "asana.list_projects":
            result = await tool_func(
                context,
                max_results=args.get("max_results", 20),
            )
        elif tool_name == "asana.create_task":
            result = await tool_func(
                context,
                name=args.get("name"),
                project_gid=args.get("project_gid"),
                workspace_gid=args.get("workspace_gid"),
                notes=args.get("notes"),
                due_on=args.get("due_on"),
                approve=args.get("approve", False),
            )
        elif tool_name == "asana.complete_task":
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

    context = {"user_id": user_id}

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
        if tool_name == "deploy.detect_project":
            result = await tool_func(context, workspace_path=workspace_path)
        elif tool_name == "deploy.check_cli":
            platform = args.get("platform", "")
            result = await tool_func(context, platform=platform)
        elif tool_name == "deploy.get_info":
            platform = args.get("platform", "")
            result = await tool_func(context, platform=platform)
        elif tool_name == "deploy.list_platforms":
            result = await tool_func(context)
        else:
            return {
                "tool": tool_name,
                "text": f"Deployment tool '{tool_name}' dispatch not configured.",
            }

        return {"tool": tool_name, "text": result.output, "sources": result.sources}
    except Exception as exc:
        logger.error("Deployment tool error: %s - %s", tool_name, exc)
        return {"tool": tool_name, "text": f"Error executing deployment tool: {exc}"}
