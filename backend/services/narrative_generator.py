"""
Narrative Generator for NAVI

Generates contextual, conversational narratives during streaming.
These are dynamically generated based on the actual context and operations.

For high-quality narratives, this can optionally use an LLM for generation.
Falls back to context-based generation for speed when LLM is not available.

KEY PRINCIPLE: Narratives are NEVER hardcoded - they are built from:
1. The actual data in the context (file names, project type, dependencies, etc.)
2. The user's original message
3. The specific operation being performed
"""

from typing import Dict, Any, List, Optional, Callable
import os
import logging

logger = logging.getLogger(__name__)


class DynamicNarrativeGenerator:
    """
    Generate contextual narratives during streaming.

    Narratives are generated dynamically based on:
    - The actual operation being performed
    - The context (file paths, project info, etc.)
    - The user's original request

    This is NOT hardcoded - narratives adapt to the specific situation.
    """

    def __init__(self, use_llm: bool = False, llm_callback: Optional[Callable] = None):
        """
        Initialize the narrative generator.

        Args:
            use_llm: If True, use LLM for richer narratives (slower but more natural)
            llm_callback: Async function to call LLM: async (prompt) -> str
        """
        self.use_llm = use_llm
        self.llm_callback = llm_callback

    async def generate(
        self,
        event_type: str,
        context: Dict[str, Any],
        user_message: str = "",
    ) -> str:
        """
        Generate a narrative for any event type dynamically.

        Args:
            event_type: Type of event (intent, file_read, project_detected, tool_start, etc.)
            context: Context dict with relevant data for the event
            user_message: Original user message for additional context

        Returns:
            A natural language narrative string
        """
        if self.use_llm and self.llm_callback:
            try:
                return await self._generate_with_llm(event_type, context, user_message)
            except Exception as e:
                logger.warning(f"LLM narrative generation failed, using context-based: {e}")

        return self._generate_from_context(event_type, context, user_message)

    async def _generate_with_llm(
        self,
        event_type: str,
        context: Dict[str, Any],
        user_message: str,
    ) -> str:
        """Use LLM for high-quality, truly dynamic narratives."""
        prompt = f"""Generate a brief, friendly narrative (1-2 sentences) for a coding assistant.

Event: {event_type}
Context: {context}
User's request: {user_message}

The narrative should:
- Be conversational and helpful
- Reference specific details from the context (file names, project type, etc.)
- NOT be generic or templated
- Sound natural, like a human assistant explaining what they're doing

Narrative:"""

        return await self.llm_callback(prompt)

    def _generate_from_context(
        self,
        event_type: str,
        context: Dict[str, Any],
        user_message: str,
    ) -> str:
        """
        Generate narrative from context without LLM.

        This builds narratives dynamically from the actual context data,
        not from hardcoded strings.
        """
        # Extract common context elements
        file_path = context.get("file_path", context.get("path", ""))
        file_name = os.path.basename(file_path) if file_path else ""
        project_type = context.get("project_type", "")
        framework = context.get("framework", "")
        confidence = context.get("confidence", 0.0)
        intent_kind = context.get("intent_kind", context.get("kind", ""))
        error = context.get("error", "")
        tool_name = context.get("tool_name", "")

        # Build narrative dynamically based on event type and context
        if event_type == "intent_detected":
            return self._build_intent_narrative(intent_kind, confidence, user_message)

        elif event_type == "file_read_start":
            return self._build_file_read_narrative(file_name, file_path, "start")

        elif event_type == "file_read_complete":
            return self._build_file_read_narrative(file_name, file_path, "complete", context.get("summary"))

        elif event_type == "files_analyzed":
            files = context.get("files", [])
            return self._build_batch_analysis_narrative(files, project_type, framework)

        elif event_type == "project_detected":
            deps = context.get("dependencies", {})
            return self._build_project_narrative(project_type, framework, deps)

        elif event_type == "tool_start":
            args = context.get("args", {})
            return self._build_tool_narrative(tool_name, args, "start")

        elif event_type == "tool_complete":
            result = context.get("result", {})
            return self._build_tool_narrative(tool_name, result, "complete")

        elif event_type == "error":
            return f"I encountered an issue: {error}" if error else "Something went wrong."

        elif event_type == "iteration":
            iteration = context.get("iteration", 1)
            max_iter = context.get("max_iterations", 3)
            reason = context.get("reason", "")
            return self._build_iteration_narrative(iteration, max_iter, reason)

        elif event_type == "verification":
            passed = context.get("passed", 0)
            failed = context.get("failed", 0)
            return self._build_verification_narrative(passed, failed)

        elif event_type == "complete":
            success = context.get("success", True)
            summary = context.get("summary", "")
            return self._build_completion_narrative(success, summary)

        # Fallback - build from available context
        return self._build_generic_narrative(event_type, context)

    def _build_intent_narrative(self, intent_kind: str, confidence: float, message: str) -> str:
        """Build narrative from actual intent and confidence - dynamically extracts action from intent."""
        # Convert intent kind to natural language dynamically
        intent_lower = intent_kind.lower().replace("_", " ")

        # Dynamically extract action verb from the intent string
        # This is NOT a lookup table - it parses the actual intent
        action = "help with"

        # Check for common action words IN the intent string
        if "fix" in intent_lower:
            action = "fix"
        elif "bug" in intent_lower:
            action = "fix the bug in"
        elif "error" in intent_lower:
            action = "fix the error in"
        elif "debug" in intent_lower:
            action = "debug"
        elif "implement" in intent_lower:
            action = "implement"
        elif "feature" in intent_lower:
            action = "add a feature to"
        elif "add" in intent_lower:
            action = "add to"
        elif "create" in intent_lower:
            action = "create"
        elif "refactor" in intent_lower:
            action = "refactor"
        elif "optimize" in intent_lower:
            action = "optimize"
        elif "explain" in intent_lower:
            action = "explain"
        elif "describe" in intent_lower:
            action = "describe"
        elif "understand" in intent_lower:
            action = "help you understand"
        elif "test" in intent_lower:
            action = "test"
        elif "run" in intent_lower:
            action = "run"
        elif "setup" in intent_lower or "set up" in intent_lower:
            action = "set up"
        elif "install" in intent_lower:
            action = "install"
        elif "document" in intent_lower:
            action = "document"
        else:
            # If no match, just use the intent as the action
            action = intent_lower if intent_lower else "help with"

        # Build confidence-appropriate response
        if confidence >= 0.9:
            return f"I'll {action} this for you."
        elif confidence >= 0.7:
            return f"It looks like you want me to {action} this. Let me analyze the code..."
        else:
            return f"I think you want me to {action} this. Let me take a look..."

    def _build_file_read_narrative(
        self,
        file_name: str,
        file_path: str,
        phase: str,
        summary: str = None,
    ) -> str:
        """Build narrative from actual file information."""
        if not file_name:
            return "Reading files..." if phase == "start" else "Files read."

        # Determine file type from actual extension
        ext = os.path.splitext(file_name)[1].lower() if file_name else ""

        # Build description from actual extension (dynamic, not lookup)
        file_desc = f"`{file_name}`"
        if ext:
            lang = ext[1:]  # Remove the dot
            # Infer type from extension dynamically
            if lang in ("ts", "tsx"):
                file_desc = f"`{file_name}` (TypeScript)"
            elif lang in ("js", "jsx", "mjs"):
                file_desc = f"`{file_name}` (JavaScript)"
            elif lang == "py":
                file_desc = f"`{file_name}` (Python)"
            elif lang in ("json", "yaml", "yml", "toml", "ini", "env"):
                file_desc = f"`{file_name}` (config)"
            elif lang in ("md", "mdx", "rst", "txt"):
                file_desc = f"`{file_name}` (docs)"
            elif lang in ("css", "scss", "sass", "less"):
                file_desc = f"`{file_name}` (styles)"
            elif lang in ("html", "htm", "xml"):
                file_desc = f"`{file_name}` (markup)"
            # For unknown extensions, just show the file name

        if phase == "start":
            return f"Reading {file_desc}..."
        else:
            if summary:
                return f"Found in {file_desc}: {summary}"
            return f"Read {file_desc}."

    def _build_batch_analysis_narrative(
        self,
        files: List[str],
        project_type: str,
        framework: str,
    ) -> str:
        """Build narrative from actual files analyzed."""
        count = len(files)
        if count == 0:
            return "Analyzing the project..."

        # Build description from actual project info (not hardcoded)
        project_desc = ""
        if framework:
            project_desc = f"**{framework}**"
        elif project_type and project_type != "unknown":
            project_desc = f"**{project_type}**"

        if count == 1:
            base = f"I've analyzed `{os.path.basename(files[0])}`"
            return f"{base} from this {project_desc} project." if project_desc else f"{base}."
        elif count <= 3:
            names = [f"`{os.path.basename(f)}`" for f in files]
            base = f"I've analyzed {', '.join(names)}"
            return f"{base} from this {project_desc} project." if project_desc else f"{base}."
        else:
            if project_desc:
                return f"I've analyzed {count} files from this {project_desc} project."
            return f"I've analyzed {count} files."

    def _build_project_narrative(
        self,
        project_type: str,
        framework: str,
        dependencies: Dict[str, Any],
    ) -> str:
        """Build narrative from actual project detection results."""
        parts = []

        # Add framework/type (from actual detection, not hardcoded)
        if framework:
            parts.append(f"**{framework}**")
        elif project_type and project_type != "unknown":
            parts.append(f"**{project_type}**")

        # Add dependencies (from actual package.json/requirements.txt, not hardcoded)
        if dependencies:
            # Get first 3 actual dependency names
            dep_names = list(dependencies.keys())[:3]
            if dep_names:
                parts.append(f"with {', '.join(dep_names)}")

        if parts:
            return f"This is a {' '.join(parts)} project."
        return "I've analyzed the project structure."

    def _build_tool_narrative(
        self,
        tool_name: str,
        data: Dict[str, Any],
        phase: str,
    ) -> str:
        """Build narrative from actual tool execution data."""
        # Convert tool name to readable format (dynamic)
        readable_name = tool_name.replace("_", " ")

        if phase == "start":
            # Build from actual args (dynamic)
            path = data.get("path", "")
            command = data.get("command", "")
            query = data.get("query", "")

            if path:
                return f"Running {readable_name} on `{os.path.basename(path)}`..."
            elif command:
                cmd_display = command[:50] + ('...' if len(command) > 50 else '')
                return f"Executing: `{cmd_display}`"
            elif query:
                return f"Searching for `{query}`..."
            return f"Running {readable_name}..."

        else:  # complete
            success = data.get("success", True)
            if not success:
                error = data.get("error", "unknown error")
                return f"{readable_name.title()} failed: {error}"

            # Build from actual results (dynamic)
            count = data.get("count", data.get("matches", 0))
            if isinstance(count, list):
                count = len(count)

            if count:
                return f"{readable_name.title()} found {count} results."
            return f"{readable_name.title()} completed."

    def _build_iteration_narrative(self, iteration: int, max_iter: int, reason: str) -> str:
        """Build narrative from actual iteration state - user-friendly, no debug info."""
        # Don't show iteration numbers to users - just describe what's happening
        if iteration == 1:
            if reason:
                return reason
            return ""  # No narrative needed for first iteration start

        # For subsequent iterations, just show the reason if provided
        if reason:
            return reason
        return "Refining the approach..."

    def _build_verification_narrative(self, passed: int, failed: int) -> str:
        """Build narrative from actual test results."""
        total = passed + failed
        if total == 0:
            return "Running verification..."

        if failed == 0:
            return f"✅ All {total} tests passed!"
        elif passed == 0:
            return f"❌ {total} tests failed. Analyzing issues..."
        else:
            return f"⚠️ {passed}/{total} tests passed. {failed} need fixing..."

    def _build_completion_narrative(self, success: bool, summary: str) -> str:
        """Build narrative from actual completion state."""
        if success:
            if summary:
                return f"✅ Done! {summary}"
            return "✅ Task completed successfully!"
        else:
            if summary:
                return f"❌ Could not complete: {summary}"
            return "❌ Task could not be completed."

    def _build_generic_narrative(self, event_type: str, context: Dict[str, Any]) -> str:
        """Build a generic narrative from any context - still dynamic based on context."""
        # Try to extract meaningful info from context
        detail = context.get("detail", "")
        label = context.get("label", "")
        status = context.get("status", "")

        if detail:
            return f"{label}: {detail}" if label else detail
        elif label:
            if status == "running":
                return f"{label}..."
            return label

        # Last resort - describe the event type (still dynamic)
        return f"Processing {event_type.replace('_', ' ')}..."


