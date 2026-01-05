"""
IncidentGraph — Causal Reasoning Engine

Builds relationships between incidents to identify patterns and root causes.
This enables NAVI to understand:
- Same file → multiple failures (hot spot analysis)
- Same test → intermittent failures (flaky test detection)
- Same author → repeated regressions (developer coaching opportunities)
- Same dependency → cascading breakage (architectural issues)
- Temporal patterns → systemic issues

This is the foundation for systems thinking and incident-level intelligence.
"""

import logging
from collections import defaultdict, Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Optional, Any
from .incident_store import Incident, IncidentType

logger = logging.getLogger(__name__)


@dataclass
class GraphNode:
    """A node in the incident graph representing an entity (file, author, test, etc.)"""

    entity_id: str
    entity_type: str  # "file", "author", "test", "dependency", "service"
    incident_ids: Set[str]
    first_seen: datetime
    last_seen: datetime
    failure_count: int


@dataclass
class GraphEdge:
    """An edge in the incident graph representing a relationship"""

    source: str
    target: str
    relationship_type: str  # "co_occurs", "causes", "depends_on", "authored_by"
    strength: float  # How strong is this relationship (0.0 to 1.0)
    incident_ids: Set[str]


@dataclass
class CausalPattern:
    """A causal pattern discovered in the incident graph"""

    pattern_type: str  # "hotspot", "cascade", "flaky", "author_pattern"
    entities: List[str]
    confidence: float
    incidents: List[str]
    description: str
    suggested_action: str


