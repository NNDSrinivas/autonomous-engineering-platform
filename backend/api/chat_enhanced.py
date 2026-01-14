# Enhanced Chat Handler - backend/api/chat_enhanced.py
"""
This replaces the overly cautious chat behavior with aggressive action-taking.
NAVI should DO things, not ask permission for everything.

Copy this to: backend/api/chat_enhanced.py
Then update your chat.py to use these handlers.
"""

from typing import Dict, Any, Optional
import re
from pathlib import Path
import os


class IntentDetector:
    """
    Detects user intent from natural language with high tolerance for:
    - Typos
    - Incomplete sentences
    - Casual language
    - Vague requests
    """

    def __init__(self):
        # Action patterns - aggressive matching
        self.patterns = {
            "open_project": [
                r"open\s+(?:the\s+)?(.+?)\s+project",
                r"open\s+(.+)",
                r"go\s+to\s+(.+)",
                r"load\s+(.+)",
                r"switch\s+to\s+(.+)",
                r"show\s+(?:me\s+)?(.+)",
            ],
            "create_file": [
                r"create\s+(?:a\s+)?(?:new\s+)?file\s+(?:called\s+)?(.+)",
                r"make\s+(?:a\s+)?(?:new\s+)?file\s+(.+)",
                r"add\s+(?:a\s+)?(?:new\s+)?file\s+(.+)",
                r"new\s+file\s+(.+)",
            ],
            "create_component": [
                r"create\s+(?:a\s+)?(?:new\s+)?component\s+(?:called\s+)?(.+)",
                r"make\s+(?:a\s+)?component\s+(.+)",
                r"add\s+(?:a\s+)?component\s+(.+)",
                r"new\s+component\s+(.+)",
            ],
            "create_page": [
                r"create\s+(?:a\s+)?(?:new\s+)?page\s+(?:called\s+)?(.+)",
                r"make\s+(?:a\s+)?page\s+(.+)",
                r"add\s+(?:a\s+)?page\s+(.+)",
                r"new\s+page\s+(.+)",
            ],
            "explain_code": [
                r"explain\s+(.+)",
                r"what\s+(?:does|is)\s+(.+)",
                r"how\s+(?:does|works)\s+(.+)",
                r"tell\s+me\s+about\s+(.+)",
            ],
            "fix_error": [
                r"fix\s+(?:the\s+)?(?:error|bug|issue)\s+in\s+(.+)",
                r"debug\s+(.+)",
                r"solve\s+(.+)",
                r"repair\s+(.+)",
            ],
            "refactor": [
                r"refactor\s+(.+)",
                r"improve\s+(.+)",
                r"clean\s+up\s+(.+)",
                r"optimize\s+(.+)",
            ],
            "add_feature": [
                r"add\s+(?:a\s+)?(.+)",
                r"implement\s+(.+)",
                r"build\s+(.+)",
                r"create\s+(.+)",
            ],
            "generate_tests": [
                r"(?:write|create|generate|add)\s+tests?\s+for\s+(.+)",
                r"test\s+(.+)",
            ],
            "search_code": [
                r"find\s+(.+)",
                r"search\s+(?:for\s+)?(.+)",
                r"locate\s+(.+)",
                r"where\s+is\s+(.+)",
            ],
        }

    def detect_intent(self, message: str) -> Dict[str, Any]:
        """
        Detect user intent from message.
        Returns: {
            'action': str,
            'params': dict,
            'confidence': float
        }
        """
        message_lower = message.lower().strip()

        # Try to match against all patterns
        for action, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, message_lower, re.IGNORECASE)
                if match:
                    return {
                        "action": action,
                        "params": {
                            "target": (
                                match.group(1).strip() if match.groups() else message
                            ),
                            "original_message": message,
                        },
                        "confidence": 0.9,
                    }

        # Fallback: general coding request
        return {
            "action": "general_coding",
            "params": {"request": message},
            "confidence": 0.6,
        }


