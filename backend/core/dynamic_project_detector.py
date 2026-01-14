"""
Dynamic Project Detector

Uses configuration files to detect project types, frameworks, and package managers
instead of hardcoded logic.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import logging

from backend.core.config_loader import get_config_loader, FrameworkDefinition

logger = logging.getLogger(__name__)


class DynamicProjectDetector:
    """
    Detects project type, frameworks, and technologies using configuration

    Instead of hardcoded if/else chains, uses loaded framework definitions
    """

    def __init__(self):
        self.config_loader = get_config_loader()
        self.frameworks = self.config_loader.load_frameworks()

    def detect(self, workspace_path: str) -> Tuple[str, List[str], Dict[str, str]]:
        """
        Detect project type, technologies, and dependencies

        Args:
            workspace_path: Path to workspace

        Returns:
            Tuple of (project_type, technologies, dependencies)
        """
        workspace = Path(workspace_path)

        # Try to detect framework
        detected_framework = self._detect_framework(workspace)

        if detected_framework:
            project_type = detected_framework.name
            technologies = detected_framework.technologies.copy()
        else:
            project_type = "unknown"
            technologies = []

        # Detect dependencies
        dependencies = self._detect_dependencies(workspace)

        # Detect additional technologies (Docker, K8s, etc.)
        additional_tech = self._detect_additional_technologies(workspace)
        technologies.extend(additional_tech)

        # Remove duplicates
        technologies = list(set(technologies))

        logger.info(
            f"Detected project: {project_type}, "
            f"technologies: {technologies}, "
            f"dependencies: {len(dependencies)}"
        )

        return project_type, technologies, dependencies

    def _detect_framework(self, workspace: Path) -> Optional[FrameworkDefinition]:
        """
        Detect framework by checking indicators in priority order

        Args:
            workspace: Workspace path

        Returns:
            First matching FrameworkDefinition or None
        """
        # Check each framework in priority order
        for framework in self.frameworks:
            if self._check_framework_indicators(workspace, framework):
                logger.info(f"Detected framework: {framework.display_name}")
                return framework

        logger.info("No specific framework detected")
        return None

    def _check_framework_indicators(
        self, workspace: Path, framework: FrameworkDefinition
    ) -> bool:
        """
        Check if workspace matches framework indicators

        Args:
            workspace: Workspace path
            framework: Framework definition

        Returns:
            True if all required indicators are present
        """
        indicators = framework.indicators

        # Check file indicators
        if "files" in indicators:
            if not self._check_files_exist(workspace, indicators["files"]):
                return False

        # Check dependency indicators
        if "dependencies" in indicators:
            deps = self._get_dependencies(workspace)
            if not any(dep in deps for dep in indicators["dependencies"]):
                return False

        # Check import indicators (for Python)
        if "imports" in indicators:
            if not self._check_imports_exist(workspace, indicators["imports"]):
                return False

        return True

    def _check_files_exist(self, workspace: Path, file_patterns: List[str]) -> bool:
        """
        Check if any of the file patterns exist

        Args:
            workspace: Workspace path
            file_patterns: List of file patterns to check

        Returns:
            True if at least one pattern matches
        """
        for pattern in file_patterns:
            # Check exact file
            if (workspace / pattern).exists():
                return True

            # Check if it's a directory pattern (ends with /)
            if pattern.endswith("/"):
                if (workspace / pattern.rstrip("/")).is_dir():
                    return True

            # Check if it's a glob pattern
            if "*" in pattern:
                matches = list(workspace.glob(pattern))
                if matches:
                    return True

        return False

    def _check_imports_exist(self, workspace: Path, import_names: List[str]) -> bool:
        """
        Check if Python files import any of the specified modules

        Args:
            workspace: Workspace path
            import_names: List of module names to check

        Returns:
            True if any Python file imports one of the modules
        """
        # Look for Python files
        python_files = list(workspace.glob("**/*.py"))[:20]  # Check first 20 files

        for py_file in python_files:
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    for import_name in import_names:
                        if (
                            f"import {import_name}" in content
                            or f"from {import_name}" in content
                        ):
                            return True
            except Exception:
                continue

        return False

    def _get_dependencies(self, workspace: Path) -> Dict[str, str]:
        """
        Get dependencies from package.json or requirements.txt

        Args:
            workspace: Workspace path

        Returns:
            Dictionary of dependencies
        """
        dependencies = {}

        # Check package.json
        package_json = workspace / "package.json"
        if package_json.exists():
            try:
                with open(package_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    dependencies.update(data.get("dependencies", {}))
                    dependencies.update(data.get("devDependencies", {}))
            except Exception as e:
                logger.error(f"Error reading package.json: {e}")

        # Check requirements.txt
        requirements = workspace / "requirements.txt"
        if requirements.exists():
            try:
                with open(requirements, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            # Parse requirement (e.g., "fastapi==0.68.0" or "fastapi>=0.68.0")
                            parts = line.split("==")
                            if len(parts) == 2:
                                dependencies[parts[0]] = parts[1]
                            else:
                                # Handle >=, <=, etc.
                                pkg_name = (
                                    line.split("[")[0]
                                    .split(">")[0]
                                    .split("<")[0]
                                    .split("!")[0]
                                )
                                dependencies[pkg_name] = "*"
            except Exception as e:
                logger.error(f"Error reading requirements.txt: {e}")

        return dependencies

    def _detect_dependencies(self, workspace: Path) -> Dict[str, str]:
        """Alias for _get_dependencies for external API"""
        return self._get_dependencies(workspace)

    def _detect_additional_technologies(self, workspace: Path) -> List[str]:
        """
        Detect additional technologies (Docker, K8s, TypeScript, etc.)

        Args:
            workspace: Workspace path

        Returns:
            List of detected technologies
        """
        technologies = []

        # Docker
        if (workspace / "Dockerfile").exists() or (
            workspace / "docker-compose.yml"
        ).exists():
            technologies.append("Docker")

        # Kubernetes
        if (workspace / "k8s").is_dir() or (workspace / "kubernetes").is_dir():
            technologies.append("Kubernetes")

        # TypeScript
        if (workspace / "tsconfig.json").exists():
            technologies.append("TypeScript")

        # Git
        if (workspace / ".git").is_dir():
            technologies.append("Git")

        return technologies

    def reload_configuration(self):
        """Reload framework configuration"""
        logger.info("Reloading project detector configuration...")
        self.frameworks = self.config_loader.load_frameworks()
        logger.info(f"Loaded {len(self.frameworks)} framework definitions")


# Global detector instance
_global_detector: Optional[DynamicProjectDetector] = None


def get_project_detector() -> DynamicProjectDetector:
    """Get the global project detector instance"""
    global _global_detector
    if _global_detector is None:
        _global_detector = DynamicProjectDetector()
    return _global_detector
