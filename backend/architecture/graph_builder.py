"""
Architecture Graph Generator - Static and Dynamic Dependency Analysis
Visualizes file dependencies, function calls, service boundaries, and architecture layers.
"""

import ast
import logging
import hashlib
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import re
import networkx as nx
from collections import defaultdict

try:
    from ..memory.episodic_memory import EpisodicMemory, MemoryEventType
except ImportError:
    from backend.memory.episodic_memory import EpisodicMemory, MemoryEventType


class NodeType(Enum):
    """Types of nodes in the architecture graph."""

    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    VARIABLE = "variable"
    API_ROUTE = "api_route"
    DATABASE_TABLE = "database_table"
    COMPONENT = "component"
    SERVICE = "service"
    EXTERNAL_DEPENDENCY = "external_dependency"


class EdgeType(Enum):
    """Types of edges in the architecture graph."""

    IMPORTS = "imports"
    CALLS = "calls"
    INHERITS = "inherits"
    USES = "uses"
    CONTAINS = "contains"
    DEPENDS_ON = "depends_on"
    COMMUNICATES_WITH = "communicates_with"
    REFERENCES = "references"


class AnalysisLevel(Enum):
    """Levels of analysis depth."""

    BASIC = "basic"  # File-level dependencies only
    INTERMEDIATE = "intermediate"  # + Function/class level
    COMPREHENSIVE = "comprehensive"  # + Variable usage, call chains
    DEEP = "deep"  # + Runtime analysis, dynamic dependencies


@dataclass
class GraphNode:
    """A node in the architecture graph."""

    node_id: str
    name: str
    node_type: NodeType
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.node_id,
            "name": self.name,
            "type": self.node_type.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "metadata": self.metadata,
        }


@dataclass
class GraphEdge:
    """An edge in the architecture graph."""

    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.edge_type.value,
            "weight": self.weight,
            "metadata": self.metadata,
        }


@dataclass
class ArchitectureGraph:
    """Complete architecture graph representation."""

    graph_id: str
    nodes: Dict[str, GraphNode]
    edges: List[GraphEdge]
    metadata: Dict[str, Any]
    created_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "statistics": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "node_types": self._count_node_types(),
                "edge_types": self._count_edge_types(),
            },
        }

    def _count_node_types(self) -> Dict[str, int]:
        """Count nodes by type."""
        counts = defaultdict(int)
        for node in self.nodes.values():
            counts[node.node_type.value] += 1
        return dict(counts)

    def _count_edge_types(self) -> Dict[str, int]:
        """Count edges by type."""
        counts = defaultdict(int)
        for edge in self.edges:
            counts[edge.edge_type.value] += 1
        return dict(counts)


