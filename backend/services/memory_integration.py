"""
Memory Integration for NAVI Streaming Endpoints

This module provides helper functions to integrate persistent session memory
with NAVI's streaming endpoints. It handles:

1. Loading workspace context at session start
2. Injecting memory context into prompts
3. Saving facts after responses
4. Finding similar error resolutions

Usage in streaming endpoints:
    from backend.services.memory_integration import (
        load_workspace_memory,
        inject_memory_context,
        save_conversation_exchange,
    )

    # At session start
    memory_context = await load_workspace_memory(user_id, workspace_path, db)

    # Before calling agent
    enhanced_message = inject_memory_context(message, memory_context)

    # After response
    await save_conversation_exchange(user_id, workspace_path, message, response, actions, db)
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def load_workspace_memory(
    user_id: str,
    workspace_path: str,
    db: Session,
) -> Dict[str, Any]:
    """
    Load persistent memory context for a workspace.

    This should be called at the start of a session to retrieve
    any previously stored context for this workspace.

    Args:
        user_id: The user ID
        workspace_path: Path to the workspace/project
        db: Database session

    Returns:
        Dictionary containing:
        - facts: Extracted facts by category
        - error_resolutions: Known error solutions
        - dependencies: Installed packages
        - context_summary: Human-readable summary for prompt injection
    """
    if not workspace_path:
        return {
            "is_new_workspace": True,
            "facts": {},
            "error_resolutions": [],
            "dependencies": [],
            "context_summary": "",
        }

    try:
        # Try to use async version if available
        from backend.services.persistent_session_memory import PersistentSessionMemory

        # For sync db sessions, we need to handle this differently
        # Check if db is async
        if isinstance(db, AsyncSession):
            memory = PersistentSessionMemory(db)
            context = await memory.load_workspace_context(
                user_id=int(user_id) if user_id.isdigit() else 1,
                workspace_path=workspace_path,
            )
            context["context_summary"] = memory.generate_context_summary(context)
            return context
        else:
            # Sync database - use synchronous approach
            return _load_workspace_memory_sync(user_id, workspace_path, db)

    except Exception as e:
        logger.warning(f"Failed to load workspace memory: {e}")
        return {
            "is_new_workspace": True,
            "facts": {},
            "error_resolutions": [],
            "dependencies": [],
            "context_summary": "",
        }


def _load_workspace_memory_sync(
    user_id: str,
    workspace_path: str,
    db: Session,
) -> Dict[str, Any]:
    """
    Synchronous version of workspace memory loading.

    Uses direct SQL queries instead of async ORM.
    """
    from sqlalchemy import text

    normalized_path = workspace_path.rstrip("/")
    user_id_int = int(user_id) if user_id.isdigit() else 1

    try:
        # Check if workspace session exists
        result = db.execute(
            text("""
                SELECT id, workspace_name, last_active, last_known_state
                FROM navi_workspace_sessions
                WHERE user_id = :user_id AND workspace_path = :workspace_path
            """),
            {"user_id": user_id_int, "workspace_path": normalized_path},
        )
        workspace_row = result.fetchone()

        if not workspace_row:
            return {
                "is_new_workspace": True,
                "facts": {},
                "error_resolutions": [],
                "dependencies": [],
                "context_summary": "",
            }

        workspace_session_id = workspace_row[0]

        # Load facts
        facts_result = db.execute(
            text("""
                SELECT category, fact_key, fact_value
                FROM navi_session_facts
                WHERE workspace_session_id = :ws_id AND is_current = true
            """),
            {"ws_id": workspace_session_id},
        )
        facts = {}
        for row in facts_result:
            category = row[0]
            if category not in facts:
                facts[category] = {}
            facts[category][row[1]] = row[2]

        # Load error resolutions
        errors_result = db.execute(
            text("""
                SELECT error_type, error_signature, resolution_summary, times_successful, times_applied
                FROM navi_error_resolutions
                WHERE workspace_session_id = :ws_id
                ORDER BY (times_successful::float / NULLIF(times_applied, 0)) DESC NULLS LAST
                LIMIT 20
            """),
            {"ws_id": workspace_session_id},
        )
        error_resolutions = [
            {
                "error_type": row[0],
                "error_signature": row[1],
                "resolution_summary": row[2],
                "success_rate": row[3] / row[4] if row[4] > 0 else 0,
            }
            for row in errors_result
        ]

        # Load dependencies
        deps_result = db.execute(
            text("""
                SELECT package_manager, package_name, package_version
                FROM navi_installed_dependencies
                WHERE workspace_session_id = :ws_id
            """),
            {"ws_id": workspace_session_id},
        )
        dependencies = [
            {"manager": row[0], "name": row[1], "version": row[2]}
            for row in deps_result
        ]

        context = {
            "is_new_workspace": False,
            "workspace_name": workspace_row[1],
            "last_active": str(workspace_row[2]) if workspace_row[2] else None,
            "facts": facts,
            "error_resolutions": error_resolutions,
            "dependencies": dependencies,
        }

        # Generate summary
        context["context_summary"] = _generate_context_summary(context)

        logger.info(
            f"Loaded workspace memory for {normalized_path}: "
            f"{len(facts)} fact categories, {len(error_resolutions)} resolutions, {len(dependencies)} deps"
        )

        return context

    except Exception as e:
        logger.warning(f"Error loading workspace memory sync: {e}")
        return {
            "is_new_workspace": True,
            "facts": {},
            "error_resolutions": [],
            "dependencies": [],
            "context_summary": "",
        }


def _generate_context_summary(context: Dict[str, Any]) -> str:
    """Generate human-readable context summary for prompt injection."""
    if context.get("is_new_workspace"):
        return ""

    lines = [
        "=== WORKSPACE MEMORY (from previous sessions) ===",
    ]

    if context.get("workspace_name"):
        lines.append(f"Project: {context['workspace_name']}")

    if context.get("last_active"):
        lines.append(f"Last session: {context['last_active']}")

    # Add facts
    facts = context.get("facts", {})
    category_labels = {
        "server": "Server Status",
        "file": "Important Files",
        "decision": "Decisions Made",
        "error": "Known Issues",
        "task": "Completed Tasks",
        "discovery": "Discovered Info",
        "dependency": "Dependencies",
        "version": "Versions",
    }

    for category, cat_facts in facts.items():
        if cat_facts:
            label = category_labels.get(category, category.title())
            lines.append(f"\n{label}:")
            for key, value in list(cat_facts.items())[:8]:
                display_key = key.replace("_", " ").title()
                lines.append(f"  - {display_key}: {value}")

    # Add error resolutions
    if context.get("error_resolutions"):
        lines.append("\nKnown Error Solutions:")
        for er in context["error_resolutions"][:3]:
            lines.append(f"  - {er['error_type']}: {er['resolution_summary'][:60]}...")

    # Add key dependencies
    if context.get("dependencies"):
        lines.append("\nInstalled Packages:")
        from collections import defaultdict

        deps_by_manager = defaultdict(list)
        for dep in context["dependencies"]:
            deps_by_manager[dep["manager"]].append(dep["name"])
        for manager, deps in deps_by_manager.items():
            lines.append(f"  {manager}: {', '.join(deps[:8])}")

    lines.append("\n=== END WORKSPACE MEMORY ===")
    return "\n".join(lines)


def inject_memory_context(
    message: str,
    memory_context: Dict[str, Any],
) -> str:
    """
    Inject memory context into the user message.

    This adds the context summary before the user's message so NAVI
    is aware of previous session information.

    Args:
        message: Original user message
        memory_context: Context from load_workspace_memory

    Returns:
        Enhanced message with memory context prepended
    """
    context_summary = memory_context.get("context_summary", "")

    if not context_summary:
        return message

    # Prepend context to message
    return f"{context_summary}\n\n{message}"


def save_conversation_exchange_sync(
    user_id: str,
    workspace_path: str,
    user_message: str,
    assistant_response: str,
    actions: Optional[List[Dict[str, Any]]],
    db: Session,
) -> bool:
    """
    Save a conversation exchange to persistent memory (synchronous version).

    This extracts facts from the exchange and stores them for future sessions.

    Args:
        user_id: The user ID
        workspace_path: Path to the workspace
        user_message: The user's message
        assistant_response: NAVI's response
        actions: List of actions taken
        db: Database session

    Returns:
        True if saved successfully, False otherwise
    """
    if not workspace_path:
        return False

    try:
        from sqlalchemy import text
        from datetime import datetime
        import uuid

        normalized_path = workspace_path.rstrip("/")
        user_id_int = int(user_id) if user_id.isdigit() else 1

        # Get or create workspace session
        result = db.execute(
            text("""
                SELECT id FROM navi_workspace_sessions
                WHERE user_id = :user_id AND workspace_path = :workspace_path
            """),
            {"user_id": user_id_int, "workspace_path": normalized_path},
        )
        row = result.fetchone()

        if row:
            workspace_session_id = row[0]
            # Update last_active
            db.execute(
                text("""
                    UPDATE navi_workspace_sessions
                    SET last_active = :now
                    WHERE id = :ws_id
                """),
                {"now": datetime.utcnow(), "ws_id": workspace_session_id},
            )
        else:
            # Create new workspace session
            workspace_session_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO navi_workspace_sessions (id, user_id, workspace_path, first_seen, last_active)
                    VALUES (:id, :user_id, :workspace_path, :now, :now)
                """),
                {
                    "id": workspace_session_id,
                    "user_id": user_id_int,
                    "workspace_path": normalized_path,
                    "now": datetime.utcnow(),
                },
            )

        # Extract and save facts from the response
        facts = _extract_facts_from_response(assistant_response, actions or [])

        for fact in facts:
            # Mark existing facts as not current
            db.execute(
                text("""
                    UPDATE navi_session_facts
                    SET is_current = false
                    WHERE workspace_session_id = :ws_id
                    AND category = :category
                    AND fact_key = :fact_key
                    AND is_current = true
                """),
                {
                    "ws_id": workspace_session_id,
                    "category": fact["category"],
                    "fact_key": fact["key"],
                },
            )

            # Insert new fact
            db.execute(
                text("""
                    INSERT INTO navi_session_facts
                    (id, workspace_session_id, category, fact_key, fact_value, is_current, created_at, last_verified)
                    VALUES (:id, :ws_id, :category, :fact_key, :fact_value, true, :now, :now)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "ws_id": workspace_session_id,
                    "category": fact["category"],
                    "fact_key": fact["key"],
                    "fact_value": fact["value"],
                    "now": datetime.utcnow(),
                },
            )

        # Extract and save dependencies
        dependencies = _extract_dependencies_from_actions(actions or [])
        for dep in dependencies:
            # Upsert dependency
            db.execute(
                text("""
                    INSERT INTO navi_installed_dependencies
                    (id, workspace_session_id, package_manager, package_name, package_version, installed_at, last_verified)
                    VALUES (:id, :ws_id, :manager, :name, :version, :now, :now)
                    ON CONFLICT (workspace_session_id, package_manager, package_name)
                    DO UPDATE SET package_version = :version, last_verified = :now
                """),
                {
                    "id": str(uuid.uuid4()),
                    "ws_id": workspace_session_id,
                    "manager": dep["manager"],
                    "name": dep["name"],
                    "version": dep.get("version"),
                    "now": datetime.utcnow(),
                },
            )

        db.commit()

        logger.info(
            f"Saved exchange to memory: {len(facts)} facts, {len(dependencies)} deps"
        )
        return True

    except Exception as e:
        logger.warning(f"Error saving conversation exchange: {e}")
        try:
            db.rollback()
        except:
            pass
        return False


def _extract_facts_from_response(
    response: str,
    actions: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Extract facts from a response and actions."""
    import re

    facts = []

    # Extract ports
    port_patterns = [
        r"port\s*[:\s]?\s*(\d{2,5})",
        r"localhost:(\d{2,5})",
        r"127\.0\.0\.1:(\d{2,5})",
    ]
    for pattern in port_patterns:
        for match in re.findall(pattern, response.lower()):
            facts.append({"category": "server", "key": f"port_{match}", "value": match})

    # Extract server status
    if re.search(r"server\s+is\s+(now\s+)?running|successfully\s+started", response.lower()):
        facts.append({"category": "server", "key": "status", "value": "running"})

    # Extract from actions
    for action in actions:
        if action.get("type") == "command":
            cmd = action.get("command", "")
            exit_code = action.get("exit_code", action.get("exitCode"))
            if exit_code == 0:
                facts.append({"category": "task", "key": "last_command", "value": cmd})
                facts.append({"category": "task", "key": "last_command_status", "value": "success"})
        elif action.get("type") in ["create", "edit"]:
            file_path = action.get("file") or action.get("path", "")
            facts.append({"category": "file", "key": f"modified_{action['type']}", "value": file_path})

    return facts


def _extract_dependencies_from_actions(
    actions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Extract installed dependencies from actions."""
    import re

    dependencies = []

    install_patterns = [
        (r"npm install\s+([^\s]+)", "npm"),
        (r"npm i\s+([^\s]+)", "npm"),
        (r"yarn add\s+([^\s]+)", "yarn"),
        (r"pip install\s+([^\s]+)", "pip"),
        (r"pip3 install\s+([^\s]+)", "pip"),
    ]

    for action in actions:
        if action.get("type") == "command":
            cmd = action.get("command", "")
            exit_code = action.get("exit_code", action.get("exitCode"))

            if exit_code != 0:
                continue

            for pattern, manager in install_patterns:
                for match in re.findall(pattern, cmd, re.IGNORECASE):
                    # Clean up package name
                    package = re.sub(r"@[\d.]+$", "", match)
                    dependencies.append({"manager": manager, "name": package})

    return dependencies


async def find_similar_error_resolution(
    user_id: str,
    workspace_path: str,
    error_message: str,
    db: Session,
) -> Optional[Dict[str, Any]]:
    """
    Find a previously successful resolution for a similar error.

    Args:
        user_id: The user ID
        workspace_path: Path to the workspace
        error_message: The error message to match
        db: Database session

    Returns:
        Resolution info if found, None otherwise
    """
    if not workspace_path:
        return None

    try:
        from sqlalchemy import text
        import hashlib
        import re

        # Create error signature
        normalized = re.sub(r":\d+:\d+", ":X:X", error_message)
        normalized = re.sub(r"[/\\][\w.-]+[/\\]", "/", normalized)
        signature = hashlib.sha256(normalized.encode()).hexdigest()[:32]

        normalized_path = workspace_path.rstrip("/")
        user_id_int = int(user_id) if user_id.isdigit() else 1

        result = db.execute(
            text("""
                SELECT er.error_type, er.resolution_summary, er.resolution_steps,
                       er.times_successful, er.times_applied
                FROM navi_error_resolutions er
                JOIN navi_workspace_sessions ws ON er.workspace_session_id = ws.id
                WHERE ws.user_id = :user_id
                AND ws.workspace_path = :workspace_path
                AND er.error_signature = :signature
                ORDER BY (er.times_successful::float / NULLIF(er.times_applied, 0)) DESC NULLS LAST
                LIMIT 1
            """),
            {
                "user_id": user_id_int,
                "workspace_path": normalized_path,
                "signature": signature,
            },
        )
        row = result.fetchone()

        if row:
            return {
                "error_type": row[0],
                "resolution_summary": row[1],
                "resolution_steps": row[2],
                "success_rate": row[3] / row[4] if row[4] > 0 else 0,
            }

        return None

    except Exception as e:
        logger.warning(f"Error finding error resolution: {e}")
        return None