class ActionExecutor:
    """
    Executes actions based on detected intent.
    DOES things rather than asking permission.
    """

    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = workspace_path or os.getcwd()

    async def execute(
        self, intent: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the detected action.
        Returns: {
            'success': bool,
            'action_taken': str,
            'result': Any,
            'message': str
        }
        """
        action = intent["action"]
        params = intent["params"]

        # Map actions to handlers
        handlers = {
            "open_project": self.open_project,
            "create_file": self.create_file,
            "create_component": self.create_component,
            "create_page": self.create_page,
            "explain_code": self.explain_code,
            "fix_error": self.fix_error,
            "refactor": self.refactor_code,
            "add_feature": self.add_feature,
            "generate_tests": self.generate_tests,
            "search_code": self.search_code,
            "general_coding": self.handle_general_request,
        }

        handler = handlers.get(action, self.handle_general_request)
        return await handler(params, context)

    async def open_project(self, params: Dict, context: Dict) -> Dict:
        """
        Open a project by searching for it in workspace.
        """
        target = params["target"]

        # Search for project folder
        workspace = Path(self.workspace_path)
        found_projects = []

        # Fuzzy search with typo tolerance
        target_clean = target.lower().replace("-", "").replace("_", "").replace(" ", "")

        for item in workspace.rglob("*"):
            if item.is_dir():
                item_clean = (
                    item.name.lower().replace("-", "").replace("_", "").replace(" ", "")
                )

                # Fuzzy match
                if target_clean in item_clean or item_clean in target_clean:
                    # Check if it looks like a project (has package.json, src/, etc.)
                    is_project = (
                        (item / "package.json").exists()
                        or (item / "src").exists()
                        or (item / "README.md").exists()
                        or (item / ".git").exists()
                    )

                    if is_project:
                        found_projects.append(
                            {
                                "path": str(item),
                                "name": item.name,
                                "score": self._calculate_match_score(target, item.name),
                            }
                        )

        if not found_projects:
            return {
                "success": False,
                "action_taken": "search_project",
                "result": None,
                "message": f"I couldn't find a project matching '{target}'. Let me search more thoroughly...",
                "suggestion": "create_project",
            }

        # Sort by match score
        found_projects.sort(key=lambda x: x["score"], reverse=True)
        best_match = found_projects[0]

        return {
            "success": True,
            "action_taken": "open_project",
            "result": {
                "project_path": best_match["path"],
                "project_name": best_match["name"],
                "alternatives": found_projects[1:3] if len(found_projects) > 1 else [],
            },
            "message": f"Opening **{best_match['name']}** at `{best_match['path']}`",
            "vscode_command": {
                "command": "vscode.openFolder",
                "args": [best_match["path"]],
            },
        }

    async def create_file(self, params: Dict, context: Dict) -> Dict:
        """Create a new file with appropriate template."""
        filename = params["target"]

        # Determine file type and generate content
        file_path, content = self._generate_file_template(filename, context)

        return {
            "success": True,
            "action_taken": "create_file",
            "result": {"path": file_path, "content": content},
            "message": f"Created **{filename}**",
            "vscode_command": {
                "command": "navi.createAndOpenFile",
                "args": [file_path, content],
            },
        }

    async def create_component(self, params: Dict, context: Dict) -> Dict:
        """Create a React/Vue component."""
        component_name = params["target"]

        # Detect framework from context
        framework = context.get("technologies", {}).get("frontend", "react")

        if framework == "react":
            content = self._generate_react_component(component_name)
        elif framework == "vue":
            content = self._generate_vue_component(component_name)
        else:
            content = self._generate_generic_component(component_name)

        file_path = f"src/components/{component_name}.tsx"

        return {
            "success": True,
            "action_taken": "create_component",
            "result": {"path": file_path, "content": content, "framework": framework},
            "message": f"Created **{component_name}** component",
            "vscode_command": {
                "command": "navi.createAndOpenFile",
                "args": [file_path, content],
            },
        }

    async def create_page(self, params: Dict, context: Dict) -> Dict:
        """Create a new page."""
        page_name = params["target"]

        # Generate page component and route
        page_content = self._generate_page_template(page_name, context)

        return {
            "success": True,
            "action_taken": "create_page",
            "result": {
                "page_path": f"src/pages/{page_name}.tsx",
                "content": page_content,
            },
            "message": f"Created **{page_name}** page with routing",
            "vscode_command": {
                "command": "navi.createAndOpenFile",
                "args": [f"src/pages/{page_name}.tsx", page_content],
            },
        }

    async def explain_code(self, params: Dict, context: Dict) -> Dict:
        """Explain code or concept."""
        target = params["target"]

        # TODO: Use LLM to generate explanation
        explanation = f"Analyzing {target}..."

        return {
            "success": True,
            "action_taken": "explain_code",
            "result": {"explanation": explanation},
            "message": explanation,
        }

    async def fix_error(self, params: Dict, context: Dict) -> Dict:
        """Fix an error in the code."""
        target = params["target"]

        # TODO: Get diagnostics and generate fixes

        return {
            "success": True,
            "action_taken": "fix_error",
            "result": {},
            "message": f"Analyzing and fixing errors in {target}...",
        }

    async def refactor_code(self, params: Dict, context: Dict) -> Dict:
        """Refactor code."""
        target = params["target"]

        return {
            "success": True,
            "action_taken": "refactor",
            "result": {},
            "message": f"Refactoring {target}...",
        }

    async def add_feature(self, params: Dict, context: Dict) -> Dict:
        """Add a new feature."""
        feature = params["target"]

        return {
            "success": True,
            "action_taken": "add_feature",
            "result": {},
            "message": f"Implementing {feature}...",
        }

    async def generate_tests(self, params: Dict, context: Dict) -> Dict:
        """Generate tests."""
        target = params["target"]

        return {
            "success": True,
            "action_taken": "generate_tests",
            "result": {},
            "message": f"Generating tests for {target}...",
        }

    async def search_code(self, params: Dict, context: Dict) -> Dict:
        """Search for code."""
        query = params["target"]

        return {
            "success": True,
            "action_taken": "search_code",
            "result": {},
            "message": f"Searching for {query}...",
        }

    async def handle_general_request(self, params: Dict, context: Dict) -> Dict:
        """Handle general coding request."""
        request = params.get("request", "")

        return {
            "success": True,
            "action_taken": "general_coding",
            "result": {},
            "message": f"Working on: {request}",
        }

    # Helper methods

    def _calculate_match_score(self, query: str, target: str) -> float:
        """Calculate fuzzy match score (0-1)."""
        query_clean = query.lower().replace("-", "").replace("_", "").replace(" ", "")
        target_clean = target.lower().replace("-", "").replace("_", "").replace(" ", "")

        # Exact match
        if query_clean == target_clean:
            return 1.0

        # Contains match
        if query_clean in target_clean:
            return 0.8

        # Substring match
        if target_clean in query_clean:
            return 0.7

        # Character overlap
        common_chars = set(query_clean) & set(target_clean)
        score = len(common_chars) / max(len(query_clean), len(target_clean))

        return score

    def _generate_file_template(self, filename: str, context: Dict) -> tuple:
        """Generate file template based on filename."""
        # Determine file type
        if filename.endswith(".tsx") or filename.endswith(".jsx"):
            return filename, self._generate_react_file_template(filename)
        elif filename.endswith(".py"):
            return filename, self._generate_python_file_template(filename)
        elif filename.endswith(".ts") or filename.endswith(".js"):
            return filename, self._generate_typescript_file_template(filename)
        else:
            return filename, f"// {filename}\n\n"

    def _generate_react_component(self, name: str) -> str:
        """Generate React component template."""
        component_name = name.replace("-", "").replace("_", "").title()

        return f"""import React from 'react';

interface {component_name}Props {{
  // Add props here
}}

export const {component_name}: React.FC<{component_name}Props> = (props) => {{
  return (
    <div className="{name.lower()}">
      <h2>{component_name}</h2>
      {{/* Component content */}}
    </div>
  );
}};

export default {component_name};
"""

    def _generate_vue_component(self, name: str) -> str:
        """Generate Vue component template."""
        return f"""<template>
  <div class="{name.lower()}">
    <h2>{name}</h2>
    <!-- Component content -->
  </div>
</template>

<script setup lang="ts">
// Component logic
</script>

<style scoped>
.{name.lower()} {{
  /* Styles */
}}
</style>
"""

    def _generate_generic_component(self, name: str) -> str:
        """Generate generic component."""
        return f"// {name} component\n\nexport default {name};\n"

    def _generate_page_template(self, name: str, context: Dict) -> str:
        """Generate page template."""
        page_name = name.replace("-", "").replace("_", "").title()

        return f"""import React from 'react';

export default function {page_name}Page() {{
  return (
    <div className="page-{name.lower()}">
      <h1>{page_name}</h1>
      {{/* Page content */}}
    </div>
  );
}}
"""

    def _generate_react_file_template(self, filename: str) -> str:
        """Generate React file template."""
        return "import React from 'react';\n\n"

    def _generate_python_file_template(self, filename: str) -> str:
        """Generate Python file template."""
        return '"""' + filename + '"""\n\n'

    def _generate_typescript_file_template(self, filename: str) -> str:
        """Generate TypeScript file template."""
        return f"// {filename}\n\nexport {{}};\n"


# Main chat endpoint handler


async def handle_chat_message(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main chat handler that:
    1. Detects intent
    2. Executes action immediately
    3. Returns result

    NO permission asking, NO hesitation, JUST DO IT!
    """
    # Initialize
    detector = IntentDetector()
    executor = ActionExecutor(context.get("workspace_path"))

    # Detect intent
    intent = detector.detect_intent(message)

    # Execute action
    result = await executor.execute(intent, context)

    return {
        "intent": intent,
        "execution": result,
        "should_execute_vscode_command": "vscode_command" in result,
    }
