"""Memory Graph Builder - Creates nodes and edges from artifacts

This worker implements batch and streaming graph construction with multiple
heuristics for detecting relationships between entities.

Heuristics implemented:
1. JIRA key matching: Extract JIRA keys from PR titles, commits, Slack messages
2. PR fixes/closes: Parse PR descriptions for "fixes #123", "closes JIRA-456"
3. Slack thread links: Thread replies create 'discusses' edges
4. Temporal adjacency: Meeting -> PR within TEMPORAL_WINDOW_HOURS with shared terms
5. Semantic similarity: Embedding cosine > threshold
6. Commit reverts: Detect git revert commits for 'caused_by' edges
"""

import re
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database.models.memory_graph import (
    MemoryNode,
    MemoryEdge,
    NodeKind,
    EdgeRelation,
)
from backend.core.ai_service import AIService
from backend.core.constants import (
    JIRA_KEY_PATTERN,
    PR_NUMBER_PATTERN,
    FIXES_PATTERN,
    REVERT_PATTERN,
    TEMPORAL_WINDOW_HOURS,
    MIN_SHARED_TERMS_COUNT,
    STOPWORDS,
)

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds and maintains the memory graph from artifacts"""

    def __init__(self, db: Session, ai_service: AIService):
        self.db = db
        self.ai_service = ai_service

    def rebuild_graph(
        self, org_id: str, since: Optional[datetime] = None
    ) -> Dict[str, int]:
        """Batch rebuild graph for an organization

        Args:
            org_id: Organization ID
            since: Optional start date (default: 90 days ago)

        Returns:
            Dict with nodes_created, edges_created counts
        """
        if since is None:
            since = datetime.utcnow() - timedelta(days=90)

        logger.info(f"Starting graph rebuild for org={org_id}, since={since}")

        stats = {"nodes_created": 0, "edges_created": 0, "nodes_updated": 0}

        # Step 1: Create/update nodes from all artifact sources
        stats["nodes_created"] += self._sync_nodes_from_memory_objects(org_id, since)

        # Step 2: Create edges using all heuristics
        stats["edges_created"] += self._create_edges_batch(org_id, since)

        logger.info(f"Graph rebuild complete: {stats}")
        return stats

    def attach_edges_for(self, node_id: int) -> int:
        """Streaming: attach edges for a newly created node

        Args:
            node_id: ID of the node to attach edges for

        Returns:
            Number of edges created
        """
        node = self.db.query(MemoryNode).filter_by(id=node_id).first()
        if not node:
            logger.warning(f"Node {node_id} not found")
            return 0

        logger.info(
            f"Attaching edges for node {node_id} ({node.kind}:{node.foreign_id})"
        )

        edges_created = 0

        # Get recent nodes (last 30 days) for potential edges
        recent_cutoff = datetime.utcnow() - timedelta(days=30)
        recent_nodes = (
            self.db.query(MemoryNode)
            .filter(
                MemoryNode.org_id == node.org_id,
                MemoryNode.id != node.id,
                MemoryNode.created_at >= recent_cutoff,
            )
            .all()
        )

        # Apply all heuristics
        for other_node in recent_nodes:
            edges = self._apply_heuristics(node, other_node)
            for edge_data in edges:
                self._create_edge_if_not_exists(**edge_data)
                edges_created += 1

        self.db.commit()
        logger.info(f"Created {edges_created} edges for node {node_id}")
        return edges_created

    def _sync_nodes_from_memory_objects(self, org_id: str, since: datetime) -> int:
        """Create memory_node entries from existing memory_object/chunk data"""
        # Query memory_object for artifacts since date
        rows = self.db.execute(
            text(
                """
                SELECT DISTINCT mo.id, mo.org_id, mo.source, mo.foreign_id,
                       mo.title, mo.url, mo.meta_json, mo.created_at
                FROM memory_object mo
                WHERE mo.org_id = :org_id
                  AND mo.created_at >= :since
                ORDER BY mo.created_at DESC
                """
            ),
            {"org_id": org_id, "since": since},
        ).fetchall()

        nodes_created = 0
        for row in rows:
            # Map source to node kind
            kind = self._map_source_to_kind(row.source)
            if not kind:
                continue

            # Check if node already exists
            existing = (
                self.db.query(MemoryNode)
                .filter_by(org_id=org_id, foreign_id=row.foreign_id)
                .first()
            )

            if not existing:
                # Create new node with safe JSON parsing
                try:
                    meta_json = json.loads(row.meta_json) if row.meta_json else {}
                except json.JSONDecodeError:
                    logger.warning(
                        f"Invalid JSON in meta_json for {row.foreign_id}, using empty dict"
                    )
                    meta_json = {}

                node = MemoryNode(
                    org_id=row.org_id,
                    kind=kind,
                    foreign_id=row.foreign_id,
                    title=row.title,
                    summary=None,  # Will be generated async
                    meta_json=meta_json,
                    created_at=row.created_at,
                )
                self.db.add(node)
                nodes_created += 1

        self.db.commit()
        return nodes_created

    def _create_edges_batch(self, org_id: str, since: datetime) -> int:
        """Create edges for all nodes using heuristics"""
        nodes = (
            self.db.query(MemoryNode)
            .filter(MemoryNode.org_id == org_id, MemoryNode.created_at >= since)
            .all()
        )

        edges_created = 0
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i + 1 :]:
                # Apply bidirectional heuristics
                edges = self._apply_heuristics(node1, node2)
                for edge_data in edges:
                    if self._create_edge_if_not_exists(**edge_data):
                        edges_created += 1

        self.db.commit()
        return edges_created

    def _apply_heuristics(
        self, node1: MemoryNode, node2: MemoryNode
    ) -> List[Dict[str, Any]]:
        """Apply all heuristics to detect relationships between two nodes

        Returns list of edge specifications: {src_id, dst_id, relation, weight, confidence, meta}
        """
        edges = []

        # Heuristic 1: JIRA key matching
        edges.extend(self._heuristic_jira_key_matching(node1, node2))

        # Heuristic 2: PR fixes/closes
        edges.extend(self._heuristic_pr_fixes(node1, node2))

        # Heuristic 3: Slack thread links
        edges.extend(self._heuristic_slack_threads(node1, node2))

        # Heuristic 4: Temporal adjacency
        edges.extend(self._heuristic_temporal_adjacency(node1, node2))

        # Heuristic 5: Semantic similarity (requires embeddings)
        # Skipped in initial implementation - requires embedding vectors

        # Heuristic 6: Commit reverts
        edges.extend(self._heuristic_commit_reverts(node1, node2))

        return edges

    def _heuristic_jira_key_matching(
        self, node1: MemoryNode, node2: MemoryNode
    ) -> List[Dict[str, Any]]:
        """Detect JIRA keys in PR titles, commits, Slack messages"""
        edges = []

        # Extract JIRA keys from both nodes
        keys1 = self._extract_jira_keys(node1)
        keys2 = self._extract_jira_keys(node2)

        # If one is a JIRA issue and the other mentions it
        if node1.kind == NodeKind.JIRA_ISSUE.value and node1.foreign_id in keys2:
            edges.append(
                {
                    "src_id": node2.id,
                    "dst_id": node1.id,
                    "relation": EdgeRelation.REFERENCES.value,
                    "weight": 0.9,
                    "confidence": 0.95,
                    "org_id": node1.org_id,
                    "meta": {"heuristic": "jira_key_match", "key": node1.foreign_id},
                }
            )

        if node2.kind == NodeKind.JIRA_ISSUE.value and node2.foreign_id in keys1:
            edges.append(
                {
                    "src_id": node1.id,
                    "dst_id": node2.id,
                    "relation": EdgeRelation.REFERENCES.value,
                    "weight": 0.9,
                    "confidence": 0.95,
                    "org_id": node2.org_id,
                    "meta": {"heuristic": "jira_key_match", "key": node2.foreign_id},
                }
            )

        return edges

    def _heuristic_pr_fixes(
        self, node1: MemoryNode, node2: MemoryNode
    ) -> List[Dict[str, Any]]:
        """Parse PR descriptions for 'fixes #123', 'closes JIRA-456'"""
        edges = []

        # Check if one is a PR
        pr_node = None
        other_node = None

        if node1.kind == NodeKind.PR.value:
            pr_node = node1
            other_node = node2
        elif node2.kind == NodeKind.PR.value:
            pr_node = node2
            other_node = node1
        else:
            return edges

        # Look for fixes/closes patterns in PR title and description
        pr_text = f"{pr_node.title or ''} {pr_node.summary or ''}"
        matches = FIXES_PATTERN.findall(pr_text)

        for match in matches:
            pr_num, jira_key = match

            # Normalize comparison: PR numbers may or may not have '#' prefix
            matched = False
            if pr_num:
                # Compare numeric part only, safely removing single '#' prefix if present
                foreign_id_normalized = (
                    other_node.foreign_id[1:]
                    if other_node.foreign_id.startswith("#")
                    else other_node.foreign_id
                )
                matched = (
                    pr_num == foreign_id_normalized
                    or f"#{pr_num}" == other_node.foreign_id
                )
            else:
                # JIRA key comparison is exact
                matched = jira_key == other_node.foreign_id

            if matched:
                target_id = f"#{pr_num}" if pr_num else jira_key
                edges.append(
                    {
                        "src_id": pr_node.id,
                        "dst_id": other_node.id,
                        "relation": EdgeRelation.FIXES.value,
                        "weight": 1.0,
                        "confidence": 0.98,
                        "org_id": pr_node.org_id,
                        "meta": {"heuristic": "pr_fixes", "pattern": target_id},
                    }
                )

        return edges

    def _heuristic_slack_threads(
        self, node1: MemoryNode, node2: MemoryNode
    ) -> List[Dict[str, Any]]:
        """Slack thread replies create 'discusses' edges"""
        edges = []

        # Both must be Slack threads
        if (
            node1.kind != NodeKind.SLACK_THREAD.value
            or node2.kind != NodeKind.SLACK_THREAD.value
        ):
            return edges

        # Check if one is a reply to the other (via metadata)
        meta1 = node1.meta_json or {}
        meta2 = node2.meta_json or {}

        if meta1.get("thread_ts") == meta2.get("ts"):
            edges.append(
                {
                    "src_id": node1.id,
                    "dst_id": node2.id,
                    "relation": EdgeRelation.DISCUSSES.value,
                    "weight": 0.8,
                    "confidence": 1.0,
                    "org_id": node1.org_id,
                    "meta": {"heuristic": "slack_thread_reply"},
                }
            )

        if meta2.get("thread_ts") == meta1.get("ts"):
            edges.append(
                {
                    "src_id": node2.id,
                    "dst_id": node1.id,
                    "relation": EdgeRelation.DISCUSSES.value,
                    "weight": 0.8,
                    "confidence": 1.0,
                    "org_id": node2.org_id,
                    "meta": {"heuristic": "slack_thread_reply"},
                }
            )

        return edges

    def _heuristic_temporal_adjacency(
        self, node1: MemoryNode, node2: MemoryNode
    ) -> List[Dict[str, Any]]:
        """Meeting -> PR within 48h with shared terms creates 'derived_from' edge"""
        edges = []

        # Check if one is a meeting and other is PR/doc
        if not (
            (
                node1.kind == NodeKind.MEETING.value
                and node2.kind in [NodeKind.PR.value, NodeKind.DOC.value]
            )
            or (
                node2.kind == NodeKind.MEETING.value
                and node1.kind in [NodeKind.PR.value, NodeKind.DOC.value]
            )
        ):
            return edges

        meeting_node = node1 if node1.kind == NodeKind.MEETING.value else node2
        artifact_node = node2 if node1.kind == NodeKind.MEETING.value else node1

        # Check temporal proximity (within 48 hours)
        time_diff = abs(
            (artifact_node.created_at - meeting_node.created_at).total_seconds() / 3600
        )
        if time_diff > TEMPORAL_WINDOW_HOURS:
            return edges

        # Check shared terms
        shared_terms = self._count_shared_terms(meeting_node, artifact_node)
        if shared_terms >= MIN_SHARED_TERMS_COUNT:
            confidence = min(0.9, 0.5 + (shared_terms / 20))
            edges.append(
                {
                    "src_id": artifact_node.id,
                    "dst_id": meeting_node.id,
                    "relation": EdgeRelation.DERIVED_FROM.value,
                    "weight": 0.7,
                    "confidence": confidence,
                    "org_id": meeting_node.org_id,
                    "meta": {
                        "heuristic": "temporal_adjacency",
                        "time_diff_hours": round(time_diff, 1),
                        "shared_terms": shared_terms,
                    },
                }
            )

        return edges

    def _heuristic_commit_reverts(
        self, node1: MemoryNode, node2: MemoryNode
    ) -> List[Dict[str, Any]]:
        """Detect git revert commits for 'caused_by' edges"""
        edges = []

        # Check if either is a PR/commit with revert in title
        for src_node, dst_node in [(node1, node2), (node2, node1)]:
            if src_node.kind != NodeKind.PR.value:
                continue

            title = (src_node.title or "").lower()
            if REVERT_PATTERN.search(title):
                # Look for PR number or commit reference in title
                references = self._extract_references(src_node.title)
                if dst_node.foreign_id in references:
                    edges.append(
                        {
                            "src_id": dst_node.id,  # Original PR caused issue
                            "dst_id": src_node.id,  # Revert PR
                            "relation": EdgeRelation.CAUSED_BY.value,
                            "weight": 0.9,
                            "confidence": 0.85,
                            "org_id": src_node.org_id,
                            "meta": {"heuristic": "commit_revert"},
                        }
                    )

        return edges

    def _extract_jira_keys(self, node: MemoryNode) -> Set[str]:
        """Extract JIRA keys from node text"""
        text = f"{node.title or ''} {node.summary or ''}"
        meta = node.meta_json or {}
        text += f" {meta.get('description', '')}"
        return set(JIRA_KEY_PATTERN.findall(text))

    def _extract_references(self, text: str) -> Set[str]:
        """Extract PR numbers and JIRA keys"""
        if not text:
            return set()
        refs = set()
        refs.update(f"#{m}" for m in PR_NUMBER_PATTERN.findall(text))
        refs.update(JIRA_KEY_PATTERN.findall(text))
        return refs

    def _count_shared_terms(self, node1: MemoryNode, node2: MemoryNode) -> int:
        """Count shared significant terms between nodes"""
        text1 = f"{node1.title or ''} {node1.summary or ''}".lower()
        text2 = f"{node2.title or ''} {node2.summary or ''}".lower()

        # Simple tokenization (exclude common words using shared STOPWORDS constant)
        words1 = set(
            w for w in re.findall(r"\w+", text1) if len(w) > 3 and w not in STOPWORDS
        )
        words2 = set(
            w for w in re.findall(r"\w+", text2) if len(w) > 3 and w not in STOPWORDS
        )

        return len(words1 & words2)

    def _create_edge_if_not_exists(
        self,
        src_id: int,
        dst_id: int,
        relation: str,
        weight: float,
        confidence: float,
        org_id: str,
        meta: Dict[str, Any],
    ) -> bool:
        """Create edge if it doesn't already exist

        Returns True if edge was created, False if it already existed
        """
        existing = (
            self.db.query(MemoryEdge)
            .filter_by(org_id=org_id, src_id=src_id, dst_id=dst_id, relation=relation)
            .first()
        )

        if existing:
            return False

        edge = MemoryEdge(
            org_id=org_id,
            src_id=src_id,
            dst_id=dst_id,
            relation=relation,
            weight=weight,
            confidence=confidence,
            meta_json=meta,
        )
        self.db.add(edge)
        return True

    def _map_source_to_kind(self, source: str) -> Optional[str]:
        """Map memory_object source to node kind

        Note: Only GitHub PRs are currently supported. GitHub issues/discussions
        are not handled. Update this mapping if other GitHub entity types are ingested.
        """
        mapping = {
            "jira": NodeKind.JIRA_ISSUE.value,
            "slack": NodeKind.SLACK_THREAD.value,
            "meeting": NodeKind.MEETING.value,
            "github": NodeKind.PR.value,
            "confluence": NodeKind.DOC.value,
            "wiki": NodeKind.WIKI.value,
        }
        return mapping.get(source.lower())
