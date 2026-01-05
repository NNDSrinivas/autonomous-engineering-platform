"""
Explainable AI - Reasoning Graph System

This system provides structured, safe, high-level reasoning graphs that show
goals, constraints, decisions, alternatives, evidence, and confidence scores
WITHOUT exposing raw chain-of-thought, sensitive prompts, or internal LLM tokens.

This satisfies enterprise requirements for AI explainability, legal compliance,
user trust, and audit readiness while maintaining security and proprietary
algorithm protection.

Key principles:
- Never expose raw chain-of-thought or LLM tokens
- Never leak sensitive prompts or hidden policy logic
- Provide structured, auditable reasoning paths
- Show evidence, alternatives, and confidence levels
- Enable drill-down investigation without security risks
- Support regulatory compliance (SOX, GDPR, HIPAA, etc.)
"""

import json
import uuid
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import logging

try:
    from ..services.llm_router import LLMRouter
    from ..services.database_service import DatabaseService
    from ..memory.memory_layer import MemoryLayer, MemoryType, MemoryImportance
    from ..core.config import get_settings
except ImportError:
    from backend.services.llm_router import LLMRouter
    from backend.services.database_service import DatabaseService
    from backend.memory.memory_layer import MemoryLayer, MemoryType, MemoryImportance
    from backend.core.config import get_settings


class ReasoningNodeType(Enum):
    """Types of reasoning nodes in the graph."""

    GOAL = "goal"
    CONSTRAINT = "constraint"
    EVIDENCE = "evidence"
    DECISION = "decision"
    ALTERNATIVE = "alternative"
    ASSUMPTION = "assumption"
    RISK_ASSESSMENT = "risk_assessment"
    CONFIDENCE = "confidence"
    VALIDATION = "validation"
    OUTCOME = "outcome"


class ConfidenceLevel(Enum):
    """AI confidence levels for decisions."""

    VERY_LOW = "very_low"  # 0.0 - 0.2
    LOW = "low"  # 0.2 - 0.4
    MEDIUM = "medium"  # 0.4 - 0.6
    HIGH = "high"  # 0.6 - 0.8
    VERY_HIGH = "very_high"  # 0.8 - 1.0


class EvidenceType(Enum):
    """Types of evidence supporting decisions."""

    CODE_ANALYSIS = "code_analysis"
    STATIC_SCAN = "static_scan"
    SECURITY_SCAN = "security_scan"
    PERFORMANCE_METRICS = "performance_metrics"
    BEST_PRACTICES = "best_practices"
    COMPLIANCE_RULES = "compliance_rules"
    USER_FEEDBACK = "user_feedback"
    HISTORICAL_DATA = "historical_data"
    DOCUMENTATION = "documentation"
    INDUSTRY_STANDARDS = "industry_standards"


@dataclass
class Evidence:
    """Represents a piece of evidence supporting a decision."""

    evidence_id: str
    evidence_type: EvidenceType
    description: str
    source: str
    reliability_score: float  # 0.0 - 1.0
    timestamp: datetime
    data_snapshot: Optional[Dict[str, Any]] = None


@dataclass
class ReasoningNode:
    """
    A node in the reasoning graph representing a step in AI reasoning.

    This is the sanitized, enterprise-safe version of AI reasoning that
    can be shown to users, auditors, and compliance officers.
    """

    node_id: str
    node_type: ReasoningNodeType
    label: str
    description: str
    evidence: List[Evidence]
    confidence_score: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningEdge:
    """Represents a connection between reasoning nodes."""

    from_node: str
    to_node: str
    relationship_type: str  # "supports", "conflicts", "requires", "leads_to"
    strength: float  # 0.0 - 1.0


@dataclass
class DecisionAlternative:
    """Represents an alternative that was considered but not chosen."""

    alternative_id: str
    description: str
    pros: List[str]
    cons: List[str]
    risk_score: float
    feasibility_score: float
    rejection_reason: str
    evidence: List[Evidence]


@dataclass
class ReasoningContext:
    """Context information for the reasoning process."""

    session_id: str
    user_id: str
    request_type: str
    input_summary: str  # Sanitized input description
    environment: str
    constraints: List[str]
    objectives: List[str]