class PythonAnalyzer:
    """Analyzer for Python source code."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def analyze_file(self, file_path: Path) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """
        Analyze a Python file and extract nodes and edges.

        Args:
            file_path: Path to Python file

        Returns:
            Tuple of (nodes, edges)
        """
        nodes = []
        edges = []

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content)

            # Create file node
            file_node_id = self._get_file_id(file_path)
            file_node = GraphNode(
                node_id=file_node_id,
                name=file_path.name,
                node_type=NodeType.FILE,
                file_path=str(file_path),
                metadata={
                    "size_bytes": len(content),
                    "lines": len(content.splitlines()),
                },
            )
            nodes.append(file_node)

            # Analyze AST
            analyzer = PythonASTAnalyzer(file_path, file_node_id)
            ast_nodes, ast_edges = analyzer.visit(tree)

            nodes.extend(ast_nodes)
            edges.extend(ast_edges)

        except Exception as e:
            self.logger.warning(f"Failed to analyze Python file {file_path}: {e}")

        return nodes, edges

    def _get_file_id(self, file_path: Path) -> str:
        """Generate unique ID for file."""
        return f"file_{hashlib.md5(str(file_path).encode()).hexdigest()[:12]}"


class PythonASTAnalyzer(ast.NodeVisitor):
    """AST visitor for analyzing Python code structure."""

    def __init__(self, file_path: Path, file_node_id: str):
        self.file_path = file_path
        self.file_node_id = file_node_id
        self.nodes: List[GraphNode] = []
        self.edges: List[GraphEdge] = []
        self.current_scope: List[str] = []
        self.imports: Dict[str, str] = {}  # alias -> module

    def visit(self, node: ast.AST) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """Visit AST and return nodes and edges."""
        super().visit(node)
        return self.nodes, self.edges

    def visit_Import(self, node: ast.Import):
        """Handle import statements."""
        for alias in node.names:
            module_name = alias.name
            alias_name = alias.asname or alias.name

            self.imports[alias_name] = module_name

            # Create external dependency node
            dep_id = f"ext_{hashlib.md5(module_name.encode()).hexdigest()[:12]}"
            dep_node = GraphNode(
                node_id=dep_id,
                name=module_name,
                node_type=NodeType.EXTERNAL_DEPENDENCY,
                metadata={"import_type": "direct"},
            )
            self.nodes.append(dep_node)

            # Create import edge
            edge = GraphEdge(
                source_id=self.file_node_id,
                target_id=dep_id,
                edge_type=EdgeType.IMPORTS,
                metadata={"line_number": node.lineno},
            )
            self.edges.append(edge)

        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Handle from ... import statements."""
        module_name = node.module or ""

        for alias in node.names:
            name = alias.name
            alias_name = alias.asname or name
            full_name = f"{module_name}.{name}" if module_name else name

            self.imports[alias_name] = full_name

            # Create external dependency node
            dep_id = f"ext_{hashlib.md5(full_name.encode()).hexdigest()[:12]}"
            dep_node = GraphNode(
                node_id=dep_id,
                name=full_name,
                node_type=NodeType.EXTERNAL_DEPENDENCY,
                metadata={"import_type": "from", "module": module_name},
            )
            self.nodes.append(dep_node)

            # Create import edge
            edge = GraphEdge(
                source_id=self.file_node_id,
                target_id=dep_id,
                edge_type=EdgeType.IMPORTS,
                metadata={"line_number": node.lineno},
            )
            self.edges.append(edge)

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        """Handle class definitions."""
        class_id = self._get_node_id("class", node.name)

        class_node = GraphNode(
            node_id=class_id,
            name=node.name,
            node_type=NodeType.CLASS,
            file_path=str(self.file_path),
            line_number=node.lineno,
            metadata={
                "docstring": ast.get_docstring(node),
                "base_classes": [
                    base.id if isinstance(base, ast.Name) else str(base)
                    for base in node.bases
                ],
            },
        )
        self.nodes.append(class_node)

        # Create containment edge
        edge = GraphEdge(
            source_id=self.file_node_id,
            target_id=class_id,
            edge_type=EdgeType.CONTAINS,
            metadata={"line_number": node.lineno},
        )
        self.edges.append(edge)

        # Handle inheritance
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_id = self._get_external_id(base.id)
                inherit_edge = GraphEdge(
                    source_id=class_id,
                    target_id=base_id,
                    edge_type=EdgeType.INHERITS,
                    metadata={"line_number": node.lineno},
                )
                self.edges.append(inherit_edge)

        # Enter class scope
        self.current_scope.append(node.name)
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Handle function definitions."""
        func_id = self._get_node_id("function", node.name)

        func_node = GraphNode(
            node_id=func_id,
            name=node.name,
            node_type=NodeType.FUNCTION,
            file_path=str(self.file_path),
            line_number=node.lineno,
            metadata={
                "docstring": ast.get_docstring(node),
                "args": [arg.arg for arg in node.args.args],
                "is_method": len(self.current_scope) > 0
                and self.current_scope[-1] != node.name,
            },
        )
        self.nodes.append(func_node)

        # Create containment edge
        parent_id = (
            self._get_current_scope_id() if self.current_scope else self.file_node_id
        )
        edge = GraphEdge(
            source_id=parent_id,
            target_id=func_id,
            edge_type=EdgeType.CONTAINS,
            metadata={"line_number": node.lineno},
        )
        self.edges.append(edge)

        # Enter function scope
        self.current_scope.append(node.name)
        self.generic_visit(node)
        self.current_scope.pop()

    def visit_Call(self, node: ast.Call):
        """Handle function calls."""
        if isinstance(node.func, ast.Name):
            called_name = node.func.id

            # Create call edge if we're in a function
            if self.current_scope:
                caller_id = self._get_current_scope_id()
                called_id = self._get_external_id(called_name)

                call_edge = GraphEdge(
                    source_id=caller_id,
                    target_id=called_id,
                    edge_type=EdgeType.CALLS,
                    metadata={"line_number": node.lineno},
                )
                self.edges.append(call_edge)

        self.generic_visit(node)

    def _get_node_id(self, node_type: str, name: str) -> str:
        """Generate unique ID for a node."""
        scope_path = ".".join(self.current_scope + [name])
        return f"{node_type}_{hashlib.md5(f'{self.file_path}:{scope_path}'.encode()).hexdigest()[:12]}"

    def _get_current_scope_id(self) -> str:
        """Get ID for current scope."""
        if not self.current_scope:
            return self.file_node_id

        scope_type = "class" if len(self.current_scope) == 1 else "function"
        return self._get_node_id(scope_type, self.current_scope[-1])

    def _get_external_id(self, name: str) -> str:
        """Get ID for external reference."""
        resolved_name = self.imports.get(name, name)
        return f"ext_{hashlib.md5(resolved_name.encode()).hexdigest()[:12]}"


class JavaScriptAnalyzer:
    """Analyzer for JavaScript/TypeScript source code."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def analyze_file(self, file_path: Path) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """
        Analyze a JavaScript/TypeScript file and extract nodes and edges.

        Args:
            file_path: Path to JS/TS file

        Returns:
            Tuple of (nodes, edges)
        """
        nodes = []
        edges = []

        try:
            content = file_path.read_text(encoding="utf-8")

            # Create file node
            file_node_id = (
                f"file_{hashlib.md5(str(file_path).encode()).hexdigest()[:12]}"
            )
            file_node = GraphNode(
                node_id=file_node_id,
                name=file_path.name,
                node_type=NodeType.FILE,
                file_path=str(file_path),
                metadata={
                    "size_bytes": len(content),
                    "lines": len(content.splitlines()),
                },
            )
            nodes.append(file_node)

            # Basic regex-based analysis (production would use proper JS/TS parser)
            js_nodes, js_edges = self._analyze_js_content(
                content, file_path, file_node_id
            )
            nodes.extend(js_nodes)
            edges.extend(js_edges)

        except Exception as e:
            self.logger.warning(f"Failed to analyze JS/TS file {file_path}: {e}")

        return nodes, edges

    def _analyze_js_content(
        self, content: str, file_path: Path, file_node_id: str
    ) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """Analyze JavaScript content using regex patterns."""
        nodes = []
        edges = []

        # Find imports
        import_patterns = [
            r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'import\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
        ]

        for pattern in import_patterns:
            for match in re.finditer(pattern, content):
                module_name = match.group(1)
                line_num = content[: match.start()].count("\n") + 1

                # Create external dependency node
                dep_id = f"ext_{hashlib.md5(module_name.encode()).hexdigest()[:12]}"
                dep_node = GraphNode(
                    node_id=dep_id,
                    name=module_name,
                    node_type=NodeType.EXTERNAL_DEPENDENCY,
                    metadata={
                        "import_type": (
                            "es6" if "import" in match.group(0) else "commonjs"
                        )
                    },
                )
                nodes.append(dep_node)

                # Create import edge
                edge = GraphEdge(
                    source_id=file_node_id,
                    target_id=dep_id,
                    edge_type=EdgeType.IMPORTS,
                    metadata={"line_number": line_num},
                )
                edges.append(edge)

        # Find function definitions
        function_patterns = [
            r"function\s+(\w+)\s*\(",
            r"const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>",
            r"(\w+)\s*:\s*(?:async\s+)?function\s*\(",
        ]

        for pattern in function_patterns:
            for match in re.finditer(pattern, content):
                func_name = match.group(1)
                line_num = content[: match.start()].count("\n") + 1

                func_id = f"function_{hashlib.md5(f'{file_path}:{func_name}'.encode()).hexdigest()[:12]}"
                func_node = GraphNode(
                    node_id=func_id,
                    name=func_name,
                    node_type=NodeType.FUNCTION,
                    file_path=str(file_path),
                    line_number=line_num,
                )
                nodes.append(func_node)

                # Create containment edge
                edge = GraphEdge(
                    source_id=file_node_id,
                    target_id=func_id,
                    edge_type=EdgeType.CONTAINS,
                    metadata={"line_number": line_num},
                )
                edges.append(edge)

        # Find class definitions
        class_pattern = r"class\s+(\w+)(?:\s+extends\s+(\w+))?"
        for match in re.finditer(class_pattern, content):
            class_name = match.group(1)
            base_class = match.group(2)
            line_num = content[: match.start()].count("\n") + 1

            class_id = f"class_{hashlib.md5(f'{file_path}:{class_name}'.encode()).hexdigest()[:12]}"
            class_node = GraphNode(
                node_id=class_id,
                name=class_name,
                node_type=NodeType.CLASS,
                file_path=str(file_path),
                line_number=line_num,
                metadata={"base_class": base_class},
            )
            nodes.append(class_node)

            # Create containment edge
            edge = GraphEdge(
                source_id=file_node_id,
                target_id=class_id,
                edge_type=EdgeType.CONTAINS,
                metadata={"line_number": line_num},
            )
            edges.append(edge)

            # Create inheritance edge if base class exists
            if base_class:
                base_id = f"ext_{hashlib.md5(base_class.encode()).hexdigest()[:12]}"
                inherit_edge = GraphEdge(
                    source_id=class_id,
                    target_id=base_id,
                    edge_type=EdgeType.INHERITS,
                    metadata={"line_number": line_num},
                )
                edges.append(inherit_edge)

        return nodes, edges


class ArchitectureAnalyzer:
    """
    Main architecture analyzer that orchestrates different language analyzers.
    """

    def __init__(self, workspace_root: str, memory: Optional[EpisodicMemory] = None):
        """
        Initialize architecture analyzer.

        Args:
            workspace_root: Root directory of the workspace
            memory: Episodic memory for learning
        """
        self.workspace_root = Path(workspace_root)
        self.memory = memory or EpisodicMemory()
        self.logger = logging.getLogger(__name__)

        # Language-specific analyzers
        self.analyzers = {
            ".py": PythonAnalyzer(),
            ".js": JavaScriptAnalyzer(),
            ".ts": JavaScriptAnalyzer(),
            ".jsx": JavaScriptAnalyzer(),
            ".tsx": JavaScriptAnalyzer(),
        }

        # Analysis configuration
        self.config = {
            "max_files": 500,
            "excluded_dirs": {
                ".git",
                "node_modules",
                "__pycache__",
                ".pytest_cache",
                "venv",
                ".venv",
                "dist",
                "build",
                ".next",
            },
            "excluded_files": {"*.min.js", "*.map", "*.d.ts"},
            "analysis_timeout_seconds": 300,
        }

    async def analyze_architecture(
        self,
        analysis_level: AnalysisLevel = AnalysisLevel.INTERMEDIATE,
        include_external_deps: bool = True,
    ) -> ArchitectureGraph:
        """
        Perform comprehensive architecture analysis.

        Args:
            analysis_level: Depth of analysis
            include_external_deps: Whether to include external dependencies

        Returns:
            Complete architecture graph
        """
        analysis_start = datetime.utcnow()
        graph_id = f"arch_{analysis_start.strftime('%Y%m%d_%H%M%S')}"

        self.logger.info(f"Starting architecture analysis: {graph_id}")

        all_nodes: Dict[str, GraphNode] = {}
        all_edges: List[GraphEdge] = []

        try:
            # Get files to analyze
            files_to_analyze = self._get_analyzable_files()

            self.logger.info(f"Analyzing {len(files_to_analyze)} files")

            # Analyze each file
            for file_path in files_to_analyze:
                try:
                    analyzer = self._get_analyzer_for_file(file_path)
                    if analyzer:
                        nodes, edges = analyzer.analyze_file(file_path)

                        # Add nodes (avoid duplicates)
                        for node in nodes:
                            if node.node_id not in all_nodes:
                                all_nodes[node.node_id] = node

                        all_edges.extend(edges)

                except Exception as e:
                    self.logger.warning(f"Failed to analyze file {file_path}: {e}")

            # Post-processing based on analysis level
            if analysis_level in [AnalysisLevel.COMPREHENSIVE, AnalysisLevel.DEEP]:
                all_nodes, all_edges = await self._enhance_analysis(
                    all_nodes, all_edges
                )

            # Filter external dependencies if requested
            if not include_external_deps:
                all_nodes, all_edges = self._filter_external_deps(all_nodes, all_edges)

            # Create architecture graph
            graph = ArchitectureGraph(
                graph_id=graph_id,
                nodes=all_nodes,
                edges=all_edges,
                metadata={
                    "analysis_level": analysis_level.value,
                    "workspace_root": str(self.workspace_root),
                    "files_analyzed": len(files_to_analyze),
                    "include_external_deps": include_external_deps,
                    "analysis_duration_seconds": (
                        datetime.utcnow() - analysis_start
                    ).total_seconds(),
                },
                created_at=analysis_start,
            )

            # Record in memory
            await self._record_analysis_in_memory(graph)

            self.logger.info(f"Architecture analysis completed: {graph_id}")
            return graph

        except Exception as e:
            self.logger.error(f"Architecture analysis failed: {e}")
            raise

    def _get_analyzable_files(self) -> List[Path]:
        """Get list of files that can be analyzed."""
        files = []

        for root, dirs, filenames in self.workspace_root.walk():
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in self.config["excluded_dirs"]]

            for filename in filenames:
                file_path = root / filename

                # Check file extension
                if file_path.suffix in self.analyzers:
                    # Check file size (skip very large files)
                    try:
                        if file_path.stat().st_size < 1_000_000:  # 1MB limit
                            files.append(file_path)
                    except OSError:
                        continue

        # Limit number of files
        return files[: self.config["max_files"]]

    def _get_analyzer_for_file(
        self, file_path: Path
    ) -> Optional[Union[PythonAnalyzer, JavaScriptAnalyzer]]:
        """Get appropriate analyzer for file."""
        return self.analyzers.get(file_path.suffix)

    async def _enhance_analysis(
        self, nodes: Dict[str, GraphNode], edges: List[GraphEdge]
    ) -> Tuple[Dict[str, GraphNode], List[GraphEdge]]:
        """Enhance analysis with additional insights."""
        # This could include:
        # - Cross-file function call analysis
        # - API route detection
        # - Database table relationships
        # - Component dependency analysis

        return nodes, edges

    def _filter_external_deps(
        self, nodes: Dict[str, GraphNode], edges: List[GraphEdge]
    ) -> Tuple[Dict[str, GraphNode], List[GraphEdge]]:
        """Filter out external dependencies."""
        # Remove external dependency nodes
        filtered_nodes = {
            node_id: node
            for node_id, node in nodes.items()
            if node.node_type != NodeType.EXTERNAL_DEPENDENCY
        }

        # Remove edges to external dependencies
        remaining_node_ids = set(filtered_nodes.keys())
        filtered_edges = [
            edge
            for edge in edges
            if edge.source_id in remaining_node_ids
            and edge.target_id in remaining_node_ids
        ]

        return filtered_nodes, filtered_edges

    def generate_networkx_graph(self, arch_graph: ArchitectureGraph) -> nx.DiGraph:
        """
        Convert architecture graph to NetworkX graph for analysis.

        Args:
            arch_graph: Architecture graph

        Returns:
            NetworkX directed graph
        """
        G = nx.DiGraph()

        # Add nodes
        for node in arch_graph.nodes.values():
            G.add_node(
                node.node_id,
                name=node.name,
                type=node.node_type.value,
                file_path=node.file_path,
                line_number=node.line_number,
                **node.metadata,
            )

        # Add edges
        for edge in arch_graph.edges:
            G.add_edge(
                edge.source_id,
                edge.target_id,
                type=edge.edge_type.value,
                weight=edge.weight,
                **edge.metadata,
            )

        return G

    def calculate_metrics(self, arch_graph: ArchitectureGraph) -> Dict[str, Any]:
        """
        Calculate architecture metrics.

        Args:
            arch_graph: Architecture graph

        Returns:
            Dictionary of metrics
        """
        G = self.generate_networkx_graph(arch_graph)

        metrics = {
            "node_count": len(G.nodes()),
            "edge_count": len(G.edges()),
            "density": nx.density(G),
            "is_connected": nx.is_weakly_connected(G),
            "connected_components": nx.number_weakly_connected_components(G),
            "average_clustering": nx.average_clustering(G.to_undirected()),
            "diameter": 0,  # Will calculate if connected
            "radius": 0,  # Will calculate if connected
            "centrality_measures": {},
        }

        # Calculate diameter and radius if graph is connected
        if metrics["is_connected"]:
            undirected_G = G.to_undirected()
            try:
                metrics["diameter"] = nx.diameter(undirected_G)
                metrics["radius"] = nx.radius(undirected_G)
            except nx.NetworkXError:
                pass  # Graph might be empty

        # Calculate centrality measures for top nodes
        if len(G.nodes()) > 0:
            try:
                degree_centrality = nx.degree_centrality(G)
                betweenness_centrality = nx.betweenness_centrality(G)
                closeness_centrality = nx.closeness_centrality(G)

                # Get top 10 nodes by degree centrality
                top_nodes = sorted(
                    degree_centrality.items(), key=lambda x: x[1], reverse=True
                )[:10]

                metrics["centrality_measures"] = {
                    "top_degree_centrality": [
                        {
                            "node_id": node_id,
                            "name": G.nodes[node_id].get("name", node_id),
                            "degree_centrality": degree_centrality[node_id],
                            "betweenness_centrality": betweenness_centrality.get(
                                node_id, 0
                            ),
                            "closeness_centrality": closeness_centrality.get(
                                node_id, 0
                            ),
                        }
                        for node_id, _ in top_nodes
                    ]
                }
            except Exception as e:
                self.logger.warning(f"Failed to calculate centrality measures: {e}")

        return metrics

    def detect_patterns(self, arch_graph: ArchitectureGraph) -> Dict[str, Any]:
        """
        Detect common architectural patterns.

        Args:
            arch_graph: Architecture graph

        Returns:
            Detected patterns
        """
        patterns = {
            "layered_architecture": False,
            "microservices": False,
            "mvc_pattern": False,
            "singleton_pattern": [],
            "factory_pattern": [],
            "observer_pattern": [],
            "circular_dependencies": [],
            "god_classes": [],
            "dead_code": [],
        }

        G = self.generate_networkx_graph(arch_graph)

        # Detect circular dependencies
        try:
            cycles = list(nx.simple_cycles(G))
            patterns["circular_dependencies"] = [
                {"cycle": cycle, "length": len(cycle)}
                for cycle in cycles[:10]  # Limit to first 10
            ]
        except Exception:
            pass

        # Detect god classes (high in-degree nodes)
        if len(G.nodes()) > 0:
            in_degrees = dict(G.in_degree())
            avg_in_degree = sum(in_degrees.values()) / len(in_degrees)

            god_classes = [
                {
                    "node_id": node_id,
                    "name": G.nodes[node_id].get("name", node_id),
                    "in_degree": degree,
                }
                for node_id, degree in in_degrees.items()
                if degree > avg_in_degree * 3 and degree > 10  # Threshold
            ]

            patterns["god_classes"] = sorted(
                god_classes, key=lambda x: x["in_degree"], reverse=True
            )[:5]

        # Detect dead code (nodes with no outgoing edges)
        dead_code = [
            {
                "node_id": node_id,
                "name": G.nodes[node_id].get("name", node_id),
                "type": G.nodes[node_id].get("type", "unknown"),
            }
            for node_id in G.nodes()
            if G.out_degree(node_id) == 0 and G.nodes[node_id].get("type") == "function"
        ]

        patterns["dead_code"] = dead_code[:10]  # Limit results

        return patterns

    async def _record_analysis_in_memory(self, graph: ArchitectureGraph):
        """Record architecture analysis in episodic memory."""
        try:
            await self.memory.record_event(
                event_type=MemoryEventType.ARCHITECTURAL_DECISION,
                content=f"Architecture analysis completed: {graph.graph_id}",
                metadata={
                    "graph_id": graph.graph_id,
                    "total_nodes": len(graph.nodes),
                    "total_edges": len(graph.edges),
                    "analysis_level": graph.metadata.get("analysis_level"),
                    "files_analyzed": graph.metadata.get("files_analyzed", 0),
                    "analysis_duration": graph.metadata.get(
                        "analysis_duration_seconds", 0
                    ),
                },
            )
        except Exception as e:
            self.logger.warning(f"Failed to record analysis in memory: {e}")


class GraphVisualizer:
    """
    Generates visualization data for architecture graphs.
    """

    @staticmethod
    def generate_d3_data(arch_graph: ArchitectureGraph) -> Dict[str, Any]:
        """
        Generate D3.js compatible data for visualization.

        Args:
            arch_graph: Architecture graph

        Returns:
            D3.js format data
        """
        nodes = []
        links = []

        # Convert nodes
        for node in arch_graph.nodes.values():
            nodes.append(
                {
                    "id": node.node_id,
                    "name": node.name,
                    "type": node.node_type.value,
                    "group": node.node_type.value,
                    "file_path": node.file_path,
                    "line_number": node.line_number,
                    "metadata": node.metadata,
                }
            )

        # Convert edges to links
        for edge in arch_graph.edges:
            links.append(
                {
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": edge.edge_type.value,
                    "weight": edge.weight,
                    "metadata": edge.metadata,
                }
            )

        return {"nodes": nodes, "links": links, "metadata": arch_graph.metadata}

    @staticmethod
    def generate_hierarchical_data(arch_graph: ArchitectureGraph) -> Dict[str, Any]:
        """
        Generate hierarchical tree data for visualization.

        Args:
            arch_graph: Architecture graph

        Returns:
            Hierarchical tree structure
        """
        # Group nodes by file
        files = {}

        for node in arch_graph.nodes.values():
            if node.node_type == NodeType.FILE:
                files[node.node_id] = {
                    "name": node.name,
                    "type": "file",
                    "children": [],
                }

        # Add contained nodes to files
        for edge in arch_graph.edges:
            if edge.edge_type == EdgeType.CONTAINS:
                source_node = arch_graph.nodes.get(edge.source_id)
                target_node = arch_graph.nodes.get(edge.target_id)

                if (
                    source_node
                    and target_node
                    and source_node.node_type == NodeType.FILE
                ):
                    files[edge.source_id]["children"].append(
                        {
                            "name": target_node.name,
                            "type": target_node.node_type.value,
                            "id": target_node.node_id,
                            "line_number": target_node.line_number,
                        }
                    )

        return {"name": "Architecture", "children": list(files.values())}
