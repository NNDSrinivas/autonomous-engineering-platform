"""Temporal Reasoner - Timeline construction and causality path finding

This module provides temporal reasoning capabilities for the Memory Graph:
1. timeline_for(): Construct ordered event sequences using next/previous edges
2. explain(): Find causality paths and generate narratives with citations

Uses weighted BFS for uniform weights, Dijkstra for variable weights.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set
from sqlalchemy.orm import Session

from backend.database.models.memory_graph import MemoryNode, MemoryEdge, EdgeRelation
from backend.core.ai_service import AIService
from backend.core.constants import (
    JIRA_KEY_PATTERN,
    MAX_CAUSALITY_PATHS,
    MAX_EDGES_IN_CONTEXT,
    MAX_PATH_LENGTH,
    MAX_PATHS_IN_CONTEXT,
    PR_NUMBER_PATTERN,
    SLACK_THREAD_PATTERN,
)

logger = logging.getLogger(__name__)


class TemporalReasoner:
    """Constructs timelines and explains causality chains in the memory graph"""

    def __init__(self, db: Session, ai_service: AIService):
        self.db = db
        self.ai_service = ai_service

    def timeline_for(
        self, org_id: str, root_foreign_id: str, window: str = "30d"
    ) -> Dict[str, Any]:
        """Construct timeline for an entity within a time window

        Args:
            org_id: Organization ID for scoping
            root_foreign_id: Entity identifier (e.g., "ENG-102", "PR#456")
            window: Time window (e.g., "30d", "7d", "90d")

        Returns:
            Dict with nodes, edges, timeline (chronologically ordered events)
        """
        logger.info(f"Building timeline for {root_foreign_id}, window={window}")

        # Parse window
        days = self._parse_window(window)
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Find root node
        root_node = (
            self.db.query(MemoryNode)
            .filter_by(org_id=org_id, foreign_id=root_foreign_id)
            .first()
        )

        if not root_node:
            return {
                "nodes": [],
                "edges": [],
                "timeline": [],
                "error": f"Node {root_foreign_id} not found",
            }

        # Build subgraph (1-hop neighborhood within window)
        nodes, edges = self._build_subgraph(root_node, depth=1, since=cutoff_date)

        # Sort nodes by timestamp to create timeline
        timeline = self._create_timeline(nodes, edges)

        return {
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "timeline": timeline,
            "root_id": root_node.id,
            "root_foreign_id": root_foreign_id,
        }

    def explain(
        self, org_id: str, query: str, depth: int = 3, k: int = 12
    ) -> Dict[str, Any]:
        """Explain a query by finding paths and generating narrative

        Args:
            org_id: Organization ID for scoping
            query: Natural language query (e.g., "why was ENG-102 reopened?")
            depth: Maximum path depth to search
            k: Maximum number of nodes to return

        Returns:
            Dict with nodes, edges, timeline, narrative, paths
        """
        logger.info(f"Explaining query: '{query}', depth={depth}, k={k}")

        # Extract entities from query (JIRA keys, PR numbers)
        entities = self._extract_entities(query)

        if not entities:
            return {
                "nodes": [],
                "edges": [],
                "timeline": [],
                "narrative": "No entities found in query. Please mention a JIRA issue, PR number, or specific artifact.",
                "paths": [],
            }

        # Find nodes for entities
        source_nodes = (
            self.db.query(MemoryNode)
            .filter(
                MemoryNode.org_id == org_id,
                MemoryNode.foreign_id.in_(entities),
            )
            .all()
        )

        if not source_nodes:
            return {
                "nodes": [],
                "edges": [],
                "timeline": [],
                "narrative": f"Entities {entities} not found in memory graph.",
                "paths": [],
            }

        # Build subgraph around source nodes
        all_nodes = set()
        all_edges = set()
        for node in source_nodes:
            nodes, edges = self._build_subgraph(node, depth=depth)
            all_nodes.update(nodes)
            all_edges.update(edges)

        # Limit to top k nodes by relevance
        if len(all_nodes) > k:
            all_nodes = set(
                sorted(all_nodes, key=lambda n: n.created_at, reverse=True)[:k]
            )

        # Find interesting paths (with caused_by, fixes, derived_from relations)
        paths = self._find_causality_paths(
            list(all_nodes), list(all_edges), source_nodes
        )

        # Create timeline
        timeline = self._create_timeline(list(all_nodes), list(all_edges))

        # Generate narrative via model router
        narrative = self._generate_narrative(
            query, list(all_nodes), list(all_edges), paths, k
        )

        return {
            "nodes": [n.to_dict() for n in all_nodes],
            "edges": [e.to_dict() for e in all_edges],
            "timeline": timeline,
            "narrative": narrative,
            "paths": [self._path_to_dict(p) for p in paths],
            "source_entities": entities,
        }

    def _build_subgraph(
        self,
        root: MemoryNode,
        depth: int = 1,
        since: Optional[datetime] = None,
    ) -> Tuple[Set[MemoryNode], Set[MemoryEdge]]:
        """Build subgraph around a root node using BFS

        Args:
            root: Starting node
            depth: Maximum depth (hops) from root
            since: Optional cutoff date

        Returns:
            (nodes, edges) sets
        """
        nodes = {root}
        edges = set()
        visited = {root.id}
        queue = [(root, 0)]  # (node, current_depth)

        while queue:
            current_node, current_depth = queue.pop(0)

            if current_depth >= depth:
                continue

            # Get outbound edges
            for edge in current_node.outbound_edges:
                if edge.org_id != root.org_id:
                    continue  # Enforce org isolation

                # Also verify destination node belongs to same org to prevent data leaks
                if edge.destination_node.org_id != root.org_id:
                    continue

                if since and edge.destination_node.created_at < since:
                    continue

                edges.add(edge)
                if edge.dst_id not in visited:
                    visited.add(edge.dst_id)
                    nodes.add(edge.destination_node)
                    queue.append((edge.destination_node, current_depth + 1))

            # Get inbound edges
            for edge in current_node.inbound_edges:
                if edge.org_id != root.org_id:
                    continue  # Enforce org isolation

                # Also verify source node belongs to same org to prevent data leaks
                if edge.source_node.org_id != root.org_id:
                    continue

                if since and edge.source_node.created_at < since:
                    continue

                edges.add(edge)
                if edge.src_id not in visited:
                    visited.add(edge.src_id)
                    nodes.add(edge.source_node)
                    queue.append((edge.source_node, current_depth + 1))

        return nodes, edges

    def _create_timeline(
        self, nodes: List[MemoryNode], edges: List[MemoryEdge]
    ) -> List[Dict[str, Any]]:
        """Create chronologically ordered timeline from nodes and edges

        Uses timestamps primarily, with next/previous edges as hints
        """
        # Sort nodes by created_at
        sorted_nodes = sorted(nodes, key=lambda n: n.created_at)

        timeline = []
        for node in sorted_nodes:
            # Find related events (edges pointing to/from this node)
            related = [
                e.to_dict() for e in edges if e.src_id == node.id or e.dst_id == node.id
            ]

            timeline.append(
                {
                    "timestamp": node.created_at.isoformat(),
                    "node": node.to_dict(),
                    "related_edges": related,
                }
            )

        return timeline

    def _find_causality_paths(
        self,
        nodes: List[MemoryNode],
        edges: List[MemoryEdge],
        source_nodes: List[MemoryNode],
    ) -> List[List[Tuple[MemoryNode, MemoryEdge]]]:
        """Find interesting causality paths using weighted BFS/Dijkstra

        Focuses on caused_by, fixes, derived_from relations
        """
        causality_relations = {
            EdgeRelation.CAUSED_BY.value,
            EdgeRelation.FIXES.value,
            EdgeRelation.DERIVED_FROM.value,
            EdgeRelation.IMPLEMENTS.value,
        }

        # Build adjacency list
        adj: Dict[int, List[Tuple[MemoryNode, MemoryEdge]]] = {}
        node_map = {n.id: n for n in nodes}

        for edge in edges:
            if edge.relation not in causality_relations:
                continue

            if edge.src_id not in adj:
                adj[edge.src_id] = []
            if edge.dst_id in node_map:
                adj[edge.src_id].append((node_map[edge.dst_id], edge))

        paths = []

        # Find paths from each source node
        for source in source_nodes:
            # Check global path limit before processing next source
            if len(paths) >= MAX_CAUSALITY_PATHS:
                break

            if source.id not in adj:
                continue

            # Weighted BFS (assuming relatively uniform weights)
            visited = {source.id}
            queue = [(source, [])]  # (node, path_so_far)

            while (
                queue and len(paths) < MAX_CAUSALITY_PATHS
            ):  # Prevent excessive path exploration that could impact performance and context length
                current_node, path = queue.pop(0)

                if (
                    len(path) >= MAX_PATH_LENGTH
                ):  # Use constant instead of hardcoded value
                    continue

                if current_node.id not in adj:
                    if path:  # Only add non-empty paths
                        paths.append(path)
                        # Break from while loop if limit reached
                        if len(paths) >= MAX_CAUSALITY_PATHS:
                            break
                    continue

                for next_node, edge in adj[current_node.id]:
                    if next_node.id in visited:
                        continue

                    visited.add(next_node.id)
                    new_path = path + [(current_node, edge)]
                    queue.append((next_node, new_path))

        return paths

    def _generate_narrative(
        self,
        query: str,
        nodes: List[MemoryNode],
        edges: List[MemoryEdge],
        paths: List[List[Tuple[MemoryNode, MemoryEdge]]],
        k: int = 10,
    ) -> str:
        """Generate natural language narrative using AI model

        Args:
            query: Original user query
            nodes: Relevant nodes in graph
            edges: Relevant edges
            paths: Causality paths found
            k: Maximum nodes to include in context (respects caller's limit)

        Returns:
            Natural language explanation with citations
        """
        # Format context for LLM
        context = f"Query: {query}\n\n"

        context += "## Relevant Entities:\n"
        # Respect caller's k parameter while protecting against excessive context
        for node in nodes[
            :k
        ]:  # Respects the caller's specified k limit for context size
            context += (
                f"- [{node.foreign_id}] {node.title or 'Untitled'} ({node.kind})\n"
            )
            if node.summary:
                context += f"  Summary: {node.summary[:200]}...\n"

        context += "\n## Relationships:\n"
        for edge in edges[:MAX_EDGES_IN_CONTEXT]:  # Limit context
            src = next((n for n in nodes if n.id == edge.src_id), None)
            dst = next((n for n in nodes if n.id == edge.dst_id), None)
            if src and dst:
                context += f"- {src.foreign_id} --[{edge.relation}]--> {dst.foreign_id} (confidence: {edge.confidence:.2f})\n"

        context += "\n## Causality Chains:\n"
        for i, path in enumerate(paths[:MAX_PATHS_IN_CONTEXT]):  # Limit paths
            context += f"Path {i+1}: "
            path_str = " → ".join(
                [f"{node.foreign_id} ({edge.relation})" for node, edge in path]
            )
            context += path_str + "\n"

        # Generate narrative
        prompt = f"""Based on the following memory graph data, provide a clear explanation answering the query.
Include specific references to entity IDs (like ENG-102, PR#456) as citations.
Explain the causal chain if one exists.

{context}

Provide a concise explanation (2-3 paragraphs) that directly answers the query."""

        try:
            narrative = self.ai_service.generate_text(
                prompt=prompt,
                max_tokens=500,
                temperature=0.3,  # Lower temperature for factual responses
            )
            return narrative
        except Exception as e:
            logger.error(f"Error generating narrative: {e}")
            return f"Found {len(nodes)} related entities and {len(edges)} relationships. Manual review recommended."

    def _extract_entities(self, query: str) -> List[str]:
        """Extract entity identifiers from query text using shared patterns"""
        entities = []

        # JIRA keys
        entities.extend(JIRA_KEY_PATTERN.findall(query))

        # PR numbers
        pr_matches = PR_NUMBER_PATTERN.findall(query)
        entities.extend([f"#{m}" for m in pr_matches])

        # Slack thread IDs
        entities.extend(SLACK_THREAD_PATTERN.findall(query))

        return list(set(entities))

    def _parse_window(self, window: str) -> int:
        """Parse window string to days (e.g., '30d' -> 30, '7d' -> 7)"""
        match = re.match(r"(\d+)d", window.lower())
        if match:
            return int(match.group(1))
        return 30  # Default

    def _path_to_dict(
        self, path: List[Tuple[MemoryNode, MemoryEdge]]
    ) -> Dict[str, Any]:
        """Convert path to dict for JSON serialization"""
        return {
            "steps": [
                {
                    "node": node.to_dict(),
                    "edge": edge.to_dict(),
                }
                for node, edge in path
            ],
            "length": len(path),
        }
