"""
Configuration Loader for Dynamic NAVI Features

Loads configuration from YAML files for:
- Intent patterns
- Framework detection
- Package managers
- Code generators
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class IntentPattern:
    """Intent pattern definition"""

    regex: str
    action: str
    confidence: float
    examples: List[str] = None

    def __post_init__(self):
        if self.examples is None:
            self.examples = []


@dataclass
class FrameworkDefinition:
    """Framework detection definition"""

    name: str
    category: str
    display_name: str
    indicators: Dict[str, List[str]]
    technologies: List[str]
    priority: int = 50


@dataclass
class PackageManagerDefinition:
    """Package manager definition"""

    name: str
    category: str
    display_name: str
    indicators: Dict[str, List[str]]
    commands: Dict[str, List[str]]
    priority: int = 50


class ConfigLoader:
    """
    Loads configuration from YAML files

    Supports hot-reloading and validation
    """

    def __init__(self, config_dir: str = None):
        if config_dir is None:
            # Default to config/ directory relative to project root
            project_root = Path(__file__).parent.parent.parent
            config_dir = project_root / "config"

        self.config_dir = Path(config_dir)
        self._cache: Dict[str, Any] = {}
        self._file_mtimes: Dict[str, float] = {}

    def load_intent_patterns(self, language: str = "english") -> List[IntentPattern]:
        """
        Load intent patterns for a specific language

        Args:
            language: Language code (e.g., "english", "spanish")

        Returns:
            List of IntentPattern objects
        """
        cache_key = f"intents_{language}"

        # Check cache
        if cache_key in self._cache and not self._is_file_modified(
            f"intents/{language}.yaml"
        ):
            return self._cache[cache_key]

        file_path = self.config_dir / "intents" / f"{language}.yaml"

        if not file_path.exists():
            logger.warning(
                f"Intent patterns file not found: {file_path}, using empty list"
            )
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            patterns = []
            for pattern_data in data.get("patterns", []):
                pattern = IntentPattern(
                    regex=pattern_data["regex"],
                    action=pattern_data["action"],
                    confidence=pattern_data.get("confidence", 0.8),
                    examples=pattern_data.get("examples", []),
                )
                patterns.append(pattern)

            # Add fallback patterns
            for fallback_data in data.get("fallback", []):
                pattern = IntentPattern(
                    regex=fallback_data["regex"],
                    action=fallback_data["action"],
                    confidence=fallback_data.get("confidence", 0.5),
                    examples=fallback_data.get("examples", []),
                )
                patterns.append(pattern)

            self._cache[cache_key] = patterns
            self._file_mtimes[f"intents/{language}.yaml"] = file_path.stat().st_mtime

            logger.info(
                f"Loaded {len(patterns)} intent patterns for language: {language}"
            )
            return patterns

        except Exception as e:
            logger.error(f"Error loading intent patterns from {file_path}: {e}")
            return []

    def load_frameworks(self) -> List[FrameworkDefinition]:
        """
        Load framework definitions

        Returns:
            List of FrameworkDefinition objects sorted by priority
        """
        cache_key = "frameworks"

        # Check cache
        if cache_key in self._cache and not self._is_file_modified("frameworks.yaml"):
            return self._cache[cache_key]

        file_path = self.config_dir / "frameworks.yaml"

        if not file_path.exists():
            logger.warning(f"Frameworks file not found: {file_path}, using empty list")
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            frameworks = []
            for fw_data in data.get("frameworks", []):
                framework = FrameworkDefinition(
                    name=fw_data["name"],
                    category=fw_data["category"],
                    display_name=fw_data["display_name"],
                    indicators=fw_data.get("indicators", {}),
                    technologies=fw_data.get("technologies", []),
                    priority=fw_data.get("priority", 50),
                )
                frameworks.append(framework)

            # Sort by priority (highest first)
            frameworks.sort(key=lambda f: f.priority, reverse=True)

            self._cache[cache_key] = frameworks
            self._file_mtimes["frameworks.yaml"] = file_path.stat().st_mtime

            logger.info(f"Loaded {len(frameworks)} framework definitions")
            return frameworks

        except Exception as e:
            logger.error(f"Error loading frameworks from {file_path}: {e}")
            return []

    def load_package_managers(self) -> List[PackageManagerDefinition]:
        """
        Load package manager definitions

        Returns:
            List of PackageManagerDefinition objects sorted by priority
        """
        cache_key = "package_managers"

        # Check cache
        if cache_key in self._cache and not self._is_file_modified(
            "package_managers.yaml"
        ):
            return self._cache[cache_key]

        file_path = self.config_dir / "package_managers.yaml"

        if not file_path.exists():
            logger.warning(
                f"Package managers file not found: {file_path}, using empty list"
            )
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            package_managers = []
            for pm_data in data.get("package_managers", []):
                pm = PackageManagerDefinition(
                    name=pm_data["name"],
                    category=pm_data["category"],
                    display_name=pm_data["display_name"],
                    indicators=pm_data.get("indicators", {}),
                    commands=pm_data.get("commands", {}),
                    priority=pm_data.get("priority", 50),
                )
                package_managers.append(pm)

            # Sort by priority (highest first)
            package_managers.sort(key=lambda p: p.priority, reverse=True)

            self._cache[cache_key] = package_managers
            self._file_mtimes["package_managers.yaml"] = file_path.stat().st_mtime

            logger.info(f"Loaded {len(package_managers)} package manager definitions")
            return package_managers

        except Exception as e:
            logger.error(f"Error loading package managers from {file_path}: {e}")
            return []

    def _is_file_modified(self, relative_path: str) -> bool:
        """Check if file has been modified since last load"""
        if relative_path not in self._file_mtimes:
            return True

        file_path = self.config_dir / relative_path
        if not file_path.exists():
            return True

        current_mtime = file_path.stat().st_mtime
        cached_mtime = self._file_mtimes.get(relative_path, 0)

        return current_mtime > cached_mtime

    def reload_all(self) -> None:
        """Force reload all configurations"""
        logger.info("Reloading all configurations...")
        self._cache.clear()
        self._file_mtimes.clear()

        self.load_intent_patterns()
        self.load_frameworks()
        self.load_package_managers()

        logger.info("Configuration reload complete")

    def get_config_info(self) -> Dict[str, Any]:
        """Get information about loaded configurations"""
        return {
            "config_dir": str(self.config_dir),
            "loaded_configs": list(self._cache.keys()),
            "cached_files": len(self._file_mtimes),
        }


# Global config loader instance
_global_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """Get the global config loader instance"""
    global _global_loader
    if _global_loader is None:
        _global_loader = ConfigLoader()
    return _global_loader
