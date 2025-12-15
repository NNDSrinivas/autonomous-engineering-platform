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

logger = logging.getLogger(__name__)

# Tools that mutate state or filesystem. Used by guardrails and UI.
WRITE_OPERATION_TOOLS = {
    "code.apply_diff",
    "code.create_file",
    "code.edit_file",
    "code.run_command",
    "repo.write",
}


def get_available_tools():
    """List supported tool entrypoints for UI/help surfaces."""
    return sorted(
        {
            "context.present_packet",
            "context.summary",
            "repo.inspect",
            "code.read_files",
            "code.search",
            "code.explain",
            "code.apply_diff",
            "code.create_file",
            "code.edit_file",
            "code.run_command",
            "jira.search_issues",
            "jira.assign_issue",
            "jira.create_issue",
            "slack.send_message",
            "github.create_pr",
            "github.rerun_check",
            "project.summary",
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

    # Slack integration tools -------------------------------------------------------
    # Slack tools not yet implemented
    # if tool_name == "slack.fetch_recent_channel_messages":
    #   return await _tool_slack_fetch_recent_channel_messages(user_id, args, db)
    # if tool_name == "slack.search_user_messages":
    #   return await _tool_slack_search_user_messages(user_id, args, db)

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
    except Exception as exc:
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
