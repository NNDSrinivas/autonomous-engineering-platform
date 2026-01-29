"""
Session Memory Service

Provides in-session memory for NAVI conversations. Extracts and stores key facts
from each exchange (like port numbers, file paths, decisions made) so NAVI can
reference them without relying solely on raw conversation history.

This addresses the issue where NAVI might "forget" things it just said by
providing a structured facts store that's injected into the context.
"""

import re
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SessionFact:
    """A single fact extracted from a conversation."""

    category: str  # e.g., "server", "file", "decision", "error"
    key: str  # e.g., "port", "running_status", "file_path"
    value: str  # e.g., "3001", "running", "/src/app.ts"
    timestamp: str
    source_message_id: Optional[str] = None
    confidence: float = 1.0


@dataclass
class SessionMemory:
    """Memory store for a single conversation session."""

    session_id: str
    facts: Dict[str, SessionFact] = field(default_factory=dict)  # key -> fact
    recent_actions: List[Dict[str, Any]] = field(default_factory=list)
    discovered_info: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def add_fact(self, fact: SessionFact) -> None:
        """Add or update a fact."""
        fact_key = f"{fact.category}:{fact.key}"
        self.facts[fact_key] = fact
        self.updated_at = datetime.utcnow().isoformat()

    def get_fact(self, category: str, key: str) -> Optional[SessionFact]:
        """Retrieve a specific fact."""
        return self.facts.get(f"{category}:{key}")

    def get_facts_by_category(self, category: str) -> List[SessionFact]:
        """Get all facts in a category."""
        return [f for k, f in self.facts.items() if k.startswith(f"{category}:")]

    def get_context_summary(self) -> str:
        """Generate a context summary for injection into prompts."""
        if not self.facts:
            return ""

        lines = ["=== SESSION CONTEXT (from earlier in this conversation) ==="]

        # Group facts by category
        by_category: Dict[str, List[SessionFact]] = defaultdict(list)
        for fact in self.facts.values():
            by_category[fact.category].append(fact)

        category_labels = {
            "server": "🖥️ Server Status",
            "file": "📁 Files Mentioned",
            "decision": "✅ Decisions Made",
            "error": "❌ Errors Encountered",
            "task": "📋 Tasks Completed",
            "discovery": "🔍 Discovered Information",
        }

        for category, facts in by_category.items():
            label = category_labels.get(category, f"📌 {category.title()}")
            lines.append(f"\n{label}:")
            for fact in facts:
                lines.append(f"  - {fact.key}: {fact.value}")

        lines.append("\n=== END SESSION CONTEXT ===\n")
        return "\n".join(lines)


