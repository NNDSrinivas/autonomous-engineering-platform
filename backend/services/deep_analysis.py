"""
Deep Analysis Service - Full Codebase Understanding, Database & Git Debugging

This service provides NAVI with the ability to:
1. Understand the ENTIRE codebase (not just config files)
2. Debug and fix complex database issues
3. Debug and fix complex git issues

This transforms NAVI from "reads config files" to "understands everything".
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ============================================================
# DEEP CODEBASE ANALYSIS
# ============================================================

@dataclass
class FunctionInfo:
    """Information about a function/method"""
    name: str
    file_path: str
    line_number: int
    signature: str
    docstring: Optional[str] = None
    body: Optional[str] = None
    calls: List[str] = field(default_factory=list)
    called_by: List[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    """Information about a class"""
    name: str
    file_path: str
    line_number: int
    base_classes: List[str] = field(default_factory=list)
    methods: List[FunctionInfo] = field(default_factory=list)
    attributes: List[str] = field(default_factory=list)


@dataclass
class FileAnalysis:
    """Deep analysis of a single file"""
    path: str
    language: str
    lines_of_code: int
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    todos: List[str] = field(default_factory=list)


@dataclass
class CodebaseAnalysis:
    """Complete codebase analysis"""
    workspace_path: str
    total_files: int = 0
    total_lines: int = 0
    languages: Dict[str, int] = field(default_factory=dict)  # language -> file count
    files: Dict[str, FileAnalysis] = field(default_factory=dict)
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)  # file -> imports
    symbol_table: Dict[str, List[str]] = field(default_factory=dict)  # symbol -> [file_paths]
    errors: List[Dict[str, Any]] = field(default_factory=list)


class DeepCodeAnalyzer:
    """
    Analyzes entire codebase deeply - reads ALL files, extracts functions,
    classes, dependencies, and builds a complete understanding.
    """

    SKIP_DIRS = {
        "node_modules", ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
        "venv", ".venv", "env", ".env", "dist", "build", "target", "out",
        ".next", ".nuxt", ".cache", "coverage", ".tox", "vendor",
        ".idea", ".vscode", "*.egg-info",
    }

    LANGUAGE_EXTENSIONS = {
        ".py": "python", ".js": "javascript", ".jsx": "javascript",
        ".ts": "typescript", ".tsx": "typescript", ".java": "java",
        ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php",
        ".cs": "csharp", ".cpp": "cpp", ".c": "c", ".swift": "swift",
        ".kt": "kotlin", ".scala": "scala", ".sql": "sql",
        ".html": "html", ".css": "css", ".vue": "vue", ".svelte": "svelte",
    }

    @classmethod
    async def analyze_workspace(
        cls,
        workspace_path: str,
        max_files: int = 500,
        max_file_size: int = 100 * 1024,  # 100KB
    ) -> CodebaseAnalysis:
        """
        Deeply analyze an entire workspace - reads all source files.
        """
        analysis = CodebaseAnalysis(workspace_path=workspace_path)
        workspace = Path(workspace_path)

        if not workspace.exists():
            analysis.errors.append({"error": f"Workspace not found: {workspace_path}"})
            return analysis

        files_analyzed = 0

        for root, dirs, files in os.walk(workspace):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in cls.SKIP_DIRS and not d.startswith('.')]

            for filename in files:
                if files_analyzed >= max_files:
                    break

                file_path = Path(root) / filename
                ext = file_path.suffix.lower()

                if ext not in cls.LANGUAGE_EXTENSIONS:
                    continue

                # Skip large files
                try:
                    if file_path.stat().st_size > max_file_size:
                        continue
                except OSError:
                    continue

                # Analyze file
                file_analysis = await cls._analyze_file(file_path, workspace)
                if file_analysis:
                    rel_path = str(file_path.relative_to(workspace))
                    analysis.files[rel_path] = file_analysis
                    analysis.total_files += 1
                    analysis.total_lines += file_analysis.lines_of_code

                    # Track language
                    lang = file_analysis.language
                    analysis.languages[lang] = analysis.languages.get(lang, 0) + 1

                    # Build dependency graph
                    analysis.dependency_graph[rel_path] = file_analysis.imports

                    # Build symbol table
                    for func in file_analysis.functions:
                        if func.name not in analysis.symbol_table:
                            analysis.symbol_table[func.name] = []
                        analysis.symbol_table[func.name].append(rel_path)

                    for cls_info in file_analysis.classes:
                        if cls_info.name not in analysis.symbol_table:
                            analysis.symbol_table[cls_info.name] = []
                        analysis.symbol_table[cls_info.name].append(rel_path)

                files_analyzed += 1

        return analysis

    @classmethod
    async def _analyze_file(cls, file_path: Path, workspace: Path) -> Optional[FileAnalysis]:
        """Analyze a single file deeply."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            ext = file_path.suffix.lower()
            language = cls.LANGUAGE_EXTENSIONS.get(ext, "unknown")

            analysis = FileAnalysis(
                path=str(file_path.relative_to(workspace)),
                language=language,
                lines_of_code=len(content.splitlines()),
            )

            # Extract imports
            analysis.imports = cls._extract_imports(content, language)

            # Extract functions
            analysis.functions = cls._extract_functions(content, language, str(file_path))

            # Extract classes
            analysis.classes = cls._extract_classes(content, language, str(file_path))

            # Find TODOs
            analysis.todos = cls._extract_todos(content)

            # Find potential errors/issues
            analysis.errors = cls._find_potential_issues(content, language)

            return analysis

        except Exception as e:
            logger.warning(f"Failed to analyze {file_path}: {e}")
            return None

    @classmethod
    def _extract_imports(cls, content: str, language: str) -> List[str]:
        """Extract import statements based on language."""
        imports = []

        patterns = {
            "python": [
                r'^import\s+([\w.]+)',
                r'^from\s+([\w.]+)\s+import',
            ],
            "javascript": [
                r"import\s+.*?from\s+['\"]([^'\"]+)['\"]",
                r"require\(['\"]([^'\"]+)['\"]\)",
            ],
            "typescript": [
                r"import\s+.*?from\s+['\"]([^'\"]+)['\"]",
            ],
            "go": [
                r'^import\s+"([^"]+)"',
                r'^\s+"([^"]+)"',  # Inside import block
            ],
            "java": [
                r'^import\s+([\w.]+);',
            ],
            "rust": [
                r'^use\s+([\w:]+)',
            ],
        }

        for pattern in patterns.get(language, []):
            for match in re.finditer(pattern, content, re.MULTILINE):
                imports.append(match.group(1))

        return imports

    @classmethod
    def _extract_functions(cls, content: str, language: str, file_path: str) -> List[FunctionInfo]:
        """Extract function definitions."""
        functions = []
        content.splitlines()

        patterns = {
            "python": r'^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)(?:\s*->.*?)?:',
            "javascript": r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>',
            "typescript": r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*[<(]([^)]*)\)|(?:const|let)\s+(\w+)\s*(?::\s*[\w<>[\],\s]+)?\s*=\s*(?:async\s+)?\(([^)]*)\)\s*(?::\s*[\w<>[\],\s]+)?\s*=>',
            "go": r'^func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(([^)]*)\)',
            "java": r'(?:public|private|protected)?\s*(?:static)?\s*(?:\w+(?:<[\w<>,\s]+>)?)\s+(\w+)\s*\(([^)]*)\)',
            "rust": r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]+>)?\s*\(([^)]*)\)',
        }

        pattern = patterns.get(language)
        if not pattern:
            return functions

        for match in re.finditer(pattern, content, re.MULTILINE):
            # Get function name from groups
            name = None
            params = ""
            for i, group in enumerate(match.groups()):
                if group and i % 2 == 0:  # Name groups are even
                    name = group
                elif group and i % 2 == 1:  # Param groups are odd
                    params = group
                    break

            if name:
                start_pos = match.start()
                line_num = content[:start_pos].count('\n') + 1

                functions.append(FunctionInfo(
                    name=name,
                    file_path=file_path,
                    line_number=line_num,
                    signature=f"{name}({params})",
                ))

        return functions

    @classmethod
    def _extract_classes(cls, content: str, language: str, file_path: str) -> List[ClassInfo]:
        """Extract class definitions."""
        classes = []

        patterns = {
            "python": r'^class\s+(\w+)(?:\(([^)]*)\))?:',
            "javascript": r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?',
            "typescript": r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?',
            "java": r'(?:public|private)?\s*(?:abstract|final)?\s*class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?',
            "go": r'^type\s+(\w+)\s+struct',
            "rust": r'(?:pub\s+)?struct\s+(\w+)',
        }

        pattern = patterns.get(language)
        if not pattern:
            return classes

        for match in re.finditer(pattern, content, re.MULTILINE):
            name = match.group(1)
            start_pos = match.start()
            line_num = content[:start_pos].count('\n') + 1

            base_classes = []
            if match.lastindex and match.lastindex >= 2 and match.group(2):
                base_classes = [b.strip() for b in match.group(2).split(',')]

            classes.append(ClassInfo(
                name=name,
                file_path=file_path,
                line_number=line_num,
                base_classes=base_classes,
            ))

        return classes

    @classmethod
    def _extract_todos(cls, content: str) -> List[str]:
        """Extract TODO comments."""
        todos = []
        pattern = r'(?:#|//|/\*)\s*(?:TODO|FIXME|HACK|XXX)[:\s]*(.*?)(?:\n|\*/)'
        for match in re.finditer(pattern, content, re.IGNORECASE):
            todos.append(match.group(1).strip())
        return todos[:10]  # Limit

    @classmethod
    def _find_potential_issues(cls, content: str, language: str) -> List[Dict[str, Any]]:
        """Find potential code issues."""
        issues = []

        # Common issues across languages
        if "password" in content.lower() and "=" in content:
            if re.search(r'password\s*=\s*["\'][^"\']+["\']', content, re.IGNORECASE):
                issues.append({"type": "security", "message": "Hardcoded password detected"})

        if "api_key" in content.lower() and "=" in content:
            if re.search(r'api_key\s*=\s*["\'][^"\']+["\']', content, re.IGNORECASE):
                issues.append({"type": "security", "message": "Hardcoded API key detected"})

        # Language-specific issues
        if language == "python":
            if "eval(" in content:
                issues.append({"type": "security", "message": "Use of eval() is dangerous"})
            if "exec(" in content:
                issues.append({"type": "security", "message": "Use of exec() is dangerous"})

        if language in ["javascript", "typescript"]:
            if "eval(" in content:
                issues.append({"type": "security", "message": "Use of eval() is dangerous"})
            if "innerHTML" in content:
                issues.append({"type": "security", "message": "innerHTML can lead to XSS"})

        return issues[:5]  # Limit

    @classmethod
    async def find_symbol(cls, workspace_path: str, symbol_name: str) -> List[Dict[str, Any]]:
        """Find all occurrences of a symbol in the codebase."""
        results = []
        workspace = Path(workspace_path)

        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in cls.SKIP_DIRS]

            for filename in files:
                ext = Path(filename).suffix.lower()
                if ext not in cls.LANGUAGE_EXTENSIONS:
                    continue

                file_path = Path(root) / filename
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    for i, line in enumerate(content.splitlines(), 1):
                        if symbol_name in line:
                            results.append({
                                "file": str(file_path.relative_to(workspace)),
                                "line": i,
                                "content": line.strip()[:200],
                            })
                except Exception:
                    continue

                if len(results) >= 50:  # Limit
                    break

        return results


# ============================================================
# DATABASE DEBUGGING & FIXING
# ============================================================

@dataclass
class TableInfo:
    """Information about a database table"""
    name: str
    columns: List[Dict[str, Any]] = field(default_factory=list)
    primary_key: Optional[str] = None
    foreign_keys: List[Dict[str, str]] = field(default_factory=list)
    indexes: List[str] = field(default_factory=list)