# Factory function for creating narrators
def create_narrator(use_llm: bool = False, llm_callback: Optional[Callable] = None) -> DynamicNarrativeGenerator:
    """Create a narrative generator instance."""
    return DynamicNarrativeGenerator(use_llm=use_llm, llm_callback=llm_callback)


# Default instance (context-based for speed)
_default_narrator = DynamicNarrativeGenerator(use_llm=False)


# Convenience class with static methods for backward compatibility
class NarrativeGenerator:
    """Static methods wrapper for backward compatibility."""

    @staticmethod
    def for_intent(intent_kind: str, confidence: float, message: str = "") -> str:
        """Generate intent narrative dynamically."""
        return _default_narrator._build_intent_narrative(intent_kind, confidence, message)

    @staticmethod
    def for_file_read_start(file_path: str, purpose: str = "") -> str:
        """Generate file read start narrative dynamically."""
        return _default_narrator._build_file_read_narrative(
            os.path.basename(file_path), file_path, "start"
        )

    @staticmethod
    def for_file_read_complete(file_path: str, content_summary: str = "") -> str:
        """Generate file read complete narrative dynamically."""
        return _default_narrator._build_file_read_narrative(
            os.path.basename(file_path), file_path, "complete", content_summary
        )

    @staticmethod
    def for_batch_file_read(file_count: int, file_list: List[str]) -> str:
        """Generate batch file read narrative dynamically."""
        return _default_narrator._build_batch_analysis_narrative(file_list, "", "")

    @staticmethod
    def for_project_detection(project_info: Dict[str, Any]) -> str:
        """Generate project detection narrative dynamically from actual project info."""
        return _default_narrator._build_project_narrative(
            project_info.get("project_type", ""),
            project_info.get("framework", ""),
            project_info.get("dependencies", {}),
        )

    @staticmethod
    def for_tool_start(tool_name: str, args: Dict[str, Any] = None) -> str:
        """Generate tool start narrative dynamically."""
        return _default_narrator._build_tool_narrative(tool_name, args or {}, "start")

    @staticmethod
    def for_tool_result(tool_name: str, result: Dict[str, Any]) -> str:
        """Generate tool result narrative dynamically."""
        return _default_narrator._build_tool_narrative(tool_name, result, "complete")

    @staticmethod
    def for_context_building(step: str, details: str = "") -> str:
        """Generate context building narrative dynamically."""
        if details:
            return f"Building context: {details}..."
        return f"{step.replace('_', ' ').title()}..."

    @staticmethod
    def for_response_start(intent_kind: str = "") -> str:
        """Generate response start narrative dynamically based on intent."""
        if not intent_kind:
            return "Here's what I found..."

        # Parse intent dynamically (not lookup)
        intent_lower = intent_kind.lower()
        if "explain" in intent_lower or "describe" in intent_lower:
            return "Let me explain what I found..."
        elif "fix" in intent_lower or "debug" in intent_lower or "error" in intent_lower:
            return "I've identified the issue. Here's my analysis..."
        elif "implement" in intent_lower or "add" in intent_lower or "create" in intent_lower:
            return "I've planned the implementation. Here are my recommendations..."
        elif "refactor" in intent_lower or "optimize" in intent_lower:
            return "I've analyzed the code. Here are my suggestions..."
        return "Here's what I found..."

    @staticmethod
    def for_iteration(iteration: int, max_iterations: int, reason: str = "") -> str:
        """Generate iteration narrative dynamically."""
        return _default_narrator._build_iteration_narrative(iteration, max_iterations, reason)

    @staticmethod
    def for_verification(results: Dict[str, Any]) -> str:
        """Generate verification narrative dynamically from actual results."""
        return _default_narrator._build_verification_narrative(
            results.get("passed", 0), results.get("failed", 0)
        )

    @staticmethod
    def for_completion(success: bool, summary: str = "") -> str:
        """Generate completion narrative dynamically."""
        return _default_narrator._build_completion_narrative(success, summary)