class SessionMemoryService:
    """
    Manages session-level memory for NAVI conversations.

    This service:
    1. Extracts key facts from assistant responses
    2. Stores them in a structured format
    3. Provides context injection for subsequent messages
    """

    def __init__(self):
        self._sessions: Dict[str, SessionMemory] = {}
        # Patterns for extracting facts from responses
        self._extractors = [
            self._extract_port_info,
            self._extract_file_paths,
            self._extract_server_status,
            self._extract_urls,
            self._extract_commands_run,
            self._extract_errors,
            self._extract_decisions,
        ]

    def get_or_create_session(self, session_id: str) -> SessionMemory:
        """Get existing session or create new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMemory(session_id=session_id)
            logger.info("Created new session memory", session_id=session_id)
        return self._sessions[session_id]

    def process_exchange(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        message_id: Optional[str] = None,
        actions: Optional[List[Dict[str, Any]]] = None,
    ) -> SessionMemory:
        """
        Process a conversation exchange and extract facts.

        Args:
            session_id: The conversation session ID
            user_message: What the user said
            assistant_response: What NAVI responded
            message_id: Optional message ID for tracing
            actions: Optional list of actions NAVI took

        Returns:
            Updated session memory
        """
        session = self.get_or_create_session(session_id)
        timestamp = datetime.utcnow().isoformat()

        # Run all extractors on the assistant response
        for extractor in self._extractors:
            try:
                facts = extractor(assistant_response, timestamp, message_id)
                for fact in facts:
                    session.add_fact(fact)
            except Exception as e:
                logger.warning(f"Extractor failed: {extractor.__name__}", error=str(e))

        # Also extract from actions if provided
        if actions:
            for action in actions:
                action_facts = self._extract_from_action(action, timestamp, message_id)
                for fact in action_facts:
                    session.add_fact(fact)
            session.recent_actions.extend(actions[-10:])  # Keep last 10 actions

        logger.info(
            "Processed exchange",
            session_id=session_id,
            facts_count=len(session.facts),
            new_facts=[f.key for f in session.facts.values()][-5:],
        )

        return session

    def get_context_for_session(self, session_id: str) -> str:
        """Get context summary for injection into prompts."""
        if session_id not in self._sessions:
            return ""
        return self._sessions[session_id].get_context_summary()

    def clear_session(self, session_id: str) -> None:
        """Clear session memory."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("Cleared session memory", session_id=session_id)

    # === Fact Extractors ===

    def _extract_port_info(
        self, text: str, timestamp: str, message_id: Optional[str]
    ) -> List[SessionFact]:
        """Extract port numbers mentioned in the response."""
        facts = []
        # Match patterns like "port 3000", "localhost:3001", ":8080"
        port_patterns = [
            r"port\s*[:\s]?\s*(\d{2,5})",
            r"localhost:(\d{2,5})",
            r"127\.0\.0\.1:(\d{2,5})",
            r"0\.0\.0\.0:(\d{2,5})",
            r"running\s+(?:on|at)\s+.*?:(\d{2,5})",
        ]

        ports_found: Set[str] = set()
        for pattern in port_patterns:
            matches = re.findall(pattern, text.lower())
            ports_found.update(matches)

        for port in ports_found:
            facts.append(
                SessionFact(
                    category="server",
                    key=f"port_{port}",
                    value=port,
                    timestamp=timestamp,
                    source_message_id=message_id,
                )
            )

        # Also store the "main" port if there's a clear indication
        if ports_found:
            # Look for context clues about which is the primary port
            primary_port = None
            if "development server" in text.lower() or "dev server" in text.lower():
                primary_port = list(ports_found)[0]
            elif "running" in text.lower() and "successfully" in text.lower():
                primary_port = list(ports_found)[0]

            if primary_port:
                facts.append(
                    SessionFact(
                        category="server",
                        key="primary_port",
                        value=primary_port,
                        timestamp=timestamp,
                        source_message_id=message_id,
                    )
                )

        return facts

    def _extract_server_status(
        self, text: str, timestamp: str, message_id: Optional[str]
    ) -> List[SessionFact]:
        """Extract server running status."""
        facts = []
        lower_text = text.lower()

        # Check for running indicators
        running_patterns = [
            r"server\s+is\s+(now\s+)?running",
            r"successfully\s+started",
            r"application\s+is\s+running",
            r"project\s+is\s+(now\s+)?(up\s+and\s+)?running",
            r"started\s+(?:on|at)\s+",
        ]

        stopped_patterns = [
            r"server\s+stopped",
            r"server\s+is\s+not\s+running",
            r"failed\s+to\s+start",
        ]

        for pattern in running_patterns:
            if re.search(pattern, lower_text):
                facts.append(
                    SessionFact(
                        category="server",
                        key="status",
                        value="running",
                        timestamp=timestamp,
                        source_message_id=message_id,
                    )
                )
                break

        for pattern in stopped_patterns:
            if re.search(pattern, lower_text):
                facts.append(
                    SessionFact(
                        category="server",
                        key="status",
                        value="stopped",
                        timestamp=timestamp,
                        source_message_id=message_id,
                    )
                )
                break

        return facts

    def _extract_file_paths(
        self, text: str, timestamp: str, message_id: Optional[str]
    ) -> List[SessionFact]:
        """Extract file paths mentioned."""
        facts = []

        # Match file paths
        path_pattern = (
            r'(?:^|[\s`"\'])(/[^\s`"\']+\.[a-z]{1,5}|[a-z]+/[^\s`"\']+\.[a-z]{1,5})'
        )
        matches = re.findall(path_pattern, text, re.MULTILINE | re.IGNORECASE)

        seen = set()
        for match in matches[:10]:  # Limit to 10 files
            if match not in seen:
                seen.add(match)
                facts.append(
                    SessionFact(
                        category="file",
                        key=f"mentioned_{len(facts)}",
                        value=match,
                        timestamp=timestamp,
                        source_message_id=message_id,
                    )
                )

        return facts

    def _extract_urls(
        self, text: str, timestamp: str, message_id: Optional[str]
    ) -> List[SessionFact]:
        """Extract URLs mentioned."""
        facts = []
        url_pattern = r'https?://[^\s<>"\')\]]+[^\s<>"\')\].,;:!?]'
        matches = re.findall(url_pattern, text)

        for i, url in enumerate(matches[:5]):  # Limit to 5 URLs
            facts.append(
                SessionFact(
                    category="discovery",
                    key=f"url_{i}",
                    value=url,
                    timestamp=timestamp,
                    source_message_id=message_id,
                )
            )

        return facts

    def _extract_commands_run(
        self, text: str, timestamp: str, message_id: Optional[str]
    ) -> List[SessionFact]:
        """Extract commands that were run."""
        facts = []

        # Look for command blocks or ran/executed patterns
        ran_patterns = [
            r"(?:ran|executed|running)[\s:]+`([^`]+)`",
            r"command[\s:]+`([^`]+)`",
        ]

        for pattern in ran_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for i, cmd in enumerate(matches[:5]):
                facts.append(
                    SessionFact(
                        category="task",
                        key=f"command_{i}",
                        value=cmd,
                        timestamp=timestamp,
                        source_message_id=message_id,
                    )
                )

        return facts

    def _extract_errors(
        self, text: str, timestamp: str, message_id: Optional[str]
    ) -> List[SessionFact]:
        """Extract error information."""
        facts = []
        lower_text = text.lower()

        # Look for error patterns
        error_patterns = [
            r"error[:\s]+([^\n.]+)",
            r"failed[:\s]+([^\n.]+)",
            r"exception[:\s]+([^\n.]+)",
        ]

        for pattern in error_patterns:
            matches = re.findall(pattern, lower_text)
            for i, error in enumerate(matches[:3]):
                facts.append(
                    SessionFact(
                        category="error",
                        key=f"error_{i}",
                        value=error.strip()[:200],  # Limit length
                        timestamp=timestamp,
                        source_message_id=message_id,
                    )
                )

        return facts

    def _extract_decisions(
        self, text: str, timestamp: str, message_id: Optional[str]
    ) -> List[SessionFact]:
        """Extract decisions or conclusions made."""
        facts = []

        # Look for decision indicators
        decision_patterns = [
            r"(?:decided|choosing|using|selected|went with)[:\s]+([^\n.]+)",
            r"(?:the solution is|fix is|answer is)[:\s]+([^\n.]+)",
        ]

        for pattern in decision_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for i, decision in enumerate(matches[:3]):
                facts.append(
                    SessionFact(
                        category="decision",
                        key=f"decision_{i}",
                        value=decision.strip()[:200],
                        timestamp=timestamp,
                        source_message_id=message_id,
                    )
                )

        return facts

    def _extract_from_action(
        self, action: Dict[str, Any], timestamp: str, message_id: Optional[str]
    ) -> List[SessionFact]:
        """Extract facts from an action object."""
        facts = []

        action_type = action.get("type", "")

        if action_type == "command":
            cmd = action.get("command", "")
            action.get("output", "")
            exit_code = action.get("exit_code", action.get("exitCode"))

            facts.append(
                SessionFact(
                    category="task",
                    key="last_command",
                    value=cmd,
                    timestamp=timestamp,
                    source_message_id=message_id,
                )
            )

            if exit_code == 0:
                facts.append(
                    SessionFact(
                        category="task",
                        key="last_command_status",
                        value="success",
                        timestamp=timestamp,
                        source_message_id=message_id,
                    )
                )
            elif exit_code is not None:
                facts.append(
                    SessionFact(
                        category="error",
                        key="last_command_status",
                        value=f"failed with exit code {exit_code}",
                        timestamp=timestamp,
                        source_message_id=message_id,
                    )
                )

        elif action_type in ["create", "edit"]:
            file_path = action.get("file") or action.get("path", "")
            facts.append(
                SessionFact(
                    category="file",
                    key=f"modified_{action_type}",
                    value=file_path,
                    timestamp=timestamp,
                    source_message_id=message_id,
                )
            )

        return facts


# Global instance
session_memory_service = SessionMemoryService()
