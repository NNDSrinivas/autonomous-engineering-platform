"""
DependencyResolver — Language-Aware Linking

Language-aware dependency resolution system that understands npm, maven, go.mod,
pip, terraform, and other dependency systems. This enables NAVI to understand
cross-repository dependencies regardless of technology stack.

Key Capabilities:
- Parse dependency files across all major languages and ecosystems
- Resolve direct and transitive dependencies
- Detect version conflicts and compatibility issues
- Map internal vs external dependencies
- Track dependency health and security vulnerabilities
"""

import logging
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)

class DependencyType(Enum):
    """Types of dependencies"""
    DIRECT = "direct"  # Explicitly declared dependency
    TRANSITIVE = "transitive"  # Dependency of a dependency
    DEV = "dev"  # Development-only dependency
    PEER = "peer"  # Peer dependency (npm)
    OPTIONAL = "optional"  # Optional dependency
    INTERNAL = "internal"  # Internal org dependency
    EXTERNAL = "external"  # External third-party dependency

@dataclass
class Dependency:
    """Represents a dependency relationship"""
    name: str
    version: str
    dependency_type: DependencyType
    source_file: str
    ecosystem: str  # npm, maven, pip, go, etc.
    is_internal: bool = False  # Whether it's an internal org dependency
    is_vulnerable: bool = False
    vulnerability_score: Optional[float] = None
    licenses: List[str] = field(default_factory=list)
    description: Optional[str] = None
    repository_url: Optional[str] = None
    last_updated: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DependencyGraph:
    """Complete dependency graph for a repository"""
    repo_name: str
    dependencies: List[Dependency] = field(default_factory=list)
    dependency_files: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    vulnerabilities: List[str] = field(default_factory=list)
    total_dependencies: int = 0
    direct_dependencies: int = 0
    transitive_dependencies: int = 0
    internal_dependencies: int = 0
    external_dependencies: int = 0
    health_score: float = 1.0  # 0.0 - 1.0
    
