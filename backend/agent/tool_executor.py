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

logger = logging.getLogger(__name__)

# Where the repo lives on disk.
# You can override this per machine:
#   export NAVI_WORKSPACE_ROOT=/Users/you/path/to/aep
DEFAULT_WORKSPACE_ROOT = Path(
    os.environ.get("NAVI_WORKSPACE_ROOT", os.getcwd())
).resolve()


async def execute_tool(
    user_id: str,
    tool_name: str,
    args: Dict[str, Any],
    db=None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    workspace_id: Optional[str] = None,
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

  # Workspace-safe tools ------------------------------------------------------
  if tool_name == "repo.inspect":
    # Enrich args with context for VS Code workspace integration
    enriched_args = {
      **args,
      "user_id": user_id,
      "attachments": attachments,
      "workspace_id": workspace_id,
    }
    return await _tool_repo_inspect(enriched_args)

  if tool_name == "code.read_files":
    return await _tool_code_read_files(args)

  if tool_name == "code.search":
    return await _tool_code_search(args)

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
  else:
    root = DEFAULT_WORKSPACE_ROOT

  return root


async def _tool_repo_inspect(args: Dict[str, Any]) -> Dict[str, Any]:
  """
  Safe tool: inspect current repository structure and produce a natural-language overview.
  
  Uses VS Code attachments when available, falls back to filesystem scan.
  """
  from backend.agent.workspace_retriever import retrieve_workspace_context
  from backend.services.llm import call_llm
  
  user_id = args.get("user_id", "default_user")
  workspace_id = args.get("workspace_id")
  attachments = args.get("attachments")
  message = args.get("message", "Explain this repository and its structure.")
  model = args.get("model", "gpt-4o-mini")
  mode = args.get("mode", "agent-full")
  
  logger.info("[TOOLS] repo.inspect workspace_id=%s attachments=%d", 
              workspace_id, len(attachments or []))
  
  # Get workspace context (VS Code attachments first, filesystem fallback)
  workspace_ctx = await retrieve_workspace_context(
    user_id=user_id,
    workspace_root=workspace_id,
    include_files=True,
    attachments=attachments,
  )
  
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
  for node in (workspace_ctx.get("file_tree") or []):
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
    reply = f"Repository at {workspace_ctx.get('project_root')}\n\nFiles detected:\n" + "\n".join(tree_lines[:10])
  
  return {
    "tool": "repo.inspect",
    "text": reply,
    "workspace_id": workspace_id,
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
    path = (root / rel).resolve()
    if not str(path).startswith(str(root)):
      # prevent traversal
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

  combined_text = "".join(combined) if combined else "No readable files were returned."

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
  globs = args.get("globs") or ["**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx", "**/*.md"]

  if not pattern:
    return {
        "tool": "code.search",
        "root": str(root),
        "matches": [],
        "text": "No search pattern provided.",
    }

  try:
    regex = re.compile(pattern)
  except re.error:
    # Fallback to literal search
    regex = None

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
    summary_lines = [
        f"- {m['path']}:{m['line']} — {m['snippet']}"
        for m in matches
    ]
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


# Legacy compatibility functions that some code might still call
def get_available_tools() -> Dict[str, str]:
    """Return available tools for legacy compatibility"""
    return {
        "repo.inspect": "Inspect repository structure and files",
        "code.read_files": "Read specific files from the repository", 
        "code.search": "Search for patterns in repository files",
        "pm.create_ticket": "Create project management tickets (stub)",
        "pm.update_ticket": "Update project management tickets (stub)",
    }


def is_write_operation(tool_name: str) -> bool:
    """Check if a tool performs write operations"""
    write_tools = {"pm.create_ticket", "pm.update_ticket", "code.apply_patch"}
    return tool_name in write_tools

