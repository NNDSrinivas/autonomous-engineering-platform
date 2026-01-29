"""
Persistent Session Memory Service

Enhanced session memory that persists across restarts and links by workspace.
This addresses the issue where NAVI forgets context when VS Code is reloaded.

Key Features:
1. Database-backed fact storage (persists across restarts)
2. Workspace-based linking (same project = same context)
3. Error resolution tracking (learn from past fixes)
4. Dependency tracking (know what's installed)
5. Automatic context loading on session start
"""

import re
import hashlib
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import structlog

from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


@dataclass
class FactUpdate:
    """Represents a fact to be stored or updated."""

    category: str
    key: str
    value: str
    confidence: float = 1.0
    source_message_id: Optional[str] = None


@dataclass
class ErrorResolutionRecord:
    """Represents an error and its resolution."""

    error_type: str
    error_message: str
    resolution_steps: List[Dict[str, Any]]
    resolution_summary: str
    context: Dict[str, Any] = field(default_factory=dict)


class PersistentSessionMemory:
    """
    Database-backed session memory service.

    Persists facts, errors, and resolutions to the database so NAVI
    can remember context across VS Code restarts.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._fact_extractors = [
            self._extract_port_info,
            self._extract_file_paths,
            self._extract_server_status,
            self._extract_urls,
            self._extract_commands_run,
            self._extract_errors,
            self._extract_decisions,
            self._extract_dependencies,
            self._extract_versions,
        ]

    async def get_or_create_workspace_session(
        self,
        user_id: int,
        workspace_path: str,
        workspace_name: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> "WorkspaceSession":
        """
        Get existing workspace session or create a new one.

        This is the key method that links sessions by workspace path.
        """
        from backend.database.models.session_facts import WorkspaceSession

        # Normalize workspace path
        normalized_path = workspace_path.rstrip("/")

        # Try to find existing workspace session
        result = await self.db.execute(
            select(WorkspaceSession).where(
                and_(
                    WorkspaceSession.user_id == user_id,
                    WorkspaceSession.workspace_path == normalized_path,
                )
            )
        )
        workspace_session = result.scalar_one_or_none()

        if workspace_session:
            # Update with new session ID and last active time
            if session_id:
                workspace_session.current_session_id = session_id
            workspace_session.last_active = datetime.utcnow()
            await self.db.commit()

            logger.info(
                "Resumed workspace session",
                workspace_path=normalized_path,
                session_id=session_id,
            )
            return workspace_session

        # Create new workspace session
        workspace_session = WorkspaceSession(
            user_id=user_id,
            workspace_path=normalized_path,
            workspace_name=workspace_name,
            current_session_id=session_id,
        )
        self.db.add(workspace_session)
        await self.db.commit()
        await self.db.refresh(workspace_session)

        logger.info(
            "Created new workspace session",
            workspace_path=normalized_path,
            session_id=session_id,
        )
        return workspace_session

    async def load_workspace_context(
        self,
        user_id: int,
        workspace_path: str,
    ) -> Dict[str, Any]:
        """
        Load all persisted context for a workspace.

        This is called when starting a new session to restore previous context.
        Returns facts, error resolutions, and installed dependencies.
        """
        from backend.database.models.session_facts import (
            WorkspaceSession,
            SessionFact,
            ErrorResolution,
            InstalledDependency,
        )

        normalized_path = workspace_path.rstrip("/")

        # Get workspace session
        result = await self.db.execute(
            select(WorkspaceSession).where(
                and_(
                    WorkspaceSession.user_id == user_id,
                    WorkspaceSession.workspace_path == normalized_path,
                )
            )
        )
        workspace_session = result.scalar_one_or_none()

        if not workspace_session:
            return {
                "is_new_workspace": True,
                "facts": {},
                "errors": [],
                "dependencies": [],
            }

        # Load current facts
        facts_result = await self.db.execute(
            select(SessionFact).where(
                and_(
                    SessionFact.workspace_session_id == workspace_session.id,
                    SessionFact.is_current,
                )
            )
        )
        facts = facts_result.scalars().all()

        # Load recent error resolutions (last 20, sorted by success rate)
        errors_result = await self.db.execute(
            select(ErrorResolution)
            .where(ErrorResolution.workspace_session_id == workspace_session.id)
            .order_by(
                (
                    ErrorResolution.times_successful / ErrorResolution.times_applied
                ).desc()
            )
            .limit(20)
        )
        error_resolutions = errors_result.scalars().all()

        # Load installed dependencies
        deps_result = await self.db.execute(
            select(InstalledDependency).where(
                InstalledDependency.workspace_session_id == workspace_session.id
            )
        )
        dependencies = deps_result.scalars().all()

        # Format for context injection
        context = {
            "is_new_workspace": False,
            "workspace_name": workspace_session.workspace_name,
            "last_active": (
                workspace_session.last_active.isoformat()
                if workspace_session.last_active
                else None
            ),
            "last_known_state": workspace_session.last_known_state or {},
            "facts": self._format_facts(facts),
            "error_resolutions": [
                {
                    "error_type": er.error_type,
                    "error_signature": er.error_signature,
                    "resolution_summary": er.resolution_summary,
                    "success_rate": (
                        er.times_successful / er.times_applied
                        if er.times_applied > 0
                        else 0
                    ),
                }
                for er in error_resolutions
            ],
            "dependencies": [
                {
                    "manager": dep.package_manager,
                    "name": dep.package_name,
                    "version": dep.package_version,
                }
                for dep in dependencies
            ],
        }

        logger.info(
            "Loaded workspace context",
            workspace_path=normalized_path,
            facts_count=len(facts),
            error_resolutions_count=len(error_resolutions),
            dependencies_count=len(dependencies),
        )

        return context

    def _format_facts(self, facts) -> Dict[str, Dict[str, str]]:
        """Format facts for context injection, grouped by category."""
        grouped = defaultdict(dict)
        for fact in facts:
            grouped[fact.category][fact.fact_key] = fact.fact_value
        return dict(grouped)

    def generate_context_summary(self, context: Dict[str, Any]) -> str:
        """
        Generate a human-readable context summary for injection into prompts.

        This is what NAVI "remembers" from previous sessions.
        """
        if context.get("is_new_workspace"):
            return ""

        lines = [
            "=== WORKSPACE MEMORY (from previous sessions) ===",
            f"Project: {context.get('workspace_name', 'Unknown')}",
        ]

        if context.get("last_active"):
            lines.append(f"Last worked on: {context['last_active']}")

        # Add facts by category
        facts = context.get("facts", {})
        category_labels = {
            "server": "Server Status",
            "file": "Important Files",
            "decision": "Decisions Made",
            "error": "Known Issues",
            "task": "Completed Tasks",
            "discovery": "Discovered Info",
            "dependency": "Installed Packages",
            "version": "Versions",
        }

        for category, cat_facts in facts.items():
            if cat_facts:
                label = category_labels.get(category, category.title())
                lines.append(f"\n{label}:")
                for key, value in list(cat_facts.items())[:10]:  # Limit per category
                    # Clean up the key for display
                    display_key = key.replace("_", " ").title()
                    lines.append(f"  - {display_key}: {value}")

        # Add relevant error resolutions
        if context.get("error_resolutions"):
            lines.append("\nKnown Error Solutions:")
            for er in context["error_resolutions"][:5]:  # Top 5
                lines.append(
                    f"  - {er['error_type']}: {er['resolution_summary'][:80]}..."
                )

        # Add key dependencies
        if context.get("dependencies"):
            lines.append("\nInstalled Dependencies:")
            deps_by_manager = defaultdict(list)
            for dep in context["dependencies"]:
                deps_by_manager[dep["manager"]].append(
                    f"{dep['name']}" + (f"@{dep['version']}" if dep["version"] else "")
                )
            for manager, deps in deps_by_manager.items():
                lines.append(f"  {manager}: {', '.join(deps[:10])}")

        lines.append("\n=== END WORKSPACE MEMORY ===\n")
        return "\n".join(lines)

    async def process_exchange(
        self,
        user_id: int,
        workspace_path: str,
        user_message: str,
        assistant_response: str,
        message_id: Optional[str] = None,
        actions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Process a conversation exchange and extract/persist facts.

        This should be called after each NAVI response to capture
        any new information for future sessions.
        """
        workspace_session = await self.get_or_create_workspace_session(
            user_id=user_id,
            workspace_path=workspace_path,
        )

        timestamp = datetime.utcnow()
        extracted_facts: List[FactUpdate] = []

        # Run all extractors on the response
        for extractor in self._fact_extractors:
            try:
                facts = extractor(assistant_response, timestamp, message_id)
                extracted_facts.extend(facts)
            except Exception as e:
                logger.warning(f"Extractor failed: {extractor.__name__}", error=str(e))

        # Also extract from actions
        if actions:
            for action in actions:
                action_facts = self._extract_from_action(action, timestamp, message_id)
                extracted_facts.extend(action_facts)

        # Persist facts
        if extracted_facts:
            await self._persist_facts(workspace_session.id, extracted_facts)

        # Check for error resolutions
        error_resolutions = self._detect_error_resolutions(
            user_message, assistant_response, actions or []
        )
        if error_resolutions:
            await self._persist_error_resolutions(
                workspace_session.id, error_resolutions
            )

        # Check for dependency installations
        dependencies = self._extract_dependency_installs(actions or [])
        if dependencies:
            await self._persist_dependencies(workspace_session.id, dependencies)

        logger.info(
            "Processed exchange",
            workspace_path=workspace_path,
            new_facts=len(extracted_facts),
            error_resolutions=len(error_resolutions),
            dependencies=len(dependencies),
        )

        return {
            "facts_extracted": len(extracted_facts),
            "error_resolutions": len(error_resolutions),
            "dependencies": len(dependencies),
        }

    async def _persist_facts(
        self,
        workspace_session_id: str,
        facts: List[FactUpdate],
    ) -> None:
        """Persist or update facts in the database."""
        from backend.database.models.session_facts import SessionFact

        for fact in facts:
            # Mark existing facts with same key as superseded
            await self.db.execute(
                update(SessionFact)
                .where(
                    and_(
                        SessionFact.workspace_session_id == workspace_session_id,
                        SessionFact.category == fact.category,
                        SessionFact.fact_key == fact.key,
                        SessionFact.is_current,
                    )
                )
                .values(is_current=False)
            )

            # Insert new fact
            new_fact = SessionFact(
                workspace_session_id=workspace_session_id,
                category=fact.category,
                fact_key=fact.key,
                fact_value=fact.value,
                confidence=fact.confidence,
                source_message_id=fact.source_message_id,
                is_current=True,
            )
            self.db.add(new_fact)

        await self.db.commit()

    async def _persist_error_resolutions(
        self,
        workspace_session_id: str,
        resolutions: List[ErrorResolutionRecord],
    ) -> None:
        """Persist error resolutions to the database."""
        from backend.database.models.session_facts import ErrorResolution

        for resolution in resolutions:
            # Create normalized signature for matching
            signature = self._create_error_signature(resolution.error_message)

            # Check if we have an existing resolution for this error
            result = await self.db.execute(
                select(ErrorResolution).where(
                    and_(
                        ErrorResolution.workspace_session_id == workspace_session_id,
                        ErrorResolution.error_signature == signature,
                    )
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing resolution
                existing.times_applied += 1
                existing.times_successful += 1  # Assume success since we got here
                existing.resolution_steps = resolution.resolution_steps
                existing.resolution_summary = resolution.resolution_summary
            else:
                # Create new resolution
                new_resolution = ErrorResolution(
                    workspace_session_id=workspace_session_id,
                    error_type=resolution.error_type,
                    error_signature=signature,
                    error_message=resolution.error_message,
                    resolution_steps=resolution.resolution_steps,
                    resolution_summary=resolution.resolution_summary,
                    context_data=resolution.context,
                )
                self.db.add(new_resolution)

        await self.db.commit()

    async def _persist_dependencies(
        self,
        workspace_session_id: str,
        dependencies: List[Dict[str, Any]],
    ) -> None:
        """Persist installed dependencies to the database."""
        from backend.database.models.session_facts import InstalledDependency

        for dep in dependencies:
            # Check if dependency already exists
            result = await self.db.execute(
                select(InstalledDependency).where(
                    and_(
                        InstalledDependency.workspace_session_id
                        == workspace_session_id,
                        InstalledDependency.package_manager == dep["manager"],
                        InstalledDependency.package_name == dep["name"],
                    )
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update version and last verified
                existing.package_version = dep.get("version")
                existing.last_verified = datetime.utcnow()
            else:
                # Create new dependency record
                new_dep = InstalledDependency(
                    workspace_session_id=workspace_session_id,
                    package_manager=dep["manager"],
                    package_name=dep["name"],
                    package_version=dep.get("version"),
                    is_dev_dependency=dep.get("is_dev", False),
                    install_command=dep.get("command"),
                )
                self.db.add(new_dep)

        await self.db.commit()

    def _create_error_signature(self, error_message: str) -> str:
        """
        Create a normalized signature for error matching.

        Removes variable parts (line numbers, timestamps, etc.)
        to match similar errors.
        """
        # Remove line numbers
        normalized = re.sub(r":\d+:\d+", ":X:X", error_message)
        # Remove file paths (keep just filename)
        normalized = re.sub(r"[/\\][\w.-]+[/\\]", "/", normalized)
        # Remove timestamps
        normalized = re.sub(
            r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", "TIMESTAMP", normalized
        )
        # Remove hex addresses
        normalized = re.sub(r"0x[0-9a-fA-F]+", "0xHEX", normalized)
        # Create hash
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]

    def _detect_error_resolutions(
        self,
        user_message: str,
        assistant_response: str,
        actions: List[Dict[str, Any]],
    ) -> List[ErrorResolutionRecord]:
        """
        Detect if an error was mentioned and then resolved in this exchange.
        """
        resolutions = []

        # Look for error patterns in user message
        error_patterns = [
            (r"error[:\s]+(.+?)(?:\n|$)", "generic_error"),
            (r"failed[:\s]+(.+?)(?:\n|$)", "command_failed"),
            (r"cannot find module[:\s]+(['\"]?\w+)", "module_not_found"),
            (r"command not found[:\s]+(\w+)", "command_not_found"),
            (r"permission denied", "permission_denied"),
            (r"ENOENT", "file_not_found"),
            (r"EADDRINUSE", "port_in_use"),
        ]

        user_lower = user_message.lower()
        response_lower = assistant_response.lower()

        for pattern, error_type in error_patterns:
            matches = re.findall(pattern, user_lower, re.IGNORECASE)
            if matches:
                # Check if response indicates a fix
                fix_indicators = [
                    "fixed",
                    "resolved",
                    "solution",
                    "try this",
                    "should work",
                    "install",
                    "run this",
                ]
                if any(indicator in response_lower for indicator in fix_indicators):
                    # Extract resolution steps from actions
                    resolution_steps = []
                    for action in actions:
                        if action.get("type") in ["command", "edit", "create"]:
                            resolution_steps.append(
                                {
                                    "type": action.get("type"),
                                    "content": action.get("command")
                                    or action.get("file"),
                                }
                            )

                    if resolution_steps:
                        resolutions.append(
                            ErrorResolutionRecord(
                                error_type=error_type,
                                error_message=(
                                    matches[0] if matches else user_message[:200]
                                ),
                                resolution_steps=resolution_steps,
                                resolution_summary=self._extract_resolution_summary(
                                    assistant_response
                                ),
                            )
                        )

        return resolutions

    def _extract_resolution_summary(self, response: str) -> str:
        """Extract a brief summary of the resolution from the response."""
        # Look for summary patterns
        patterns = [
            r"(?:the fix|solution|to fix this|try)[:\s]+(.+?)(?:\n|$)",
            r"(?:I've|I have|this will)[:\s]+(.+?)(?:\n|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:200]

        # Fallback: first sentence
        sentences = response.split(".")
        if sentences:
            return sentences[0].strip()[:200]
        return response[:200]

    def _extract_dependency_installs(
        self,
        actions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Extract dependency installations from actions."""
        dependencies = []

        install_patterns = [
            (r"npm install\s+([^\s]+)", "npm", False),
            (r"npm i\s+([^\s]+)", "npm", False),
            (r"npm install --save-dev\s+([^\s]+)", "npm", True),
            (r"npm i -D\s+([^\s]+)", "npm", True),
            (r"yarn add\s+([^\s]+)", "yarn", False),
            (r"yarn add --dev\s+([^\s]+)", "yarn", True),
            (r"pip install\s+([^\s]+)", "pip", False),
            (r"pip3 install\s+([^\s]+)", "pip", False),
            (r"cargo add\s+([^\s]+)", "cargo", False),
        ]

        for action in actions:
            if action.get("type") == "command":
                command = action.get("command", "")
                exit_code = action.get("exit_code", action.get("exitCode"))

                # Only track successful installs
                if exit_code != 0:
                    continue

                for pattern, manager, is_dev in install_patterns:
                    matches = re.findall(pattern, command, re.IGNORECASE)
                    for match in matches:
                        # Clean up package name (remove version specifier)
                        package = re.sub(r"@[\d.]+$", "", match)
                        dependencies.append(
                            {
                                "manager": manager,
                                "name": package,
                                "is_dev": is_dev,
                                "command": command,
                            }
                        )

        return dependencies

    # === Fact Extractors ===

    def _extract_port_info(
        self,
        text: str,
        timestamp: datetime,
        message_id: Optional[str],
    ) -> List[FactUpdate]:
        """Extract port numbers from response."""
        facts = []
        port_patterns = [
            r"port\s*[:\s]?\s*(\d{2,5})",
            r"localhost:(\d{2,5})",
            r"127\.0\.0\.1:(\d{2,5})",
            r"running\s+(?:on|at)\s+.*?:(\d{2,5})",
        ]

        ports_found: Set[str] = set()
        for pattern in port_patterns:
            matches = re.findall(pattern, text.lower())
            ports_found.update(matches)

        for port in ports_found:
            facts.append(
                FactUpdate(
                    category="server",
                    key=f"port_{port}",
                    value=port,
                    source_message_id=message_id,
                )
            )

        # Identify primary port
        if ports_found:
            if "development server" in text.lower() or "dev server" in text.lower():
                facts.append(
                    FactUpdate(
                        category="server",
                        key="primary_port",
                        value=list(ports_found)[0],
                        source_message_id=message_id,
                    )
                )

        return facts

    def _extract_server_status(
        self,
        text: str,
        timestamp: datetime,
        message_id: Optional[str],
    ) -> List[FactUpdate]:
        """Extract server running status."""
        facts = []
        lower_text = text.lower()

        running_patterns = [
            r"server\s+is\s+(now\s+)?running",
            r"successfully\s+started",
            r"application\s+is\s+running",
        ]

        for pattern in running_patterns:
            if re.search(pattern, lower_text):
                facts.append(
                    FactUpdate(
                        category="server",
                        key="status",
                        value="running",
                        source_message_id=message_id,
                    )
                )
                break

        if re.search(r"server\s+stopped|failed\s+to\s+start", lower_text):
            facts.append(
                FactUpdate(
                    category="server",
                    key="status",
                    value="stopped",
                    source_message_id=message_id,
                )
            )

        return facts

    def _extract_file_paths(
        self,
        text: str,
        timestamp: datetime,
        message_id: Optional[str],
    ) -> List[FactUpdate]:
        """Extract important file paths."""
        facts = []
        path_pattern = (
            r"(?:^|[\s`\"'])(/[^\s`\"']+\.[a-z]{1,5}|[a-z]+/[^\s`\"']+\.[a-z]{1,5})"
        )
        matches = re.findall(path_pattern, text, re.MULTILINE | re.IGNORECASE)

        seen = set()
        for match in matches[:5]:  # Limit to 5
            if match not in seen:
                seen.add(match)
                facts.append(
                    FactUpdate(
                        category="file",
                        key=f"mentioned_{len(facts)}",
                        value=match,
                        source_message_id=message_id,
                    )
                )

        return facts

    def _extract_urls(
        self,
        text: str,
        timestamp: datetime,
        message_id: Optional[str],
    ) -> List[FactUpdate]:
        """Extract URLs."""
        facts = []
        url_pattern = r"https?://[^\s<>\"')\]]+[^\s<>\"')\].,;:!?]"
        matches = re.findall(url_pattern, text)

        for i, url in enumerate(matches[:3]):
            facts.append(
                FactUpdate(
                    category="discovery",
                    key=f"url_{i}",
                    value=url,
                    source_message_id=message_id,
                )
            )

        return facts

    def _extract_commands_run(
        self,
        text: str,
        timestamp: datetime,
        message_id: Optional[str],
    ) -> List[FactUpdate]:
        """Extract commands that were run."""
        facts = []
        ran_patterns = [
            r"(?:ran|executed|running)[\s:]+`([^`]+)`",
            r"command[\s:]+`([^`]+)`",
        ]

        for pattern in ran_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for i, cmd in enumerate(matches[:3]):
                facts.append(
                    FactUpdate(
                        category="task",
                        key=f"command_{i}",
                        value=cmd,
                        source_message_id=message_id,
                    )
                )

        return facts

    def _extract_errors(
        self,
        text: str,
        timestamp: datetime,
        message_id: Optional[str],
    ) -> List[FactUpdate]:
        """Extract error information."""
        facts = []
        error_patterns = [
            r"error[:\s]+([^\n.]+)",
            r"failed[:\s]+([^\n.]+)",
        ]

        for pattern in error_patterns:
            matches = re.findall(pattern, text.lower())
            for i, error in enumerate(matches[:2]):
                facts.append(
                    FactUpdate(
                        category="error",
                        key=f"error_{i}",
                        value=error.strip()[:150],
                        source_message_id=message_id,
                    )
                )

        return facts

    def _extract_decisions(
        self,
        text: str,
        timestamp: datetime,
        message_id: Optional[str],
    ) -> List[FactUpdate]:
        """Extract decisions made."""
        facts = []
        decision_patterns = [
            r"(?:decided|using|selected)[:\s]+([^\n.]+)",
            r"(?:the solution is|fix is)[:\s]+([^\n.]+)",
        ]

        for pattern in decision_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for i, decision in enumerate(matches[:2]):
                facts.append(
                    FactUpdate(
                        category="decision",
                        key=f"decision_{i}",
                        value=decision.strip()[:150],
                        source_message_id=message_id,
                    )
                )

        return facts

    def _extract_dependencies(
        self,
        text: str,
        timestamp: datetime,
        message_id: Optional[str],
    ) -> List[FactUpdate]:
        """Extract mentioned dependencies."""
        facts = []

        # Look for package installation patterns
        install_patterns = [
            r"installed\s+([a-z0-9@/-]+)",
            r"npm install[ed]?\s+([a-z0-9@/-]+)",
            r"pip install[ed]?\s+([a-z0-9_-]+)",
        ]

        for pattern in install_patterns:
            matches = re.findall(pattern, text.lower())
            for pkg in matches[:3]:
                facts.append(
                    FactUpdate(
                        category="dependency",
                        key=f"package_{pkg.replace('@', '_').replace('/', '_')}",
                        value=pkg,
                        source_message_id=message_id,
                    )
                )

        return facts

    def _extract_versions(
        self,
        text: str,
        timestamp: datetime,
        message_id: Optional[str],
    ) -> List[FactUpdate]:
        """Extract version information."""
        facts = []

        version_patterns = [
            (r"node\s+v?(\d+\.\d+\.\d+)", "node_version"),
            (r"npm\s+v?(\d+\.\d+\.\d+)", "npm_version"),
            (r"python\s+(\d+\.\d+\.\d+)", "python_version"),
            (r"react\s+v?(\d+\.\d+\.\d+)", "react_version"),
        ]

        for pattern, key in version_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                facts.append(
                    FactUpdate(
                        category="version",
                        key=key,
                        value=match.group(1),
                        source_message_id=message_id,
                    )
                )

        return facts

    def _extract_from_action(
        self,
        action: Dict[str, Any],
        timestamp: datetime,
        message_id: Optional[str],
    ) -> List[FactUpdate]:
        """Extract facts from an action object."""
        facts = []
        action_type = action.get("type", "")

        if action_type == "command":
            cmd = action.get("command", "")
            exit_code = action.get("exit_code", action.get("exitCode"))

            facts.append(
                FactUpdate(
                    category="task",
                    key="last_command",
                    value=cmd,
                    source_message_id=message_id,
                )
            )

            if exit_code == 0:
                facts.append(
                    FactUpdate(
                        category="task",
                        key="last_command_status",
                        value="success",
                        source_message_id=message_id,
                    )
                )
            elif exit_code is not None:
                facts.append(
                    FactUpdate(
                        category="error",
                        key="last_command_status",
                        value=f"failed with exit code {exit_code}",
                        source_message_id=message_id,
                    )
                )

        elif action_type in ["create", "edit"]:
            file_path = action.get("file") or action.get("path", "")
            facts.append(
                FactUpdate(
                    category="file",
                    key=f"modified_{action_type}",
                    value=file_path,
                    source_message_id=message_id,
                )
            )

        return facts

    async def find_similar_error_resolution(
        self,
        user_id: int,
        workspace_path: str,
        error_message: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a previously successful resolution for a similar error.

        This is called when NAVI encounters an error to check if
        we've solved something similar before.
        """
        from backend.database.models.session_facts import (
            WorkspaceSession,
            ErrorResolution,
        )

        normalized_path = workspace_path.rstrip("/")
        signature = self._create_error_signature(error_message)

        # First check workspace-specific resolutions
        result = await self.db.execute(
            select(ErrorResolution)
            .join(WorkspaceSession)
            .where(
                and_(
                    WorkspaceSession.user_id == user_id,
                    WorkspaceSession.workspace_path == normalized_path,
                    ErrorResolution.error_signature == signature,
                )
            )
            .order_by(
                (
                    ErrorResolution.times_successful / ErrorResolution.times_applied
                ).desc()
            )
            .limit(1)
        )
        resolution = result.scalar_one_or_none()

        if resolution:
            return {
                "error_type": resolution.error_type,
                "resolution_summary": resolution.resolution_summary,
                "resolution_steps": resolution.resolution_steps,
                "success_rate": resolution.times_successful / resolution.times_applied,
                "times_applied": resolution.times_applied,
            }

        return None


# Factory function for dependency injection
async def get_persistent_session_memory(db: AsyncSession) -> PersistentSessionMemory:
    """Get a PersistentSessionMemory instance with database session."""
    return PersistentSessionMemory(db)
