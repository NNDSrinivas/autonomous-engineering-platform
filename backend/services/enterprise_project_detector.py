"""
Enterprise Project Detector

Detects when a user request is for an enterprise-level project that requires:
- Unlimited iterations with checkpointing
- Task decomposition into 50+ tasks
- Human checkpoint gates for architecture/security/cost decisions
- Multi-agent parallel execution

This service analyzes the user's request and workspace to determine if it should
be routed through the EnterpriseAgentCoordinator instead of the standard agent.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger(__name__)


class ProjectScale(Enum):
    """Scale of the project based on request analysis."""
    SIMPLE = "simple"  # Single file fixes, small changes (standard agent)
    MEDIUM = "medium"  # Multi-file changes, moderate features (standard agent)
    COMPLEX = "complex"  # Large features, refactoring (standard agent with more iterations)
    ENTERPRISE = "enterprise"  # Full application development (enterprise coordinator)


@dataclass
class EnterpriseProjectSpec:
    """Specification for an enterprise project detected from user request."""
    name: str
    description: str
    project_type: str  # e-commerce, microservices, api, web-app, mobile-backend
    estimated_tasks: int
    goals: List[Dict[str, str]]
    requires_database: bool
    requires_deployment: bool
    requires_auth: bool
    scale_indicators: List[str]
    confidence: float  # 0.0 - 1.0


# Patterns that indicate enterprise-level project requests
ENTERPRISE_PATTERNS = [
    # Full application keywords
    (r"(?:build|create|develop|implement)\s+(?:a\s+)?(?:full|complete|entire|end.?to.?end|e2e)", 0.7),
    (r"(?:build|create)\s+(?:an?\s+)?(?:e-?commerce|ecommerce|shop|marketplace|store)", 0.9),
    (r"(?:build|create)\s+(?:an?\s+)?(?:saas|platform|application|app|system)", 0.6),
    (r"(?:build|create)\s+(?:microservices?|distributed\s+system)", 0.9),

    # Scale indicators
    (r"(?:million|10m|100k|\d+k)\s+(?:users?|requests?|transactions?)", 0.8),
    (r"(?:scale|scaling|scalable)\s+(?:to|for)?\s*(?:\d+|millions?)", 0.7),
    (r"production.?ready|enterprise.?grade|production\s+deployment", 0.7),

    # Comprehensive features
    (r"with\s+(?:authentication|auth|login|signup|user\s+management)", 0.4),
    (r"with\s+(?:database|db|data\s+persistence|storage)", 0.3),
    (r"with\s+(?:deployment|deploy|ci/?cd|pipeline)", 0.4),
    (r"with\s+(?:testing|tests?|test\s+coverage)", 0.3),
    (r"with\s+(?:monitoring|logging|observability|metrics)", 0.4),

    # Architecture keywords
    (r"api\s+(?:gateway|layer|service)", 0.5),
    (r"(?:payment|checkout|billing)\s+(?:system|integration|flow)", 0.6),
    (r"(?:admin|dashboard|management)\s+(?:panel|interface|portal)", 0.5),

    # Explicit project scope
    (r"multi-?(?:service|module|component|tier)", 0.6),
    (r"(?:frontend|backend|api|database|infra)\s+(?:and|,)\s+(?:frontend|backend|api|database|infra)", 0.7),
]

# Project type detection patterns
PROJECT_TYPE_PATTERNS = {
    "e-commerce": [
        r"e-?commerce|ecommerce|shop|store|marketplace",
        r"cart|checkout|payment|order|product|catalog|inventory",
        r"seller|buyer|merchant|customer\s+portal",
    ],
    "microservices": [
        r"microservices?|micro-?services?",
        r"distributed\s+system|service\s+mesh|event\s+driven",
        r"message\s+queue|kafka|rabbitmq|event\s+bus",
    ],
    "api": [
        r"api\s+(?:platform|service|backend)",
        r"rest\s+api|graphql|grpc",
        r"api\s+gateway|api\s+management",
    ],
    "web-app": [
        r"web\s+(?:app|application|platform)",
        r"(?:react|vue|angular|next|nuxt)\s+(?:app|application)",
        r"single\s+page\s+application|spa",
    ],
    "mobile-backend": [
        r"mobile\s+(?:backend|api|app\s+backend)",
        r"(?:ios|android|react\s+native|flutter)\s+(?:backend|api)",
    ],
    "saas": [
        r"saas|software\s+as\s+a\s+service",
        r"(?:multi-?)?tenant|subscription|billing\s+system",
    ],
}


def _calculate_enterprise_score(message: str) -> Tuple[float, List[str]]:
    """
    Calculate enterprise score based on pattern matching.

    Returns:
        Tuple of (score, list of matched indicators)
    """
    message_lower = message.lower()
    total_score = 0.0
    indicators = []

    for pattern, weight in ENTERPRISE_PATTERNS:
        if re.search(pattern, message_lower, re.IGNORECASE):
            total_score += weight
            # Extract matched text as indicator
            match = re.search(pattern, message_lower, re.IGNORECASE)
            if match:
                indicators.append(match.group(0))

    # Normalize score to 0-1 range
    max_possible_score = sum(w for _, w in ENTERPRISE_PATTERNS)
    normalized_score = min(1.0, total_score / (max_possible_score * 0.3))  # 30% threshold

    return normalized_score, indicators


def _detect_project_type(message: str) -> str:
    """Detect the type of enterprise project from the message."""
    message_lower = message.lower()

    best_match = "web-app"  # Default
    best_score = 0

    for project_type, patterns in PROJECT_TYPE_PATTERNS.items():
        score = sum(1 for p in patterns if re.search(p, message_lower, re.IGNORECASE))
        if score > best_score:
            best_score = score
            best_match = project_type

    return best_match


def _estimate_task_count(message: str, project_type: str) -> int:
    """Estimate the number of tasks based on message and project type."""
    base_counts = {
        "e-commerce": 120,
        "microservices": 150,
        "api": 60,
        "web-app": 80,
        "mobile-backend": 70,
        "saas": 100,
    }

    base = base_counts.get(project_type, 80)

    # Adjust based on features mentioned
    message_lower = message.lower()

    if re.search(r"authentication|auth|login", message_lower):
        base += 15
    if re.search(r"payment|checkout|billing", message_lower):
        base += 25
    if re.search(r"admin|dashboard", message_lower):
        base += 20
    if re.search(r"deploy|ci/?cd|production", message_lower):
        base += 15
    if re.search(r"test|coverage", message_lower):
        base += 10
    if re.search(r"monitoring|logging", message_lower):
        base += 10

    return base


def _extract_goals(message: str, project_type: str) -> List[Dict[str, str]]:
    """Extract goals from the user message."""
    goals = []
    message_lower = message.lower()

    # Core goals based on project type
    if project_type == "e-commerce":
        goals.append({"id": "core", "description": "Build core e-commerce platform with product catalog and shopping cart"})
        if re.search(r"payment|checkout", message_lower):
            goals.append({"id": "payment", "description": "Implement payment processing and checkout flow"})
        if re.search(r"order|fulfillment", message_lower):
            goals.append({"id": "orders", "description": "Build order management and fulfillment system"})
        if re.search(r"admin|seller", message_lower):
            goals.append({"id": "admin", "description": "Create admin/seller dashboard for product and order management"})

    elif project_type == "microservices":
        goals.append({"id": "arch", "description": "Design and implement microservices architecture"})
        goals.append({"id": "infra", "description": "Set up service discovery, API gateway, and infrastructure"})
        goals.append({"id": "services", "description": "Implement core domain services"})

    else:
        goals.append({"id": "core", "description": f"Build core {project_type} functionality"})

    # Common goals
    if re.search(r"auth|login|user", message_lower):
        goals.append({"id": "auth", "description": "Implement user authentication and authorization"})
    if re.search(r"database|db", message_lower):
        goals.append({"id": "db", "description": "Design and implement database schema and data layer"})
    if re.search(r"api|endpoint", message_lower):
        goals.append({"id": "api", "description": "Build RESTful API endpoints"})
    if re.search(r"frontend|ui|interface", message_lower):
        goals.append({"id": "frontend", "description": "Create responsive frontend user interface"})
    if re.search(r"deploy|production", message_lower):
        goals.append({"id": "deploy", "description": "Set up CI/CD and production deployment"})
    if re.search(r"test", message_lower):
        goals.append({"id": "testing", "description": "Implement comprehensive test coverage"})

    return goals if goals else [{"id": "core", "description": f"Build the requested {project_type} application"}]


def detect_enterprise_project(
    message: str,
    workspace_path: Optional[str] = None,
) -> Tuple[bool, Optional[EnterpriseProjectSpec], ProjectScale]:
    """
    Analyze a user request to determine if it's an enterprise-level project.

    Args:
        message: The user's request message
        workspace_path: Optional path to the workspace

    Returns:
        Tuple of:
        - is_enterprise: Whether this is an enterprise project
        - spec: EnterpriseProjectSpec if enterprise, None otherwise
        - scale: The detected project scale
    """
    # Calculate enterprise score
    score, indicators = _calculate_enterprise_score(message)

    logger.info(f"[EnterpriseDetector] Score: {score:.2f}, Indicators: {indicators}")

    # Determine scale based on score
    if score >= 0.7:
        scale = ProjectScale.ENTERPRISE
    elif score >= 0.4:
        scale = ProjectScale.COMPLEX
    elif score >= 0.2:
        scale = ProjectScale.MEDIUM
    else:
        scale = ProjectScale.SIMPLE

    # Only create enterprise spec if it's an enterprise project
    if scale != ProjectScale.ENTERPRISE:
        return False, None, scale

    # Detect project type
    project_type = _detect_project_type(message)

    # Estimate task count
    estimated_tasks = _estimate_task_count(message, project_type)

    # Extract goals
    goals = _extract_goals(message, project_type)

    # Build project name from message (first 50 chars cleaned up)
    name_match = re.search(r"(?:build|create|develop)\s+(.{10,50}?)(?:\s+with|\s+that|\s+using|$)", message.lower())
    project_name = name_match.group(1).strip().title() if name_match else "Enterprise Project"

    # Feature detection
    message_lower = message.lower()

    spec = EnterpriseProjectSpec(
        name=project_name,
        description=message[:500],  # First 500 chars as description
        project_type=project_type,
        estimated_tasks=estimated_tasks,
        goals=goals,
        requires_database=bool(re.search(r"database|db|storage|persist", message_lower)),
        requires_deployment=bool(re.search(r"deploy|production|ci/?cd|hosting", message_lower)),
        requires_auth=bool(re.search(r"auth|login|user|account|permission", message_lower)),
        scale_indicators=indicators,
        confidence=score,
    )

    logger.info(f"[EnterpriseDetector] Detected enterprise project: {spec.name} ({spec.project_type})")
    logger.info(f"[EnterpriseDetector] Estimated tasks: {spec.estimated_tasks}, Goals: {len(spec.goals)}")

    return True, spec, scale


async def create_enterprise_project_from_spec(
    spec: EnterpriseProjectSpec,
    user_id: int,
    workspace_session_id: str,
    db_session,
) -> str:
    """
    Create an EnterpriseProject in the database from a detected spec.

    Returns:
        The created project ID
    """
    from backend.services.enterprise_project_service import EnterpriseProjectService

    service = EnterpriseProjectService(db_session)

    project = await service.create_project(
        user_id=user_id,
        workspace_session_id=workspace_session_id,
        name=spec.name,
        description=spec.description,
        project_type=spec.project_type,
        goals=[
            {
                "id": g["id"],
                "description": g["description"],
                "status": "pending",
            }
            for g in spec.goals
        ],
    )

    logger.info(f"[EnterpriseDetector] Created enterprise project: {project.id}")

    return str(project.id)
