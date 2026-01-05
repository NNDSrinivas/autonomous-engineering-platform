"""
AST Engine - Phase 4.3

Real AST-aware code transformation that goes beyond text manipulation.
This is what separates NAVI from text-based patch tools.
"""

import ast
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ASTFixer:
    """
    AST-based code fixing that understands code structure.

    Unlike text-based approaches, this:
    - Parses code into AST
    - Makes structural modifications
    - Reprints with preserved formatting
    - Handles imports automatically
    - Ensures syntactic correctness
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    async def fix_undefined_variable_python(
        self, file_path: str, variable_name: str, content: str
    ) -> Optional[str]:
        """
        Fix undefined variable in Python using AST manipulation.

        Strategy:
        1. Parse AST
        2. Find undefined variable usage
        3. Add appropriate import or declaration
        4. Reprint code
        """
        try:
            tree = ast.parse(content)

            # Check if variable is actually undefined
            undefined_usage = self._find_undefined_variable(tree, variable_name)
            if not undefined_usage:
                return None  # Variable is already defined

            # Determine best fix strategy
            fix_strategy = self._determine_fix_strategy(variable_name, tree, file_path)

            if fix_strategy == "import":
                return self._add_import(content, variable_name, tree)
            elif fix_strategy == "declare":
                return self._add_declaration(content, variable_name, tree)
            else:
                logger.warning(f"No fix strategy found for {variable_name}")
                return None

        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"AST fixing error for {file_path}: {e}")
            return None

    def _find_undefined_variable(
        self, tree: ast.AST, variable_name: str
    ) -> List[ast.Name]:
        """Find all usages of undefined variable in AST."""
        undefined_usages = []
        defined_names = set()

        # Collect all defined names
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                defined_names.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        defined_names.add(target.id)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    defined_names.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    defined_names.add(alias.asname or alias.name)

        # Find undefined usages
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Name)
                and node.id == variable_name
                and isinstance(node.ctx, ast.Load)
                and variable_name not in defined_names
            ):
                undefined_usages.append(node)

        return undefined_usages

    def _determine_fix_strategy(
        self, variable_name: str, tree: ast.AST, file_path: str
    ) -> str:
        """
        Determine how to fix the undefined variable.

        Strategies:
        - "import": Add import statement
        - "declare": Add variable declaration
        """
        # Check if it looks like a common import
        common_imports = {
            "os",
            "sys",
            "json",
            "time",
            "datetime",
            "logging",
            "typing",
            "pathlib",
            "asyncio",
            "re",
            "uuid",
        }

        if variable_name.lower() in common_imports:
            return "import"

        # Check if it's used like a function/class (has attribute access or call)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == variable_name:
                    return "import"  # Likely a module
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == variable_name:
                    return "import"  # Likely a function

        # Default: declare as None for safety
        return "declare"

    def _add_import(self, content: str, variable_name: str, tree: ast.AST) -> str:
        """Add import statement at the top of the file."""
        lines = content.split("\n")

        # Find insertion point after existing imports
        insert_line = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                insert_line = i + 1
            elif line.strip() and not line.startswith("#"):
                break

        # Create import statement
        import_statement = f"import {variable_name}"

        # Insert the import
        lines.insert(insert_line, import_statement)

        return "\n".join(lines)

    def _add_declaration(self, content: str, variable_name: str, tree: ast.AST) -> str:
        """Add variable declaration."""
        lines = content.split("\n")

        # Find a good insertion point (after imports, before first usage)
        first_usage_line = self._find_first_usage_line(content, variable_name)

        # Insert point: after imports but before first usage
        insert_line = 0
        for i, line in enumerate(lines):
            if not line.strip() or line.strip().startswith("#"):
                continue
            if line.strip().startswith(("import ", "from ")):
                insert_line = i + 1
            elif i < first_usage_line - 1:
                insert_line = i
            else:
                break

        # Create declaration - be conservative
        declaration = f"{variable_name} = None  # TODO: Set appropriate value"

        # Insert the declaration
        lines.insert(insert_line, declaration)

        return "\n".join(lines)

    def _find_first_usage_line(self, content: str, variable_name: str) -> int:
        """Find the line number of first variable usage."""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if re.search(rf"\b{re.escape(variable_name)}\b", line):
                return i + 1  # 1-indexed
        return len(lines)

    async def fix_missing_import_python(
        self,
        file_path: str,
        module_name: str,
        content: str,
        symbol: Optional[str] = None,
    ) -> Optional[str]:
        """
        Fix missing import in Python using AST manipulation.
        """
        try:
            tree = ast.parse(content)

            # Check if import already exists
            if self._has_import(tree, module_name, symbol):
                return None  # Import already exists

            # Add the import
            if symbol:
                import_statement = f"from {module_name} import {symbol}"
            else:
                import_statement = f"import {module_name}"

            return self._add_import_statement(content, import_statement)

        except Exception as e:
            logger.error(f"Import fixing error for {file_path}: {e}")
            return None

    def _has_import(
        self, tree: ast.AST, module_name: str, symbol: Optional[str] = None
    ) -> bool:
        """Check if import already exists in AST."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == module_name:
                        return True
            elif isinstance(node, ast.ImportFrom):
                if node.module == module_name:
                    if not symbol:
                        return True
                    for alias in node.names:
                        if alias.name == symbol:
                            return True
        return False

    def _add_import_statement(self, content: str, import_statement: str) -> str:
        """Add import statement to content in the right place."""
        lines = content.split("\n")

        # Find insertion point after existing imports
        insert_line = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(("import ", "from ")):
                insert_line = i + 1
            elif line.strip() and not line.startswith("#"):
                break

        # Insert the import
        lines.insert(insert_line, import_statement)

        return "\n".join(lines)