class DependencyResolver:
    """
    Multi-language dependency resolution system that can parse and understand
    dependency files across different ecosystems and technology stacks.
    """
    
    def __init__(self):
        """Initialize the dependency resolver"""
        self.internal_org_patterns = [
            r"^@company/",  # npm scoped packages
            r"^com\.company\.",  # java packages
            r"^company-",  # prefixed packages
        ]
        logger.info("DependencyResolver initialized for multi-language dependency analysis")
    
    def resolve_dependencies(self, repo_path: str, 
                           repo_name: str,
                           include_transitive: bool = False) -> DependencyGraph:
        """
        Resolve all dependencies for a repository
        
        Args:
            repo_path: Path to the repository
            repo_name: Name of the repository
            include_transitive: Whether to include transitive dependencies
            
        Returns:
            Complete dependency graph
        """
        logger.info(f"Resolving dependencies for repository: {repo_name}")
        
        repo_path = Path(repo_path)
        dependencies = []
        dependency_files = []
        
        # JavaScript/Node.js dependencies
        package_json = repo_path / "package.json"
        if package_json.exists():
            deps = self._parse_package_json(package_json)
            dependencies.extend(deps)
            dependency_files.append(str(package_json))
        
        # Python dependencies
        requirements_txt = repo_path / "requirements.txt"
        if requirements_txt.exists():
            deps = self._parse_requirements_txt(requirements_txt)
            dependencies.extend(deps)
            dependency_files.append(str(requirements_txt))
        
        pyproject_toml = repo_path / "pyproject.toml"
        if pyproject_toml.exists():
            deps = self._parse_pyproject_toml(pyproject_toml)
            dependencies.extend(deps)
            dependency_files.append(str(pyproject_toml))
        
        # Java dependencies
        pom_xml = repo_path / "pom.xml"
        if pom_xml.exists():
            deps = self._parse_pom_xml(pom_xml)
            dependencies.extend(deps)
            dependency_files.append(str(pom_xml))
        
        # Go dependencies
        go_mod = repo_path / "go.mod"
        if go_mod.exists():
            deps = self._parse_go_mod(go_mod)
            dependencies.extend(deps)
            dependency_files.append(str(go_mod))
        
        # Rust dependencies
        cargo_toml = repo_path / "Cargo.toml"
        if cargo_toml.exists():
            deps = self._parse_cargo_toml(cargo_toml)
            dependencies.extend(deps)
            dependency_files.append(str(cargo_toml))
        
        # Terraform dependencies
        tf_files = list(repo_path.glob("**/*.tf"))
        if tf_files:
            for tf_file in tf_files[:5]:  # Limit to avoid too many files
                deps = self._parse_terraform(tf_file)
                dependencies.extend(deps)
                dependency_files.append(str(tf_file))
        
        # Dockerfile dependencies
        dockerfile = repo_path / "Dockerfile"
        if dockerfile.exists():
            deps = self._parse_dockerfile(dockerfile)
            dependencies.extend(deps)
            dependency_files.append(str(dockerfile))
        
        # Mark internal dependencies
        for dep in dependencies:
            dep.is_internal = self._is_internal_dependency(dep.name)
        
        # Calculate statistics
        direct_deps = [d for d in dependencies if d.dependency_type == DependencyType.DIRECT]
        internal_deps = [d for d in dependencies if d.is_internal]
        external_deps = [d for d in dependencies if not d.is_internal]
        vulnerable_deps = [d for d in dependencies if d.is_vulnerable]
        
        # Calculate health score
        health_score = self._calculate_health_score(dependencies)
        
        graph = DependencyGraph(
            repo_name=repo_name,
            dependencies=dependencies,
            dependency_files=dependency_files,
            total_dependencies=len(dependencies),
            direct_dependencies=len(direct_deps),
            internal_dependencies=len(internal_deps),
            external_dependencies=len(external_deps),
            vulnerabilities=[d.name for d in vulnerable_deps],
            health_score=health_score
        )
        
        logger.info(f"Resolved {len(dependencies)} dependencies for {repo_name}")
        return graph
    
    def _parse_package_json(self, file_path: Path) -> List[Dependency]:
        """Parse npm package.json file"""
        try:
            with open(file_path) as f:
                data = json.load(f)
            
            dependencies = []
            
            # Production dependencies
            for name, version in data.get('dependencies', {}).items():
                dep = Dependency(
                    name=name,
                    version=version,
                    dependency_type=DependencyType.DIRECT,
                    source_file=str(file_path),
                    ecosystem="npm"
                )
                dependencies.append(dep)
            
            # Dev dependencies
            for name, version in data.get('devDependencies', {}).items():
                dep = Dependency(
                    name=name,
                    version=version,
                    dependency_type=DependencyType.DEV,
                    source_file=str(file_path),
                    ecosystem="npm"
                )
                dependencies.append(dep)
            
            # Peer dependencies
            for name, version in data.get('peerDependencies', {}).items():
                dep = Dependency(
                    name=name,
                    version=version,
                    dependency_type=DependencyType.PEER,
                    source_file=str(file_path),
                    ecosystem="npm"
                )
                dependencies.append(dep)
            
            return dependencies
            
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return []
    
    def _parse_requirements_txt(self, file_path: Path) -> List[Dependency]:
        """Parse Python requirements.txt file"""
        try:
            with open(file_path) as f:
                lines = f.readlines()
            
            dependencies = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Parse package==version or package>=version format
                    match = re.match(r'^([a-zA-Z0-9_-]+)([><=!]+.*)?', line)
                    if match:
                        name = match.group(1)
                        version = match.group(2) or "*"
                        
                        dep = Dependency(
                            name=name,
                            version=version,
                            dependency_type=DependencyType.DIRECT,
                            source_file=str(file_path),
                            ecosystem="pip"
                        )
                        dependencies.append(dep)
            
            return dependencies
            
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return []
    
    def _parse_pyproject_toml(self, file_path: Path) -> List[Dependency]:
        """Parse Python pyproject.toml file"""
        try:
            import toml
            with open(file_path) as f:
                data = toml.load(f)
            
            dependencies = []
            
            # Poetry dependencies
            if 'tool' in data and 'poetry' in data['tool']:
                poetry_deps = data['tool']['poetry'].get('dependencies', {})
                for name, version in poetry_deps.items():
                    if name != 'python':  # Skip Python version requirement
                        dep = Dependency(
                            name=name,
                            version=str(version),
                            dependency_type=DependencyType.DIRECT,
                            source_file=str(file_path),
                            ecosystem="poetry"
                        )
                        dependencies.append(dep)
                
                # Dev dependencies
                dev_deps = data['tool']['poetry'].get('dev-dependencies', {})
                for name, version in dev_deps.items():
                    dep = Dependency(
                        name=name,
                        version=str(version),
                        dependency_type=DependencyType.DEV,
                        source_file=str(file_path),
                        ecosystem="poetry"
                    )
                    dependencies.append(dep)
            
            return dependencies
            
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return []
    
    def _parse_pom_xml(self, file_path: Path) -> List[Dependency]:
        """Parse Maven pom.xml file"""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Handle XML namespaces
            namespace = {'maven': 'http://maven.apache.org/POM/4.0.0'}
            if root.tag.startswith('{'):
                namespace['maven'] = root.tag.split('}')[0][1:]
            
            dependencies = []
            
            # Find all dependency elements
            for dep in root.findall('.//maven:dependency', namespace):
                group_id = dep.find('maven:groupId', namespace)
                artifact_id = dep.find('maven:artifactId', namespace)
                version = dep.find('maven:version', namespace)
                scope = dep.find('maven:scope', namespace)
                
                if group_id is not None and artifact_id is not None:
                    name = f"{group_id.text}:{artifact_id.text}"
                    version_str = version.text if version is not None else "*"
                    
                    dep_type = DependencyType.DIRECT
                    if scope is not None:
                        if scope.text == 'test':
                            dep_type = DependencyType.DEV
                        elif scope.text == 'provided':
                            dep_type = DependencyType.OPTIONAL
                    
                    dependency = Dependency(
                        name=name,
                        version=version_str,
                        dependency_type=dep_type,
                        source_file=str(file_path),
                        ecosystem="maven"
                    )
                    dependencies.append(dependency)
            
            return dependencies
            
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return []
    
    def _parse_go_mod(self, file_path: Path) -> List[Dependency]:
        """Parse Go go.mod file"""
        try:
            with open(file_path) as f:
                content = f.read()
            
            dependencies = []
            
            # Parse require block
            require_match = re.search(r'require \((.*?)\)', content, re.DOTALL)
            if require_match:
                require_block = require_match.group(1)
                for line in require_block.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('//'):
                        parts = line.split()
                        if len(parts) >= 2:
                            name = parts[0]
                            version = parts[1]
                            
                            dep = Dependency(
                                name=name,
                                version=version,
                                dependency_type=DependencyType.DIRECT,
                                source_file=str(file_path),
                                ecosystem="go"
                            )
                            dependencies.append(dep)
            
            # Parse single require statements
            single_requires = re.findall(r'require ([^\s]+) ([^\s]+)', content)
            for name, version in single_requires:
                dep = Dependency(
                    name=name,
                    version=version,
                    dependency_type=DependencyType.DIRECT,
                    source_file=str(file_path),
                    ecosystem="go"
                )
                dependencies.append(dep)
            
            return dependencies
            
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return []
    
    def _parse_cargo_toml(self, file_path: Path) -> List[Dependency]:
        """Parse Rust Cargo.toml file"""
        try:
            import toml
            with open(file_path) as f:
                data = toml.load(f)
            
            dependencies = []
            
            # Production dependencies
            for name, version in data.get('dependencies', {}).items():
                dep = Dependency(
                    name=name,
                    version=str(version),
                    dependency_type=DependencyType.DIRECT,
                    source_file=str(file_path),
                    ecosystem="cargo"
                )
                dependencies.append(dep)
            
            # Dev dependencies
            for name, version in data.get('dev-dependencies', {}).items():
                dep = Dependency(
                    name=name,
                    version=str(version),
                    dependency_type=DependencyType.DEV,
                    source_file=str(file_path),
                    ecosystem="cargo"
                )
                dependencies.append(dep)
            
            return dependencies
            
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return []
    
    def _parse_terraform(self, file_path: Path) -> List[Dependency]:
        """Parse Terraform .tf file for module dependencies"""
        try:
            with open(file_path) as f:
                content = f.read()
            
            dependencies = []
            
            # Find module blocks
            module_matches = re.finditer(r'module\s+"([^"]+)"\s*{([^{}]*(?:{[^{}]*}[^{}]*)*)}', content, re.MULTILINE | re.DOTALL)
            
            for match in module_matches:
                module_name = match.group(1)
                module_content = match.group(2)
                
                # Look for source attribute
                source_match = re.search(r'source\s*=\s*"([^"]+)"', module_content)
                if source_match:
                    source = source_match.group(1)
                    
                    # Look for version attribute
                    version_match = re.search(r'version\s*=\s*"([^"]+)"', module_content)
                    version = version_match.group(1) if version_match else "*"
                    
                    dep = Dependency(
                        name=f"module:{module_name}",
                        version=version,
                        dependency_type=DependencyType.DIRECT,
                        source_file=str(file_path),
                        ecosystem="terraform",
                        repository_url=source
                    )
                    dependencies.append(dep)
            
            return dependencies
            
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return []
    
    def _parse_dockerfile(self, file_path: Path) -> List[Dependency]:
        """Parse Dockerfile for base image dependencies"""
        try:
            with open(file_path) as f:
                lines = f.readlines()
            
            dependencies = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('FROM '):
                    # Extract base image
                    from_parts = line.split()
                    if len(from_parts) >= 2:
                        image = from_parts[1]
                        
                        # Split image:tag
                        if ':' in image:
                            name, tag = image.rsplit(':', 1)
                        else:
                            name, tag = image, 'latest'
                        
                        dep = Dependency(
                            name=f"docker:{name}",
                            version=tag,
                            dependency_type=DependencyType.DIRECT,
                            source_file=str(file_path),
                            ecosystem="docker"
                        )
                        dependencies.append(dep)
            
            return dependencies
            
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            return []
    
    def _is_internal_dependency(self, name: str) -> bool:
        """Check if a dependency is internal to the organization"""
        for pattern in self.internal_org_patterns:
            if re.match(pattern, name):
                return True
        return False
    
    def _calculate_health_score(self, dependencies: List[Dependency]) -> float:
        """Calculate dependency health score"""
        if not dependencies:
            return 1.0
        
        score = 1.0
        
        # Penalize vulnerabilities
        vulnerable_count = sum(1 for d in dependencies if d.is_vulnerable)
        vulnerability_penalty = min(0.5, vulnerable_count * 0.1)
        score -= vulnerability_penalty
        
        # Penalize too many external dependencies
        external_count = sum(1 for d in dependencies if not d.is_internal)
        if external_count > 50:
            external_penalty = min(0.3, (external_count - 50) * 0.01)
            score -= external_penalty
        
        # Bonus for internal dependencies
        internal_ratio = sum(1 for d in dependencies if d.is_internal) / len(dependencies)
        score += internal_ratio * 0.1
        
        return max(0.0, min(1.0, score))
    
    def find_version_conflicts(self, graphs: List[DependencyGraph]) -> List[Dict[str, Any]]:
        """
        Find version conflicts across multiple dependency graphs
        
        Args:
            graphs: List of dependency graphs to analyze
            
        Returns:
            List of version conflicts
        """
        conflicts = []
        
        # Group dependencies by name across all graphs
        dep_versions = defaultdict(list)
        
        for graph in graphs:
            for dep in graph.dependencies:
                dep_versions[dep.name].append({
                    'repo': graph.repo_name,
                    'version': dep.version,
                    'ecosystem': dep.ecosystem
                })
        
        # Find conflicts (same dependency with different versions)
        for dep_name, versions in dep_versions.items():
            if len(set(v['version'] for v in versions)) > 1:
                conflicts.append({
                    'dependency': dep_name,
                    'versions': versions,
                    'conflict_type': 'version_mismatch'
                })
        
        return conflicts
    
    def analyze_dependency_drift(self, graphs: List[DependencyGraph]) -> Dict[str, Any]:
        """
        Analyze dependency drift across repositories
        
        Args:
            graphs: List of dependency graphs
            
        Returns:
            Drift analysis results
        """
        analysis = {
            'total_unique_dependencies': 0,
            'shared_dependencies': [],
            'ecosystem_distribution': defaultdict(int),
            'internal_vs_external': {'internal': 0, 'external': 0},
            'most_used_dependencies': [],
            'outdated_dependencies': []
        }
        
        all_deps = []
        for graph in graphs:
            all_deps.extend(graph.dependencies)
        
        # Count unique dependencies
        unique_deps = set((dep.name, dep.ecosystem) for dep in all_deps)
        analysis['total_unique_dependencies'] = len(unique_deps)
        
        # Ecosystem distribution
        for dep in all_deps:
            analysis['ecosystem_distribution'][dep.ecosystem] += 1
        
        # Internal vs external
        for dep in all_deps:
            if dep.is_internal:
                analysis['internal_vs_external']['internal'] += 1
            else:
                analysis['internal_vs_external']['external'] += 1
        
        # Most used dependencies
        dep_usage = Counter((dep.name, dep.ecosystem) for dep in all_deps)
        analysis['most_used_dependencies'] = [
            {'name': name, 'ecosystem': ecosystem, 'usage_count': count}
            for (name, ecosystem), count in dep_usage.most_common(20)
        ]
        
        return analysis

# Convenience function
def resolve_dependencies(repo_path: str, repo_name: str) -> DependencyGraph:
    """Convenience function to resolve dependencies"""
    resolver = DependencyResolver()
    return resolver.resolve_dependencies(repo_path, repo_name)