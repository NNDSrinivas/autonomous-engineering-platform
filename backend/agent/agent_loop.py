"""
NAVI Agent Loop - The Core 7-Stage Reasoning Pipeline

This is the main entry point for NAVI's autonomous agent behavior.
Called by /api/navi/chat for every user message.

Pipeline stages:
1. Load user state (what were they doing?)
2. Build full context (workspace + org + memory)
3. Classify intent (what do they want?)
4. Generate plan (how to accomplish it?)
5. Check approval (destructive actions need confirmation)
6. Execute or respond (tools vs. chat)
7. Update state (remember for next turn)
"""

import logging
import time
import json
from typing import Dict, Any, Optional, List
from dataclasses import asdict

from backend.agent.context_builder import build_context
from backend.agent.memory_retriever import retrieve_memories
from backend.agent.org_retriever import retrieve_org_context
from backend.agent.workspace_retriever import retrieve_workspace_context
from backend.agent.intent_classifier import IntentClassifier
from backend.ai.intent_llm_classifier import LLMIntentClassifier
from backend.agent.tool_executor import execute_tool, execute_tool_with_sources
from backend.agent.state_manager import (
    get_user_state,
    update_user_state,
    clear_user_state,
)
from backend.services.llm import call_llm

logger = logging.getLogger(__name__)


def _shape_actions_from_plan(plan) -> List[Dict[str, Any]]:
    """
    Convert planner steps into workspace-ready actions.

    Each action looks like:

    {
      "id": "step-1",
      "title": "Analyze user requirements",
      "description": "...same as title for now...",
      "tool": "repo.inspect",
      "arguments": {...},          # original arguments
      "type": "fileEdit" | "workspaceRead" | "task" | "generic",
      "filePath": "src/main.ts",   # when applicable
      "content": "diff/contents",  # when applicable
    }
    """
    actions: List[Dict[str, Any]] = []

    if not plan or not getattr(plan, "steps", None):
        return actions

    for idx, step in enumerate(plan.steps):
        # Step might be a dataclass – normalize to dict-ish access
        try:
            step_dict = asdict(step)
        except Exception:  # noqa: BLE001
            # Fall back to attribute-based access
            step_dict = {
                "id": getattr(step, "id", None),
                "description": getattr(step, "description", None),
                "tool": getattr(step, "tool", None),
                "arguments": getattr(step, "arguments", None),
            }

        tool = step_dict.get("tool") or ""
        args = step_dict.get("arguments") or step_dict.get("args") or {}  # be forgiving

        # Infer basic type + file metadata
        step_type = "generic"
        file_path: Optional[str] = None
        content: Optional[str] = None

        # File-editing tools
        if tool in {"code.apply_patch", "code.write_file", "code.create_file", "code.overwrite_file"}:
            step_type = "fileEdit"
            file_path = (
                args.get("path")
                or args.get("file_path")
                or args.get("filename")
                or args.get("file")
            )
            content = args.get("content") or args.get("patch") or None

        # Read-only workspace operations
        elif tool in {"repo.inspect", "code.read_files", "code.search"}:
            step_type = "workspaceRead"

        # Project-management tasks
        elif tool.startswith("pm."):
            step_type = "task"

        title = step_dict.get("description") or tool or f"Step {idx + 1}"

        actions.append(
            {
                "id": step_dict.get("id") or f"step-{idx + 1}",
                "title": title,
                "description": title,
                "tool": tool,
                "arguments": args,
                "type": step_type,
                "filePath": file_path,
                "content": content,
            }
        )

    return actions


def _looks_like_project_overview_question(text: str) -> bool:
    """
    Heuristic: is the user asking "what is this project / repo / codebase?"
    Used to trigger a repo.inspect + explanation flow.
    """
    if not text:
        return False

    text = text.lower()

    # Needs at least one "project/repo/codebase" keyword...
    project_keywords = ["project", "repo", "repository", "codebase", "service", "app"]
    if not any(k in text for k in project_keywords):
        return False

    # ...and at least one "explain/what/overview/structure" keyword.
    explain_keywords = [
        "what is",
        "what's",
        "whats",
        "about",
        "explain",
        "overview",
        "structure",
        "tell me",
        "describe",
        "summary",
        "summarise",
        "summarize",
    ]
    if not any(k in text for k in explain_keywords):
        return False

    return True