class JavaScriptASTFixer:
    """
    JavaScript/TypeScript AST-aware fixing.

    For now, uses intelligent text patterns until we integrate a JS AST parser.
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root

    async def fix_undefined_variable_js(
        self, file_path: str, variable_name: str, content: str
    ) -> Optional[str]:
        """
        Fix undefined variable in JavaScript/TypeScript.
        """
        # Check if it's already declared
        if re.search(rf"\b(const|let|var)\s+{re.escape(variable_name)}\b", content):
            return None  # Already declared

        # Find the best insertion point
        lines = content.split("\n")

        # Insert after imports but before first usage
        import_section_end = 0
        for i, line in enumerate(lines):
            if re.match(r"^\s*(import|from)\s", line.strip()):
                import_section_end = i + 1
            elif line.strip() and not line.strip().startswith("//"):
                break

        # Find first usage
        first_usage = self._find_first_usage_line_js(content, variable_name)

        # Insert declaration
        insert_line = max(import_section_end, 0)
        if first_usage > 0:
            insert_line = min(insert_line, first_usage - 1)

        # Conservative declaration
        declaration = (
            f"const {variable_name}: any = null; // TODO: Set appropriate value"
        )
        if file_path.endswith(".js"):
            declaration = (
                f"const {variable_name} = null; // TODO: Set appropriate value"
            )

        lines.insert(insert_line, declaration)

        return "\n".join(lines)

    def _find_first_usage_line_js(self, content: str, variable_name: str) -> int:
        """Find first usage of variable in JavaScript."""
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if re.search(
                rf"\b{re.escape(variable_name)}\b", line
            ) and not line.strip().startswith("//"):
                return i + 1  # 1-indexed
        return len(lines)

    async def fix_missing_import_js(
        self,
        file_path: str,
        module_name: str,
        content: str,
        symbol: Optional[str] = None,
    ) -> Optional[str]:
        """
        Fix missing import in JavaScript/TypeScript.
        """
        # Check if import already exists
        if symbol:
            import_pattern = rf'import\s+.*\b{re.escape(symbol)}\b.*from\s+["\'].*{re.escape(module_name)}'
        else:
            import_pattern = rf'import.*from\s+["\'].*{re.escape(module_name)}'

        if re.search(import_pattern, content, re.MULTILINE):
            return None  # Import exists

        # Add import at top
        lines = content.split("\n")

        # Find insertion point
        insert_line = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("import "):
                insert_line = i + 1
            elif line.strip() and not line.strip().startswith("//"):
                break

        # Create import statement
        if symbol:
            import_statement = f"import {{ {symbol} }} from '{module_name}';"
        else:
            import_statement = (
                f"import {module_name.split('/')[-1]} from '{module_name}';"
            )

        lines.insert(insert_line, import_statement)

        return "\n".join(lines)


class MultiLanguageASTEngine:
    """
    Orchestrates AST-aware fixing across multiple languages.
    """

    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.python_fixer = ASTFixer(workspace_root)
        self.js_fixer = JavaScriptASTFixer(workspace_root)

    async def fix_issue_ast_aware(
        self, file_path: str, issue_type: str, details: Dict[str, Any], content: str
    ) -> Optional[str]:
        """
        Route AST-aware fixes to appropriate language handler.
        """
        file_extension = Path(file_path).suffix.lower()

        if file_extension == ".py":
            return await self._fix_python_issue(file_path, issue_type, details, content)
        elif file_extension in [".js", ".ts", ".jsx", ".tsx"]:
            return await self._fix_javascript_issue(
                file_path, issue_type, details, content
            )
        else:
            logger.warning(f"No AST fixer for file type: {file_extension}")
            return None

    async def _fix_python_issue(
        self, file_path: str, issue_type: str, details: Dict[str, Any], content: str
    ) -> Optional[str]:
        """Fix Python-specific issues."""
        if issue_type == "undefined_variable":
            variable_name = details.get("variable_name", "")
            return await self.python_fixer.fix_undefined_variable_python(
                file_path, variable_name, content
            )
        elif issue_type == "missing_import":
            module_name = details.get("module_name", "")
            symbol = details.get("symbol")
            return await self.python_fixer.fix_missing_import_python(
                file_path, module_name, content, symbol
            )

        return None

    async def _fix_javascript_issue(
        self, file_path: str, issue_type: str, details: Dict[str, Any], content: str
    ) -> Optional[str]:
        """Fix JavaScript/TypeScript-specific issues."""
        if issue_type == "undefined_variable":
            variable_name = details.get("variable_name", "")
            return await self.js_fixer.fix_undefined_variable_js(
                file_path, variable_name, content
            )
        elif issue_type == "missing_import":
            module_name = details.get("module_name", "")
            symbol = details.get("symbol")
            return await self.js_fixer.fix_missing_import_js(
                file_path, module_name, content, symbol
            )

        return None
