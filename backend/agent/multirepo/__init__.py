"""
Phase 4.8 — Multi-Repo & Monorepo Intelligence

This module transforms NAVI from repo-aware to organization-system-aware.
It enables cross-repository reasoning, coordinated changes, and blast-radius
control at a level that matches Principal Engineers and Platform Architects.

Key Capabilities:
- Organization-wide repository awareness and topology
- Language-agnostic dependency resolution
- API and schema contract intelligence
- True blast radius analysis across repo boundaries
- Multi-repository change coordination
- Safe execution gating for organization-scale changes

This is where NAVI becomes impossible to compete with on system-level thinking.
"""

from .repo_registry import RepoRegistry, RepoMeta, RepoType, register_repo, list_repos
from .repo_graph_builder import (
    RepoGraphBuilder,
    RepoGraph,
    DependencyEdge,
    build_repo_graph,
)
from .dependency_resolver import (
    DependencyResolver,
    DependencyType,
    Dependency,
    resolve_dependencies,
)
from .contract_analyzer import (
    ContractAnalyzer,
    ContractChange,
    BreakingChange,
    analyze_contract_changes,
)
from .impact_analyzer import ImpactAnalyzer, ImpactAnalysis, AffectedRepository
from .change_coordinator import ChangeCoordinator, CoordinatedChange, ChangeRequest
from .orchestrator import MultiRepoOrchestrator, ArchitecturalDecision, DecisionType

__all__ = [
    # Repository registry and metadata
    "RepoRegistry",
    "RepoMeta",
    "RepoType",
    "register_repo",
    "list_repos",
    # System topology and graphs
    "RepoGraphBuilder",
    "RepoGraph",
    "DependencyEdge",
    "build_repo_graph",
    # Dependency resolution
    "DependencyResolver",
    "DependencyType",
    "Dependency",
    "resolve_dependencies",
    # Contract and API intelligence
    "ContractAnalyzer",
    "ContractChange",
    "BreakingChange",
    "analyze_contract_changes",
    # Multi-repo impact analysis
    "ImpactAnalyzer",
    "ImpactAnalysis",
    "AffectedRepository",
    # Change coordination
    "ChangeCoordinator",
    "CoordinatedChange",
    "ChangeRequest",
    # High-level orchestration
    "MultiRepoOrchestrator",
    "ArchitecturalDecision",
    "DecisionType",
]