async def _handle_project_overview(
    *,
    user_id: str,
    message: str,
    model: str,
    mode: str,
    full_context: Dict[str, Any],
    db,
    started: float,
    attachments: Optional[List[Dict[str, Any]]] = None,
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Smart path for "explain the project / repo" questions.

    1) Calls repo.inspect to get structure.
    2) Tries to read a few key files (README, package.json, pyproject, pom.xml, etc).
    3) Feeds all of that into the LLM to generate a plain-language explanation.
    """

    logger.info("[AGENT] Handling project-overview question via repo.inspect")

    repo_result: Any = None
    files_result: Any = None
    tool_snippets: List[str] = []

    # 1) Always try repo.inspect first
    try:
        repo_result = await execute_tool(
            user_id,
            "repo.inspect",
            {
                # Be conservative – we just want the high-level layout.
                "max_depth": 3,
                "max_files": 200,
            },
            db=db,
            attachments=attachments,
            workspace=workspace,
        )
        repo_text = json.dumps(repo_result, indent=2, default=str)
        tool_snippets.append(f"REPO_INSPECT_RESULT:\n{repo_text}")
    except Exception as e:  # noqa: BLE001
        logger.warning("[AGENT] repo.inspect failed in project overview: %s", e)
        tool_snippets.append(f"REPO_INSPECT_ERROR: {str(e)}")

    # 2) Try to read a few "anchor" files if they exist
    try:
        # The tool executor can decide which of these actually exist.
        files_result = await execute_tool(
            user_id,
            "code.read_files",
            {
                "paths": [
                    "README.md",
                    "readme.md",
                    "package.json",
                    "pyproject.toml",
                    "pom.xml",
                    "setup.py",
                    "main.py",
                    "src/main.py",
                    "src/index.tsx",
                    "src/index.ts",
                ]
            },
            db=db,
            attachments=attachments,
            workspace=workspace,
        )
        files_text = json.dumps(files_result, indent=2, default=str)
        tool_snippets.append(f"KEY_FILES_RESULT:\n{files_text}")
    except Exception as e:  # noqa: BLE001
        logger.warning("[AGENT] code.read_files failed in project overview: %s", e)
        tool_snippets.append(f"KEY_FILES_ERROR: {str(e)}")

    # 3) Build enriched context for the LLM
    extra_context = "\n\n".join(tool_snippets)
    llm_context = dict(full_context)
    combined = llm_context.get("combined", "")
    llm_context["combined"] = combined + "\n\n" + extra_context

    # 4) Ask LLM to explain the project using actual repo info
    answer = await call_llm(
        message,
        llm_context,
        model=model,
        mode=mode,
    )

    clear_user_state(user_id)
    elapsed_ms = int((time.monotonic() - started) * 1000)

    # We can also surface the actions we *implicitly* took, so the panel
    # could show them later if desired.
    actions = [
        {
            "id": "repo-overview-1",
            "title": "Inspect repository structure",
            "description": "Inspect the repository structure and main folders.",
            "tool": "repo.inspect",
            "arguments": {"max_depth": 3, "max_files": 200},
            "type": "workspaceRead",
            "filePath": None,
            "content": None,
        },
        {
            "id": "repo-overview-2",
            "title": "Read key project files",
            "description": "Read key files like README and main entrypoints.",
            "tool": "code.read_files",
            "arguments": {
                "paths": [
                    "README.md",
                    "readme.md",
                    "package.json",
                    "pyproject.toml",
                    "pom.xml",
                    "setup.py",
                    "main.py",
                    "src/main.py",
                    "src/index.tsx",
                    "src/index.ts",
                ]
            },
            "type": "workspaceRead",
            "filePath": None,
            "content": None,
        },
    ]

    return {
        "reply": answer,
        "actions": actions,
        "should_stream": True,
        "state": {"completed": True, "mode": "project_overview"},
        "duration_ms": elapsed_ms,
    }


async def run_agent_loop(
    user_id: str,
    message: str,
    model: str = "gpt-4",
    mode: str = "chat",
    db=None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    workspace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Main NAVI agent pipeline.
    This is called every time the user sends a message.

    Args:
        user_id: User identifier
        message: User's message
        model: LLM model to use
        mode: "chat" or "agent-full"
        db: Database session

    Returns:
        {
            "reply": str,              # NAVI's response
            "actions": List[Dict],     # Proposed actions (for approval / apply)
            "should_stream": bool,     # Whether to stream response
            "state": Dict,             # Updated state (for debugging)
            "duration_ms": int         # Total run duration in ms (for UI)
        }
    """

    started = time.monotonic()

    try:
        logger.info(
            "[AGENT] Starting loop for user=%s, message='%s...'",
            user_id,
            message[:50],
        )

        # ---------------------------------------------------------
        # STAGE 1: Load user state (what were they doing last?)
        # ---------------------------------------------------------
        previous_state = await get_user_state(user_id)
        logger.info("[AGENT] Previous state: %s", previous_state)

        normalized_msg = message.strip().lower()

        # Special case: user typed a generic affirmative
        if normalized_msg in (
            "yes",
            "sure",
            "okay",
            "ok",
            "go ahead",
            "yes please",
            "please",
        ):
            if previous_state and previous_state.get("pending_action"):
                logger.info("[AGENT] Affirmative detected, executing pending action")
                pending = previous_state["pending_action"]
                tool_name = pending if isinstance(pending, str) else pending.get(
                    "tool", ""
                )
                tool_args = {} if isinstance(pending, str) else pending.get(
                    "args", {}
                )
                tool_result = await execute_tool_with_sources(
                    user_id, tool_name, tool_args, db=db,
                    attachments=attachments, workspace=workspace
                )
                elapsed_ms = int((time.monotonic() - started) * 1000)
                # Return unified result with sources
                return {
                    "reply": tool_result.output.get("text", str(tool_result.output)),
                    "actions": [],
                    "sources": tool_result.sources,
                    "should_stream": False,
                    "state": {"executed_pending_action": True},
                    "duration_ms": elapsed_ms,
                }
                return {
                    "reply": str(result),
                    "actions": [],
                    "should_stream": False,
                    "state": {"executed_pending_action": True},
                    "duration_ms": elapsed_ms,
                }

            # If no pending action, treat as continuation
            message = f"(user agrees to continue previous task) {message}"
            logger.info(
                "[AGENT] Affirmative without pending action, continuing conversation"
            )

        # Special case: pure greetings should just chat, not plan repo work
        if normalized_msg in ("hi", "hello", "hey", "hola", "yo", "hi!", "hey!"):
            logger.info("[AGENT] Greeting detected, using direct chat mode")
            # Build minimal/lightweight context for greetings
            workspace_root = workspace.get("workspace_root") if workspace else None
            workspace_ctx = await retrieve_workspace_context(
                user_id=user_id,
                workspace_root=workspace_root,
                include_files=True,
                attachments=attachments,
            )
            org_ctx = await retrieve_org_context(user_id, message, db=db)
            memory_ctx = await retrieve_memories(user_id, message, db=db)
            full_context = build_context(
                workspace_ctx,
                org_ctx,
                memory_ctx.to_dict(),
                previous_state,
                message,
            )
            answer = await call_llm(message, full_context, model=model, mode=mode)
            clear_user_state(user_id)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "reply": answer,
                "actions": [],
                "should_stream": True,
                "state": {"completed": True, "mode": "greeting"},
                "duration_ms": elapsed_ms,
            }

        # ---------------------------------------------------------
        # STAGE 2: Build perfect workspace context 
        # ---------------------------------------------------------
        logger.info("[AGENT] Retrieving perfect workspace context...")
        from backend.agent.perfect_workspace_retriever import retrieve_perfect_workspace_context
        
        workspace_ctx = {}
        if workspace:
            workspace_ctx = await retrieve_perfect_workspace_context(workspace)
        
        org_ctx = await retrieve_org_context(user_id, message, db=db)
        memory_ctx = await retrieve_memories(user_id, message, db=db)

        full_context = build_context(
            workspace_ctx,
            org_ctx,
            memory_ctx.to_dict(),
            previous_state,
            message,
        )
        logger.info(
            "[AGENT] Context built: %d chars",
            len(full_context.get("combined", "")),
        )

        # ---------------------------------------------------------
        # PROJECT OVERVIEW FAST-PATH
        # ---------------------------------------------------------
        if _looks_like_project_overview_question(normalized_msg):
            return await _handle_project_overview(
                user_id=user_id,
                message=message,
                model=model,
                mode=mode,
                full_context=full_context,
                db=db,
                started=started,
                attachments=attachments,
                workspace=workspace,
            )

        # ---------------------------------------------------------
        # STAGE 3: Classify the user's intent using LLM-powered provider-aware classifier
        # ---------------------------------------------------------
        logger.info("[AGENT] Classifying intent...")
        try:
            # Use new LLM-powered classifier for provider-aware classification
            llm_classifier = LLMIntentClassifier()
            intent = await llm_classifier.classify(
                message=message,
                metadata={"user_id": user_id, "workspace": workspace}
            )
            logger.info("[AGENT] LLM Intent: %s/%s (provider: %s)", 
                       intent.family.value if intent.family else "None", 
                       intent.kind.value if intent.kind else "None",
                       intent.provider.value if intent.provider else "None")
        except Exception as e:
            # Fallback to rule-based classifier if LLM fails
            logger.warning("[AGENT] LLM classifier failed (%s), using rule-based fallback", e)
            classifier = IntentClassifier()
            intent = classifier.classify(message)
            logger.info("[AGENT] Fallback Intent: %s/%s", intent.family.value, intent.kind.value)

        # ---------------------------------------------------------
        # STAGE 4: Handle low confidence intents
        # ---------------------------------------------------------
        if intent.confidence < 0.5:
            logger.info(
                "[AGENT] Intent confidence low (%.2f), asking for clarification",
                intent.confidence,
            )
            await update_user_state(
                user_id,
                {"pending_clarification": intent.model_dump()},
            )
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "reply": (
                    "I'm not quite sure what you'd like me to do. "
                    f"Could you be more specific? (Confidence: {intent.confidence:.1f})"
                ),
                "actions": [],
                "should_stream": False,
                "state": {"intent": "ambiguous"},
                "duration_ms": elapsed_ms,
            }

        # ---------------------------------------------------------
        # STAGE 5: Generate multi-step plan using NAVI OS v3
        # ---------------------------------------------------------
        logger.info("[AGENT] Generating plan...")
        from backend.agent.planner_v3 import PlannerV3
        planner = PlannerV3()
        plan = await planner.plan(intent, full_context)
        logger.info("[AGENT] Plan generated with %d steps", len(plan.steps))

        # Prepare shaped actions once so all branches can reuse them
        planned_actions = _shape_actions_from_plan(plan)

        # ---------------------------------------------------------
        # STAGE 6: Check if plan needs approval (destructive actions)
        # ---------------------------------------------------------
        requires_approval = any(
            step.tool in ["code.apply_patch", "pm.create_ticket", "pm.update_ticket"]
            for step in plan.steps
        )

        if requires_approval:
            # Save pending plan
            await update_user_state(
                user_id,
                {
                    "pending_plan": asdict(plan),
                    "pending_intent": intent.model_dump(),
                    "last_plan": asdict(plan),
                },
            )
            logger.info("[AGENT] Plan requires approval, waiting for user")
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "reply": (
                    plan.summary
                    or "I have a workspace plan to help with that. Should I proceed?"
                ),
                # M2-1: return shaped actions so the panel can show Workspace plan + Approve/Reject
                "actions": planned_actions,
                "should_stream": False,
                "state": {"pending_approval": True},
                "duration_ms": elapsed_ms,
            }

        # ---------------------------------------------------------
        # STAGE 7a: If no executable steps, provide summary
        # ---------------------------------------------------------
        if not plan.steps:
            logger.info("[AGENT] No steps in plan, providing summary")
            answer = await call_llm(
                message,
                full_context,
                model=model,
                mode=mode,
            )
            clear_user_state(user_id)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "reply": answer,
                "actions": [],
                "should_stream": True,
                "state": {"completed": True},
                "duration_ms": elapsed_ms,
            }

        # ---------------------------------------------------------
        # STAGE 7b: Execute safe tools immediately, then let LLM explain
        # ---------------------------------------------------------
        safe_tools = ["repo.inspect", "code.read_files", "code.search"]
        if plan.steps and all(step.tool in safe_tools for step in plan.steps):
            logger.info("[AGENT] Executing safe tools immediately (LLM will explain)")
            tool_snippets: List[str] = []
            all_sources: List[Dict[str, Any]] = []
            for step in plan.steps[:3]:  # Limit to first 3 steps
                try:
                    tool_result = await execute_tool_with_sources(
                        user_id, step.tool, step.arguments, db=db,
                        attachments=attachments, workspace=workspace
                    )
                    # Collect sources
                    if tool_result.sources:
                        all_sources.extend(tool_result.sources)
                    
                    # Format output for LLM context
                    result_text = json.dumps(tool_result.output, indent=2, default=str)
                    tool_snippets.append(
                        f"TOOL {step.tool} (description={step.description!r}):\n{result_text}"
                    )
                except Exception as e:  # noqa: BLE001
                    logger.exception(
                        "[AGENT] Safe tool %s failed: %s", step.tool, e
                    )
                    tool_snippets.append(
                        f"TOOL_ERROR {step.tool} (description={step.description!r}): {str(e)}"
                    )

            extra_context = "\n\n".join(tool_snippets)
            llm_context = dict(full_context)
            combined = llm_context.get("combined", "")
            llm_context["combined"] = combined + "\n\n" + extra_context

            answer = await call_llm(
                message,
                llm_context,
                model=model,
                mode=mode,
            )

            # De-duplicate sources by (type, url, name)
            dedup = {}
            for s in all_sources:
                key = (s.get("type"), s.get("url"), s.get("name"))
                dedup[key] = s
            all_sources = list(dedup.values())

            clear_user_state(user_id)
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return {
                "reply": answer,
                "actions": planned_actions,
                "sources": all_sources,  # Add sources to response
                "should_stream": True,
                "state": {"completed": True, "mode": "safe_tools_exec"},
                "duration_ms": elapsed_ms,
            }

        # ---------------------------------------------------------
        # Safety fallback - show plan summary
        # ---------------------------------------------------------
        logger.warning(
            "[AGENT] Reached safety fallback, %d steps planned", len(plan.steps)
        )
        clear_user_state(user_id)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "reply": (
                plan.summary
                or "I have a plan but need your approval to proceed. What would you like me to do?"
            ),
            "actions": planned_actions,
            "should_stream": False,
            "state": {"fallback": True},
            "duration_ms": elapsed_ms,
        }

    except Exception as e:  # noqa: BLE001
        logger.error("[AGENT] Error in agent loop: %s", e, exc_info=True)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        return {
            "reply": (
                "I encountered an error while processing your request. "
                "Let me try a different approach – could you rephrase what you need?"
            ),
            "actions": [],
            "should_stream": False,
            "state": {"error": str(e)},
            "duration_ms": elapsed_ms,
        }