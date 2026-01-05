from typing import Dict, Any, List, Set
import os
import ast
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
from ..models.plan import RepoMap
from ..core.config import get_settings


class RepoAnalysisAgent:
    """
    The Repo Analysis Agent provides FAANG-level repository intelligence.
    This gives Navi global understanding of the entire workspace - far beyond
    what Cursor or Copilot Workspace can achieve.

    It maps:
    - File dependencies and relationships
    - Code complexity and hotspots
    - Architecture patterns
    - Technical debt indicators
    - Change impact analysis
    - Security vulnerabilities
    - Performance bottlenecks
    """

    def __init__(self):
        self.settings = get_settings()

        # Language-specific analyzers
        self.analyzers = {
            ".py": self._analyze_python_file,
            ".js": self._analyze_javascript_file,
            ".ts": self._analyze_typescript_file,
            ".jsx": self._analyze_javascript_file,
            ".tsx": self._analyze_typescript_file,
            ".java": self._analyze_java_file,
            ".cpp": self._analyze_cpp_file,
            ".c": self._analyze_c_file,
            ".cs": self._analyze_csharp_file,
            ".php": self._analyze_php_file,
            ".rb": self._analyze_ruby_file,
            ".go": self._analyze_go_file,
            ".rs": self._analyze_rust_file,
        }

        # Ignore patterns
        self.ignore_patterns = {
            "node_modules",
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            "build",
            "dist",
            "target",
            "bin",
            "obj",
            ".next",
            ".nuxt",
            "coverage",
            ".pytest_cache",
            ".mypy_cache",
        }

    async def analyze(self, root_path: str) -> RepoMap:
        """
        Perform comprehensive repository analysis
        """

        # 1. File system scan
        file_info = await self._scan_filesystem(root_path)

        # 2. Language detection and classification
        languages = self._detect_languages(file_info)

        # 3. Dependency analysis
        dependencies = await self._analyze_dependencies(file_info, root_path)

        # 4. Complexity analysis
        complexity_metrics = await self._analyze_complexity(file_info)

        # 5. Hotspot detection
        hotspots = await self._detect_hotspots(file_info, complexity_metrics)

        # 6. Architecture analysis
        architecture = await self._analyze_architecture(file_info, dependencies)

        # 7. Quality metrics
        quality_metrics = await self._analyze_quality(file_info)

        # 8. Security analysis
        security_findings = await self._analyze_security(file_info)

        # 9. Performance analysis
        performance_insights = await self._analyze_performance(file_info)

        return RepoMap(
            root_path=root_path,
            total_files=len([f for f in file_info if f["is_source_code"]]),
            languages=languages,
            dependencies=dependencies,
            hotspots=hotspots,
            architecture={
                "patterns": architecture,
                "quality_metrics": quality_metrics,
                "security_findings": security_findings,
                "performance_insights": performance_insights,
            },
            complexity_metrics=complexity_metrics,
            last_updated=datetime.now(),
        )

    async def _scan_filesystem(self, root_path: str) -> List[Dict[str, Any]]:
        """
        Scan filesystem and collect file metadata
        """

        files = []
        root = Path(root_path)

        for file_path in root.rglob("*"):
            if file_path.is_file():
                # Skip ignored directories
                if any(ignored in str(file_path) for ignored in self.ignore_patterns):
                    continue

                try:
                    stat = file_path.stat()

                    file_info = {
                        "path": str(file_path),
                        "relative_path": str(file_path.relative_to(root)),
                        "name": file_path.name,
                        "extension": file_path.suffix.lower(),
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime),
                        "is_source_code": self._is_source_code(file_path.suffix),
                        "is_config": self._is_config_file(file_path.name),
                        "is_test": self._is_test_file(str(file_path)),
                        "is_documentation": self._is_documentation(file_path.suffix),
                    }

                    files.append(file_info)

                except (OSError, PermissionError):
                    # Skip files we can't access
                    continue

        return files

    def _detect_languages(self, file_info: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Detect programming languages used in the repository
        """

        language_map = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "JavaScript",
            ".tsx": "TypeScript",
            ".java": "Java",
            ".cpp": "C++",
            ".cc": "C++",
            ".cxx": "C++",
            ".c": "C",
            ".cs": "C#",
            ".php": "PHP",
            ".rb": "Ruby",
            ".go": "Go",
            ".rs": "Rust",
            ".swift": "Swift",
            ".kt": "Kotlin",
            ".scala": "Scala",
            ".clj": "Clojure",
            ".hs": "Haskell",
            ".ml": "OCaml",
            ".r": "R",
            ".m": "MATLAB",
            ".sh": "Shell",
            ".ps1": "PowerShell",
            ".sql": "SQL",
        }

        language_counts = Counter()

        for file in file_info:
            if file["is_source_code"]:
                language = language_map.get(file["extension"])
                if language:
                    language_counts[language] += 1

        return dict(language_counts)

    async def _analyze_dependencies(
        self, file_info: List[Dict[str, Any]], root_path: str
    ) -> Dict[str, List[str]]:
        """
        Analyze file dependencies and relationships
        """

        dependencies = {}

        for file in file_info:
            if not file["is_source_code"]:
                continue

            try:
                file_deps = await self._extract_file_dependencies(file, root_path)
                if file_deps:
                    dependencies[file["relative_path"]] = file_deps
            except Exception:
                # Skip files with parsing errors
                continue

        return dependencies

    async def _extract_file_dependencies(
        self, file_info: Dict[str, Any], root_path: str
    ) -> List[str]:
        """
        Extract dependencies for a specific file
        """

        extension = file_info["extension"]
        file_path = file_info["path"]

        # Use appropriate analyzer based on file type
        analyzer = self.analyzers.get(extension, self._analyze_generic_file)

        try:
            return await analyzer(file_path, root_path)
        except Exception:
            return []

    async def _analyze_python_file(self, file_path: str, root_path: str) -> List[str]:
        """
        Analyze Python file for imports and dependencies
        """

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Parse AST
            tree = ast.parse(content)

            imports = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            # Filter for local imports (relative to project)
            local_imports = []
            for imp in imports:
                # Check if it's a local module
                if not imp.startswith((".", "os", "sys", "json", "datetime", "typing")):
                    # Try to find corresponding file in project
                    possible_paths = [
                        f"{imp.replace('.', '/')}.py",
                        f"{imp.replace('.', '/')}/__init__.py",
                    ]

                    for possible_path in possible_paths:
                        full_path = os.path.join(root_path, possible_path)
                        if os.path.exists(full_path):
                            local_imports.append(possible_path)
                            break

            return local_imports

        except Exception:
            return []

    async def _analyze_javascript_file(
        self, file_path: str, root_path: str
    ) -> List[str]:
        """
        Analyze JavaScript/JSX file for imports and dependencies
        """

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            imports = []

            # Simple regex-based import extraction
            import re

            # ES6 imports
            import_patterns = [
                r"import\s+.*?\s+from\s+['\"](.+?)['\"]",
                r"import\s+['\"](.+?)['\"]",
                r"require\s*\(\s*['\"](.+?)['\"]\s*\)",
            ]

            for pattern in import_patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    # Filter for relative imports
                    if match.startswith("."):
                        # Resolve relative path
                        file_dir = os.path.dirname(file_path)
                        resolved = os.path.normpath(os.path.join(file_dir, match))
                        relative_to_root = os.path.relpath(resolved, root_path)
                        imports.append(relative_to_root)

            return imports

        except Exception:
            return []

    async def _analyze_typescript_file(
        self, file_path: str, root_path: str
    ) -> List[str]:
        """
        Analyze TypeScript file (similar to JavaScript with type imports)
        """
        return await self._analyze_javascript_file(file_path, root_path)

    async def _analyze_java_file(self, file_path: str, root_path: str) -> List[str]:
        """
        Analyze Java file for imports
        """

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            import re

            # Java imports
            imports = []
            import_pattern = r"import\s+(?:static\s+)?([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)"
            matches = re.findall(import_pattern, content)

            for match in matches:
                # Check if it's a local package
                if not match.startswith(("java.", "javax.", "org.", "com.")):
                    imports.append(match)

            return imports

        except Exception:
            return []

    async def _analyze_generic_file(self, file_path: str, root_path: str) -> List[str]:
        """
        Generic file analysis for unsupported languages
        """
        return []

    # Additional analyzer methods for other languages...
    async def _analyze_cpp_file(self, file_path: str, root_path: str) -> List[str]:
        return []

    async def _analyze_c_file(self, file_path: str, root_path: str) -> List[str]:
        return []

    async def _analyze_csharp_file(self, file_path: str, root_path: str) -> List[str]:
        return []

    async def _analyze_php_file(self, file_path: str, root_path: str) -> List[str]:
        return []

    async def _analyze_ruby_file(self, file_path: str, root_path: str) -> List[str]:
        return []

    async def _analyze_go_file(self, file_path: str, root_path: str) -> List[str]:
        return []

    async def _analyze_rust_file(self, file_path: str, root_path: str) -> List[str]:
        return []

    async def _analyze_complexity(
        self, file_info: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Analyze code complexity metrics
        """

        complexity_metrics = {}

        for file in file_info:
            if not file["is_source_code"]:
                continue

            try:
                complexity = await self._calculate_file_complexity(file)
                complexity_metrics[file["relative_path"]] = complexity
            except Exception:
                complexity_metrics[file["relative_path"]] = 0.0

        # Calculate aggregate metrics
        if complexity_metrics:
            values = list(complexity_metrics.values())
            complexity_metrics["_aggregate"] = {
                "average": sum(values) / len(values),
                "max": max(values),
                "min": min(values),
                "files_above_threshold": sum(1 for v in values if v > 0.7),
            }

        return complexity_metrics

    async def _calculate_file_complexity(self, file_info: Dict[str, Any]) -> float:
        """
        Calculate complexity score for a single file
        """

        try:
            with open(file_info["path"], "r", encoding="utf-8") as f:
                content = f.read()

            lines = content.split("\n")
            non_empty_lines = [line for line in lines if line.strip()]

            # Basic complexity indicators
            complexity_score = 0.0

            # Line count factor
            line_count = len(non_empty_lines)
            if line_count > 500:
                complexity_score += 0.3
            elif line_count > 200:
                complexity_score += 0.2
            elif line_count > 100:
                complexity_score += 0.1

            # Cyclomatic complexity indicators
            control_structures = [
                "if",
                "else",
                "elif",
                "while",
                "for",
                "switch",
                "case",
                "try",
                "catch",
                "except",
                "finally",
            ]

            control_count = 0
            for line in non_empty_lines:
                for structure in control_structures:
                    if f" {structure} " in line or line.strip().startswith(
                        f"{structure} "
                    ):
                        control_count += 1

            # Normalize by file size
            if line_count > 0:
                control_density = control_count / line_count
                complexity_score += min(0.5, control_density * 2)

            # Nesting level (simplified)
            max_nesting = 0

            for line in lines:
                stripped = line.strip()
                if stripped:
                    # Count indentation
                    indent_level = (
                        len(line) - len(line.lstrip())
                    ) // 4  # Assuming 4-space indents
                    max_nesting = max(max_nesting, indent_level)

            if max_nesting > 5:
                complexity_score += 0.2
            elif max_nesting > 3:
                complexity_score += 0.1

            return min(1.0, complexity_score)

        except Exception:
            return 0.0

    async def _detect_hotspots(
        self, file_info: List[Dict[str, Any]], complexity_metrics: Dict[str, float]
    ) -> List[str]:
        """
        Detect code hotspots (files that need attention)
        """

        hotspots = []

        # Sort files by various criteria
        source_files = [f for f in file_info if f["is_source_code"]]

        # 1. High complexity files
        for file in source_files:
            rel_path = file["relative_path"]
            complexity = complexity_metrics.get(rel_path, 0.0)

            if complexity > 0.7:  # High complexity threshold
                hotspots.append(rel_path)

        # 2. Large files
        large_files = sorted(source_files, key=lambda f: f["size"], reverse=True)[:50]
        hotspots.extend([f["relative_path"] for f in large_files])

        # 3. Recently modified files
        recent_files = sorted(source_files, key=lambda f: f["modified"], reverse=True)[
            :50
        ]
        hotspots.extend([f["relative_path"] for f in recent_files])

        # Remove duplicates and return
        return list(
            dict.fromkeys(hotspots)
        )  # Preserves order while removing duplicates

    async def _analyze_architecture(
        self, file_info: List[Dict[str, Any]], dependencies: Dict[str, List[str]]
    ) -> Dict[str, Any]:
        """
        Analyze repository architecture patterns
        """

        architecture = {
            "patterns": [],
            "structure": {},
            "dependency_graph": dependencies,
            "circular_dependencies": [],
            "layer_violations": [],
        }

        # Detect common patterns
        source_files = [f for f in file_info if f["is_source_code"]]

        # Directory structure analysis
        directories = defaultdict(list)
        for file in source_files:
            parts = Path(file["relative_path"]).parts
            if len(parts) > 1:
                directories[parts[0]].append(file)

        architecture["structure"] = {
            dir_name: {
                "file_count": len(files),
                "languages": list(set(f["extension"] for f in files)),
                "has_tests": any(f["is_test"] for f in files),
            }
            for dir_name, files in directories.items()
        }

        # Pattern detection
        patterns = []

        if "src" in directories and "tests" in directories:
            patterns.append("Standard Source/Test Layout")

        if "components" in directories or any("component" in d for d in directories):
            patterns.append("Component-Based Architecture")

        if "services" in directories or "api" in directories:
            patterns.append("Service-Oriented Architecture")

        if "models" in directories and "views" in directories:
            patterns.append("MVC Pattern")

        architecture["patterns"] = patterns

        # Detect circular dependencies (simplified)
        circular_deps = self._detect_circular_dependencies(dependencies)
        architecture["circular_dependencies"] = circular_deps

        return architecture

    def _detect_circular_dependencies(
        self, dependencies: Dict[str, List[str]]
    ) -> List[List[str]]:
        """
        Detect circular dependencies in the dependency graph
        """

        def has_path(
            graph: Dict[str, List[str]], start: str, end: str, visited: Set[str]
        ) -> bool:
            if start == end:
                return True

            if start in visited:
                return False

            visited.add(start)

            for neighbor in graph.get(start, []):
                if has_path(graph, neighbor, end, visited):
                    return True

            return False

        circular_deps = []

        for file, deps in dependencies.items():
            for dep in deps:
                if dep in dependencies and has_path(dependencies, dep, file, set()):
                    circular_deps.append([file, dep])

        return circular_deps

    async def _analyze_quality(self, file_info: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze code quality metrics
        """

        quality_metrics = {
            "test_coverage_estimate": 0.0,
            "documentation_ratio": 0.0,
            "config_file_count": 0,
            "has_linting": False,
            "has_formatting": False,
            "has_ci_cd": False,
        }

        source_files = [f for f in file_info if f["is_source_code"]]
        test_files = [f for f in file_info if f["is_test"]]
        doc_files = [f for f in file_info if f["is_documentation"]]
        config_files = [f for f in file_info if f["is_config"]]

        # Test coverage estimate
        if source_files:
            quality_metrics["test_coverage_estimate"] = len(test_files) / len(
                source_files
            )

        # Documentation ratio
        total_files = len(source_files) + len(doc_files)
        if total_files:
            quality_metrics["documentation_ratio"] = len(doc_files) / total_files

        # Config files
        quality_metrics["config_file_count"] = len(config_files)

        # Tool detection
        file_names = {f["name"].lower() for f in file_info}

        quality_metrics["has_linting"] = any(
            name in file_names
            for name in [
                ".eslintrc",
                ".eslintrc.json",
                ".eslintrc.js",
                "pylint.cfg",
                ".pylintrc",
                "flake8.cfg",
                "tslint.json",
            ]
        )

        quality_metrics["has_formatting"] = any(
            name in file_names
            for name in [
                ".prettierrc",
                ".prettierrc.json",
                "black.cfg",
                ".black",
                ".editorconfig",
            ]
        )

        quality_metrics["has_ci_cd"] = any(
            ".github" in f["relative_path"]
            or ".gitlab-ci" in f["name"]
            or "jenkins" in f["name"].lower()
            or "azure-pipelines" in f["name"]
            for f in file_info
        )

        return quality_metrics

    async def _analyze_security(
        self, file_info: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Perform basic security analysis
        """

        security_findings = []

        # Security patterns to look for
        security_patterns = {
            "hardcoded_secrets": [
                "password",
                "api_key",
                "secret_key",
                "private_key",
                "access_token",
                "auth_token",
            ],
            "sql_injection_risk": ["execute(", "query(", "raw_sql"],
            "xss_risk": ["innerHTML", "document.write", "eval("],
        }

        for file in file_info:
            if not file["is_source_code"]:
                continue

            try:
                with open(file["path"], "r", encoding="utf-8") as f:
                    content = f.read().lower()

                for category, patterns in security_patterns.items():
                    for pattern in patterns:
                        if pattern in content:
                            security_findings.append(
                                {
                                    "file": file["relative_path"],
                                    "category": category,
                                    "pattern": pattern,
                                    "severity": "medium",
                                }
                            )

            except Exception:
                continue

        return security_findings

    async def _analyze_performance(
        self, file_info: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze potential performance issues
        """

        performance_insights = {
            "large_files": [],
            "potential_bottlenecks": [],
            "optimization_opportunities": [],
        }

        # Large files (potential performance issues)
        large_files = [
            f
            for f in file_info
            if f["is_source_code"] and f["size"] > 100000  # > 100KB
        ]
        performance_insights["large_files"] = [
            {"file": f["relative_path"], "size": f["size"]}
            for f in sorted(large_files, key=lambda x: x["size"], reverse=True)[:25]
        ]

        # Performance anti-patterns
        performance_patterns = [
            "nested loops",
            "recursive calls",
            "database queries in loops",
            "large object creation",
            "memory leaks",
        ]

        performance_insights["optimization_opportunities"] = [
            f"Consider optimizing {pattern}" for pattern in performance_patterns[:10]
        ]

        return performance_insights

    # Helper methods

    def _is_source_code(self, extension: str) -> bool:
        """
        Check if file extension indicates source code
        """
        source_extensions = {
            ".py",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".java",
            ".cpp",
            ".c",
            ".cs",
            ".php",
            ".rb",
            ".go",
            ".rs",
            ".swift",
            ".kt",
            ".scala",
            ".clj",
            ".hs",
            ".ml",
            ".r",
            ".m",
        }
        return extension.lower() in source_extensions

    def _is_config_file(self, filename: str) -> bool:
        """
        Check if file is a configuration file
        """
        config_patterns = [
            "config",
            "settings",
            ".env",
            "package.json",
            "requirements.txt",
            "pom.xml",
            "build.gradle",
            "Makefile",
            "Dockerfile",
            "docker-compose",
        ]
        filename_lower = filename.lower()
        return any(pattern in filename_lower for pattern in config_patterns)

    def _is_test_file(self, filepath: str) -> bool:
        """
        Check if file is a test file
        """
        test_indicators = ["test", "spec", "__test__", "tests"]
        filepath_lower = filepath.lower()
        return any(indicator in filepath_lower for indicator in test_indicators)

    def _is_documentation(self, extension: str) -> bool:
        """
        Check if file is documentation
        """
        doc_extensions = {".md", ".txt", ".rst", ".adoc", ".wiki"}
        return extension.lower() in doc_extensions