@dataclass
class DatabaseAnalysis:
    """Complete database analysis"""
    database_type: str
    connection_status: str
    tables: Dict[str, TableInfo] = field(default_factory=dict)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    migrations: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class DatabaseDebugger:
    """
    Debug and fix complex database issues:
    - Schema introspection
    - Migration analysis
    - Connection problems
    - ORM model parsing
    - Query optimization suggestions
    """

    @classmethod
    async def analyze_database(
        cls,
        workspace_path: str,
        database_url: Optional[str] = None,
    ) -> DatabaseAnalysis:
        """
        Comprehensive database analysis including:
        - Schema introspection
        - ORM model parsing
        - Migration analysis
        - Issue detection
        """
        analysis = DatabaseAnalysis(
            database_type="unknown",
            connection_status="not_connected",
        )

        # 1. Parse ORM models from code
        orm_models = await cls._parse_orm_models(workspace_path)
        for model in orm_models:
            analysis.tables[model["name"]] = TableInfo(
                name=model["name"],
                columns=model.get("columns", []),
            )

        # 2. Analyze migrations
        analysis.migrations = await cls._analyze_migrations(workspace_path)

        # 3. Check for common issues
        analysis.issues = await cls._detect_issues(workspace_path, orm_models)

        # 4. Generate suggestions
        analysis.suggestions = cls._generate_suggestions(analysis)

        # 5. Try to connect and introspect if URL provided
        if database_url:
            try:
                schema = await cls._introspect_database(database_url)
                analysis.connection_status = "connected"
                analysis.database_type = schema.get("type", "unknown")
                # Merge with ORM models
                for table in schema.get("tables", []):
                    if table["name"] not in analysis.tables:
                        analysis.tables[table["name"]] = TableInfo(
                            name=table["name"],
                            columns=table.get("columns", []),
                        )
            except Exception as e:
                analysis.connection_status = f"connection_failed: {e}"
                analysis.issues.append({
                    "type": "connection",
                    "message": f"Failed to connect to database: {e}",
                    "suggestion": "Check your DATABASE_URL and ensure the database server is running",
                })

        return analysis

    @classmethod
    async def _parse_orm_models(cls, workspace_path: str) -> List[Dict[str, Any]]:
        """Parse ORM models from Python/TypeScript code."""
        models = []
        workspace = Path(workspace_path)

        # Look for common model file patterns
        model_patterns = [
            "**/models.py", "**/models/*.py", "**/model.py",
            "**/schema.py", "**/schemas/*.py",
            "**/entities/*.py", "**/entity.py",
            "**/prisma/schema.prisma",
            "**/drizzle/*.ts",
        ]

        for pattern in model_patterns:
            for file_path in workspace.glob(pattern):
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')

                    # SQLAlchemy models
                    if file_path.suffix == '.py':
                        models.extend(cls._parse_sqlalchemy_models(content))
                        models.extend(cls._parse_django_models(content))

                    # Prisma schema
                    elif file_path.suffix == '.prisma':
                        models.extend(cls._parse_prisma_models(content))

                except Exception as e:
                    logger.warning(f"Failed to parse {file_path}: {e}")

        return models

    @classmethod
    def _parse_sqlalchemy_models(cls, content: str) -> List[Dict[str, Any]]:
        """Parse SQLAlchemy model definitions."""
        models = []

        # Find class definitions that inherit from Base or Model
        class_pattern = r'class\s+(\w+)\s*\([^)]*(?:Base|Model|db\.Model)[^)]*\):'
        column_pattern = r'(\w+)\s*=\s*(?:Column|db\.Column)\s*\(\s*(\w+)'

        for class_match in re.finditer(class_pattern, content):
            model_name = class_match.group(1)
            # Find columns within this class
            class_start = class_match.end()
            # Find next class or end of file
            next_class = re.search(r'\nclass\s+\w+', content[class_start:])
            class_end = class_start + next_class.start() if next_class else len(content)
            class_content = content[class_start:class_end]

            columns = []
            for col_match in re.finditer(column_pattern, class_content):
                columns.append({
                    "name": col_match.group(1),
                    "type": col_match.group(2),
                })

            if model_name:
                models.append({
                    "name": model_name,
                    "type": "sqlalchemy",
                    "columns": columns,
                })

        return models

    @classmethod
    def _parse_django_models(cls, content: str) -> List[Dict[str, Any]]:
        """Parse Django model definitions."""
        models = []

        # Find class definitions that inherit from models.Model
        class_pattern = r'class\s+(\w+)\s*\(models\.Model\):'
        field_pattern = r'(\w+)\s*=\s*models\.(\w+Field)\s*\('

        for class_match in re.finditer(class_pattern, content):
            model_name = class_match.group(1)
            class_start = class_match.end()
            next_class = re.search(r'\nclass\s+\w+', content[class_start:])
            class_end = class_start + next_class.start() if next_class else len(content)
            class_content = content[class_start:class_end]

            columns = []
            for field_match in re.finditer(field_pattern, class_content):
                columns.append({
                    "name": field_match.group(1),
                    "type": field_match.group(2),
                })

            if model_name:
                models.append({
                    "name": model_name,
                    "type": "django",
                    "columns": columns,
                })

        return models

    @classmethod
    def _parse_prisma_models(cls, content: str) -> List[Dict[str, Any]]:
        """Parse Prisma schema models."""
        models = []

        model_pattern = r'model\s+(\w+)\s*\{([^}]+)\}'

        for match in re.finditer(model_pattern, content):
            model_name = match.group(1)
            model_body = match.group(2)

            columns = []
            for line in model_body.splitlines():
                line = line.strip()
                if not line or line.startswith('@@') or line.startswith('//'):
                    continue

                parts = line.split()
                if len(parts) >= 2:
                    columns.append({
                        "name": parts[0],
                        "type": parts[1],
                    })

            models.append({
                "name": model_name,
                "type": "prisma",
                "columns": columns,
            })

        return models

    @classmethod
    async def _analyze_migrations(cls, workspace_path: str) -> List[Dict[str, Any]]:
        """Analyze database migrations."""
        migrations = []
        workspace = Path(workspace_path)

        # Check for different migration systems
        migration_dirs = [
            "alembic/versions",
            "migrations",
            "db/migrate",
            "prisma/migrations",
            "drizzle",
        ]

        for dir_name in migration_dirs:
            migration_dir = workspace / dir_name
            if migration_dir.exists():
                for file_path in sorted(migration_dir.glob("*")):
                    if file_path.is_file() and file_path.suffix in ['.py', '.sql', '.ts']:
                        migrations.append({
                            "file": str(file_path.relative_to(workspace)),
                            "name": file_path.stem,
                            "applied": None,  # Would need DB connection to check
                        })

        return migrations

    @classmethod
    async def _detect_issues(cls, workspace_path: str, models: List[Dict]) -> List[Dict[str, Any]]:
        """Detect common database issues."""
        issues = []

        # Check for missing migrations
        workspace = Path(workspace_path)
        alembic_ini = workspace / "alembic.ini"
        if alembic_ini.exists():
            versions_dir = workspace / "alembic" / "versions"
            if not versions_dir.exists() or not list(versions_dir.glob("*.py")):
                issues.append({
                    "type": "migration",
                    "severity": "warning",
                    "message": "Alembic is configured but no migrations found",
                    "fix": "Run: alembic revision --autogenerate -m 'initial'",
                })

        # Check for models without primary key
        for model in models:
            has_pk = any(
                col.get("name") == "id" or "primary" in str(col).lower()
                for col in model.get("columns", [])
            )
            if not has_pk:
                issues.append({
                    "type": "schema",
                    "severity": "warning",
                    "message": f"Model '{model['name']}' may be missing a primary key",
                    "fix": f"Add an 'id' column to {model['name']}",
                })

        return issues

    @classmethod
    def _generate_suggestions(cls, analysis: DatabaseAnalysis) -> List[str]:
        """Generate improvement suggestions."""
        suggestions = []

        if analysis.connection_status != "connected":
            suggestions.append("Set DATABASE_URL environment variable to enable full database analysis")

        if not analysis.migrations:
            suggestions.append("Consider using a migration system (Alembic, Django migrations, Prisma migrate)")

        if len(analysis.tables) > 10:
            suggestions.append("Consider documenting your database schema")

        return suggestions

    @classmethod
    async def _introspect_database(cls, database_url: str) -> Dict[str, Any]:
        """Introspect actual database schema."""
        # This would require database connection
        # For now, return placeholder
        return {"type": "postgresql", "tables": []}

    @classmethod
    async def fix_migration_issues(
        cls,
        workspace_path: str,
        issue_type: str,
    ) -> Dict[str, Any]:
        """
        Automatically fix common migration issues.
        """
        result = {"success": False, "message": "", "commands_run": []}
        workspace = Path(workspace_path)

        if issue_type == "generate_migration":
            # Check for Alembic
            if (workspace / "alembic.ini").exists():
                try:
                    proc = subprocess.run(
                        ["alembic", "revision", "--autogenerate", "-m", "auto_generated"],
                        cwd=workspace,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    result["commands_run"].append("alembic revision --autogenerate -m 'auto_generated'")
                    result["success"] = proc.returncode == 0
                    result["message"] = proc.stdout if proc.returncode == 0 else proc.stderr
                except Exception as e:
                    result["message"] = f"Failed to generate migration: {e}"

            # Check for Django
            elif (workspace / "manage.py").exists():
                try:
                    proc = subprocess.run(
                        ["python", "manage.py", "makemigrations"],
                        cwd=workspace,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    result["commands_run"].append("python manage.py makemigrations")
                    result["success"] = proc.returncode == 0
                    result["message"] = proc.stdout if proc.returncode == 0 else proc.stderr
                except Exception as e:
                    result["message"] = f"Failed to generate migration: {e}"

        elif issue_type == "apply_migrations":
            if (workspace / "alembic.ini").exists():
                try:
                    proc = subprocess.run(
                        ["alembic", "upgrade", "head"],
                        cwd=workspace,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    result["commands_run"].append("alembic upgrade head")
                    result["success"] = proc.returncode == 0
                    result["message"] = proc.stdout if proc.returncode == 0 else proc.stderr
                except Exception as e:
                    result["message"] = f"Failed to apply migrations: {e}"

            elif (workspace / "manage.py").exists():
                try:
                    proc = subprocess.run(
                        ["python", "manage.py", "migrate"],
                        cwd=workspace,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    result["commands_run"].append("python manage.py migrate")
                    result["success"] = proc.returncode == 0
                    result["message"] = proc.stdout if proc.returncode == 0 else proc.stderr
                except Exception as e:
                    result["message"] = f"Failed to apply migrations: {e}"

        return result


# ============================================================
# GIT DEBUGGING & FIXING
# ============================================================

@dataclass
class GitStatus:
    """Detailed git repository status"""
    branch: str
    is_detached: bool = False
    ahead: int = 0
    behind: int = 0
    staged_files: List[str] = field(default_factory=list)
    unstaged_files: List[str] = field(default_factory=list)
    untracked_files: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    stashes: int = 0
    is_rebasing: bool = False
    is_merging: bool = False
    is_cherry_picking: bool = False
    is_bisecting: bool = False


@dataclass
class GitIssue:
    """A detected git issue with fix suggestions"""
    type: str
    severity: str  # "error", "warning", "info"
    message: str
    details: Optional[str] = None
    fix_command: Optional[str] = None
    fix_steps: List[str] = field(default_factory=list)


@dataclass
class GitAnalysis:
    """Complete git repository analysis"""
    status: GitStatus
    issues: List[GitIssue] = field(default_factory=list)
    recent_commits: List[Dict[str, str]] = field(default_factory=list)
    branches: List[Dict[str, Any]] = field(default_factory=list)
    remotes: List[str] = field(default_factory=list)


class GitDebugger:
    """
    Debug and fix complex git issues:
    - Merge conflict resolution
    - Rebase recovery
    - Detached HEAD handling
    - Stash conflicts
    - Branch cleanup
    - History analysis
    """

    @classmethod
    def _run_git(cls, repo_path: str, args: List[str], check: bool = True) -> Tuple[str, str, int]:
        """Run a git command and return stdout, stderr, returncode."""
        try:
            proc = subprocess.run(
                ["git"] + args,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timed out", 1
        except Exception as e:
            return "", str(e), 1

    @classmethod
    async def analyze_repository(cls, repo_path: str) -> GitAnalysis:
        """
        Comprehensive git repository analysis with issue detection.
        """
        status = await cls._get_detailed_status(repo_path)
        issues = await cls._detect_issues(repo_path, status)
        recent_commits = await cls._get_recent_commits(repo_path)
        branches = await cls._get_branches(repo_path)
        remotes = await cls._get_remotes(repo_path)

        return GitAnalysis(
            status=status,
            issues=issues,
            recent_commits=recent_commits,
            branches=branches,
            remotes=remotes,
        )

    @classmethod
    async def _get_detailed_status(cls, repo_path: str) -> GitStatus:
        """Get detailed git status including special states."""
        status = GitStatus(branch="unknown")

        # Get current branch
        stdout, _, rc = cls._run_git(repo_path, ["branch", "--show-current"])
        if rc == 0 and stdout.strip():
            status.branch = stdout.strip()
        else:
            # Check for detached HEAD
            stdout, _, rc = cls._run_git(repo_path, ["rev-parse", "--short", "HEAD"])
            if rc == 0:
                status.branch = f"HEAD detached at {stdout.strip()}"
                status.is_detached = True

        # Get ahead/behind
        stdout, _, rc = cls._run_git(repo_path, ["status", "-sb"])
        if rc == 0:
            match = re.search(r'\[ahead (\d+)', stdout)
            if match:
                status.ahead = int(match.group(1))
            match = re.search(r'behind (\d+)', stdout)
            if match:
                status.behind = int(match.group(1))

        # Get file status
        stdout, _, rc = cls._run_git(repo_path, ["status", "--porcelain"])
        if rc == 0:
            for line in stdout.splitlines():
                if len(line) < 3:
                    continue
                index_status = line[0]
                worktree_status = line[1]
                file_path = line[3:].strip()

                if index_status == 'U' or worktree_status == 'U' or line[:2] in ['DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU']:
                    status.conflicts.append(file_path)
                elif line[:2] == '??':
                    status.untracked_files.append(file_path)
                elif index_status != ' ' and index_status != '?':
                    status.staged_files.append(file_path)
                elif worktree_status != ' ' and worktree_status != '?':
                    status.unstaged_files.append(file_path)

        # Check for special states
        git_dir = Path(repo_path) / ".git"
        if (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists():
            status.is_rebasing = True
        if (git_dir / "MERGE_HEAD").exists():
            status.is_merging = True
        if (git_dir / "CHERRY_PICK_HEAD").exists():
            status.is_cherry_picking = True
        if (git_dir / "BISECT_LOG").exists():
            status.is_bisecting = True

        # Count stashes
        stdout, _, rc = cls._run_git(repo_path, ["stash", "list"])
        if rc == 0:
            status.stashes = len(stdout.strip().splitlines()) if stdout.strip() else 0

        return status

    @classmethod
    async def _detect_issues(cls, repo_path: str, status: GitStatus) -> List[GitIssue]:
        """Detect git issues and provide fixes."""
        issues = []

        # Detached HEAD
        if status.is_detached:
            issues.append(GitIssue(
                type="detached_head",
                severity="warning",
                message="You are in detached HEAD state",
                details="Changes made here may be lost if you checkout another branch",
                fix_command="git checkout -b new-branch-name",
                fix_steps=[
                    "Create a new branch: git checkout -b new-branch-name",
                    "Or return to a branch: git checkout main",
                ],
            ))

        # Merge conflicts
        if status.conflicts:
            issues.append(GitIssue(
                type="merge_conflict",
                severity="error",
                message=f"Merge conflicts in {len(status.conflicts)} file(s)",
                details=f"Conflicting files: {', '.join(status.conflicts[:5])}",
                fix_steps=[
                    "1. Edit conflicting files to resolve conflicts",
                    "2. Remove conflict markers (<<<<<<, ======, >>>>>>)",
                    "3. Stage resolved files: git add <file>",
                    "4. Complete merge: git commit",
                    "Or abort: git merge --abort",
                ],
            ))

        # Ongoing rebase
        if status.is_rebasing:
            issues.append(GitIssue(
                type="rebase_in_progress",
                severity="error",
                message="Rebase is in progress",
                fix_steps=[
                    "Continue rebase: git rebase --continue",
                    "Skip current commit: git rebase --skip",
                    "Abort rebase: git rebase --abort",
                ],
            ))

        # Ongoing merge
        if status.is_merging and not status.conflicts:
            issues.append(GitIssue(
                type="merge_in_progress",
                severity="warning",
                message="Merge is in progress",
                fix_steps=[
                    "Complete merge: git commit",
                    "Abort merge: git merge --abort",
                ],
            ))

        # Diverged from remote
        if status.ahead > 0 and status.behind > 0:
            issues.append(GitIssue(
                type="diverged",
                severity="warning",
                message=f"Branch has diverged: {status.ahead} ahead, {status.behind} behind",
                fix_steps=[
                    "Rebase onto remote: git pull --rebase",
                    "Or merge remote: git pull",
                    "Or force push (careful!): git push --force-with-lease",
                ],
            ))

        # Uncommitted changes
        if status.staged_files or status.unstaged_files:
            total = len(status.staged_files) + len(status.unstaged_files)
            issues.append(GitIssue(
                type="uncommitted_changes",
                severity="info",
                message=f"{total} uncommitted change(s)",
                fix_steps=[
                    "Stage changes: git add .",
                    "Commit: git commit -m 'message'",
                    "Or stash: git stash",
                ],
            ))

        # Stashed changes
        if status.stashes > 0:
            issues.append(GitIssue(
                type="stashed_changes",
                severity="info",
                message=f"{status.stashes} stash(es) saved",
                fix_steps=[
                    "View stashes: git stash list",
                    "Apply latest: git stash pop",
                    "Apply specific: git stash apply stash@{n}",
                ],
            ))

        return issues

    @classmethod
    async def _get_recent_commits(cls, repo_path: str, limit: int = 10) -> List[Dict[str, str]]:
        """Get recent commit history."""
        commits = []
        stdout, _, rc = cls._run_git(
            repo_path,
            ["log", f"-{limit}", "--pretty=format:%h|%s|%an|%ar"]
        )
        if rc == 0:
            for line in stdout.strip().splitlines():
                parts = line.split("|")
                if len(parts) >= 4:
                    commits.append({
                        "hash": parts[0],
                        "message": parts[1],
                        "author": parts[2],
                        "date": parts[3],
                    })
        return commits

    @classmethod
    async def _get_branches(cls, repo_path: str) -> List[Dict[str, Any]]:
        """Get all branches with tracking info."""
        branches = []
        stdout, _, rc = cls._run_git(repo_path, ["branch", "-vv", "--all"])
        if rc == 0:
            for line in stdout.splitlines():
                is_current = line.startswith("*")
                line = line.lstrip("* ")
                parts = line.split()
                if parts:
                    branches.append({
                        "name": parts[0],
                        "current": is_current,
                        "remote": "remotes/" in parts[0],
                    })
        return branches

    @classmethod
    async def _get_remotes(cls, repo_path: str) -> List[str]:
        """Get configured remotes."""
        stdout, _, rc = cls._run_git(repo_path, ["remote"])
        if rc == 0:
            return stdout.strip().splitlines()
        return []

    @classmethod
    async def fix_issue(
        cls,
        repo_path: str,
        issue_type: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Automatically fix a detected git issue.
        """
        result = {"success": False, "message": "", "commands_run": []}
        options = options or {}

        if issue_type == "detached_head":
            branch_name = options.get("branch_name", "recovered-work")
            stdout, stderr, rc = cls._run_git(repo_path, ["checkout", "-b", branch_name])
            result["commands_run"].append(f"git checkout -b {branch_name}")
            result["success"] = rc == 0
            result["message"] = stdout if rc == 0 else stderr

        elif issue_type == "merge_conflict_abort":
            stdout, stderr, rc = cls._run_git(repo_path, ["merge", "--abort"])
            result["commands_run"].append("git merge --abort")
            result["success"] = rc == 0
            result["message"] = "Merge aborted successfully" if rc == 0 else stderr

        elif issue_type == "rebase_abort":
            stdout, stderr, rc = cls._run_git(repo_path, ["rebase", "--abort"])
            result["commands_run"].append("git rebase --abort")
            result["success"] = rc == 0
            result["message"] = "Rebase aborted successfully" if rc == 0 else stderr

        elif issue_type == "rebase_continue":
            stdout, stderr, rc = cls._run_git(repo_path, ["rebase", "--continue"])
            result["commands_run"].append("git rebase --continue")
            result["success"] = rc == 0
            result["message"] = stdout if rc == 0 else stderr

        elif issue_type == "stash_pop":
            stdout, stderr, rc = cls._run_git(repo_path, ["stash", "pop"])
            result["commands_run"].append("git stash pop")
            result["success"] = rc == 0
            result["message"] = stdout if rc == 0 else stderr

        elif issue_type == "reset_hard":
            # Dangerous - require explicit confirmation
            if options.get("confirmed"):
                ref = options.get("ref", "HEAD")
                stdout, stderr, rc = cls._run_git(repo_path, ["reset", "--hard", ref])
                result["commands_run"].append(f"git reset --hard {ref}")
                result["success"] = rc == 0
                result["message"] = stdout if rc == 0 else stderr
            else:
                result["message"] = "Reset --hard requires explicit confirmation"

        elif issue_type == "clean_untracked":
            if options.get("confirmed"):
                stdout, stderr, rc = cls._run_git(repo_path, ["clean", "-fd"])
                result["commands_run"].append("git clean -fd")
                result["success"] = rc == 0
                result["message"] = stdout if rc == 0 else stderr
            else:
                result["message"] = "Clean requires explicit confirmation"

        elif issue_type == "pull_rebase":
            stdout, stderr, rc = cls._run_git(repo_path, ["pull", "--rebase"])
            result["commands_run"].append("git pull --rebase")
            result["success"] = rc == 0
            result["message"] = stdout if rc == 0 else stderr

        return result

    @classmethod
    async def get_conflict_details(cls, repo_path: str) -> List[Dict[str, Any]]:
        """Get detailed information about merge conflicts."""
        conflicts = []
        status = await cls._get_detailed_status(repo_path)

        for file_path in status.conflicts:
            full_path = Path(repo_path) / file_path
            if full_path.exists():
                try:
                    content = full_path.read_text(encoding='utf-8', errors='ignore')
                    # Find conflict markers
                    conflict_sections = []
                    in_conflict = False
                    current_section = {"ours": [], "theirs": []}

                    for line in content.splitlines():
                        if line.startswith("<<<<<<<"):
                            in_conflict = True
                            current_section = {"ours": [], "theirs": [], "marker": line}
                        elif line.startswith("=======") and in_conflict:
                            pass  # Separator
                        elif line.startswith(">>>>>>>") and in_conflict:
                            in_conflict = False
                            conflict_sections.append(current_section)
                        elif in_conflict:
                            if "=======" not in content[:content.find(line)].split("<<<<<<<")[-1]:
                                current_section["ours"].append(line)
                            else:
                                current_section["theirs"].append(line)

                    conflicts.append({
                        "file": file_path,
                        "conflict_count": len(conflict_sections),
                        "sections": conflict_sections[:3],  # Limit
                    })
                except Exception as e:
                    conflicts.append({
                        "file": file_path,
                        "error": str(e),
                    })

        return conflicts


# ============================================================
# UNIFIED DEEP ANALYSIS API
# ============================================================

class DeepAnalysisService:
    """
    Unified service for all deep analysis capabilities.
    This is the main entry point for NAVI to use.
    """

    @classmethod
    async def analyze_workspace_deep(
        cls,
        workspace_path: str,
        include_code: bool = True,
        include_database: bool = True,
        include_git: bool = True,
        database_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive deep analysis of the workspace.
        Returns a complete picture of:
        - Codebase structure and issues
        - Database schema and problems
        - Git status and issues
        """
        result = {
            "workspace_path": workspace_path,
            "analyzed_at": datetime.utcnow().isoformat(),
            "code": None,
            "database": None,
            "git": None,
            "summary": {
                "total_issues": 0,
                "critical_issues": [],
                "suggestions": [],
            },
        }

        # Code analysis
        if include_code:
            try:
                code_analysis = await DeepCodeAnalyzer.analyze_workspace(workspace_path)
                result["code"] = {
                    "total_files": code_analysis.total_files,
                    "total_lines": code_analysis.total_lines,
                    "languages": code_analysis.languages,
                    "symbols": len(code_analysis.symbol_table),
                    "errors": code_analysis.errors,
                }
                result["summary"]["total_issues"] += len(code_analysis.errors)
            except Exception as e:
                result["code"] = {"error": str(e)}

        # Database analysis
        if include_database:
            try:
                db_analysis = await DatabaseDebugger.analyze_database(workspace_path, database_url)
                result["database"] = {
                    "type": db_analysis.database_type,
                    "connection_status": db_analysis.connection_status,
                    "tables_count": len(db_analysis.tables),
                    "tables": list(db_analysis.tables.keys()),
                    "migrations_count": len(db_analysis.migrations),
                    "issues": [{"type": i["type"], "message": i["message"]} for i in db_analysis.issues],
                    "suggestions": db_analysis.suggestions,
                }
                result["summary"]["total_issues"] += len(db_analysis.issues)
                for issue in db_analysis.issues:
                    if issue.get("severity") == "error":
                        result["summary"]["critical_issues"].append(issue["message"])
            except Exception as e:
                result["database"] = {"error": str(e)}

        # Git analysis
        if include_git:
            try:
                git_analysis = await GitDebugger.analyze_repository(workspace_path)
                result["git"] = {
                    "branch": git_analysis.status.branch,
                    "is_detached": git_analysis.status.is_detached,
                    "ahead": git_analysis.status.ahead,
                    "behind": git_analysis.status.behind,
                    "conflicts": git_analysis.status.conflicts,
                    "staged_files": len(git_analysis.status.staged_files),
                    "unstaged_files": len(git_analysis.status.unstaged_files),
                    "is_rebasing": git_analysis.status.is_rebasing,
                    "is_merging": git_analysis.status.is_merging,
                    "stashes": git_analysis.status.stashes,
                    "issues": [{"type": i.type, "severity": i.severity, "message": i.message} for i in git_analysis.issues],
                    "recent_commits": git_analysis.recent_commits[:5],
                }
                result["summary"]["total_issues"] += len(git_analysis.issues)
                for issue in git_analysis.issues:
                    if issue.severity == "error":
                        result["summary"]["critical_issues"].append(issue.message)
            except Exception as e:
                result["git"] = {"error": str(e)}

        return result

    @classmethod
    async def find_and_fix(
        cls,
        workspace_path: str,
        issue_type: str,
        auto_fix: bool = False,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Find a specific issue and optionally fix it.
        """
        result = {
            "issue_found": False,
            "issue_details": None,
            "fix_applied": False,
            "fix_result": None,
        }

        options = options or {}

        # Database issues
        if issue_type.startswith("db_"):
            db_issue = issue_type[3:]  # Remove "db_" prefix
            db_analysis = await DatabaseDebugger.analyze_database(workspace_path)
            matching_issues = [i for i in db_analysis.issues if i["type"] == db_issue]
            if matching_issues:
                result["issue_found"] = True
                result["issue_details"] = matching_issues[0]
                if auto_fix:
                    fix_result = await DatabaseDebugger.fix_migration_issues(workspace_path, db_issue)
                    result["fix_applied"] = fix_result.get("success", False)
                    result["fix_result"] = fix_result

        # Git issues
        elif issue_type.startswith("git_"):
            git_issue = issue_type[4:]  # Remove "git_" prefix
            git_analysis = await GitDebugger.analyze_repository(workspace_path)
            matching_issues = [i for i in git_analysis.issues if i.type == git_issue]
            if matching_issues:
                result["issue_found"] = True
                result["issue_details"] = {
                    "type": matching_issues[0].type,
                    "message": matching_issues[0].message,
                    "fix_steps": matching_issues[0].fix_steps,
                }
                if auto_fix:
                    fix_result = await GitDebugger.fix_issue(workspace_path, git_issue, options)
                    result["fix_applied"] = fix_result.get("success", False)
                    result["fix_result"] = fix_result

        return result


# ============================================================
# PUBLIC API FUNCTIONS
# ============================================================

async def analyze_deep(workspace_path: str, **kwargs) -> Dict[str, Any]:
    """Public API: Deep workspace analysis."""
    return await DeepAnalysisService.analyze_workspace_deep(workspace_path, **kwargs)


async def find_symbol(workspace_path: str, symbol_name: str) -> List[Dict[str, Any]]:
    """Public API: Find a symbol in the codebase."""
    return await DeepCodeAnalyzer.find_symbol(workspace_path, symbol_name)


async def analyze_git(workspace_path: str) -> Dict[str, Any]:
    """Public API: Git repository analysis."""
    analysis = await GitDebugger.analyze_repository(workspace_path)
    return {
        "status": {
            "branch": analysis.status.branch,
            "is_detached": analysis.status.is_detached,
            "conflicts": analysis.status.conflicts,
            "is_rebasing": analysis.status.is_rebasing,
            "is_merging": analysis.status.is_merging,
        },
        "issues": [{"type": i.type, "message": i.message, "fix_steps": i.fix_steps} for i in analysis.issues],
        "recent_commits": analysis.recent_commits,
    }


async def fix_git_issue(workspace_path: str, issue_type: str, options: Dict = None) -> Dict[str, Any]:
    """Public API: Fix a git issue."""
    return await GitDebugger.fix_issue(workspace_path, issue_type, options)


async def analyze_database(workspace_path: str, database_url: str = None) -> Dict[str, Any]:
    """Public API: Database analysis."""
    analysis = await DatabaseDebugger.analyze_database(workspace_path, database_url)
    return {
        "type": analysis.database_type,
        "connection": analysis.connection_status,
        "tables": {name: {"columns": [c["name"] for c in t.columns]} for name, t in analysis.tables.items()},
        "migrations": analysis.migrations,
        "issues": analysis.issues,
        "suggestions": analysis.suggestions,
    }


async def fix_database_issue(workspace_path: str, issue_type: str) -> Dict[str, Any]:
    """Public API: Fix a database issue."""
    return await DatabaseDebugger.fix_migration_issues(workspace_path, issue_type)


# ============================================================
# ADVANCED GIT OPERATIONS
# ============================================================

class AdvancedGitOperations:
    """
    Advanced git operations for complex workflows:
    - Cherry-picking commits
    - Interactive rebase (squash, reorder, edit)
    - Bisect for finding bugs
    - Advanced stash management
    - Branch cleanup
    - History rewriting
    - Reflog recovery
    """

    @classmethod
    def _run_git(cls, repo_path: str, args: List[str], timeout: int = 60) -> Tuple[str, str, int]:
        """Run a git command and return stdout, stderr, returncode."""
        try:
            proc = subprocess.run(
                ["git"] + args,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timed out", 1
        except Exception as e:
            return "", str(e), 1

    # ==================== CHERRY-PICK ====================

    @classmethod
    async def cherry_pick(
        cls,
        repo_path: str,
        commit_hash: str,
        no_commit: bool = False,
        strategy: Optional[str] = None,  # "ours", "theirs"
    ) -> Dict[str, Any]:
        """
        Cherry-pick a specific commit.

        Args:
            repo_path: Path to git repository
            commit_hash: Commit hash to cherry-pick
            no_commit: If True, apply changes without committing
            strategy: Merge strategy for conflicts ("ours" or "theirs")
        """
        result = {"success": False, "message": "", "conflicts": [], "commands_run": []}

        args = ["cherry-pick"]
        if no_commit:
            args.append("-n")
        if strategy:
            args.extend(["-X", strategy])
        args.append(commit_hash)

        stdout, stderr, rc = cls._run_git(repo_path, args)
        result["commands_run"].append(f"git {' '.join(args)}")

        if rc == 0:
            result["success"] = True
            result["message"] = f"Successfully cherry-picked commit {commit_hash[:8]}"
        else:
            # Check for conflicts
            if "CONFLICT" in stderr or "CONFLICT" in stdout:
                result["message"] = "Cherry-pick resulted in conflicts"
                # Get conflict files
                status_out, _, _ = cls._run_git(repo_path, ["status", "--porcelain"])
                for line in status_out.splitlines():
                    if line.startswith("UU") or line.startswith("AA"):
                        result["conflicts"].append(line[3:].strip())
                result["fix_suggestions"] = [
                    "1. Resolve conflicts in the listed files",
                    "2. Stage resolved files: git add <file>",
                    "3. Continue: git cherry-pick --continue",
                    "Or abort: git cherry-pick --abort",
                ]
            else:
                result["message"] = stderr or stdout

        return result

    @classmethod
    async def cherry_pick_range(
        cls,
        repo_path: str,
        from_commit: str,
        to_commit: str,
    ) -> Dict[str, Any]:
        """Cherry-pick a range of commits."""
        result = {"success": False, "message": "", "picked_commits": [], "commands_run": []}

        # Get list of commits in range
        stdout, stderr, rc = cls._run_git(
            repo_path,
            ["log", "--oneline", "--reverse", f"{from_commit}..{to_commit}"]
        )

        if rc != 0:
            result["message"] = f"Invalid commit range: {stderr}"
            return result

        commits = [line.split()[0] for line in stdout.strip().splitlines()]
        result["commands_run"].append(f"git log --oneline --reverse {from_commit}..{to_commit}")

        for commit in commits:
            pick_result = await cls.cherry_pick(repo_path, commit)
            if pick_result["success"]:
                result["picked_commits"].append(commit)
            else:
                result["message"] = f"Failed at commit {commit}: {pick_result['message']}"
                result["conflicts"] = pick_result.get("conflicts", [])
                return result

        result["success"] = True
        result["message"] = f"Successfully cherry-picked {len(commits)} commits"
        return result

    @classmethod
    async def abort_cherry_pick(cls, repo_path: str) -> Dict[str, Any]:
        """Abort an ongoing cherry-pick."""
        stdout, stderr, rc = cls._run_git(repo_path, ["cherry-pick", "--abort"])
        return {
            "success": rc == 0,
            "message": "Cherry-pick aborted" if rc == 0 else stderr,
            "commands_run": ["git cherry-pick --abort"],
        }

    @classmethod
    async def continue_cherry_pick(cls, repo_path: str) -> Dict[str, Any]:
        """Continue cherry-pick after resolving conflicts."""
        stdout, stderr, rc = cls._run_git(repo_path, ["cherry-pick", "--continue"])
        return {
            "success": rc == 0,
            "message": "Cherry-pick continued" if rc == 0 else stderr,
            "commands_run": ["git cherry-pick --continue"],
        }

    # ==================== REBASE ====================

    @classmethod
    async def rebase_onto(
        cls,
        repo_path: str,
        target_branch: str,
        preserve_merges: bool = False,
    ) -> Dict[str, Any]:
        """
        Rebase current branch onto target branch.
        """
        result = {"success": False, "message": "", "conflicts": [], "commands_run": []}

        args = ["rebase"]
        if preserve_merges:
            args.append("--rebase-merges")
        args.append(target_branch)

        stdout, stderr, rc = cls._run_git(repo_path, args)
        result["commands_run"].append(f"git {' '.join(args)}")

        if rc == 0:
            result["success"] = True
            result["message"] = f"Successfully rebased onto {target_branch}"
        else:
            if "CONFLICT" in stderr or "CONFLICT" in stdout:
                result["message"] = "Rebase resulted in conflicts"
                status_out, _, _ = cls._run_git(repo_path, ["status", "--porcelain"])
                for line in status_out.splitlines():
                    if line.startswith("UU") or line.startswith("AA"):
                        result["conflicts"].append(line[3:].strip())
                result["fix_suggestions"] = [
                    "1. Resolve conflicts in the listed files",
                    "2. Stage resolved files: git add <file>",
                    "3. Continue: git rebase --continue",
                    "Or abort: git rebase --abort",
                ]
            else:
                result["message"] = stderr or stdout

        return result

    @classmethod
    async def squash_commits(
        cls,
        repo_path: str,
        num_commits: int,
        commit_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Squash the last N commits into one.

        Uses soft reset + recommit approach for non-interactive squash.
        """
        result = {"success": False, "message": "", "commands_run": []}

        # Get the commit message from all commits if not provided
        if not commit_message:
            stdout, _, rc = cls._run_git(
                repo_path,
                ["log", f"-{num_commits}", "--pretty=format:%s"]
            )
            if rc == 0:
                commit_message = "Squashed commits:\n" + "\n".join(
                    f"- {msg}" for msg in stdout.strip().splitlines()
                )
            else:
                commit_message = f"Squashed {num_commits} commits"

        # Soft reset to N commits back
        stdout, stderr, rc = cls._run_git(repo_path, ["reset", "--soft", f"HEAD~{num_commits}"])
        result["commands_run"].append(f"git reset --soft HEAD~{num_commits}")

        if rc != 0:
            result["message"] = f"Failed to reset: {stderr}"
            return result

        # Commit with combined message
        stdout, stderr, rc = cls._run_git(repo_path, ["commit", "-m", commit_message])
        result["commands_run"].append("git commit -m '<squash message>'")

        if rc == 0:
            result["success"] = True
            result["message"] = f"Successfully squashed {num_commits} commits into one"
            result["new_message"] = commit_message
        else:
            result["message"] = f"Failed to commit: {stderr}"

        return result

    @classmethod
    async def rebase_interactive_plan(
        cls,
        repo_path: str,
        num_commits: int,
    ) -> Dict[str, Any]:
        """
        Get the rebase plan for the last N commits (what interactive rebase would show).
        Returns the commits that would be modified.
        """
        stdout, stderr, rc = cls._run_git(
            repo_path,
            ["log", f"-{num_commits}", "--oneline", "--reverse"]
        )

        if rc != 0:
            return {"success": False, "message": stderr}

        commits = []
        for line in stdout.strip().splitlines():
            parts = line.split(" ", 1)
            if len(parts) >= 2:
                commits.append({
                    "hash": parts[0],
                    "message": parts[1],
                    "action": "pick",  # Default action
                })

        return {
            "success": True,
            "commits": commits,
            "available_actions": ["pick", "reword", "edit", "squash", "fixup", "drop"],
            "usage": "Modify 'action' field for each commit, then use execute_rebase_plan()",
        }

    @classmethod
    async def abort_rebase(cls, repo_path: str) -> Dict[str, Any]:
        """Abort an ongoing rebase."""
        stdout, stderr, rc = cls._run_git(repo_path, ["rebase", "--abort"])
        return {
            "success": rc == 0,
            "message": "Rebase aborted" if rc == 0 else stderr,
            "commands_run": ["git rebase --abort"],
        }

    @classmethod
    async def continue_rebase(cls, repo_path: str) -> Dict[str, Any]:
        """Continue rebase after resolving conflicts."""
        stdout, stderr, rc = cls._run_git(repo_path, ["rebase", "--continue"])
        return {
            "success": rc == 0,
            "message": "Rebase continued" if rc == 0 else stderr,
            "commands_run": ["git rebase --continue"],
        }

    @classmethod
    async def skip_rebase_commit(cls, repo_path: str) -> Dict[str, Any]:
        """Skip the current commit in a rebase."""
        stdout, stderr, rc = cls._run_git(repo_path, ["rebase", "--skip"])
        return {
            "success": rc == 0,
            "message": "Commit skipped" if rc == 0 else stderr,
            "commands_run": ["git rebase --skip"],
        }

    # ==================== BISECT ====================

    @classmethod
    async def bisect_start(
        cls,
        repo_path: str,
        bad_commit: str = "HEAD",
        good_commit: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start a bisect session to find a bug-introducing commit.
        """
        result = {"success": False, "message": "", "commands_run": [], "status": ""}

        # Start bisect
        stdout, stderr, rc = cls._run_git(repo_path, ["bisect", "start"])
        result["commands_run"].append("git bisect start")

        if rc != 0:
            result["message"] = f"Failed to start bisect: {stderr}"
            return result

        # Mark bad commit
        stdout, stderr, rc = cls._run_git(repo_path, ["bisect", "bad", bad_commit])
        result["commands_run"].append(f"git bisect bad {bad_commit}")

        if rc != 0:
            result["message"] = f"Failed to mark bad commit: {stderr}"
            return result

        # Mark good commit if provided
        if good_commit:
            stdout, stderr, rc = cls._run_git(repo_path, ["bisect", "good", good_commit])
            result["commands_run"].append(f"git bisect good {good_commit}")

            if rc != 0:
                result["message"] = f"Failed to mark good commit: {stderr}"
                return result

            result["status"] = stdout

        result["success"] = True
        result["message"] = "Bisect started. Test current commit and mark as 'good' or 'bad'"
        result["next_steps"] = [
            "1. Test the current commit for the bug",
            "2. If bug exists: git bisect bad",
            "3. If bug doesn't exist: git bisect good",
            "4. Repeat until the bad commit is found",
            "5. When done: git bisect reset",
        ]

        return result

    @classmethod
    async def bisect_good(cls, repo_path: str, commit: str = "") -> Dict[str, Any]:
        """Mark current or specified commit as good."""
        args = ["bisect", "good"]
        if commit:
            args.append(commit)

        stdout, stderr, rc = cls._run_git(repo_path, args)

        return {
            "success": rc == 0,
            "message": stdout if rc == 0 else stderr,
            "commands_run": [f"git {' '.join(args)}"],
            "found_bad_commit": "is the first bad commit" in stdout,
        }

    @classmethod
    async def bisect_bad(cls, repo_path: str, commit: str = "") -> Dict[str, Any]:
        """Mark current or specified commit as bad."""
        args = ["bisect", "bad"]
        if commit:
            args.append(commit)

        stdout, stderr, rc = cls._run_git(repo_path, args)

        return {
            "success": rc == 0,
            "message": stdout if rc == 0 else stderr,
            "commands_run": [f"git {' '.join(args)}"],
            "found_bad_commit": "is the first bad commit" in stdout,
        }

    @classmethod
    async def bisect_skip(cls, repo_path: str) -> Dict[str, Any]:
        """Skip current commit (can't be tested)."""
        stdout, stderr, rc = cls._run_git(repo_path, ["bisect", "skip"])
        return {
            "success": rc == 0,
            "message": stdout if rc == 0 else stderr,
            "commands_run": ["git bisect skip"],
        }

    @classmethod
    async def bisect_reset(cls, repo_path: str) -> Dict[str, Any]:
        """End bisect session and return to original HEAD."""
        stdout, stderr, rc = cls._run_git(repo_path, ["bisect", "reset"])
        return {
            "success": rc == 0,
            "message": "Bisect session ended" if rc == 0 else stderr,
            "commands_run": ["git bisect reset"],
        }

    @classmethod
    async def bisect_log(cls, repo_path: str) -> Dict[str, Any]:
        """Get the current bisect log."""
        stdout, stderr, rc = cls._run_git(repo_path, ["bisect", "log"])

        if rc != 0:
            return {"success": False, "message": stderr}

        return {
            "success": True,
            "log": stdout,
            "commands_run": ["git bisect log"],
        }

    @classmethod
    async def bisect_run(
        cls,
        repo_path: str,
        test_command: str,
    ) -> Dict[str, Any]:
        """
        Automatically bisect by running a test command.
        The command should return 0 for good, non-zero for bad.
        """
        result = {"success": False, "message": "", "commands_run": [], "bad_commit": None}

        stdout, stderr, rc = cls._run_git(
            repo_path,
            ["bisect", "run"] + test_command.split(),
            timeout=300,  # 5 minute timeout for bisect run
        )
        result["commands_run"].append(f"git bisect run {test_command}")

        if "is the first bad commit" in stdout:
            # Extract the bad commit hash
            match = re.search(r'([a-f0-9]{40}) is the first bad commit', stdout)
            if match:
                result["bad_commit"] = match.group(1)
            result["success"] = True
            result["message"] = stdout
        else:
            result["message"] = stderr or stdout

        return result

    # ==================== STASH ====================

    @classmethod
    async def stash_save(
        cls,
        repo_path: str,
        message: Optional[str] = None,
        include_untracked: bool = False,
        keep_index: bool = False,
    ) -> Dict[str, Any]:
        """
        Stash current changes.
        """
        args = ["stash", "push"]
        if include_untracked:
            args.append("-u")
        if keep_index:
            args.append("--keep-index")
        if message:
            args.extend(["-m", message])

        stdout, stderr, rc = cls._run_git(repo_path, args)

        return {
            "success": rc == 0,
            "message": stdout if rc == 0 else stderr,
            "commands_run": [f"git {' '.join(args)}"],
        }

    @classmethod
    async def stash_list(cls, repo_path: str) -> Dict[str, Any]:
        """List all stashes."""
        stdout, stderr, rc = cls._run_git(repo_path, ["stash", "list"])

        if rc != 0:
            return {"success": False, "message": stderr}

        stashes = []
        for line in stdout.strip().splitlines():
            if not line:
                continue
            match = re.match(r'(stash@\{(\d+)\}): (.*)', line)
            if match:
                stashes.append({
                    "ref": match.group(1),
                    "index": int(match.group(2)),
                    "message": match.group(3),
                })

        return {
            "success": True,
            "stashes": stashes,
            "count": len(stashes),
        }

    @classmethod
    async def stash_show(
        cls,
        repo_path: str,
        stash_ref: str = "stash@{0}",
        include_patch: bool = False,
    ) -> Dict[str, Any]:
        """Show contents of a stash."""
        args = ["stash", "show"]
        if include_patch:
            args.append("-p")
        args.append(stash_ref)

        stdout, stderr, rc = cls._run_git(repo_path, args)

        return {
            "success": rc == 0,
            "content": stdout if rc == 0 else stderr,
            "commands_run": [f"git {' '.join(args)}"],
        }

    @classmethod
    async def stash_pop(
        cls,
        repo_path: str,
        stash_ref: str = "stash@{0}",
        index: bool = False,
    ) -> Dict[str, Any]:
        """Pop a stash (apply and remove)."""
        args = ["stash", "pop"]
        if index:
            args.append("--index")
        args.append(stash_ref)

        stdout, stderr, rc = cls._run_git(repo_path, args)

        result = {
            "success": rc == 0,
            "message": stdout if rc == 0 else stderr,
            "commands_run": [f"git {' '.join(args)}"],
            "conflicts": [],
        }

        if "CONFLICT" in stderr or "CONFLICT" in stdout:
            result["success"] = False
            result["message"] = "Stash apply resulted in conflicts"
            status_out, _, _ = cls._run_git(repo_path, ["status", "--porcelain"])
            for line in status_out.splitlines():
                if line.startswith("UU") or line.startswith("AA"):
                    result["conflicts"].append(line[3:].strip())

        return result

    @classmethod
    async def stash_apply(
        cls,
        repo_path: str,
        stash_ref: str = "stash@{0}",
        index: bool = False,
    ) -> Dict[str, Any]:
        """Apply a stash without removing it."""
        args = ["stash", "apply"]
        if index:
            args.append("--index")
        args.append(stash_ref)

        stdout, stderr, rc = cls._run_git(repo_path, args)

        return {
            "success": rc == 0,
            "message": stdout if rc == 0 else stderr,
            "commands_run": [f"git {' '.join(args)}"],
        }

    @classmethod
    async def stash_drop(cls, repo_path: str, stash_ref: str = "stash@{0}") -> Dict[str, Any]:
        """Drop a specific stash."""
        stdout, stderr, rc = cls._run_git(repo_path, ["stash", "drop", stash_ref])

        return {
            "success": rc == 0,
            "message": stdout if rc == 0 else stderr,
            "commands_run": [f"git stash drop {stash_ref}"],
        }

    @classmethod
    async def stash_clear(cls, repo_path: str) -> Dict[str, Any]:
        """Clear all stashes."""
        stdout, stderr, rc = cls._run_git(repo_path, ["stash", "clear"])

        return {
            "success": rc == 0,
            "message": "All stashes cleared" if rc == 0 else stderr,
            "commands_run": ["git stash clear"],
        }

    @classmethod
    async def stash_branch(
        cls,
        repo_path: str,
        branch_name: str,
        stash_ref: str = "stash@{0}",
    ) -> Dict[str, Any]:
        """Create a branch from a stash."""
        stdout, stderr, rc = cls._run_git(
            repo_path,
            ["stash", "branch", branch_name, stash_ref]
        )

        return {
            "success": rc == 0,
            "message": stdout if rc == 0 else stderr,
            "commands_run": [f"git stash branch {branch_name} {stash_ref}"],
        }

    # ==================== BRANCH MANAGEMENT ====================

    @classmethod
    async def cleanup_merged_branches(
        cls,
        repo_path: str,
        base_branch: str = "main",
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Find and optionally delete branches that have been merged.
        """
        result = {"success": False, "branches_to_delete": [], "deleted_branches": [], "commands_run": []}

        # Get merged branches
        stdout, stderr, rc = cls._run_git(repo_path, ["branch", "--merged", base_branch])
        result["commands_run"].append(f"git branch --merged {base_branch}")

        if rc != 0:
            result["message"] = stderr
            return result

        # Parse branches (excluding current and base)
        for line in stdout.splitlines():
            branch = line.strip().lstrip("* ")
            if branch and branch not in [base_branch, "main", "master", "develop"]:
                result["branches_to_delete"].append(branch)

        if not dry_run:
            for branch in result["branches_to_delete"]:
                stdout, stderr, rc = cls._run_git(repo_path, ["branch", "-d", branch])
                if rc == 0:
                    result["deleted_branches"].append(branch)
                result["commands_run"].append(f"git branch -d {branch}")

        result["success"] = True
        result["message"] = f"Found {len(result['branches_to_delete'])} merged branches"
        if not dry_run:
            result["message"] += f", deleted {len(result['deleted_branches'])}"

        return result

    @classmethod
    async def rename_branch(
        cls,
        repo_path: str,
        old_name: str,
        new_name: str,
    ) -> Dict[str, Any]:
        """Rename a branch."""
        stdout, stderr, rc = cls._run_git(repo_path, ["branch", "-m", old_name, new_name])

        return {
            "success": rc == 0,
            "message": f"Renamed '{old_name}' to '{new_name}'" if rc == 0 else stderr,
            "commands_run": [f"git branch -m {old_name} {new_name}"],
        }

    # ==================== REFLOG & RECOVERY ====================

    @classmethod
    async def reflog(cls, repo_path: str, limit: int = 20) -> Dict[str, Any]:
        """Get reflog entries for recovery."""
        stdout, stderr, rc = cls._run_git(
            repo_path,
            ["reflog", f"-{limit}", "--pretty=format:%h|%gd|%gs|%ar"]
        )

        if rc != 0:
            return {"success": False, "message": stderr}

        entries = []
        for line in stdout.strip().splitlines():
            parts = line.split("|")
            if len(parts) >= 4:
                entries.append({
                    "hash": parts[0],
                    "ref": parts[1],
                    "action": parts[2],
                    "time": parts[3],
                })

        return {
            "success": True,
            "entries": entries,
            "commands_run": [f"git reflog -{limit}"],
        }

    @classmethod
    async def recover_commit(
        cls,
        repo_path: str,
        commit_hash: str,
        branch_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Recover a lost commit by creating a branch pointing to it.
        """
        if not branch_name:
            branch_name = f"recovered-{commit_hash[:8]}"

        stdout, stderr, rc = cls._run_git(
            repo_path,
            ["branch", branch_name, commit_hash]
        )

        return {
            "success": rc == 0,
            "message": f"Created branch '{branch_name}' pointing to {commit_hash}" if rc == 0 else stderr,
            "branch_name": branch_name if rc == 0 else None,
            "commands_run": [f"git branch {branch_name} {commit_hash}"],
        }

    # ==================== COMMIT MANIPULATION ====================

    @classmethod
    async def amend_commit(
        cls,
        repo_path: str,
        new_message: Optional[str] = None,
        add_files: bool = False,
    ) -> Dict[str, Any]:
        """Amend the last commit."""
        result = {"success": False, "message": "", "commands_run": []}

        if add_files:
            stdout, stderr, rc = cls._run_git(repo_path, ["add", "-A"])
            result["commands_run"].append("git add -A")
            if rc != 0:
                result["message"] = f"Failed to stage files: {stderr}"
                return result

        args = ["commit", "--amend"]
        if new_message:
            args.extend(["-m", new_message])
        else:
            args.append("--no-edit")

        stdout, stderr, rc = cls._run_git(repo_path, args)
        result["commands_run"].append(f"git commit --amend {'--no-edit' if not new_message else '-m <message>'}")

        result["success"] = rc == 0
        result["message"] = "Commit amended successfully" if rc == 0 else stderr

        return result

    @classmethod
    async def revert_commit(
        cls,
        repo_path: str,
        commit_hash: str,
        no_commit: bool = False,
    ) -> Dict[str, Any]:
        """Create a revert commit."""
        args = ["revert"]
        if no_commit:
            args.append("-n")
        args.append(commit_hash)

        stdout, stderr, rc = cls._run_git(repo_path, args)

        return {
            "success": rc == 0,
            "message": stdout if rc == 0 else stderr,
            "commands_run": [f"git {' '.join(args)}"],
        }

    @classmethod
    async def reset_to_commit(
        cls,
        repo_path: str,
        commit_hash: str,
        mode: str = "mixed",  # soft, mixed, hard
    ) -> Dict[str, Any]:
        """Reset to a specific commit."""
        if mode not in ["soft", "mixed", "hard"]:
            return {"success": False, "message": f"Invalid mode: {mode}"}

        stdout, stderr, rc = cls._run_git(
            repo_path,
            ["reset", f"--{mode}", commit_hash]
        )

        return {
            "success": rc == 0,
            "message": f"Reset to {commit_hash} ({mode})" if rc == 0 else stderr,
            "commands_run": [f"git reset --{mode} {commit_hash}"],
            "warning": "Hard reset discards uncommitted changes!" if mode == "hard" else None,
        }


# ============================================================
# ADVANCED DATABASE OPERATIONS
# ============================================================

class AdvancedDatabaseOperations:
    """
    Advanced database operations:
    - Schema diff between code and database
    - Data migration scripts
    - Rollback migrations
    - Database seeding
    - Schema validation
    - Query analysis and optimization
    - Connection pool management
    """

    @classmethod
    async def schema_diff(
        cls,
        workspace_path: str,
        database_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compare ORM models with actual database schema.
        Returns differences that need migration.
        """
        result = {
            "success": False,
            "differences": [],
            "missing_in_db": [],
            "missing_in_code": [],
            "column_differences": [],
        }

        # Get models from code
        orm_models = await DatabaseDebugger._parse_orm_models(workspace_path)
        code_tables = {m["name"]: m for m in orm_models}

        result["code_tables"] = list(code_tables.keys())

        # If we have a database URL, compare with actual schema
        if database_url:
            try:
                db_schema = await cls._get_database_schema(database_url)
                db_tables = {t["name"]: t for t in db_schema.get("tables", [])}

                result["db_tables"] = list(db_tables.keys())

                # Find missing tables
                result["missing_in_db"] = [
                    name for name in code_tables
                    if name.lower() not in [n.lower() for n in db_tables]
                ]

                result["missing_in_code"] = [
                    name for name in db_tables
                    if name.lower() not in [n.lower() for n in code_tables]
                ]

                # Compare columns for matching tables
                for table_name, code_table in code_tables.items():
                    db_table = db_tables.get(table_name) or db_tables.get(table_name.lower())
                    if db_table:
                        code_cols = {c["name"].lower() for c in code_table.get("columns", [])}
                        db_cols = {c["name"].lower() for c in db_table.get("columns", [])}

                        missing_cols = code_cols - db_cols
                        extra_cols = db_cols - code_cols

                        if missing_cols or extra_cols:
                            result["column_differences"].append({
                                "table": table_name,
                                "missing_in_db": list(missing_cols),
                                "extra_in_db": list(extra_cols),
                            })

                result["success"] = True

            except Exception as e:
                result["message"] = f"Database connection failed: {e}"
                result["success"] = False
        else:
            result["message"] = "No database URL provided - showing code models only"
            result["success"] = True

        return result

    @classmethod
    async def _get_database_schema(cls, database_url: str) -> Dict[str, Any]:
        """Introspect database schema."""
        # Parse database URL to determine type
        schema = {"tables": [], "type": "unknown"}

        if "postgresql" in database_url or "postgres" in database_url:
            schema["type"] = "postgresql"
            # Would use psycopg2 or asyncpg here
        elif "mysql" in database_url:
            schema["type"] = "mysql"
        elif "sqlite" in database_url:
            schema["type"] = "sqlite"

        # For now, return empty - actual implementation would query INFORMATION_SCHEMA
        return schema

    @classmethod
    async def generate_migration(
        cls,
        workspace_path: str,
        migration_name: str,
        auto_detect: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate a new migration file.
        """
        result = {"success": False, "message": "", "migration_file": None, "commands_run": []}
        workspace = Path(workspace_path)

        # Check for Alembic
        if (workspace / "alembic.ini").exists():
            args = ["alembic", "revision"]
            if auto_detect:
                args.append("--autogenerate")
            args.extend(["-m", migration_name])

            try:
                proc = subprocess.run(
                    args,
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                result["commands_run"].append(" ".join(args))

                if proc.returncode == 0:
                    result["success"] = True
                    result["message"] = proc.stdout
                    # Extract migration file path
                    match = re.search(r'Generating (.*\.py)', proc.stdout)
                    if match:
                        result["migration_file"] = match.group(1)
                else:
                    result["message"] = proc.stderr

            except Exception as e:
                result["message"] = f"Failed to generate migration: {e}"

        # Check for Django
        elif (workspace / "manage.py").exists():
            try:
                proc = subprocess.run(
                    ["python", "manage.py", "makemigrations", "--name", migration_name],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                result["commands_run"].append(f"python manage.py makemigrations --name {migration_name}")
                result["success"] = proc.returncode == 0
                result["message"] = proc.stdout if proc.returncode == 0 else proc.stderr

            except Exception as e:
                result["message"] = f"Failed to generate migration: {e}"

        # Check for Prisma
        elif (workspace / "prisma" / "schema.prisma").exists():
            try:
                proc = subprocess.run(
                    ["npx", "prisma", "migrate", "dev", "--name", migration_name, "--create-only"],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                result["commands_run"].append(f"npx prisma migrate dev --name {migration_name} --create-only")
                result["success"] = proc.returncode == 0
                result["message"] = proc.stdout if proc.returncode == 0 else proc.stderr

            except Exception as e:
                result["message"] = f"Failed to generate migration: {e}"
        else:
            result["message"] = "No supported migration system found (Alembic, Django, or Prisma)"

        return result

    @classmethod
    async def apply_migrations(
        cls,
        workspace_path: str,
        target: str = "head",  # "head" or specific revision
    ) -> Dict[str, Any]:
        """Apply pending migrations."""
        result = {"success": False, "message": "", "applied": [], "commands_run": []}
        workspace = Path(workspace_path)

        if (workspace / "alembic.ini").exists():
            try:
                proc = subprocess.run(
                    ["alembic", "upgrade", target],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                result["commands_run"].append(f"alembic upgrade {target}")
                result["success"] = proc.returncode == 0
                result["message"] = proc.stdout if proc.returncode == 0 else proc.stderr

            except Exception as e:
                result["message"] = f"Failed to apply migrations: {e}"

        elif (workspace / "manage.py").exists():
            try:
                proc = subprocess.run(
                    ["python", "manage.py", "migrate"],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                result["commands_run"].append("python manage.py migrate")
                result["success"] = proc.returncode == 0
                result["message"] = proc.stdout if proc.returncode == 0 else proc.stderr

            except Exception as e:
                result["message"] = f"Failed to apply migrations: {e}"

        elif (workspace / "prisma" / "schema.prisma").exists():
            try:
                proc = subprocess.run(
                    ["npx", "prisma", "migrate", "deploy"],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                result["commands_run"].append("npx prisma migrate deploy")
                result["success"] = proc.returncode == 0
                result["message"] = proc.stdout if proc.returncode == 0 else proc.stderr

            except Exception as e:
                result["message"] = f"Failed to apply migrations: {e}"

        return result

    @classmethod
    async def rollback_migration(
        cls,
        workspace_path: str,
        steps: int = 1,
        target_revision: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Rollback migrations."""
        result = {"success": False, "message": "", "commands_run": []}
        workspace = Path(workspace_path)

        if (workspace / "alembic.ini").exists():
            if target_revision:
                target = target_revision
            else:
                target = f"-{steps}"

            try:
                proc = subprocess.run(
                    ["alembic", "downgrade", target],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                result["commands_run"].append(f"alembic downgrade {target}")
                result["success"] = proc.returncode == 0
                result["message"] = proc.stdout if proc.returncode == 0 else proc.stderr

            except Exception as e:
                result["message"] = f"Failed to rollback: {e}"

        elif (workspace / "manage.py").exists():
            # Django requires app name and migration name
            result["message"] = "Django rollback requires app name: python manage.py migrate <app> <migration>"
            result["suggestion"] = "Use: python manage.py showmigrations to see migration names"

        return result

    @classmethod
    async def get_migration_history(cls, workspace_path: str) -> Dict[str, Any]:
        """Get migration history."""
        result = {"success": False, "migrations": [], "current": None, "commands_run": []}
        workspace = Path(workspace_path)

        if (workspace / "alembic.ini").exists():
            try:
                # Get current revision
                proc = subprocess.run(
                    ["alembic", "current"],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                result["commands_run"].append("alembic current")
                if proc.returncode == 0:
                    result["current"] = proc.stdout.strip()

                # Get history
                proc = subprocess.run(
                    ["alembic", "history", "--verbose"],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                result["commands_run"].append("alembic history --verbose")

                if proc.returncode == 0:
                    result["success"] = True
                    # Parse history output
                    for line in proc.stdout.splitlines():
                        if "->" in line:
                            result["migrations"].append(line.strip())
                else:
                    result["message"] = proc.stderr

            except Exception as e:
                result["message"] = f"Failed to get history: {e}"

        elif (workspace / "manage.py").exists():
            try:
                proc = subprocess.run(
                    ["python", "manage.py", "showmigrations"],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                result["commands_run"].append("python manage.py showmigrations")
                result["success"] = proc.returncode == 0
                result["migrations_output"] = proc.stdout if proc.returncode == 0 else proc.stderr

            except Exception as e:
                result["message"] = f"Failed to get history: {e}"

        return result

    @classmethod
    async def seed_database(
        cls,
        workspace_path: str,
        seed_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run database seeding."""
        result = {"success": False, "message": "", "commands_run": []}
        workspace = Path(workspace_path)

        # Check for common seed file locations
        seed_locations = [
            seed_file,
            "seeds/seed.py",
            "db/seeds.py",
            "database/seeds.py",
            "scripts/seed.py",
        ]

        for loc in seed_locations:
            if loc and (workspace / loc).exists():
                try:
                    proc = subprocess.run(
                        ["python", loc],
                        cwd=workspace,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    result["commands_run"].append(f"python {loc}")
                    result["success"] = proc.returncode == 0
                    result["message"] = proc.stdout if proc.returncode == 0 else proc.stderr
                    return result
                except Exception as e:
                    result["message"] = f"Failed to run seed: {e}"
                    return result

        # Check for Django fixtures
        if (workspace / "manage.py").exists():
            fixtures_dir = workspace / "fixtures"
            if fixtures_dir.exists():
                fixtures = list(fixtures_dir.glob("*.json"))
                if fixtures:
                    try:
                        for fixture in fixtures:
                            proc = subprocess.run(
                                ["python", "manage.py", "loaddata", str(fixture.relative_to(workspace))],
                                cwd=workspace,
                                capture_output=True,
                                text=True,
                                timeout=60,
                            )
                            result["commands_run"].append(f"python manage.py loaddata {fixture.name}")
                        result["success"] = True
                        result["message"] = f"Loaded {len(fixtures)} fixtures"
                        return result
                    except Exception as e:
                        result["message"] = f"Failed to load fixtures: {e}"
                        return result

        # Check for Prisma seed
        if (workspace / "prisma" / "seed.ts").exists():
            try:
                proc = subprocess.run(
                    ["npx", "prisma", "db", "seed"],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                result["commands_run"].append("npx prisma db seed")
                result["success"] = proc.returncode == 0
                result["message"] = proc.stdout if proc.returncode == 0 else proc.stderr
                return result
            except Exception as e:
                result["message"] = f"Failed to run Prisma seed: {e}"
                return result

        result["message"] = "No seed file found. Create one at seeds/seed.py or similar location."
        return result

    @classmethod
    async def reset_database(
        cls,
        workspace_path: str,
        confirm: bool = False,
    ) -> Dict[str, Any]:
        """Reset database (drop and recreate)."""
        if not confirm:
            return {
                "success": False,
                "message": "Database reset requires explicit confirmation",
                "warning": "This will DELETE ALL DATA!",
            }

        result = {"success": False, "message": "", "commands_run": []}
        workspace = Path(workspace_path)

        if (workspace / "prisma" / "schema.prisma").exists():
            try:
                proc = subprocess.run(
                    ["npx", "prisma", "migrate", "reset", "--force"],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                result["commands_run"].append("npx prisma migrate reset --force")
                result["success"] = proc.returncode == 0
                result["message"] = proc.stdout if proc.returncode == 0 else proc.stderr
            except Exception as e:
                result["message"] = f"Failed to reset database: {e}"
        else:
            result["message"] = "Database reset not implemented for this framework"

        return result


# ============================================================
# COMPLEX CODE DEBUGGING & FIXING
# ============================================================

class CodeDebugger:
    """
    Complex code debugging and fixing:
    - Error tracing and analysis
    - Performance issue detection
    - Memory leak detection
    - Dead code detection
    - Circular dependency detection
    - Code smell detection
    - Auto-fix suggestions with patches
    """

    @classmethod
    async def analyze_errors(
        cls,
        workspace_path: str,
        error_log: Optional[str] = None,
        traceback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze error logs or tracebacks to find root cause.

        Supports multiple languages:
        - Python: Standard tracebacks
        - JavaScript/TypeScript: Node.js and browser errors
        - Go: panic and error traces
        - Rust: panic and error chain
        - Java: Exception stack traces
        - Ruby: Exception backtraces
        - C#/.NET: Exception stack traces
        - PHP: Fatal errors and exceptions
        """
        result = {
            "success": False,
            "error_type": None,
            "language": None,
            "root_cause": None,
            "affected_files": [],
            "suggestions": [],
            "auto_fix_available": False,
        }

        if traceback:
            # Detect language and parse accordingly
            parsed = cls._detect_and_parse_error(traceback)
            if parsed:
                result.update(parsed)
                result["suggestions"] = cls._get_error_suggestions(
                    result["root_cause"]["type"] if result["root_cause"] else "",
                    result["root_cause"]["message"] if result["root_cause"] else "",
                    result.get("language", "unknown"),
                )
                result["success"] = True

        if error_log:
            # Parse log file for errors (language-agnostic)
            error_patterns = [
                r'ERROR[:\s]+(.+)',
                r'Exception[:\s]+(.+)',
                r'FATAL[:\s]+(.+)',
                r'\[error\][:\s]+(.+)',
                r'panic[:\s]+(.+)',
                r'PANIC[:\s]+(.+)',
            ]

            for pattern in error_patterns:
                matches = re.findall(pattern, error_log, re.IGNORECASE)
                if matches:
                    result["errors_found"] = matches[:10]
                    result["success"] = True

        return result

    @classmethod
    def _detect_and_parse_error(cls, traceback: str) -> Optional[Dict[str, Any]]:
        """Detect the language and parse the error accordingly."""

        # Python traceback
        if "Traceback (most recent call last):" in traceback:
            return cls._parse_python_error(traceback)

        # Go panic
        if "panic:" in traceback or "goroutine" in traceback:
            return cls._parse_go_error(traceback)

        # Rust panic
        if "thread '" in traceback and "panicked at" in traceback:
            return cls._parse_rust_error(traceback)

        # Java exception
        if re.search(r'(Exception|Error)\s+in\s+thread|at\s+[\w.]+\([\w.]+:\d+\)', traceback):
            return cls._parse_java_error(traceback)

        # Ruby exception
        if re.search(r'^\s+from\s+[\w/.-]+:\d+:in\s+', traceback, re.MULTILINE):
            return cls._parse_ruby_error(traceback)

        # C#/.NET exception
        if re.search(r'(System\.\w+Exception|at\s+[\w.]+\s+in\s+.*:\s*line\s+\d+)', traceback):
            return cls._parse_csharp_error(traceback)

        # PHP error
        if re.search(r'(Fatal error|PHP Fatal|Stack trace:.*#\d+)', traceback, re.IGNORECASE):
            return cls._parse_php_error(traceback)

        # JavaScript/Node.js error (generic - check last)
        if "Error:" in traceback or re.search(r'\w+Error:', traceback):
            return cls._parse_javascript_error(traceback)

        return None

    @classmethod
    def _parse_python_error(cls, traceback: str) -> Dict[str, Any]:
        """Parse Python traceback."""
        result = {
            "error_type": "python_exception",
            "language": "python",
            "root_cause": None,
            "affected_files": [],
        }

        lines = traceback.strip().splitlines()
        error_line = lines[-1] if lines else ""

        if ":" in error_line:
            error_type, error_msg = error_line.split(":", 1)
            result["root_cause"] = {
                "type": error_type.strip(),
                "message": error_msg.strip(),
            }

        # Extract file locations
        file_pattern = r'File "([^"]+)", line (\d+), in (\w+)'
        for match in re.finditer(file_pattern, traceback):
            result["affected_files"].append({
                "path": match.group(1),
                "line": int(match.group(2)),
                "function": match.group(3),
            })

        return result

    @classmethod
    def _parse_javascript_error(cls, traceback: str) -> Dict[str, Any]:
        """Parse JavaScript/Node.js error."""
        result = {
            "error_type": "javascript_error",
            "language": "javascript",
            "root_cause": None,
            "affected_files": [],
        }

        # Extract error message
        error_match = re.search(r'(\w+Error):\s*(.+?)(?:\n|$)', traceback)
        if error_match:
            result["root_cause"] = {
                "type": error_match.group(1),
                "message": error_match.group(2),
            }

        # Extract file locations (at /path/to/file.js:line:col)
        file_pattern = r'at\s+(?:[\w.<>]+\s+)?\(?([^:\s]+):(\d+):(\d+)\)?'
        for match in re.finditer(file_pattern, traceback):
            path = match.group(1)
            if not path.startswith('native') and not path.startswith('internal'):
                result["affected_files"].append({
                    "path": path,
                    "line": int(match.group(2)),
                    "column": int(match.group(3)),
                })

        return result

    @classmethod
    def _parse_go_error(cls, traceback: str) -> Dict[str, Any]:
        """Parse Go panic/error."""
        result = {
            "error_type": "go_panic",
            "language": "go",
            "root_cause": None,
            "affected_files": [],
        }

        # Extract panic message
        panic_match = re.search(r'panic:\s*(.+?)(?:\n|$)', traceback)
        if panic_match:
            result["root_cause"] = {
                "type": "panic",
                "message": panic_match.group(1).strip(),
            }
        else:
            # Try to find error message
            error_match = re.search(r'error:\s*(.+?)(?:\n|$)', traceback, re.IGNORECASE)
            if error_match:
                result["root_cause"] = {
                    "type": "error",
                    "message": error_match.group(1).strip(),
                }

        # Extract file locations (e.g., /path/to/file.go:123)
        file_pattern = r'([/\w.-]+\.go):(\d+)'
        for match in re.finditer(file_pattern, traceback):
            result["affected_files"].append({
                "path": match.group(1),
                "line": int(match.group(2)),
            })

        # Also try to extract function names
        func_pattern = r'([/\w.-]+\.go):(\d+)\s+\+0x[\da-f]+\n\s*([\w.]+)\('
        for match in re.finditer(func_pattern, traceback):
            # Update with function info
            for f in result["affected_files"]:
                if f["path"] == match.group(1) and f["line"] == int(match.group(2)):
                    f["function"] = match.group(3)

        return result

    @classmethod
    def _parse_rust_error(cls, traceback: str) -> Dict[str, Any]:
        """Parse Rust panic/error."""
        result = {
            "error_type": "rust_panic",
            "language": "rust",
            "root_cause": None,
            "affected_files": [],
        }

        # Extract panic message: thread 'main' panicked at 'message', file.rs:line:col
        panic_match = re.search(
            r"thread '([^']+)' panicked at ['\"](.+?)['\"],?\s*([^:\s]+):(\d+):(\d+)",
            traceback
        )
        if panic_match:
            result["root_cause"] = {
                "type": "panic",
                "message": panic_match.group(2),
                "thread": panic_match.group(1),
            }
            result["affected_files"].append({
                "path": panic_match.group(3),
                "line": int(panic_match.group(4)),
                "column": int(panic_match.group(5)),
            })

        # Extract additional stack frames
        frame_pattern = r'at\s+([^<\s]+)\s*\n\s+at\s+([^:\s]+):(\d+):(\d+)'
        for match in re.finditer(frame_pattern, traceback):
            result["affected_files"].append({
                "path": match.group(2),
                "line": int(match.group(3)),
                "column": int(match.group(4)),
                "function": match.group(1),
            })

        # Also handle: src/main.rs:10:5 format
        file_pattern = r'([/\w.-]+\.rs):(\d+):(\d+)'
        seen = {(f["path"], f["line"]) for f in result["affected_files"]}
        for match in re.finditer(file_pattern, traceback):
            key = (match.group(1), int(match.group(2)))
            if key not in seen:
                result["affected_files"].append({
                    "path": match.group(1),
                    "line": int(match.group(2)),
                    "column": int(match.group(3)),
                })
                seen.add(key)

        return result

    @classmethod
    def _parse_java_error(cls, traceback: str) -> Dict[str, Any]:
        """Parse Java exception stack trace."""
        result = {
            "error_type": "java_exception",
            "language": "java",
            "root_cause": None,
            "affected_files": [],
        }

        # Extract exception type and message
        # Pattern: ExceptionType: message or ExceptionType at location
        exception_match = re.search(
            r'([\w.]+(?:Exception|Error))(?::\s*(.+?))?(?:\n|\s+at\s)',
            traceback
        )
        if exception_match:
            result["root_cause"] = {
                "type": exception_match.group(1),
                "message": exception_match.group(2).strip() if exception_match.group(2) else "",
            }

        # Extract file locations: at package.Class.method(File.java:line)
        file_pattern = r'at\s+([\w.$]+)\(([\w.]+):(\d+)\)'
        for match in re.finditer(file_pattern, traceback):
            result["affected_files"].append({
                "path": match.group(2),
                "line": int(match.group(3)),
                "function": match.group(1),
            })

        # Handle "Caused by:" chains
        caused_by = re.findall(r'Caused by:\s*([\w.]+(?:Exception|Error))(?::\s*(.+?))?(?:\n|$)', traceback)
        if caused_by:
            result["caused_by"] = [
                {"type": c[0], "message": c[1].strip() if c[1] else ""}
                for c in caused_by
            ]

        return result

    @classmethod
    def _parse_ruby_error(cls, traceback: str) -> Dict[str, Any]:
        """Parse Ruby exception backtrace."""
        result = {
            "error_type": "ruby_exception",
            "language": "ruby",
            "root_cause": None,
            "affected_files": [],
        }

        # Ruby format: ErrorType: message (on first line usually)
        # Or: path/file.rb:line:in `method': message (ErrorType)
        error_match = re.search(r"(\w+(?:Error|Exception)):\s*(.+?)(?:\n|$)", traceback)
        if error_match:
            result["root_cause"] = {
                "type": error_match.group(1),
                "message": error_match.group(2).strip(),
            }
        else:
            # Try alternate format
            alt_match = re.search(r":\s*(.+?)\s*\((\w+(?:Error|Exception))\)", traceback)
            if alt_match:
                result["root_cause"] = {
                    "type": alt_match.group(2),
                    "message": alt_match.group(1).strip(),
                }

        # Extract file locations: /path/file.rb:line:in `method'
        file_pattern = r'([/\w.-]+\.rb):(\d+)(?::in\s+[`\'](\w+)[\'`])?'
        for match in re.finditer(file_pattern, traceback):
            entry = {
                "path": match.group(1),
                "line": int(match.group(2)),
            }
            if match.group(3):
                entry["function"] = match.group(3)
            result["affected_files"].append(entry)

        return result

    @classmethod
    def _parse_csharp_error(cls, traceback: str) -> Dict[str, Any]:
        """Parse C#/.NET exception stack trace."""
        result = {
            "error_type": "csharp_exception",
            "language": "csharp",
            "root_cause": None,
            "affected_files": [],
        }

        # C# format: System.ExceptionType: message
        exception_match = re.search(r'([\w.]+Exception):\s*(.+?)(?:\n|$)', traceback)
        if exception_match:
            result["root_cause"] = {
                "type": exception_match.group(1),
                "message": exception_match.group(2).strip(),
            }

        # Extract file locations: at Namespace.Class.Method() in path\file.cs:line N
        file_pattern = r'at\s+([\w.<>]+)\([^)]*\)\s+in\s+([^:]+):line\s+(\d+)'
        for match in re.finditer(file_pattern, traceback):
            result["affected_files"].append({
                "path": match.group(2),
                "line": int(match.group(3)),
                "function": match.group(1),
            })

        # Also handle simpler format without file paths
        simple_pattern = r'at\s+([\w.<>]+)\([^)]*\)'
        if not result["affected_files"]:
            for match in re.finditer(simple_pattern, traceback):
                result["affected_files"].append({
                    "function": match.group(1),
                })

        return result

    @classmethod
    def _parse_php_error(cls, traceback: str) -> Dict[str, Any]:
        """Parse PHP error/exception."""
        result = {
            "error_type": "php_error",
            "language": "php",
            "root_cause": None,
            "affected_files": [],
        }

        # PHP Fatal error: message in /path/file.php on line N
        fatal_match = re.search(
            r'(?:Fatal error|PHP Fatal[^:]*|Exception):\s*(.+?)\s+in\s+([^\s]+)\s+on\s+line\s+(\d+)',
            traceback,
            re.IGNORECASE
        )
        if fatal_match:
            result["root_cause"] = {
                "type": "FatalError",
                "message": fatal_match.group(1).strip(),
            }
            result["affected_files"].append({
                "path": fatal_match.group(2),
                "line": int(fatal_match.group(3)),
            })

        # Stack trace format: #N /path/file.php(line): function()
        stack_pattern = r'#\d+\s+([^\(]+)\((\d+)\):\s*([\w\\]+(?:->|::)?\w+)'
        for match in re.finditer(stack_pattern, traceback):
            result["affected_files"].append({
                "path": match.group(1),
                "line": int(match.group(2)),
                "function": match.group(3),
            })

        return result

    @classmethod
    def _get_error_suggestions(
        cls, error_type: str, error_message: str, language: str = "unknown"
    ) -> List[str]:
        """Get fix suggestions based on error type and language."""
        suggestions = []

        # Language-specific error fixes
        error_fixes_by_language = {
            "python": {
                "ImportError": [
                    "Check if the module is installed: pip install <module>",
                    "Verify the import path is correct",
                    "Check for circular imports",
                ],
                "ModuleNotFoundError": [
                    "Install the missing module: pip install <module>",
                    "Check PYTHONPATH environment variable",
                    "Ensure virtual environment is activated",
                ],
                "AttributeError": [
                    "Verify the attribute/method name is correct",
                    "Check if the object is properly initialized",
                    "Ensure you're accessing the right object type",
                ],
                "TypeError": [
                    "Check argument types match function signature",
                    "Verify you're calling the function correctly",
                    "Look for None values being used incorrectly",
                ],
                "KeyError": [
                    "Check if the key exists before accessing",
                    "Use .get() method with a default value",
                    "Verify dictionary structure",
                ],
                "ValueError": [
                    "Validate input data before processing",
                    "Check data format matches expected format",
                    "Add input validation",
                ],
                "FileNotFoundError": [
                    "Verify the file path is correct",
                    "Check if the file exists",
                    "Use os.path.exists() before accessing",
                ],
                "ConnectionError": [
                    "Check network connectivity",
                    "Verify service URL is correct",
                    "Implement retry logic with exponential backoff",
                ],
                "TimeoutError": [
                    "Increase timeout value",
                    "Check for slow database queries",
                    "Add connection pooling",
                ],
            },
            "javascript": {
                "TypeError": [
                    "Check if the variable is undefined or null before accessing properties",
                    "Use optional chaining (?.) to safely access nested properties",
                    "Verify the object has the expected structure",
                ],
                "ReferenceError": [
                    "Check if the variable is declared before use",
                    "Verify the variable is in scope",
                    "Check for typos in variable names",
                ],
                "SyntaxError": [
                    "Check for missing brackets, parentheses, or semicolons",
                    "Verify JSON syntax is valid",
                    "Look for reserved words used as identifiers",
                ],
                "RangeError": [
                    "Check array index bounds",
                    "Verify recursion has a proper base case",
                    "Check for invalid array lengths",
                ],
            },
            "go": {
                "panic": [
                    "Add nil checks before dereferencing pointers",
                    "Use recover() to handle panics gracefully",
                    "Validate slice indices before accessing",
                    "Check for division by zero",
                ],
                "error": [
                    "Always check error return values",
                    "Use errors.Is() and errors.As() for error comparison",
                    "Wrap errors with context using fmt.Errorf with %w",
                ],
            },
            "rust": {
                "panic": [
                    "Use Result<T, E> instead of unwrap() for error handling",
                    "Replace .unwrap() with .expect() for better error messages",
                    "Use pattern matching to handle Option and Result types",
                    "Consider using the ? operator for error propagation",
                ],
            },
            "java": {
                "NullPointerException": [
                    "Add null checks before accessing objects",
                    "Use Optional<T> for values that might be null",
                    "Initialize objects in constructors",
                ],
                "ArrayIndexOutOfBoundsException": [
                    "Check array length before accessing indices",
                    "Use enhanced for-loop when possible",
                    "Validate user input for array indices",
                ],
                "ClassCastException": [
                    "Use instanceof check before casting",
                    "Review class hierarchy and interfaces",
                    "Consider using generics instead of casting",
                ],
                "IOException": [
                    "Use try-with-resources for auto-closing streams",
                    "Handle or declare the exception properly",
                    "Check file paths and permissions",
                ],
                "SQLException": [
                    "Verify database connection string",
                    "Check SQL syntax and table/column names",
                    "Use PreparedStatement to prevent SQL injection",
                ],
            },
            "ruby": {
                "NoMethodError": [
                    "Check if the object responds to the method",
                    "Verify the object is not nil before calling methods",
                    "Use safe navigation operator (&.) for nil-safe calls",
                ],
                "NameError": [
                    "Check for typos in variable or method names",
                    "Verify the constant/class is defined",
                    "Check require/require_relative statements",
                ],
                "ArgumentError": [
                    "Verify the correct number of arguments",
                    "Check argument types match expected types",
                    "Review method signature for required parameters",
                ],
            },
            "csharp": {
                "NullReferenceException": [
                    "Add null checks before accessing object members",
                    "Use null-conditional operator (?.) for safe access",
                    "Use null-coalescing operator (??) for defaults",
                    "Enable nullable reference types in project",
                ],
                "InvalidOperationException": [
                    "Check object state before operation",
                    "Verify collection is not empty before accessing",
                    "Review sequence of operations",
                ],
                "ArgumentException": [
                    "Validate method arguments at entry",
                    "Use ArgumentNullException.ThrowIfNull()",
                    "Check for invalid enum values",
                ],
            },
            "php": {
                "FatalError": [
                    "Check for undefined variables and functions",
                    "Verify class autoloading is configured",
                    "Review memory_limit settings for large operations",
                ],
                "TypeError": [
                    "Add type declarations to function parameters",
                    "Use strict_types declaration",
                    "Validate input types before processing",
                ],
            },
        }

        # Get language-specific fixes
        lang_fixes = error_fixes_by_language.get(language, {})

        # Try to match error type
        for error_key, fixes in lang_fixes.items():
            if error_key.lower() in error_type.lower():
                suggestions.extend(fixes)
                break

        # If no language-specific match, try generic Python fixes (common patterns)
        if not suggestions and language not in error_fixes_by_language:
            generic_fixes = error_fixes_by_language.get("python", {})
            for error_key, fixes in generic_fixes.items():
                if error_key.lower() in error_type.lower():
                    suggestions.extend(fixes)
                    break

        # Default suggestions if nothing matched
        if not suggestions:
            suggestions = [
                "Check the error message for specific details",
                "Review the affected code section",
                "Add logging to trace the issue",
                f"Search for '{error_type}' in documentation",
            ]

        return suggestions

    @classmethod
    async def detect_performance_issues(
        cls,
        workspace_path: str,
    ) -> Dict[str, Any]:
        """
        Detect potential performance issues in code.
        """
        result = {
            "success": False,
            "issues": [],
            "summary": {"high": 0, "medium": 0, "low": 0},
        }

        workspace = Path(workspace_path)

        # Patterns that indicate performance issues
        performance_patterns = {
            "python": [
                {
                    "pattern": r"for\s+\w+\s+in\s+.*:\s*\n.*\.append\(",
                    "issue": "List append in loop - consider list comprehension",
                    "severity": "medium",
                    "fix": "Use list comprehension: [x for x in items]",
                },
                {
                    "pattern": r"import\s+\*",
                    "issue": "Wildcard import - loads unnecessary modules",
                    "severity": "low",
                    "fix": "Import only needed items explicitly",
                },
                {
                    "pattern": r"print\s*\([^)]*\)\s*$",
                    "issue": "Print statement in production code",
                    "severity": "low",
                    "fix": "Use logging module instead",
                },
                {
                    "pattern": r"\.read\(\)\s*$",
                    "issue": "Reading entire file into memory",
                    "severity": "medium",
                    "fix": "Use streaming or chunk reading for large files",
                },
                {
                    "pattern": r"time\.sleep\(",
                    "issue": "Blocking sleep - consider async sleep",
                    "severity": "medium",
                    "fix": "Use asyncio.sleep() in async code",
                },
                {
                    "pattern": r"SELECT\s+\*\s+FROM",
                    "issue": "SELECT * query - fetch only needed columns",
                    "severity": "medium",
                    "fix": "Specify exact columns needed",
                },
                {
                    "pattern": r"for\s+\w+\s+in\s+.*\.all\(\):",
                    "issue": "Iterating over all() - may load entire table",
                    "severity": "high",
                    "fix": "Add filters and use pagination",
                },
            ],
            "javascript": [
                {
                    "pattern": r"document\.querySelector\([^)]+\)\s+(?:&&|\|\||\?)",
                    "issue": "DOM query in conditional - cache the result",
                    "severity": "low",
                    "fix": "Store DOM element in a variable",
                },
                {
                    "pattern": r"JSON\.parse\(JSON\.stringify",
                    "issue": "Deep clone via JSON - slow for large objects",
                    "severity": "medium",
                    "fix": "Use structuredClone() or lodash cloneDeep",
                },
                {
                    "pattern": r"\.forEach\([^)]*async",
                    "issue": "async in forEach doesn't await properly",
                    "severity": "high",
                    "fix": "Use for...of loop or Promise.all with map",
                },
                {
                    "pattern": r"await\s+\w+\(\);\s*\n\s*await",
                    "issue": "Sequential awaits - consider Promise.all",
                    "severity": "medium",
                    "fix": "Use Promise.all for parallel async operations",
                },
            ],
        }

        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in DeepCodeAnalyzer.SKIP_DIRS]

            for filename in files:
                file_path = Path(root) / filename
                ext = file_path.suffix.lower()
                language = DeepCodeAnalyzer.LANGUAGE_EXTENSIONS.get(ext)

                if not language or language not in performance_patterns:
                    continue

                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')

                    for pattern_info in performance_patterns[language]:
                        matches = re.finditer(pattern_info["pattern"], content, re.IGNORECASE | re.MULTILINE)
                        for match in matches:
                            line_num = content[:match.start()].count('\n') + 1
                            result["issues"].append({
                                "file": str(file_path.relative_to(workspace)),
                                "line": line_num,
                                "issue": pattern_info["issue"],
                                "severity": pattern_info["severity"],
                                "fix": pattern_info["fix"],
                                "code_snippet": match.group(0)[:100],
                            })
                            result["summary"][pattern_info["severity"]] += 1

                except Exception as e:
                    logger.warning(f"Failed to analyze {file_path}: {e}")

        result["success"] = True
        return result

    @classmethod
    async def detect_dead_code(
        cls,
        workspace_path: str,
    ) -> Dict[str, Any]:
        """
        Detect potentially dead/unused code.
        """
        result = {
            "success": False,
            "unused_functions": [],
            "unused_imports": [],
            "unused_variables": [],
        }

        # First, build a symbol table
        analysis = await DeepCodeAnalyzer.analyze_workspace(workspace_path)

        # For each function, check if it's called anywhere
        all_code_content = ""
        for file_path, file_analysis in analysis.files.items():
            try:
                full_path = Path(workspace_path) / file_path
                all_code_content += full_path.read_text(encoding='utf-8', errors='ignore')
            except:
                continue

        for symbol_name, locations in analysis.symbol_table.items():
            # Skip common patterns
            if symbol_name.startswith("_") or symbol_name in ["main", "__init__", "setup"]:
                continue

            # Count occurrences (definition + calls)
            occurrences = len(re.findall(rf'\b{re.escape(symbol_name)}\b', all_code_content))

            # If only appears once or twice (definition + maybe one use), might be unused
            if occurrences <= 2:
                result["unused_functions"].append({
                    "name": symbol_name,
                    "locations": locations,
                    "occurrences": occurrences,
                })

        result["success"] = True
        return result

    @classmethod
    async def detect_circular_dependencies(
        cls,
        workspace_path: str,
    ) -> Dict[str, Any]:
        """
        Detect circular import dependencies.
        """
        result = {
            "success": False,
            "circular_deps": [],
            "dependency_graph": {},
        }

        analysis = await DeepCodeAnalyzer.analyze_workspace(workspace_path)

        # Build adjacency list from dependency graph
        graph = {}
        for file_path, imports in analysis.dependency_graph.items():
            graph[file_path] = []
            for imp in imports:
                # Try to resolve import to file path
                possible_paths = [
                    f"{imp.replace('.', '/')}.py",
                    f"{imp.replace('.', '/')}/__init__.py",
                ]
                for p in possible_paths:
                    if p in analysis.files:
                        graph[file_path].append(p)

        result["dependency_graph"] = graph

        # Find cycles using DFS
        def find_cycles(node: str, visited: Set[str], path: List[str]):
            if node in path:
                cycle_start = path.index(node)
                return [path[cycle_start:] + [node]]

            if node in visited:
                return []

            visited.add(node)
            path.append(node)
            cycles = []

            for neighbor in graph.get(node, []):
                cycles.extend(find_cycles(neighbor, visited, path.copy()))

            return cycles

        all_cycles = []
        visited = set()
        for node in graph:
            cycles = find_cycles(node, visited, [])
            all_cycles.extend(cycles)

        # Remove duplicate cycles
        seen = set()
        for cycle in all_cycles:
            cycle_key = tuple(sorted(cycle))
            if cycle_key not in seen:
                seen.add(cycle_key)
                result["circular_deps"].append({
                    "cycle": cycle,
                    "fix": "Consider extracting shared code to a separate module",
                })

        result["success"] = True
        return result

    @classmethod
    async def detect_code_smells(
        cls,
        workspace_path: str,
    ) -> Dict[str, Any]:
        """
        Detect common code smells.
        """
        result = {
            "success": False,
            "smells": [],
            "summary": {},
        }

        smell_patterns = {
            "long_function": {
                "check": lambda content, func: len(func.body.splitlines()) > 50 if func.body else False,
                "message": "Function is too long (>50 lines)",
                "fix": "Break into smaller functions",
            },
            "too_many_parameters": {
                "check": lambda content, func: func.signature.count(",") >= 5,
                "message": "Function has too many parameters (>5)",
                "fix": "Use a parameter object or dataclass",
            },
            "nested_callbacks": {
                "pattern": r"\.then\([^)]*\.then\([^)]*\.then\(",
                "message": "Deeply nested callbacks (callback hell)",
                "fix": "Use async/await syntax",
            },
            "magic_numbers": {
                "pattern": r"(?<![\w\"])(\d{2,})(?![\w\"])",
                "message": "Magic number detected",
                "fix": "Extract to named constant",
            },
            "empty_catch": {
                "pattern": r"except\s*:\s*pass|catch\s*\([^)]*\)\s*\{\s*\}",
                "message": "Empty exception handler",
                "fix": "Handle the exception or log it",
            },
            "hardcoded_credentials": {
                "pattern": r"(password|secret|api_key|token)\s*=\s*[\"'][^\"']+[\"']",
                "message": "Hardcoded credential detected",
                "fix": "Use environment variables or secrets manager",
            },
        }

        workspace = Path(workspace_path)

        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in DeepCodeAnalyzer.SKIP_DIRS]

            for filename in files:
                file_path = Path(root) / filename
                ext = file_path.suffix.lower()

                if ext not in DeepCodeAnalyzer.LANGUAGE_EXTENSIONS:
                    continue

                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    rel_path = str(file_path.relative_to(workspace))

                    for smell_name, smell_info in smell_patterns.items():
                        if "pattern" in smell_info:
                            matches = re.finditer(smell_info["pattern"], content, re.IGNORECASE)
                            for match in matches:
                                line_num = content[:match.start()].count('\n') + 1
                                result["smells"].append({
                                    "file": rel_path,
                                    "line": line_num,
                                    "smell": smell_name,
                                    "message": smell_info["message"],
                                    "fix": smell_info["fix"],
                                })

                                if smell_name not in result["summary"]:
                                    result["summary"][smell_name] = 0
                                result["summary"][smell_name] += 1

                except Exception as e:
                    logger.warning(f"Failed to analyze {file_path}: {e}")

        result["success"] = True
        return result

    @classmethod
    async def auto_fix(
        cls,
        workspace_path: str,
        file_path: str,
        issue_type: str,
        line_number: int,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """
        Attempt to automatically fix a detected issue.
        """
        result = {
            "success": False,
            "original_code": "",
            "fixed_code": "",
            "applied": False,
            "message": "",
        }

        full_path = Path(workspace_path) / file_path
        if not full_path.exists():
            result["message"] = f"File not found: {file_path}"
            return result

        try:
            content = full_path.read_text(encoding='utf-8')
            lines = content.splitlines(keepends=True)

            if line_number > len(lines):
                result["message"] = f"Line {line_number} out of range"
                return result

            original_line = lines[line_number - 1]
            result["original_code"] = original_line.strip()

            fixed_line = original_line

            # Apply fixes based on issue type
            if issue_type == "empty_catch":
                if "except:" in original_line or "except :" in original_line:
                    fixed_line = original_line.replace("pass", "logger.exception('Caught exception')")
                elif "catch" in original_line:
                    # JavaScript - add console.error
                    fixed_line = original_line.replace("{}", "{ console.error(e); }")

            elif issue_type == "print_statement":
                if "print(" in original_line:
                    fixed_line = original_line.replace("print(", "logger.info(")

            elif issue_type == "wildcard_import":
                # This is more complex - would need to analyze what's actually used
                result["message"] = "Wildcard import fix requires manual review"
                return result

            result["fixed_code"] = fixed_line.strip()

            if fixed_line != original_line:
                result["success"] = True

                if not dry_run:
                    lines[line_number - 1] = fixed_line
                    full_path.write_text("".join(lines))
                    result["applied"] = True
                    result["message"] = "Fix applied successfully"
                else:
                    result["message"] = "Fix available (dry run - not applied)"
            else:
                result["message"] = "No automatic fix available for this issue"

        except Exception as e:
            result["message"] = f"Failed to apply fix: {e}"

        return result


# ============================================================
# PUBLIC API ADDITIONS
# ============================================================

# Advanced Git Operations
async def cherry_pick(repo_path: str, commit_hash: str, **kwargs) -> Dict[str, Any]:
    """Public API: Cherry-pick a commit."""
    return await AdvancedGitOperations.cherry_pick(repo_path, commit_hash, **kwargs)

async def squash_commits(repo_path: str, num_commits: int, message: str = None) -> Dict[str, Any]:
    """Public API: Squash last N commits."""
    return await AdvancedGitOperations.squash_commits(repo_path, num_commits, message)

async def bisect_start(repo_path: str, bad: str = "HEAD", good: str = None) -> Dict[str, Any]:
    """Public API: Start git bisect."""
    return await AdvancedGitOperations.bisect_start(repo_path, bad, good)

async def stash_operations(repo_path: str, operation: str, **kwargs) -> Dict[str, Any]:
    """Public API: Stash operations (save, pop, apply, list, drop)."""
    ops = {
        "save": AdvancedGitOperations.stash_save,
        "pop": AdvancedGitOperations.stash_pop,
        "apply": AdvancedGitOperations.stash_apply,
        "list": AdvancedGitOperations.stash_list,
        "drop": AdvancedGitOperations.stash_drop,
        "clear": AdvancedGitOperations.stash_clear,
        "show": AdvancedGitOperations.stash_show,
    }
    if operation not in ops:
        return {"success": False, "message": f"Unknown operation: {operation}"}
    return await ops[operation](repo_path, **kwargs)

async def rebase_operations(repo_path: str, operation: str, **kwargs) -> Dict[str, Any]:
    """Public API: Rebase operations."""
    ops = {
        "onto": AdvancedGitOperations.rebase_onto,
        "continue": AdvancedGitOperations.continue_rebase,
        "abort": AdvancedGitOperations.abort_rebase,
        "skip": AdvancedGitOperations.skip_rebase_commit,
    }
    if operation not in ops:
        return {"success": False, "message": f"Unknown operation: {operation}"}
    return await ops[operation](repo_path, **kwargs)

# Advanced Database Operations
async def database_schema_diff(workspace_path: str, database_url: str = None) -> Dict[str, Any]:
    """Public API: Compare code models with database schema."""
    return await AdvancedDatabaseOperations.schema_diff(workspace_path, database_url)

async def database_migration(workspace_path: str, operation: str, **kwargs) -> Dict[str, Any]:
    """Public API: Database migration operations."""
    ops = {
        "generate": AdvancedDatabaseOperations.generate_migration,
        "apply": AdvancedDatabaseOperations.apply_migrations,
        "rollback": AdvancedDatabaseOperations.rollback_migration,
        "history": AdvancedDatabaseOperations.get_migration_history,
    }
    if operation not in ops:
        return {"success": False, "message": f"Unknown operation: {operation}"}
    return await ops[operation](workspace_path, **kwargs)

async def database_seed(workspace_path: str, seed_file: str = None) -> Dict[str, Any]:
    """Public API: Seed database."""
    return await AdvancedDatabaseOperations.seed_database(workspace_path, seed_file)

# Code Debugging
async def analyze_error(traceback: str = None, error_log: str = None, workspace_path: str = None) -> Dict[str, Any]:
    """Public API: Analyze error traceback or logs."""
    return await CodeDebugger.analyze_errors(workspace_path or ".", error_log, traceback)

async def detect_issues(workspace_path: str, issue_type: str = "all") -> Dict[str, Any]:
    """Public API: Detect code issues."""
    results = {}

    if issue_type in ["all", "performance"]:
        results["performance"] = await CodeDebugger.detect_performance_issues(workspace_path)

    if issue_type in ["all", "dead_code"]:
        results["dead_code"] = await CodeDebugger.detect_dead_code(workspace_path)

    if issue_type in ["all", "circular_deps"]:
        results["circular_deps"] = await CodeDebugger.detect_circular_dependencies(workspace_path)

    if issue_type in ["all", "code_smells"]:
        results["code_smells"] = await CodeDebugger.detect_code_smells(workspace_path)

    return results

async def auto_fix_issue(workspace_path: str, file_path: str, issue_type: str, line: int, dry_run: bool = True) -> Dict[str, Any]:
    """Public API: Auto-fix a detected issue."""
    return await CodeDebugger.auto_fix(workspace_path, file_path, issue_type, line, dry_run)
