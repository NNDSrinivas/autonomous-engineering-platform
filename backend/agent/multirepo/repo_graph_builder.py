"""
RepoGraphBuilder — System Topology

System topology builder that creates dependency graphs showing relationships
between repositories, services, and components. This enables NAVI to understand
the organization's system architecture and make topology-aware decisions.

Key Capabilities:
- Build comprehensive dependency graphs from repository metadata
- Map service-to-service relationships and dependencies
- Identify dependency cycles and architectural issues
- Calculate dependency metrics and health scores
- Support both direct and transitive dependency analysis
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from .repo_registry import RepoRegistry, RepoMeta

logger = logging.getLogger(__name__)


class DependencyType(Enum):
    """Types of dependencies between repositories"""

    CODE_DEPENDENCY = "code"  # Direct code dependency (imports, requires)
    API_DEPENDENCY = "api"  # REST/GraphQL API calls
    EVENT_DEPENDENCY = "event"  # Event-driven communication
    DATA_DEPENDENCY = "data"  # Shared database or data store
    DEPLOYMENT_DEPENDENCY = "deployment"  # Deployment order dependency
    INFRASTRUCTURE_DEPENDENCY = "infrastructure"  # Shared infra resources
    BUILD_DEPENDENCY = "build"  # Build-time dependency
    RUNTIME_DEPENDENCY = "runtime"  # Runtime service dependency


@dataclass
class DependencyEdge:
    """An edge in the repository dependency graph"""

    source: str  # Source repository name
    target: str  # Target repository name
    dependency_type: DependencyType
    strength: float = 1.0  # Dependency strength (0.0 - 1.0)
    criticality: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    description: Optional[str] = None
    last_verified: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RepoNode:
    """A node in the repository dependency graph"""

    repo: RepoMeta
    incoming_edges: List[DependencyEdge] = field(default_factory=list)
    outgoing_edges: List[DependencyEdge] = field(default_factory=list)

    @property
    def dependencies(self) -> List[str]:
        """Repositories this repo depends on"""
        return [edge.target for edge in self.outgoing_edges]

    @property
    def dependents(self) -> List[str]:
        """Repositories that depend on this repo"""
        return [edge.source for edge in self.incoming_edges]

    @property
    def fan_out(self) -> int:
        """Number of outgoing dependencies"""
        return len(self.outgoing_edges)

    @property
    def fan_in(self) -> int:
        """Number of incoming dependencies"""
        return len(self.incoming_edges)


@dataclass
class RepoGraph:
    """Complete repository dependency graph"""

    nodes: Dict[str, RepoNode] = field(default_factory=dict)
    edges: List[DependencyEdge] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_node(self, repo_name: str) -> Optional[RepoNode]:
        """Get a node by repository name"""
        return self.nodes.get(repo_name)

    def add_node(self, repo: RepoMeta) -> RepoNode:
        """Add a repository node to the graph"""
        node = RepoNode(repo=repo)
        self.nodes[repo.name] = node
        return node

    def add_edge(self, edge: DependencyEdge) -> None:
        """Add a dependency edge to the graph"""
        self.edges.append(edge)

        # Update node edge lists
        if edge.source in self.nodes:
            self.nodes[edge.source].outgoing_edges.append(edge)

        if edge.target in self.nodes:
            self.nodes[edge.target].incoming_edges.append(edge)

    def get_dependencies(self, repo_name: str, transitive: bool = False) -> List[str]:
        """Get dependencies for a repository"""
        if repo_name not in self.nodes:
            return []

        if not transitive:
            return self.nodes[repo_name].dependencies

        # BFS for transitive dependencies
        visited = set()
        queue = deque([repo_name])
        dependencies = set()

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            if current in self.nodes:
                for dep in self.nodes[current].dependencies:
                    if dep not in visited:
                        dependencies.add(dep)
                        queue.append(dep)

        return list(dependencies)

    def get_dependents(self, repo_name: str, transitive: bool = False) -> List[str]:
        """Get dependents for a repository"""
        if repo_name not in self.nodes:
            return []

        if not transitive:
            return self.nodes[repo_name].dependents

        # BFS for transitive dependents
        visited = set()
        queue = deque([repo_name])
        dependents = set()

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            if current in self.nodes:
                for dep in self.nodes[current].dependents:
                    if dep not in visited:
                        dependents.add(dep)
                        queue.append(dep)

        return list(dependents)

    def find_cycles(self) -> List[List[str]]:
        """Find dependency cycles in the graph"""
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> None:
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)

            if node in self.nodes:
                for dep in self.nodes[node].dependencies:
                    dfs(dep, path + [node])

            rec_stack.remove(node)

        for repo_name in self.nodes:
            if repo_name not in visited:
                dfs(repo_name, [])

        return cycles

    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate graph metrics"""
        total_nodes = len(self.nodes)
        total_edges = len(self.edges)

        # Fan-in and fan-out distributions
        fan_ins = [node.fan_in for node in self.nodes.values()]
        fan_outs = [node.fan_out for node in self.nodes.values()]

        # Find highly connected nodes
        high_fan_in = sorted(
            [(name, node.fan_in) for name, node in self.nodes.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        high_fan_out = sorted(
            [(name, node.fan_out) for name, node in self.nodes.items()],
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        # Dependency cycles
        cycles = self.find_cycles()

        return {
            "total_repositories": total_nodes,
            "total_dependencies": total_edges,
            "average_fan_in": sum(fan_ins) / max(1, total_nodes),
            "average_fan_out": sum(fan_outs) / max(1, total_nodes),
            "max_fan_in": max(fan_ins) if fan_ins else 0,
            "max_fan_out": max(fan_outs) if fan_outs else 0,
            "highly_depended_upon": high_fan_in,
            "highly_dependent": high_fan_out,
            "dependency_cycles": len(cycles),
            "cycle_details": cycles[:5],  # Show first 5 cycles
        }


class RepoGraphBuilder:
    """
    Builder for creating comprehensive repository dependency graphs from
    organizational metadata and discovered relationships.
    """

    def __init__(self, registry: Optional[RepoRegistry] = None):
        """Initialize the graph builder"""
        self.registry = registry
        logger.info("RepoGraphBuilder initialized")

    def build_repo_graph(
        self, repos: Optional[List[RepoMeta]] = None, include_archived: bool = False
    ) -> RepoGraph:
        """
        Build a comprehensive repository dependency graph

        Args:
            repos: Optional list of repositories to include
            include_archived: Whether to include archived repositories

        Returns:
            Complete repository dependency graph
        """
        if repos is None and self.registry:
            repos = self.registry.list_repos(archived=include_archived)
        elif repos is None:
            repos = []

        logger.info(f"Building repository graph for {len(repos)} repositories")

        graph = RepoGraph()

        # Add all repositories as nodes
        for repo in repos:
            graph.add_node(repo)

        # Add dependency edges
        for repo in repos:
            for dep_name in repo.depends_on:
                if dep_name in graph.nodes:
                    edge = DependencyEdge(
                        source=repo.name,
                        target=dep_name,
                        dependency_type=DependencyType.CODE_DEPENDENCY,
                        description=f"{repo.name} depends on {dep_name}",
                    )
                    graph.add_edge(edge)

        # Enhance with inferred dependencies
        self._infer_api_dependencies(graph)
        self._infer_shared_library_dependencies(graph)
        self._infer_infrastructure_dependencies(graph)

        logger.info(
            f"Built graph with {len(graph.nodes)} nodes and {len(graph.edges)} edges"
        )
        return graph

    def build_service_graph(self, repos: List[RepoMeta]) -> RepoGraph:
        """
        Build a graph focused on service-to-service dependencies

        Args:
            repos: List of repositories to analyze

        Returns:
            Service-focused dependency graph
        """
        # Filter to service repositories
        service_repos = [
            repo
            for repo in repos
            if repo.repo_type.value in ["service", "frontend", "mobile"]
        ]

        graph = self.build_repo_graph(service_repos)

        # Add service-specific analysis
        self._analyze_service_patterns(graph)

        return graph

    def analyze_critical_path(self, graph: RepoGraph, target_repo: str) -> List[str]:
        """
        Analyze the critical path to a target repository

        Args:
            graph: Repository dependency graph
            target_repo: Target repository to analyze

        Returns:
            List of repositories in the critical path
        """
        if target_repo not in graph.nodes:
            return []

        # Find all paths to the target using BFS
        paths = []
        visited = set()
        queue = deque([(target_repo, [target_repo])])

        while queue:
            current, path = queue.popleft()

            if current in visited:
                continue
            visited.add(current)

            node = graph.nodes[current]

            # If this is a leaf node (no dependencies), it's a complete path
            if not node.dependencies:
                paths.append(path)
            else:
                for dep in node.dependencies:
                    if dep not in path:  # Avoid cycles
                        queue.append((dep, [dep] + path))

        # Find the longest critical path
        if paths:
            critical_path = max(paths, key=len)
            return critical_path

        return [target_repo]

    def identify_shared_components(self, graph: RepoGraph) -> List[str]:
        """
        Identify repositories that are heavily depended upon

        Args:
            graph: Repository dependency graph

        Returns:
            List of shared component repository names
        """
        # Repositories with high fan-in are typically shared components
        shared_threshold = 3  # More than 3 dependents

        shared_components = []
        for name, node in graph.nodes.items():
            if node.fan_in >= shared_threshold:
                shared_components.append(name)

        # Sort by fan-in (most depended upon first)
        shared_components.sort(key=lambda name: graph.nodes[name].fan_in, reverse=True)

        return shared_components

    def _infer_api_dependencies(self, graph: RepoGraph) -> None:
        """Infer API dependencies between services"""
        service_nodes = {
            name: node
            for name, node in graph.nodes.items()
            if node.repo.repo_type.value in ["service", "frontend"]
        }

        for name, node in service_nodes.items():
            # Look for API-related patterns in frameworks and metadata
            if "express" in node.repo.frameworks or "fastapi" in node.repo.frameworks:
                # This is likely an API service
                node.repo.metadata["is_api_service"] = True

            # Infer potential API calls based on business domain
            if node.repo.business_domain:
                for other_name, other_node in service_nodes.items():
                    if (
                        name != other_name
                        and other_node.repo.business_domain != node.repo.business_domain
                        and other_node.repo.metadata.get("is_api_service", False)
                    ):
                        # Check if there's already a dependency
                        existing = any(
                            edge.target == other_name
                            and edge.dependency_type == DependencyType.API_DEPENDENCY
                            for edge in node.outgoing_edges
                        )

                        if not existing:
                            edge = DependencyEdge(
                                source=name,
                                target=other_name,
                                dependency_type=DependencyType.API_DEPENDENCY,
                                strength=0.5,  # Inferred, not confirmed
                                description=f"Inferred API dependency: {name} → {other_name}",
                            )
                            graph.add_edge(edge)

    def _infer_shared_library_dependencies(self, graph: RepoGraph) -> None:
        """Infer dependencies on shared libraries"""
        library_nodes = {
            name: node
            for name, node in graph.nodes.items()
            if node.repo.repo_type.value == "library"
        }

        for lib_name, lib_node in library_nodes.items():
            # All services in the same language likely depend on org libraries
            for name, node in graph.nodes.items():
                if (
                    name != lib_name
                    and node.repo.primary_language == lib_node.repo.primary_language
                    and node.repo.repo_type.value in ["service", "frontend"]
                ):
                    # Check if dependency already exists
                    existing = any(
                        edge.target == lib_name for edge in node.outgoing_edges
                    )

                    if not existing:
                        edge = DependencyEdge(
                            source=name,
                            target=lib_name,
                            dependency_type=DependencyType.CODE_DEPENDENCY,
                            strength=0.7,
                            description=f"Inferred library dependency: {name} → {lib_name}",
                        )
                        graph.add_edge(edge)

    def _infer_infrastructure_dependencies(self, graph: RepoGraph) -> None:
        """Infer infrastructure dependencies"""
        infra_nodes = {
            name: node
            for name, node in graph.nodes.items()
            if node.repo.repo_type.value == "infrastructure"
        }

        for infra_name, infra_node in infra_nodes.items():
            # Services likely depend on infrastructure in the same domain
            for name, node in graph.nodes.items():
                if (
                    name != infra_name
                    and node.repo.business_domain == infra_node.repo.business_domain
                    and node.repo.repo_type.value == "service"
                ):
                    edge = DependencyEdge(
                        source=name,
                        target=infra_name,
                        dependency_type=DependencyType.INFRASTRUCTURE_DEPENDENCY,
                        strength=0.8,
                        description=f"Infrastructure dependency: {name} → {infra_name}",
                    )
                    graph.add_edge(edge)

    def _analyze_service_patterns(self, graph: RepoGraph) -> None:
        """Analyze patterns specific to service architectures"""
        # Identify potential API gateways (high fan-out)
        for name, node in graph.nodes.items():
            if node.fan_out >= 5 and "gateway" in name.lower():
                node.repo.metadata["likely_api_gateway"] = True

            # Identify potential shared services (high fan-in)
            if node.fan_in >= 5:
                node.repo.metadata["shared_service"] = True

            # Identify potential leaf services (no dependents)
            if node.fan_in == 0:
                node.repo.metadata["leaf_service"] = True


# Convenience function
def build_repo_graph(repos: List[RepoMeta]) -> RepoGraph:
    """Convenience function to build a repository graph"""
    builder = RepoGraphBuilder()
    return builder.build_repo_graph(repos)

    def __init__(self, repo_registry: Optional[RepoRegistry] = None):
        """
        Initialize the graph builder

        Args:
            repo_registry: Optional repository registry for metadata lookup
        """
        self.repo_registry = repo_registry or RepoRegistry()

    async def build_dependency_graph(self, repos: List[RepoMeta]) -> RepoGraph:
        """
        Build dependency graph (async version)

        Args:
            repos: List of repository metadata

        Returns:
            Repository dependency graph
        """
        return self.build_repo_graph(repos)

    def build_repo_graph(self, repos: List[RepoMeta]) -> RepoGraph:
        """Build comprehensive repository dependency graph"""
        return build_repo_graph(repos)