class IncidentGraph:
    """
    Causal reasoning engine that builds and analyzes relationships
    between incidents to identify systemic patterns and root causes.
    """

    def __init__(self):
        """Initialize the incident graph"""
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[Tuple[str, str], GraphEdge] = {}
        self.patterns: List[CausalPattern] = []
        logger.info("IncidentGraph initialized for causal reasoning")

    def build_from_incidents(self, incidents: List[Incident]) -> None:
        """Build the incident graph from a list of incidents"""
        logger.info(f"Building incident graph from {len(incidents)} incidents")

        # Clear existing graph
        self.nodes.clear()
        self.edges.clear()
        self.patterns.clear()

        # Build nodes for different entity types
        self._build_file_nodes(incidents)
        self._build_author_nodes(incidents)
        self._build_dependency_nodes(incidents)
        self._build_service_nodes(incidents)

        # Build relationships (edges)
        self._build_co_occurrence_edges(incidents)
        self._build_authorship_edges(incidents)
        self._build_dependency_edges(incidents)
        self._build_temporal_edges(incidents)

        # Analyze patterns
        self._analyze_patterns()

        logger.info(
            f"Built graph with {len(self.nodes)} nodes and {len(self.edges)} edges"
        )

    def _build_file_nodes(self, incidents: List[Incident]) -> None:
        """Build nodes for files involved in incidents"""
        file_incidents = defaultdict(set)
        file_timestamps = defaultdict(list)

        for incident in incidents:
            for file_path in incident.files:
                file_incidents[file_path].add(incident.id)
                file_timestamps[file_path].append(incident.timestamp)

        for file_path, incident_ids in file_incidents.items():
            timestamps = file_timestamps[file_path]
            self.nodes[f"file:{file_path}"] = GraphNode(
                entity_id=file_path,
                entity_type="file",
                incident_ids=incident_ids,
                first_seen=min(timestamps),
                last_seen=max(timestamps),
                failure_count=len(incident_ids),
            )

    def _build_author_nodes(self, incidents: List[Incident]) -> None:
        """Build nodes for authors involved in incidents"""
        author_incidents = defaultdict(set)
        author_timestamps = defaultdict(list)

        for incident in incidents:
            if incident.author:
                author_incidents[incident.author].add(incident.id)
                author_timestamps[incident.author].append(incident.timestamp)

        for author, incident_ids in author_incidents.items():
            timestamps = author_timestamps[author]
            self.nodes[f"author:{author}"] = GraphNode(
                entity_id=author,
                entity_type="author",
                incident_ids=incident_ids,
                first_seen=min(timestamps),
                last_seen=max(timestamps),
                failure_count=len(incident_ids),
            )

    def _build_dependency_nodes(self, incidents: List[Incident]) -> None:
        """Build nodes for dependencies involved in incidents"""
        for incident in incidents:
            if incident.incident_type == IncidentType.DEPENDENCY_ISSUE:
                # Extract dependency info from error message or tags
                if incident.tags:
                    for tag in incident.tags:
                        if tag.startswith("dependency:"):
                            dep_name = tag.replace("dependency:", "")
                            node_id = f"dependency:{dep_name}"

                            if node_id not in self.nodes:
                                self.nodes[node_id] = GraphNode(
                                    entity_id=dep_name,
                                    entity_type="dependency",
                                    incident_ids={incident.id},
                                    first_seen=incident.timestamp,
                                    last_seen=incident.timestamp,
                                    failure_count=1,
                                )
                            else:
                                node = self.nodes[node_id]
                                node.incident_ids.add(incident.id)
                                node.last_seen = max(node.last_seen, incident.timestamp)
                                node.failure_count += 1

    def _build_service_nodes(self, incidents: List[Incident]) -> None:
        """Build nodes for services based on file paths"""
        service_incidents = defaultdict(set)
        service_timestamps = defaultdict(list)

        for incident in incidents:
            # Infer service from file paths (basic heuristic)
            services = self._infer_services_from_files(incident.files)
            for service in services:
                service_incidents[service].add(incident.id)
                service_timestamps[service].append(incident.timestamp)

        for service, incident_ids in service_incidents.items():
            timestamps = service_timestamps[service]
            self.nodes[f"service:{service}"] = GraphNode(
                entity_id=service,
                entity_type="service",
                incident_ids=incident_ids,
                first_seen=min(timestamps),
                last_seen=max(timestamps),
                failure_count=len(incident_ids),
            )

    def _infer_services_from_files(self, files: List[str]) -> Set[str]:
        """Infer service names from file paths using common patterns"""
        services = set()

        for file_path in files:
            parts = file_path.split("/")

            # Common service directory patterns
            if "services" in parts:
                idx = parts.index("services")
                if idx + 1 < len(parts):
                    services.add(parts[idx + 1])
            elif "src" in parts and len(parts) > parts.index("src") + 1:
                idx = parts.index("src")
                if idx + 1 < len(parts):
                    services.add(parts[idx + 1])
            elif parts and not parts[0].startswith("."):
                # Use top-level directory as service name
                services.add(parts[0])

        return services

    def _build_co_occurrence_edges(self, incidents: List[Incident]) -> None:
        """Build edges for entities that co-occur in incidents"""
        # File co-occurrence
        for incident in incidents:
            files = [f"file:{f}" for f in incident.files]
            for i, file1 in enumerate(files):
                for file2 in files[i + 1 :]:
                    self._add_or_update_edge(
                        file1, file2, "co_occurs", 0.1, incident.id
                    )

    def _build_authorship_edges(self, incidents: List[Incident]) -> None:
        """Build edges for author relationships"""
        for incident in incidents:
            if incident.author:
                author_node = f"author:{incident.author}"
                for file_path in incident.files:
                    file_node = f"file:{file_path}"
                    self._add_or_update_edge(
                        author_node, file_node, "authored_by", 0.3, incident.id
                    )

    def _build_dependency_edges(self, incidents: List[Incident]) -> None:
        """Build edges for dependency relationships"""
        # This would be enhanced with actual dependency analysis
        for incident in incidents:
            if (
                incident.incident_type == IncidentType.DEPENDENCY_ISSUE
                and incident.tags
            ):
                for tag in incident.tags:
                    if tag.startswith("dependency:"):
                        dep_name = tag.replace("dependency:", "")
                        dep_node = f"dependency:{dep_name}"
                        for file_path in incident.files:
                            file_node = f"file:{file_path}"
                            self._add_or_update_edge(
                                dep_node, file_node, "depends_on", 0.5, incident.id
                            )

    def _build_temporal_edges(self, incidents: List[Incident]) -> None:
        """Build edges for temporal relationships (cascading failures)"""
        # Sort incidents by timestamp
        sorted_incidents = sorted(incidents, key=lambda i: i.timestamp)

        # Look for incidents within a short time window (potential cascades)
        for i, incident1 in enumerate(sorted_incidents):
            for incident2 in sorted_incidents[i + 1 :]:
                time_diff = incident2.timestamp - incident1.timestamp

                # If incidents are within 1 hour and involve related entities
                if time_diff <= timedelta(hours=1):
                    if self._have_shared_entities(incident1, incident2):
                        # Create temporal relationship
                        node1 = f"incident:{incident1.id}"
                        node2 = f"incident:{incident2.id}"
                        strength = max(
                            0.1, 1.0 - (time_diff.total_seconds() / 3600)
                        )  # Closer in time = stronger
                        self._add_or_update_edge(
                            node1, node2, "temporal_cascade", strength, incident2.id
                        )
                else:
                    # Beyond time window, stop looking
                    break

    def _have_shared_entities(self, incident1: Incident, incident2: Incident) -> bool:
        """Check if two incidents share any entities (files, author, etc.)"""
        return (
            bool(set(incident1.files) & set(incident2.files))  # Shared files
            or (
                incident1.author and incident1.author == incident2.author
            )  # Same author
            or (incident1.repo == incident2.repo)  # Same repo
        )

    def _add_or_update_edge(
        self,
        source: str,
        target: str,
        relationship_type: str,
        strength: float,
        incident_id: str,
    ) -> None:
        """Add or update an edge in the graph"""
        edge_key = (source, target)

        if edge_key in self.edges:
            edge = self.edges[edge_key]
            edge.strength += strength
            edge.incident_ids.add(incident_id)
        else:
            self.edges[edge_key] = GraphEdge(
                source=source,
                target=target,
                relationship_type=relationship_type,
                strength=strength,
                incident_ids={incident_id},
            )

    def _analyze_patterns(self) -> None:
        """Analyze the graph to identify causal patterns"""
        self.patterns.clear()

        # Identify hotspots (files with many failures)
        self._identify_hotspots()

        # Identify flaky tests
        self._identify_flaky_patterns()

        # Identify author patterns
        self._identify_author_patterns()

        # Identify cascade patterns
        self._identify_cascade_patterns()

        logger.info(f"Identified {len(self.patterns)} causal patterns")

    def _identify_hotspots(self) -> None:
        """Identify files that are failure hotspots"""
        file_nodes = {k: v for k, v in self.nodes.items() if v.entity_type == "file"}

        # Files with 3+ failures are considered hotspots
        hotspots = {k: v for k, v in file_nodes.items() if v.failure_count >= 3}

        for node_id, node in hotspots.items():
            confidence = min(1.0, node.failure_count / 10.0)  # Cap at 1.0

            self.patterns.append(
                CausalPattern(
                    pattern_type="hotspot",
                    entities=[node.entity_id],
                    confidence=confidence,
                    incidents=list(node.incident_ids),
                    description=f"File '{node.entity_id}' has {node.failure_count} failures - potential hotspot",
                    suggested_action="Consider refactoring or adding defensive programming",
                )
            )

    def _identify_flaky_patterns(self) -> None:
        """Identify flaky test patterns from temporal inconsistencies"""
        test_files = {
            k: v
            for k, v in self.nodes.items()
            if v.entity_type == "file"
            and ("test" in v.entity_id.lower() or "spec" in v.entity_id.lower())
        }

        for node_id, node in test_files.items():
            # If test fails intermittently (multiple incidents but not resolved consistently)
            if node.failure_count >= 2:
                time_span = node.last_seen - node.first_seen
                if time_span.days > 1:  # Failures over multiple days
                    confidence = min(1.0, node.failure_count / 5.0)

                    self.patterns.append(
                        CausalPattern(
                            pattern_type="flaky_test",
                            entities=[node.entity_id],
                            confidence=confidence,
                            incidents=list(node.incident_ids),
                            description=f"Test '{node.entity_id}' fails intermittently over {time_span.days} days",
                            suggested_action="Stabilize test or quarantine until fixed",
                        )
                    )

    def _identify_author_patterns(self) -> None:
        """Identify patterns in author-related failures"""
        author_nodes = {
            k: v for k, v in self.nodes.items() if v.entity_type == "author"
        }

        for node_id, node in author_nodes.items():
            if node.failure_count >= 3:  # Author involved in 3+ incidents
                confidence = min(1.0, node.failure_count / 8.0)

                self.patterns.append(
                    CausalPattern(
                        pattern_type="author_pattern",
                        entities=[node.entity_id],
                        confidence=confidence,
                        incidents=list(node.incident_ids),
                        description=f"Author '{node.entity_id}' associated with {node.failure_count} incidents",
                        suggested_action="Consider pair programming or code review focus",
                    )
                )

    def _identify_cascade_patterns(self) -> None:
        """Identify cascade failure patterns from temporal edges"""
        cascade_edges = [
            e for e in self.edges.values() if e.relationship_type == "temporal_cascade"
        ]

        if len(cascade_edges) >= 2:  # At least 2 cascading relationships
            entities = set()
            incidents = set()

            for edge in cascade_edges:
                entities.update([edge.source, edge.target])
                incidents.update(edge.incident_ids)

            confidence = min(1.0, len(cascade_edges) / 5.0)

            self.patterns.append(
                CausalPattern(
                    pattern_type="cascade",
                    entities=list(entities),
                    confidence=confidence,
                    incidents=list(incidents),
                    description=f"Detected {len(cascade_edges)} cascading failure relationships",
                    suggested_action="Investigate system dependencies and add circuit breakers",
                )
            )

    def get_hotspots(self, min_failures: int = 3) -> List[GraphNode]:
        """Get file nodes that are failure hotspots"""
        return [
            node
            for node in self.nodes.values()
            if node.entity_type == "file" and node.failure_count >= min_failures
        ]

    def get_patterns_by_type(self, pattern_type: str) -> List[CausalPattern]:
        """Get patterns of a specific type"""
        return [p for p in self.patterns if p.pattern_type == pattern_type]

    def get_related_entities(
        self, entity_id: str, relationship_type: Optional[str] = None
    ) -> List[str]:
        """Get entities related to a given entity"""
        related = []

        for (source, target), edge in self.edges.items():
            if relationship_type is None or edge.relationship_type == relationship_type:
                if source == entity_id:
                    related.append(target)
                elif target == entity_id:
                    related.append(source)

        return related

    def get_graph_summary(self) -> Dict[str, Any]:
        """Get a summary of the incident graph"""
        node_types = Counter(node.entity_type for node in self.nodes.values())
        edge_types = Counter(edge.relationship_type for edge in self.edges.values())
        pattern_types = Counter(pattern.pattern_type for pattern in self.patterns)

        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "total_patterns": len(self.patterns),
            "node_types": dict(node_types),
            "edge_types": dict(edge_types),
            "pattern_types": dict(pattern_types),
            "top_hotspots": [
                {"entity": node.entity_id, "failures": node.failure_count}
                for node in sorted(
                    self.nodes.values(), key=lambda n: n.failure_count, reverse=True
                )[:5]
                if node.entity_type == "file"
            ],
        }


def build_incident_graph(incidents: List[Incident]) -> IncidentGraph:
    """Utility function to build an incident graph from incidents"""
    graph = IncidentGraph()
    graph.build_from_incidents(incidents)
    return graph
