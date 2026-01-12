"""
Workspace Retriever - Enhanced Codebase Indexer (STEP C Enhanced)

Retrieves comprehensive workspace context using existing analyzers:
- File structure and project metadata (existing)
- Project type detection (NEW)
- Dependencies via DependencyResolver (existing)
- Code analysis via IncrementalStaticAnalyzer (existing)
- Entry points and architecture patterns

Provides NAVI with full workspace intelligence for context-sensitive responses.
"""

import logging
import os
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Import existing analyzers - NO DUPLICATION!
try:
    from backend.agent.multirepo.dependency_resolver import DependencyResolver

    HAS_DEPENDENCY_RESOLVER = True
except ImportError:
    logger.warning("DependencyResolver not available - dependency analysis disabled")
    HAS_DEPENDENCY_RESOLVER = False

try:
    from backend.static_analysis.incremental_analyzer import IncrementalAnalysisService

    HAS_STATIC_ANALYZER = True
except ImportError:
    logger.warning(
        "IncrementalAnalysisService not available - static analysis disabled"
    )
    HAS_STATIC_ANALYZER = False


async def retrieve_workspace_context(
    user_id: str,
    workspace_root: Optional[str] = None,
    include_files: bool = True,
    attachments: Optional[List[Any]] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Retrieve relevant workspace context.

    Args:
        user_id: User identifier
        workspace_root: Path to workspace root directory
        include_files: Whether to include file listings
        attachments: Additional file attachments
        limit: Maximum number of files to include

    Returns:
        {
            "workspace_root": str,
            "files": [...],
            "structure": {...},
            "metadata": {...}
        }
    """
    logger.info(f"[WORKSPACE] Retrieving context for user {user_id}")

    try:
        result = {
            "workspace_root": workspace_root,
            "files": [],
            "structure": {},
            "metadata": {},
        }

        if not workspace_root or not os.path.exists(workspace_root):
            logger.warning(f"[WORKSPACE] Invalid workspace root: {workspace_root}")
            return result

        # Get basic workspace info
        workspace_path = Path(workspace_root)
        result["metadata"] = {
            "name": workspace_path.name,
            "path": str(workspace_path.absolute()),
            "exists": workspace_path.exists(),
        }

        if include_files and workspace_path.exists():
            # Get file structure (basic implementation)
            files = []
            try:
                for root, dirs, file_names in os.walk(workspace_root):
                    # Skip common non-essential directories
                    dirs[:] = [
                        d
                        for d in dirs
                        if not d.startswith(".")
                        and d not in ["node_modules", "__pycache__", "venv", ".venv"]
                    ]

                    for file_name in file_names[:limit]:
                        if not file_name.startswith("."):
                            file_path = os.path.join(root, file_name)
                            rel_path = os.path.relpath(file_path, workspace_root)
                            files.append(
                                {
                                    "name": file_name,
                                    "path": rel_path,
                                    "full_path": file_path,
                                    "size": (
                                        os.path.getsize(file_path)
                                        if os.path.exists(file_path)
                                        else 0
                                    ),
                                }
                            )

                            if len(files) >= limit:
                                break

                    if len(files) >= limit:
                        break

                result["files"] = files[:limit]

            except Exception as e:
                logger.error(f"[WORKSPACE] Error reading files: {e}")

        # Add attachments if provided
        if attachments:
            result["attachments"] = attachments

        logger.info(
            f"[WORKSPACE] Retrieved {len(result['files'])} files from workspace"
        )
        return result

    except Exception as e:
        logger.error(f"[WORKSPACE] Error retrieving workspace context: {e}")
        return {
            "workspace_root": workspace_root,
            "files": [],
            "structure": {},
            "metadata": {},
            "error": str(e),
        }


# ============================================================================
# NEW: Enhanced Workspace Indexing Using Existing Components
# ============================================================================


def _detect_project_type(files: List[Dict[str, Any]]) -> str:
    """
    Detect project type from file list.

    Returns: 'python', 'fastapi', 'flask', 'django', 'nodejs', 'react',
             'nextjs', 'go', 'java-maven', 'rust', 'monorepo', 'unknown'
    """
    file_names = [f.get("name", "") for f in files]
    file_paths = [f.get("path", "") for f in files]

    # Check for monorepo first - if multiple project types exist
    has_python = any(
        "requirements.txt" in fn or "pyproject.toml" in fn for fn in file_names
    )
    has_nodejs = "package.json" in file_names
    has_go = "go.mod" in file_names
    has_java = "pom.xml" in file_names or any("build.gradle" in fn for fn in file_names)
    has_rust = "Cargo.toml" in file_names

    project_type_count = sum([has_python, has_nodejs, has_go, has_java, has_rust])

    # If multiple project types detected, it's a monorepo
    if project_type_count > 1:
        types = []
        if has_nodejs:
            if any("next.config" in fn for fn in file_names):
                types.append("nextjs")
            else:
                types.append("nodejs")
        if has_python:
            if any("fastapi" in fn.lower() or "main.py" in fn for fn in file_names):
                types.append("fastapi")
            else:
                types.append("python")
        if has_go:
            types.append("go")
        if has_rust:
            types.append("rust")
        return "monorepo:" + "+".join(types)

    # Python-based projects
    if has_python:
        # Check for specific Python frameworks
        if any("fastapi" in fn.lower() or "main.py" in fn for fn in file_names):
            return "fastapi"
        elif any("flask" in fn.lower() or "app.py" in fn for fn in file_names):
            return "flask"
        elif any("django" in fn.lower() or "manage.py" in fn for fn in file_names):
            return "django"
        return "python"

    # JavaScript/TypeScript projects
    if has_nodejs:
        # Check for React/Next.js
        if any("next.config" in fn for fn in file_names):
            return "nextjs"
        elif any(
            "react" in fp.lower() or "App.tsx" in fn or "App.jsx" in fn
            for fn, fp in zip(file_names, file_paths)
        ):
            return "react"
        return "nodejs"

    # Go projects
    if has_go:
        return "go"

    # Java projects
    if has_java:
        if "pom.xml" in file_names:
            return "java-maven"
        return "java-gradle"

    # Rust projects
    if has_rust:
        return "rust"

    return "unknown"


def _find_entry_points(files: List[Dict[str, Any]], project_type: str) -> List[str]:
    """
    Find entry point files based on project type.

    Returns: List of relative file paths that are entry points
    """
    file_map = {f.get("name", ""): f.get("path", "") for f in files}

    entry_point_patterns = {
        "python": ["main.py", "app.py", "__main__.py", "run.py"],
        "fastapi": ["main.py", "app.py", "server.py"],
        "flask": ["app.py", "main.py", "wsgi.py"],
        "django": ["manage.py", "wsgi.py"],
        "nodejs": ["index.js", "server.js", "app.js", "main.js", "index.ts", "main.ts"],
        "react": [
            "index.tsx",
            "index.jsx",
            "App.tsx",
            "App.jsx",
            "main.tsx",
            "main.jsx",
        ],
        "nextjs": [
            "pages/_app.tsx",
            "pages/_app.jsx",
            "app/layout.tsx",
            "next.config.js",
        ],
        "go": ["main.go", "cmd/main.go"],
        "java-maven": ["Main.java", "Application.java"],
        "rust": ["main.rs", "lib.rs"],
    }

    patterns = entry_point_patterns.get(project_type, ["main.*", "index.*", "app.*"])
    entry_points = []

    for pattern in patterns:
        if "*" in pattern:
            # Wildcard matching
            prefix = pattern.replace("*", "")
            for name, path in file_map.items():
                if name.startswith(prefix):
                    entry_points.append(path)
        else:
            # Exact matching
            if pattern in file_map:
                entry_points.append(file_map[pattern])

    return entry_points


async def index_workspace_full(
    workspace_root: str,
    user_id: str = "system",
    include_code_analysis: bool = True,
    include_dependencies: bool = True,
) -> Dict[str, Any]:
    """
    Full workspace indexing using existing components.

    Combines:
    - Basic file scanning (retrieve_workspace_context)
    - Project type detection (_detect_project_type)
    - Entry point detection (_find_entry_points)
    - Dependency resolution (DependencyResolver - if available)
    - Static code analysis (IncrementalStaticAnalyzer - if available)

    Args:
        workspace_root: Path to workspace root directory
        user_id: User identifier
        include_code_analysis: Whether to run static analysis
        include_dependencies: Whether to resolve dependencies

    Returns:
        {
            "workspace_root": str,
            "project_type": str,
            "entry_points": List[str],
            "files": List[Dict],
            "dependencies": Dict (if include_dependencies=True),
            "code_analysis": Dict (if include_code_analysis=True),
            "metadata": Dict,
            "indexed_at": str
        }
    """
    logger.info(f"[WORKSPACE] Full indexing for {workspace_root}")

    try:
        # Step 1: Use existing file scanning
        basic_context = await retrieve_workspace_context(
            user_id=user_id,
            workspace_root=workspace_root,
            include_files=True,
            limit=1000,  # Increase limit for full indexing
        )

        if "error" in basic_context:
            logger.error(
                f"[WORKSPACE] Basic context retrieval failed: {basic_context['error']}"
            )
            return basic_context

        # Step 2: Detect project type (NEW)
        project_type = _detect_project_type(basic_context.get("files", []))
        logger.info(f"[WORKSPACE] Detected project type: {project_type}")

        # Step 3: Find entry points (NEW)
        entry_points = _find_entry_points(basic_context.get("files", []), project_type)
        logger.info(f"[WORKSPACE] Found {len(entry_points)} entry points")

        # Step 4: Resolve dependencies using EXISTING resolver
        dependencies_info = None
        if include_dependencies and HAS_DEPENDENCY_RESOLVER:
            try:
                dependency_resolver = DependencyResolver()
                workspace_name = Path(workspace_root).name
                dep_graph = dependency_resolver.resolve_dependencies(
                    workspace_root, workspace_name
                )

                dependencies_info = {
                    "total": dep_graph.total_dependencies,
                    "direct": dep_graph.direct_dependencies,
                    "internal": dep_graph.internal_dependencies,
                    "external": dep_graph.external_dependencies,
                    "files": dep_graph.dependency_files,
                    "health_score": dep_graph.health_score,
                    "vulnerabilities": dep_graph.vulnerabilities,
                    "conflicts": dep_graph.conflicts,
                }
                logger.info(
                    f"[WORKSPACE] Resolved {dep_graph.total_dependencies} dependencies"
                )
            except Exception as e:
                logger.warning(f"[WORKSPACE] Dependency resolution failed: {e}")
                dependencies_info = {"error": str(e)}

        # Step 5: Get code analysis using EXISTING analyzer
        code_analysis_info = None
        if include_code_analysis and HAS_STATIC_ANALYZER:
            try:
                analysis_service = IncrementalAnalysisService(workspace_root)
                analysis_dashboard = await analysis_service.get_analysis_dashboard()
                code_analysis_info = analysis_dashboard
                logger.info("[WORKSPACE] Code analysis completed")
            except Exception as e:
                logger.warning(f"[WORKSPACE] Static analysis failed: {e}")
                code_analysis_info = {"error": str(e)}

        # Step 6: Return comprehensive index
        result = {
            **basic_context,
            "project_type": project_type,
            "entry_points": entry_points,
            "indexed_at": __import__("datetime").datetime.now().isoformat(),
        }

        if dependencies_info:
            result["dependencies"] = dependencies_info

        if code_analysis_info:
            result["code_analysis"] = code_analysis_info

        logger.info(f"[WORKSPACE] Full indexing completed for {workspace_root}")
        return result

    except Exception as e:
        logger.error(f"[WORKSPACE] Error in full workspace indexing: {e}")
        return {
            "workspace_root": workspace_root,
            "project_type": "unknown",
            "entry_points": [],
            "files": [],
            "metadata": {},
            "error": str(e),
        }