class ReasoningGraph:
    """
    A structured representation of AI reasoning that is safe for enterprise use.

    This graph shows the logical flow of AI decision-making without exposing
    sensitive implementation details, raw prompts, or proprietary algorithms.
    """

    def __init__(self, context: ReasoningContext):
        """Initialize a new reasoning graph."""
        self.graph_id = str(uuid.uuid4())
        self.context = context
        self.nodes: Dict[str, ReasoningNode] = {}
        self.edges: List[ReasoningEdge] = []
        self.alternatives: List[DecisionAlternative] = []
        self.created_at = datetime.now()
        self.finalized = False

        # Graph structure tracking
        self.root_nodes: Set[str] = set()
        self.leaf_nodes: Set[str] = set()
        self.decision_nodes: Set[str] = set()

        # Metadata
        self.tags: Set[str] = set()
        self.risk_level: str = "unknown"
        self.overall_confidence: float = 0.0

    def add_node(self, node: ReasoningNode) -> str:
        """Add a reasoning node to the graph."""
        self.nodes[node.node_id] = node

        # Track special node types
        if node.node_type == ReasoningNodeType.DECISION:
            self.decision_nodes.add(node.node_id)

        return node.node_id

    def add_edge(self, edge: ReasoningEdge) -> None:
        """Add an edge between reasoning nodes."""
        if edge.from_node not in self.nodes or edge.to_node not in self.nodes:
            raise ValueError("Both nodes must exist before adding edge")

        self.edges.append(edge)

        # Update root/leaf tracking
        self.root_nodes.discard(edge.to_node)
        self.leaf_nodes.discard(edge.from_node)

        if edge.from_node not in [e.to_node for e in self.edges]:
            self.root_nodes.add(edge.from_node)
        if edge.to_node not in [e.from_node for e in self.edges]:
            self.leaf_nodes.add(edge.to_node)

    def add_alternative(self, alternative: DecisionAlternative) -> None:
        """Add an alternative that was considered but not chosen."""
        self.alternatives.append(alternative)

    def get_decision_path(self, target_decision: str) -> List[ReasoningNode]:
        """Get the path of reasoning leading to a specific decision."""
        if target_decision not in self.decision_nodes:
            raise ValueError("Target must be a decision node")

        # Use BFS to find path from root to decision
        visited = set()
        queue = deque([(node_id, [node_id]) for node_id in self.root_nodes])

        while queue:
            current_node, path = queue.popleft()

            if current_node == target_decision:
                return [self.nodes[node_id] for node_id in path]

            if current_node in visited:
                continue

            visited.add(current_node)

            # Add connected nodes to queue
            for edge in self.edges:
                if edge.from_node == current_node:
                    queue.append((edge.to_node, path + [edge.to_node]))

        return []  # No path found

    def get_supporting_evidence(self, node_id: str) -> List[Evidence]:
        """Get all evidence supporting a specific node."""
        if node_id not in self.nodes:
            return []

        node = self.nodes[node_id]
        all_evidence = node.evidence.copy()

        # Collect evidence from supporting nodes
        for edge in self.edges:
            if edge.to_node == node_id and edge.relationship_type == "supports":
                supporting_node = self.nodes[edge.from_node]
                all_evidence.extend(supporting_node.evidence)

        # Remove duplicates and sort by reliability
        unique_evidence = {e.evidence_id: e for e in all_evidence}
        sorted_evidence = sorted(
            unique_evidence.values(), key=lambda x: x.reliability_score, reverse=True
        )

        return sorted_evidence

    def calculate_confidence_metrics(self) -> Dict[str, float]:
        """Calculate overall confidence metrics for the graph."""
        if not self.decision_nodes:
            return {"overall": 0.0, "evidence_strength": 0.0, "consistency": 0.0}

        # Calculate decision confidence average
        decision_confidences = [
            self.nodes[node_id].confidence_score for node_id in self.decision_nodes
        ]
        overall_confidence = sum(decision_confidences) / len(decision_confidences)

        # Calculate evidence strength
        all_evidence = []
        for node in self.nodes.values():
            all_evidence.extend(node.evidence)

        evidence_strength = 0.0
        if all_evidence:
            evidence_strength = sum(e.reliability_score for e in all_evidence) / len(
                all_evidence
            )

        # Calculate consistency (how well connected the graph is)
        total_possible_edges = len(self.nodes) * (len(self.nodes) - 1)
        consistency = len(self.edges) / max(1, total_possible_edges)

        return {
            "overall": overall_confidence,
            "evidence_strength": evidence_strength,
            "consistency": consistency,
        }

    def finalize_graph(self) -> None:
        """Finalize the graph and calculate final metrics."""
        if self.finalized:
            return

        # Calculate overall confidence
        confidence_metrics = self.calculate_confidence_metrics()
        self.overall_confidence = confidence_metrics["overall"]

        # Determine risk level based on confidence and evidence
        if (
            self.overall_confidence > 0.8
            and confidence_metrics["evidence_strength"] > 0.7
        ):
            self.risk_level = "low"
        elif (
            self.overall_confidence > 0.6
            and confidence_metrics["evidence_strength"] > 0.5
        ):
            self.risk_level = "medium"
        else:
            self.risk_level = "high"

        self.finalized = True

    def export_for_ui(self) -> Dict[str, Any]:
        """Export graph in format suitable for UI visualization."""
        return {
            "graph_id": self.graph_id,
            "context": {
                "session_id": self.context.session_id,
                "user_id": self.context.user_id,
                "request_type": self.context.request_type,
                "input_summary": self.context.input_summary,
                "objectives": self.context.objectives,
                "constraints": self.context.constraints,
            },
            "nodes": [
                {
                    "id": node.node_id,
                    "type": node.node_type.value,
                    "label": node.label,
                    "description": node.description,
                    "confidence": node.confidence_score,
                    "evidence_count": len(node.evidence),
                    "timestamp": node.timestamp.isoformat(),
                }
                for node in self.nodes.values()
            ],
            "edges": [
                {
                    "from": edge.from_node,
                    "to": edge.to_node,
                    "type": edge.relationship_type,
                    "strength": edge.strength,
                }
                for edge in self.edges
            ],
            "alternatives": [
                {
                    "id": alt.alternative_id,
                    "description": alt.description,
                    "rejection_reason": alt.rejection_reason,
                    "risk_score": alt.risk_score,
                    "feasibility_score": alt.feasibility_score,
                }
                for alt in self.alternatives
            ],
            "metrics": {
                "overall_confidence": self.overall_confidence,
                "risk_level": self.risk_level,
                "decision_count": len(self.decision_nodes),
                "evidence_count": sum(len(n.evidence) for n in self.nodes.values()),
            },
            "created_at": self.created_at.isoformat(),
        }

    def export_for_audit(self) -> Dict[str, Any]:
        """Export detailed graph for audit and compliance purposes."""
        audit_export = self.export_for_ui()

        # Add detailed evidence information
        detailed_nodes = []
        for node in self.nodes.values():
            node_data = {
                "id": node.node_id,
                "type": node.node_type.value,
                "label": node.label,
                "description": node.description,
                "confidence": node.confidence_score,
                "timestamp": node.timestamp.isoformat(),
                "evidence": [
                    {
                        "id": e.evidence_id,
                        "type": e.evidence_type.value,
                        "description": e.description,
                        "source": e.source,
                        "reliability": e.reliability_score,
                        "timestamp": e.timestamp.isoformat(),
                    }
                    for e in node.evidence
                ],
            }
            detailed_nodes.append(node_data)

        audit_export["detailed_nodes"] = detailed_nodes

        # Add detailed alternatives
        audit_export["detailed_alternatives"] = [
            {
                "id": alt.alternative_id,
                "description": alt.description,
                "pros": alt.pros,
                "cons": alt.cons,
                "risk_score": alt.risk_score,
                "feasibility_score": alt.feasibility_score,
                "rejection_reason": alt.rejection_reason,
                "evidence": [
                    {
                        "id": e.evidence_id,
                        "type": e.evidence_type.value,
                        "description": e.description,
                        "reliability": e.reliability_score,
                    }
                    for e in alt.evidence
                ],
            }
            for alt in self.alternatives
        ]

        return audit_export


class ExplainableAISystem:
    """
    System for creating and managing explainable AI reasoning graphs.

    This system ensures that all AI decisions made by Navi are traceable,
    explainable, and auditable for enterprise and regulatory compliance.
    """

    def __init__(self):
        """Initialize the Explainable AI System."""
        self.llm = LLMRouter()
        self.db = DatabaseService()
        self.memory = MemoryLayer()
        self.settings = get_settings()

        # Active reasoning sessions
        self.active_graphs: Dict[str, ReasoningGraph] = {}
        self.completed_graphs: Dict[str, ReasoningGraph] = {}

        # System configuration
        self.config = {
            "min_confidence_for_auto_action": 0.8,
            "require_human_review_below": 0.6,
            "max_alternatives_to_track": 5,
            "evidence_retention_days": 2555,  # 7 years for compliance
            "auto_export_for_audit": True,
        }

    async def start_reasoning_session(
        self,
        user_id: str,
        request_type: str,
        input_summary: str,
        objectives: List[str],
        constraints: Optional[List[str]] = None,
    ) -> str:
        """Start a new explainable reasoning session."""

        session_id = str(uuid.uuid4())

        context = ReasoningContext(
            session_id=session_id,
            user_id=user_id,
            request_type=request_type,
            input_summary=input_summary,
            environment="production",  # Could be configurable
            constraints=constraints or [],
            objectives=objectives,
        )

        reasoning_graph = ReasoningGraph(context)
        self.active_graphs[session_id] = reasoning_graph

        logging.info(
            f"Started explainable reasoning session {session_id} for user {user_id}"
        )

        return session_id

    async def add_reasoning_step(
        self,
        session_id: str,
        step_type: ReasoningNodeType,
        label: str,
        description: str,
        evidence: Optional[List[Evidence]] = None,
        confidence: float = 1.0,
    ) -> str:
        """Add a reasoning step to an active session."""

        if session_id not in self.active_graphs:
            raise ValueError(f"No active reasoning session: {session_id}")

        graph = self.active_graphs[session_id]

        node_id = str(uuid.uuid4())
        node = ReasoningNode(
            node_id=node_id,
            node_type=step_type,
            label=label,
            description=description,
            evidence=evidence or [],
            confidence_score=confidence,
            timestamp=datetime.now(),
        )

        graph.add_node(node)

        return node_id

    async def connect_reasoning_steps(
        self,
        session_id: str,
        from_node: str,
        to_node: str,
        relationship_type: str = "leads_to",
        strength: float = 1.0,
    ) -> None:
        """Connect two reasoning steps with a relationship."""

        if session_id not in self.active_graphs:
            raise ValueError(f"No active reasoning session: {session_id}")

        graph = self.active_graphs[session_id]

        edge = ReasoningEdge(
            from_node=from_node,
            to_node=to_node,
            relationship_type=relationship_type,
            strength=strength,
        )

        graph.add_edge(edge)

    async def add_considered_alternative(
        self,
        session_id: str,
        description: str,
        pros: List[str],
        cons: List[str],
        risk_score: float,
        feasibility_score: float,
        rejection_reason: str,
        evidence: Optional[List[Evidence]] = None,
    ) -> str:
        """Add an alternative that was considered but rejected."""

        if session_id not in self.active_graphs:
            raise ValueError(f"No active reasoning session: {session_id}")

        graph = self.active_graphs[session_id]

        alternative_id = str(uuid.uuid4())
        alternative = DecisionAlternative(
            alternative_id=alternative_id,
            description=description,
            pros=pros,
            cons=cons,
            risk_score=risk_score,
            feasibility_score=feasibility_score,
            rejection_reason=rejection_reason,
            evidence=evidence or [],
        )

        graph.add_alternative(alternative)

        return alternative_id

    async def finalize_reasoning_session(self, session_id: str) -> ReasoningGraph:
        """Finalize a reasoning session and move it to completed graphs."""

        if session_id not in self.active_graphs:
            raise ValueError(f"No active reasoning session: {session_id}")

        graph = self.active_graphs[session_id]
        graph.finalize_graph()

        # Move to completed graphs
        self.completed_graphs[session_id] = graph
        del self.active_graphs[session_id]

        # Store in memory for future reference
        await self.memory.store_memory(
            MemoryType.REASONING_GRAPH,
            f"Reasoning Graph {graph.context.session_id}",
            str(graph.export_for_audit()),
            importance=MemoryImportance.HIGH,
            tags=[
                f"user_{graph.context.user_id}",
                f"type_{graph.context.request_type}",
            ],
        )

        # Auto-export for audit if configured
        if self.config["auto_export_for_audit"]:
            await self._store_audit_export(graph)

        logging.info(
            f"Finalized reasoning session {session_id} with confidence {graph.overall_confidence}"
        )

        return graph

    async def get_reasoning_graph(self, session_id: str) -> Optional[ReasoningGraph]:
        """Get a reasoning graph by session ID."""

        if session_id in self.active_graphs:
            return self.active_graphs[session_id]

        if session_id in self.completed_graphs:
            return self.completed_graphs[session_id]

        return None

    async def explain_decision(
        self, session_id: str, decision_node_id: str
    ) -> Dict[str, Any]:
        """Generate a human-readable explanation for a specific decision."""

        graph = await self.get_reasoning_graph(session_id)
        if not graph:
            raise ValueError(f"Reasoning graph not found: {session_id}")

        if decision_node_id not in graph.decision_nodes:
            raise ValueError(f"Not a decision node: {decision_node_id}")

        # Get decision path and supporting evidence
        decision_path = graph.get_decision_path(decision_node_id)
        supporting_evidence = graph.get_supporting_evidence(decision_node_id)
        decision_node = graph.nodes[decision_node_id]

        # Find alternatives for this decision
        relevant_alternatives = [
            alt
            for alt in graph.alternatives
            if any(
                e.evidence_id in [ev.evidence_id for ev in decision_node.evidence]
                for e in alt.evidence
            )
        ]

        explanation = {
            "decision": {
                "id": decision_node_id,
                "label": decision_node.label,
                "description": decision_node.description,
                "confidence": decision_node.confidence_score,
            },
            "reasoning_path": [
                {
                    "step": i + 1,
                    "type": node.node_type.value,
                    "description": node.description,
                    "confidence": node.confidence_score,
                }
                for i, node in enumerate(decision_path)
            ],
            "supporting_evidence": [
                {
                    "type": evidence.evidence_type.value,
                    "description": evidence.description,
                    "source": evidence.source,
                    "reliability": evidence.reliability_score,
                }
                for evidence in supporting_evidence[:10]  # Limit to top 10
            ],
            "alternatives_considered": [
                {
                    "description": alt.description,
                    "rejection_reason": alt.rejection_reason,
                    "risk_score": alt.risk_score,
                    "pros": alt.pros[:3],  # Limit to top 3
                    "cons": alt.cons[:3],  # Limit to top 3
                }
                for alt in relevant_alternatives[:3]  # Limit to top 3
            ],
            "risk_assessment": {
                "overall_risk": graph.risk_level,
                "confidence_level": self._get_confidence_level(
                    decision_node.confidence_score
                ).value,
                "evidence_strength": len(supporting_evidence),
            },
        }

        return explanation

    async def generate_reasoning_summary(self, session_id: str) -> str:
        """Generate a human-readable summary of the entire reasoning process."""

        graph = await self.get_reasoning_graph(session_id)
        if not graph:
            raise ValueError(f"Reasoning graph not found: {session_id}")

        # Create structured summary
        summary_parts = [
            f"**Objective**: {', '.join(graph.context.objectives)}",
            f"**Request Type**: {graph.context.request_type}",
            f"**Overall Confidence**: {graph.overall_confidence:.2f}",
            f"**Risk Level**: {graph.risk_level}",
            "",
        ]

        # Add key decisions
        if graph.decision_nodes:
            summary_parts.append("**Key Decisions Made**:")
            for decision_id in graph.decision_nodes:
                decision = graph.nodes[decision_id]
                summary_parts.append(
                    f"- {decision.label} (confidence: {decision.confidence_score:.2f})"
                )
            summary_parts.append("")

        # Add alternatives considered
        if graph.alternatives:
            summary_parts.append("**Alternatives Considered**:")
            for alt in graph.alternatives[:3]:  # Top 3
                summary_parts.append(
                    f"- {alt.description} → Rejected: {alt.rejection_reason}"
                )
            summary_parts.append("")

        # Add evidence summary
        total_evidence = sum(len(node.evidence) for node in graph.nodes.values())
        summary_parts.append(
            f"**Evidence Analyzed**: {total_evidence} pieces of evidence from various sources"
        )

        return "\n".join(summary_parts)

    def _get_confidence_level(self, score: float) -> ConfidenceLevel:
        """Convert numeric confidence score to categorical level."""
        if score >= 0.8:
            return ConfidenceLevel.VERY_HIGH
        elif score >= 0.6:
            return ConfidenceLevel.HIGH
        elif score >= 0.4:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.2:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    async def _store_audit_export(self, graph: ReasoningGraph) -> None:
        """Store audit export of reasoning graph."""

        audit_data = graph.export_for_audit()

        # Store in database for compliance
        await self.db.execute(
            """
            INSERT INTO reasoning_audit_log 
            (session_id, user_id, request_type, reasoning_data, created_at, confidence_score, risk_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                graph.context.session_id,
                graph.context.user_id,
                graph.context.request_type,
                json.dumps(audit_data),
                graph.created_at.isoformat(),
                graph.overall_confidence,
                graph.risk_level,
            ],
        )


# Helper function to create evidence
def create_evidence(
    evidence_type: EvidenceType,
    description: str,
    source: str,
    reliability: float = 1.0,
    data_snapshot: Optional[Dict[str, Any]] = None,
) -> Evidence:
    """Helper function to create evidence objects."""

    return Evidence(
        evidence_id=str(uuid.uuid4()),
        evidence_type=evidence_type,
        description=description,
        source=source,
        reliability_score=reliability,
        timestamp=datetime.now(),
        data_snapshot=data_snapshot,
    )


# Example usage for testing
async def example_reasoning_session():
    """Example of how to use the explainable AI system."""

    explainer = ExplainableAISystem()

    # Start reasoning session
    session_id = await explainer.start_reasoning_session(
        user_id="user123",
        request_type="security_fix",
        input_summary="Remove hardcoded secrets from configuration files",
        objectives=["Improve security posture", "Maintain functionality"],
        constraints=["No breaking changes", "Preserve existing API"],
    )

    # Add goal node
    goal_node = await explainer.add_reasoning_step(
        session_id,
        ReasoningNodeType.GOAL,
        "Remove Security Vulnerabilities",
        "Eliminate hardcoded secrets to improve security posture",
        evidence=[
            create_evidence(
                EvidenceType.SECURITY_SCAN,
                "Hardcoded API keys found in config.py lines 15-17",
                "static_analyzer",
                0.95,
            )
        ],
        confidence=0.9,
    )

    # Add constraint node
    constraint_node = await explainer.add_reasoning_step(
        session_id,
        ReasoningNodeType.CONSTRAINT,
        "No Breaking Changes",
        "Must preserve existing functionality and API compatibility",
        evidence=[
            create_evidence(
                EvidenceType.BEST_PRACTICES,
                "Breaking changes require version bump and migration plan",
                "engineering_guidelines",
                0.9,
            )
        ],
        confidence=1.0,
    )

    # Add decision node
    decision_node = await explainer.add_reasoning_step(
        session_id,
        ReasoningNodeType.DECISION,
        "Move Secrets to Environment Variables",
        "Replace hardcoded secrets with environment variable references",
        evidence=[
            create_evidence(
                EvidenceType.BEST_PRACTICES,
                "Environment variables are secure and configurable",
                "security_guidelines",
                0.95,
            ),
            create_evidence(
                EvidenceType.COMPLIANCE_RULES,
                "OWASP recommends external configuration for secrets",
                "owasp_guidelines",
                0.98,
            ),
        ],
        confidence=0.92,
    )

    # Connect reasoning steps
    await explainer.connect_reasoning_steps(
        session_id, goal_node, decision_node, "leads_to", 0.9
    )
    await explainer.connect_reasoning_steps(
        session_id, constraint_node, decision_node, "constrains", 0.8
    )

    # Add rejected alternative
    await explainer.add_considered_alternative(
        session_id,
        "Encrypt secrets in repository",
        pros=["Keeps secrets in code", "No deployment changes needed"],
        cons=[
            "Encryption key must be managed",
            "Still visible to developers",
            "Key rotation complexity",
        ],
        risk_score=0.7,
        feasibility_score=0.6,
        rejection_reason="Encryption key management introduces new security risks",
        evidence=[
            create_evidence(
                EvidenceType.SECURITY_SCAN,
                "Encrypted secrets still pose key management challenges",
                "security_analysis",
                0.8,
            )
        ],
    )

    # Finalize session
    final_graph = await explainer.finalize_reasoning_session(session_id)

    # Get explanation
    explanation = await explainer.explain_decision(session_id, decision_node)

    return final_graph, explanation
