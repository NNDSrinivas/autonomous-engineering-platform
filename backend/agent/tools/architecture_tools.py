"""
Architecture planning tools for NAVI agent.

Provides tools for software architecture design:
- Tech stack recommendations
- System architecture design
- Microservices decomposition
- Architecture Decision Records (ADRs)
- Dependency analysis
- Architecture diagrams

Works dynamically for any project type.
"""

import os
import re
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog

from backend.services.connector_base import ToolResult

logger = structlog.get_logger(__name__)


# Tech stack recommendation database
TECH_STACKS = {
    "web_frontend": {
        "frameworks": {
            "next_js": {
                "description": "React framework with SSR/SSG, API routes, and excellent DX",
                "best_for": [
                    "SEO-critical apps",
                    "marketing sites",
                    "e-commerce",
                    "dashboards",
                ],
                "learning_curve": "medium",
                "ecosystem": "excellent",
                "performance": "excellent",
            },
            "react": {
                "description": "Component-based UI library, most popular choice",
                "best_for": ["SPAs", "complex UIs", "large teams"],
                "learning_curve": "medium",
                "ecosystem": "excellent",
                "performance": "good",
            },
            "vue_js": {
                "description": "Progressive framework, easier learning curve than React",
                "best_for": ["rapid prototyping", "smaller teams", "gradual adoption"],
                "learning_curve": "easy",
                "ecosystem": "good",
                "performance": "excellent",
            },
            "svelte": {
                "description": "Compiler-based framework with minimal runtime",
                "best_for": [
                    "performance-critical apps",
                    "smaller bundles",
                    "animations",
                ],
                "learning_curve": "easy",
                "ecosystem": "growing",
                "performance": "excellent",
            },
        },
    },
    "web_backend": {
        "frameworks": {
            "node.js/express": {
                "description": "Minimal, flexible Node.js web framework",
                "best_for": ["APIs", "microservices", "real-time apps"],
                "learning_curve": "easy",
                "ecosystem": "excellent",
                "performance": "good",
            },
            "fastapi": {
                "description": "Modern Python framework with automatic API docs",
                "best_for": ["APIs", "ML services", "async workloads"],
                "learning_curve": "easy",
                "ecosystem": "good",
                "performance": "excellent",
            },
            "django": {
                "description": "Batteries-included Python framework",
                "best_for": ["content sites", "admin panels", "rapid development"],
                "learning_curve": "medium",
                "ecosystem": "excellent",
                "performance": "good",
            },
            "go": {
                "description": "Compiled language with excellent concurrency",
                "best_for": ["high-performance APIs", "microservices", "CLI tools"],
                "learning_curve": "medium",
                "ecosystem": "good",
                "performance": "excellent",
            },
            "rust/actix": {
                "description": "Memory-safe systems language with web frameworks",
                "best_for": ["performance-critical services", "system programming"],
                "learning_curve": "hard",
                "ecosystem": "growing",
                "performance": "excellent",
            },
        },
    },
    "databases": {
        "relational": {
            "postgresql": {
                "description": "Advanced open-source relational database",
                "best_for": ["complex queries", "ACID compliance", "JSON support"],
                "scaling": "vertical + read replicas",
            },
            "mysql": {
                "description": "Popular open-source relational database",
                "best_for": ["web applications", "read-heavy workloads"],
                "scaling": "vertical + read replicas",
            },
        },
        "nosql": {
            "mongodb": {
                "description": "Document database with flexible schema",
                "best_for": [
                    "rapid iteration",
                    "unstructured data",
                    "horizontal scaling",
                ],
                "scaling": "horizontal (sharding)",
            },
            "redis": {
                "description": "In-memory data store for caching and sessions",
                "best_for": ["caching", "sessions", "real-time features"],
                "scaling": "cluster mode",
            },
            "dynamodb": {
                "description": "AWS managed NoSQL database",
                "best_for": ["serverless", "high availability", "auto-scaling"],
                "scaling": "automatic",
            },
        },
    },
    "deployment": {
        "platforms": {
            "vercel": {
                "description": "Optimized for frontend/Next.js deployments",
                "best_for": ["Next.js", "static sites", "serverless functions"],
                "pricing": "generous free tier",
            },
            "railway": {
                "description": "Simple full-stack deployment with databases",
                "best_for": ["full-stack apps", "quick deployments", "databases"],
                "pricing": "usage-based",
            },
            "aws": {
                "description": "Comprehensive cloud platform",
                "best_for": ["enterprise", "complex architectures", "compliance"],
                "pricing": "pay-as-you-go",
            },
            "gcp": {
                "description": "Google's cloud platform with ML focus",
                "best_for": ["ML/AI workloads", "Kubernetes", "data analytics"],
                "pricing": "pay-as-you-go",
            },
        },
    },
}

# Architecture patterns
ARCHITECTURE_PATTERNS = {
    "monolith": {
        "description": "Single deployable unit containing all functionality",
        "pros": [
            "Simple deployment",
            "Easy debugging",
            "Lower latency",
            "Easier testing",
        ],
        "cons": ["Scaling challenges", "Technology lock-in", "Deployment risk"],
        "best_for": ["Startups", "Small teams", "MVPs", "Simple domains"],
    },
    "microservices": {
        "description": "Distributed system of small, independent services",
        "pros": [
            "Independent scaling",
            "Technology flexibility",
            "Team autonomy",
            "Fault isolation",
        ],
        "cons": [
            "Operational complexity",
            "Network latency",
            "Data consistency",
            "Debugging difficulty",
        ],
        "best_for": [
            "Large teams",
            "Complex domains",
            "High scale",
            "Different scaling needs",
        ],
    },
    "serverless": {
        "description": "Event-driven functions without server management",
        "pros": [
            "No server management",
            "Auto-scaling",
            "Pay-per-use",
            "Quick deployment",
        ],
        "cons": [
            "Cold starts",
            "Vendor lock-in",
            "Debugging difficulty",
            "Execution limits",
        ],
        "best_for": [
            "Event processing",
            "APIs",
            "Scheduled tasks",
            "Variable workloads",
        ],
    },
    "event_driven": {
        "description": "Asynchronous communication through events",
        "pros": ["Loose coupling", "Scalability", "Resilience", "Audit trail"],
        "cons": ["Eventual consistency", "Complexity", "Debugging difficulty"],
        "best_for": ["Real-time systems", "Integration", "Workflows", "Analytics"],
    },
    "modular_monolith": {
        "description": "Monolith with clear module boundaries",
        "pros": [
            "Simple deployment",
            "Clear boundaries",
            "Easy to evolve",
            "Good for extraction",
        ],
        "cons": ["Still single deployment", "Discipline required"],
        "best_for": ["Growing teams", "Evolving domains", "Future microservices"],
    },
}

# ADR template
ADR_TEMPLATE = """# {number}. {title}

Date: {date}

## Status

{status}

## Context

{context}

## Decision

{decision}

## Consequences

### Positive
{positive_consequences}

### Negative
{negative_consequences}

## Alternatives Considered

{alternatives}
"""


@dataclass
class ArchitectureRecommendation:
    """Architecture recommendation result."""

    pattern: str
    frontend: Optional[str]
    backend: Optional[str]
    database: Optional[str]
    deployment: Optional[str]
    reasoning: str
    considerations: List[str]


async def recommend_tech_stack(
    context: Dict[str, Any],
    requirements: Dict[str, Any],
) -> ToolResult:
    """
    Recommend optimal tech stack based on project requirements.

    Args:
        requirements: Dictionary with:
            - type: Project type (web, api, mobile, cli, data)
            - scale: Expected scale (small, medium, large, enterprise)
            - team_size: Team size (1-5, 5-20, 20+)
            - existing_skills: List of technologies team knows
            - constraints: Any specific constraints
            - features: Required features list

    Returns:
        ToolResult with tech stack recommendation
    """
    logger.info("recommend_tech_stack", requirements=requirements)

    project_type = requirements.get("type", "web").lower()
    scale = requirements.get("scale", "medium").lower()
    team_size = requirements.get("team_size", "5-20")
    existing_skills = requirements.get("existing_skills", [])
    constraints = requirements.get("constraints", [])
    features = requirements.get("features", [])

    # Determine architecture pattern
    if scale == "enterprise" or "microservices" in constraints:
        pattern = "microservices"
    elif scale == "small" or team_size == "1-5":
        pattern = "monolith"
    elif "serverless" in constraints:
        pattern = "serverless"
    else:
        pattern = "modular_monolith"

    # Recommend frontend
    frontend_rec = None
    if project_type in ("web", "fullstack"):
        if "ssr" in features or "seo" in features:
            frontend_rec = ("Next.js", "SSR/SSG support, excellent for SEO")
        elif "react" in [s.lower() for s in existing_skills]:
            frontend_rec = ("React + Vite", "Fast development with familiar technology")
        elif "vue" in [s.lower() for s in existing_skills]:
            frontend_rec = ("Vue.js + Nuxt", "Progressive framework with SSR option")
        else:
            frontend_rec = ("Next.js", "Best overall DX and feature set")

    # Recommend backend
    backend_rec = None
    if project_type in ("api", "backend", "fullstack", "web"):
        if "python" in [s.lower() for s in existing_skills]:
            if "ml" in features or "ai" in features:
                backend_rec = ("FastAPI", "Excellent for ML services, async support")
            else:
                backend_rec = ("FastAPI or Django", "Python ecosystem, great for APIs")
        elif "go" in [s.lower() for s in existing_skills]:
            backend_rec = ("Go + Chi/Gin", "High performance, excellent concurrency")
        elif scale == "enterprise":
            backend_rec = (
                "Go or Java/Spring",
                "Enterprise-grade performance and tooling",
            )
        else:
            backend_rec = (
                "Node.js + Express/Fastify",
                "JavaScript ecosystem, rapid development",
            )

    # Recommend database
    db_rec = None
    if "nosql" in constraints:
        db_rec = ("MongoDB", "Flexible schema, horizontal scaling")
    elif "real-time" in features:
        db_rec = ("PostgreSQL + Redis", "Relational + caching for real-time")
    elif scale == "enterprise":
        db_rec = ("PostgreSQL", "Robust, ACID-compliant, excellent features")
    else:
        db_rec = ("PostgreSQL", "Best general-purpose choice")

    # Recommend deployment
    deploy_rec = None
    if pattern == "serverless":
        deploy_rec = ("AWS Lambda + Vercel", "Serverless-first platforms")
    elif scale == "enterprise":
        deploy_rec = ("AWS/GCP + Kubernetes", "Full control and scaling")
    elif frontend_rec and "Next.js" in frontend_rec[0]:
        deploy_rec = ("Vercel + Railway/Render", "Optimized for Next.js + backend")
    else:
        deploy_rec = ("Railway or Render", "Simple deployment with databases")

    # Build output
    lines = ["## Tech Stack Recommendation\n"]

    lines.append("### Architecture Pattern")
    lines.append(f"**Recommended**: {pattern.replace('_', ' ').title()}")
    pattern_info = ARCHITECTURE_PATTERNS.get(pattern, {})
    lines.append(f"\n{pattern_info.get('description', '')}")
    lines.append(f"\n**Pros**: {', '.join(pattern_info.get('pros', []))}")
    lines.append(f"**Cons**: {', '.join(pattern_info.get('cons', []))}")

    lines.append("\n### Recommended Stack")

    if frontend_rec:
        lines.append(f"\n**Frontend**: {frontend_rec[0]}")
        lines.append(f"- {frontend_rec[1]}")

    if backend_rec:
        lines.append(f"\n**Backend**: {backend_rec[0]}")
        lines.append(f"- {backend_rec[1]}")

    if db_rec:
        lines.append(f"\n**Database**: {db_rec[0]}")
        lines.append(f"- {db_rec[1]}")

    if deploy_rec:
        lines.append(f"\n**Deployment**: {deploy_rec[0]}")
        lines.append(f"- {deploy_rec[1]}")

    # Additional recommendations
    lines.append("\n### Additional Recommendations")
    lines.append("- **Version Control**: Git + GitHub/GitLab")
    lines.append("- **CI/CD**: GitHub Actions")
    lines.append("- **Monitoring**: Sentry + Datadog/New Relic")
    lines.append("- **Testing**: Jest/Vitest (JS) or pytest (Python)")

    # Considerations based on requirements
    lines.append("\n### Considerations")
    if scale == "enterprise":
        lines.append("- Plan for horizontal scaling from the start")
        lines.append("- Implement comprehensive monitoring and alerting")
        lines.append("- Consider multi-region deployment for high availability")
    if "ml" in features or "ai" in features:
        lines.append("- Consider GPU instances for model inference")
        lines.append("- Implement model versioning and A/B testing")
    if "real-time" in features:
        lines.append("- Use WebSockets or Server-Sent Events for real-time updates")
        lines.append("- Consider Redis Pub/Sub for message broadcasting")

    return ToolResult(output="\n".join(lines), sources=[])


async def design_system_architecture(
    context: Dict[str, Any],
    description: str,
    pattern: Optional[str] = None,
) -> ToolResult:
    """
    Design system architecture from requirements description.

    Args:
        description: Natural language description of the system
        pattern: Optional specific pattern (monolith, microservices, serverless, event_driven)

    Returns:
        ToolResult with architecture design and diagrams
    """
    logger.info("design_system_architecture", description=description[:100])

    # Parse description for components
    components = _extract_components(description)

    # Determine pattern if not specified
    if not pattern:
        if len(components) > 5:
            pattern = "microservices"
        elif "event" in description.lower() or "real-time" in description.lower():
            pattern = "event_driven"
        elif "serverless" in description.lower() or "function" in description.lower():
            pattern = "serverless"
        else:
            pattern = "modular_monolith"

    pattern_info = ARCHITECTURE_PATTERNS.get(pattern, ARCHITECTURE_PATTERNS["monolith"])

    lines = ["## System Architecture Design\n"]
    lines.append(f"**Pattern**: {pattern.replace('_', ' ').title()}")
    lines.append(f"\n{pattern_info['description']}")

    # Generate component list
    lines.append("\n### System Components")
    if components:
        for comp in components:
            lines.append(f"\n#### {comp['name']}")
            lines.append(f"- **Responsibility**: {comp['responsibility']}")
            lines.append(f"- **Type**: {comp['type']}")
            if comp.get("dependencies"):
                lines.append(f"- **Dependencies**: {', '.join(comp['dependencies'])}")
    else:
        # Default components based on description
        lines.append("\n#### API Gateway")
        lines.append("- Entry point for all client requests")
        lines.append("- Authentication and rate limiting")

        lines.append("\n#### Core Service")
        lines.append("- Main business logic")
        lines.append("- Domain operations")

        lines.append("\n#### Database Layer")
        lines.append("- Data persistence")
        lines.append("- Query optimization")

    # Data flow
    lines.append("\n### Data Flow")
    if pattern == "event_driven":
        lines.append("1. Client sends request to API Gateway")
        lines.append("2. API Gateway publishes event to message queue")
        lines.append("3. Relevant services consume and process events")
        lines.append("4. Results published as new events")
        lines.append("5. Response aggregated and returned to client")
    elif pattern == "microservices":
        lines.append("1. Client request hits API Gateway/Load Balancer")
        lines.append("2. Request routed to appropriate service")
        lines.append("3. Service processes request, may call other services")
        lines.append("4. Each service accesses its own database")
        lines.append("5. Response aggregated and returned")
    else:
        lines.append("1. Client sends request to application")
        lines.append("2. Controller receives and validates request")
        lines.append("3. Service layer executes business logic")
        lines.append("4. Repository layer interacts with database")
        lines.append("5. Response returned through the layers")

    # Architecture diagram
    lines.append("\n### Architecture Diagram")
    lines.append("```mermaid")
    lines.append(_generate_architecture_diagram(pattern, components))
    lines.append("```")

    # Technology recommendations
    lines.append("\n### Technology Recommendations")
    if pattern == "microservices":
        lines.append("- **Service Communication**: gRPC or REST")
        lines.append("- **Service Discovery**: Consul or Kubernetes DNS")
        lines.append("- **API Gateway**: Kong, AWS API Gateway, or Nginx")
        lines.append("- **Message Queue**: RabbitMQ, Kafka, or AWS SQS")
    elif pattern == "event_driven":
        lines.append("- **Event Bus**: Apache Kafka or AWS EventBridge")
        lines.append("- **Event Store**: EventStoreDB or custom")
        lines.append("- **Saga Orchestration**: Temporal or custom")
    elif pattern == "serverless":
        lines.append(
            "- **Functions**: AWS Lambda, Vercel Functions, or Cloudflare Workers"
        )
        lines.append("- **API**: AWS API Gateway or Vercel")
        lines.append("- **Database**: DynamoDB, Fauna, or PlanetScale")
    else:
        lines.append("- **Framework**: Next.js, Django, or Rails")
        lines.append("- **Database**: PostgreSQL")
        lines.append("- **Caching**: Redis")

    # Non-functional requirements
    lines.append("\n### Non-Functional Considerations")
    lines.append(
        "- **Scalability**: "
        + (
            "Horizontal scaling via service replication"
            if pattern == "microservices"
            else "Vertical scaling + read replicas"
        )
    )
    lines.append(
        "- **Availability**: Multi-AZ deployment, health checks, auto-recovery"
    )
    lines.append(
        "- **Security**: TLS everywhere, authentication at gateway, principle of least privilege"
    )
    lines.append(
        "- **Observability**: Distributed tracing, centralized logging, metrics dashboards"
    )

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_architecture_diagram(
    context: Dict[str, Any],
    workspace_path: str,
    format: str = "mermaid",
) -> ToolResult:
    """
    Generate architecture diagram from existing codebase.

    Args:
        workspace_path: Path to the project root
        format: Output format (mermaid, plantuml, c4)

    Returns:
        ToolResult with generated diagram
    """
    logger.info("generate_architecture_diagram", workspace_path=workspace_path)

    if not os.path.exists(workspace_path):
        return ToolResult(output=f"Directory not found: {workspace_path}", sources=[])

    # Analyze project structure
    structure = _analyze_codebase_structure(workspace_path)

    lines = ["## Architecture Diagram\n"]
    lines.append(f"**Format**: {format}")
    lines.append(f"**Components Found**: {len(structure['components'])}")

    if format == "mermaid":
        diagram = _generate_mermaid_from_structure(structure)
        lines.append("\n### System Overview")
        lines.append("```mermaid")
        lines.append(diagram)
        lines.append("```")

        # Component diagram
        lines.append("\n### Component Diagram")
        lines.append("```mermaid")
        lines.append(_generate_component_diagram(structure))
        lines.append("```")

    elif format == "c4":
        lines.append("\n### C4 Context Diagram")
        lines.append("```mermaid")
        lines.append(_generate_c4_diagram(structure))
        lines.append("```")

    elif format == "plantuml":
        diagram = _generate_plantuml_from_structure(structure)
        lines.append("\n### PlantUML Diagram")
        lines.append("```plantuml")
        lines.append(diagram)
        lines.append("```")

    # Dependencies
    if structure.get("dependencies"):
        lines.append("\n### Key Dependencies")
        for dep, version in list(structure["dependencies"].items())[:10]:
            lines.append(f"- {dep}: {version}")

    return ToolResult(output="\n".join(lines), sources=[])


async def decompose_to_microservices(
    context: Dict[str, Any],
    workspace_path: str,
    strategy: str = "domain",
) -> ToolResult:
    """
    Analyze monolith and suggest microservices decomposition.

    Args:
        workspace_path: Path to the project root
        strategy: Decomposition strategy (domain, feature, layer)

    Returns:
        ToolResult with decomposition plan
    """
    logger.info(
        "decompose_to_microservices", workspace_path=workspace_path, strategy=strategy
    )

    if not os.path.exists(workspace_path):
        return ToolResult(output=f"Directory not found: {workspace_path}", sources=[])

    # Analyze codebase
    structure = _analyze_codebase_structure(workspace_path)

    lines = ["## Microservices Decomposition Plan\n"]
    lines.append(f"**Strategy**: {strategy.title()}-Driven Decomposition")

    # Identify bounded contexts
    contexts = _identify_bounded_contexts(structure, strategy)

    lines.append("\n### Identified Bounded Contexts")
    for i, ctx in enumerate(contexts, 1):
        lines.append(f"\n#### {i}. {ctx['name']} Service")
        lines.append(f"**Responsibility**: {ctx['responsibility']}")
        lines.append(f"**Entities**: {', '.join(ctx.get('entities', ['N/A']))}")
        lines.append(f"**API Endpoints**: {', '.join(ctx.get('endpoints', ['N/A']))}")

    # Migration plan
    lines.append("\n### Migration Plan")
    lines.append("\n**Phase 1: Preparation**")
    lines.append("1. Add clear module boundaries in monolith")
    lines.append("2. Define interfaces between modules")
    lines.append("3. Implement feature flags for gradual rollout")
    lines.append("4. Set up monitoring and distributed tracing")

    lines.append("\n**Phase 2: Extract First Service**")
    lines.append("1. Choose the most independent bounded context")
    lines.append("2. Create new service with its own database")
    lines.append("3. Implement API gateway for routing")
    lines.append("4. Use strangler fig pattern for gradual migration")

    lines.append("\n**Phase 3: Continue Extraction**")
    lines.append("1. Extract remaining services one at a time")
    lines.append("2. Implement event-driven communication where needed")
    lines.append("3. Handle distributed transactions with sagas")
    lines.append("4. Decommission monolith components as extracted")

    # Risks and mitigations
    lines.append("\n### Risks and Mitigations")
    lines.append("| Risk | Mitigation |")
    lines.append("|------|------------|")
    lines.append("| Data consistency | Use saga pattern, eventual consistency |")
    lines.append("| Network failures | Circuit breakers, retries with backoff |")
    lines.append("| Debugging complexity | Distributed tracing, centralized logging |")
    lines.append("| Operational overhead | Kubernetes, service mesh, GitOps |")

    # Diagram
    lines.append("\n### Target Architecture")
    lines.append("```mermaid")
    lines.append(_generate_microservices_diagram(contexts))
    lines.append("```")

    return ToolResult(output="\n".join(lines), sources=[])


async def generate_adr(
    context: Dict[str, Any],
    title: str,
    context_text: str,
    decision: str,
    alternatives: Optional[List[str]] = None,
) -> ToolResult:
    """
    Generate an Architecture Decision Record (ADR).

    Args:
        title: ADR title
        context_text: Context and problem statement
        decision: The decision made
        alternatives: List of alternatives considered

    Returns:
        ToolResult with generated ADR
    """
    logger.info("generate_adr", title=title)

    # Generate ADR number (would normally read from existing ADRs)
    adr_number = "0001"

    date = datetime.now().strftime("%Y-%m-%d")

    # Parse decision for consequences
    positive = [
        "Aligns with current team skills",
        "Proven technology with good ecosystem",
        "Supports future scaling requirements",
    ]

    negative = [
        "May require learning curve for some team members",
        "Adds some operational complexity",
    ]

    # Format alternatives
    if alternatives:
        alt_text = "\n".join(
            f"- **{alt}**: Considered but rejected because..." for alt in alternatives
        )
    else:
        alt_text = "No alternatives were formally evaluated."

    adr_content = ADR_TEMPLATE.format(
        number=adr_number,
        title=title,
        date=date,
        status="Proposed",
        context=context_text,
        decision=decision,
        positive_consequences="\n".join(f"- {p}" for p in positive),
        negative_consequences="\n".join(f"- {n}" for n in negative),
        alternatives=alt_text,
    )

    lines = ["## Generated Architecture Decision Record\n"]
    lines.append(f"**Title**: {title}")
    lines.append(f"**Number**: ADR-{adr_number}")

    lines.append("\n### ADR Content")
    lines.append("```markdown")
    lines.append(adr_content)
    lines.append("```")

    lines.append("\n### Next Steps")
    lines.append(
        f"1. Save to `docs/adr/{adr_number}-{title.lower().replace(' ', '-')}.md`"
    )
    lines.append("2. Review with team")
    lines.append("3. Update status to 'Accepted' or 'Rejected'")
    lines.append("4. Link to related ADRs if applicable")

    return ToolResult(output="\n".join(lines), sources=[])


async def analyze_dependencies(
    context: Dict[str, Any],
    workspace_path: str,
) -> ToolResult:
    """
    Analyze project dependencies for security and architecture concerns.

    Args:
        workspace_path: Path to the project root

    Returns:
        ToolResult with dependency analysis
    """
    logger.info("analyze_dependencies", workspace_path=workspace_path)

    if not os.path.exists(workspace_path):
        return ToolResult(output=f"Directory not found: {workspace_path}", sources=[])

    analysis = {
        "direct_deps": 0,
        "dev_deps": 0,
        "outdated": [],
        "security_concerns": [],
        "large_deps": [],
        "duplicate_functionality": [],
    }

    # Analyze package.json
    package_json_path = os.path.join(workspace_path, "package.json")
    if os.path.exists(package_json_path):
        try:
            with open(package_json_path, "r") as f:
                pkg = json.load(f)

            deps = pkg.get("dependencies", {})
            dev_deps = pkg.get("devDependencies", {})

            analysis["direct_deps"] = len(deps)
            analysis["dev_deps"] = len(dev_deps)

            # Check for known large dependencies
            large_deps = ["moment", "lodash", "jquery", "rxjs"]
            for dep in large_deps:
                if dep in deps:
                    analysis["large_deps"].append(
                        {
                            "name": dep,
                            "suggestion": _get_lightweight_alternative(dep),
                        }
                    )

            # Check for duplicate functionality
            date_libs = ["moment", "dayjs", "date-fns", "luxon"]
            found_date = [d for d in date_libs if d in deps]
            if len(found_date) > 1:
                analysis["duplicate_functionality"].append(
                    {
                        "category": "Date manipulation",
                        "packages": found_date,
                        "suggestion": "Consider using only one (date-fns recommended)",
                    }
                )

        except (json.JSONDecodeError, IOError):
            pass

    # Analyze requirements.txt
    requirements_path = os.path.join(workspace_path, "requirements.txt")
    if os.path.exists(requirements_path):
        try:
            with open(requirements_path, "r") as f:
                lines_content = f.readlines()
                analysis["direct_deps"] = len(
                    [l for l in lines_content if l.strip() and not l.startswith("#")]
                )
        except IOError:
            pass

    # Build output
    lines = ["## Dependency Analysis\n"]
    lines.append(f"**Direct Dependencies**: {analysis['direct_deps']}")
    lines.append(f"**Dev Dependencies**: {analysis['dev_deps']}")

    if analysis["large_deps"]:
        lines.append("\n### Large Dependencies")
        lines.append("Consider lighter alternatives:")
        for dep in analysis["large_deps"]:
            lines.append(f"- **{dep['name']}**: {dep['suggestion']}")

    if analysis["duplicate_functionality"]:
        lines.append("\n### Duplicate Functionality")
        for dup in analysis["duplicate_functionality"]:
            lines.append(f"- **{dup['category']}**: {', '.join(dup['packages'])}")
            lines.append(f"  - {dup['suggestion']}")

    lines.append("\n### Recommendations")
    lines.append("1. Run `npm audit` or `pip-audit` for security vulnerabilities")
    lines.append("2. Use `npm outdated` or `pip list --outdated` for updates")
    lines.append("3. Consider dependency injection for better testability")
    lines.append("4. Document why each dependency is needed")

    return ToolResult(output="\n".join(lines), sources=[])


# Helper functions


def _extract_components(description: str) -> List[Dict]:
    """Extract system components from description."""
    components = []

    # Common component patterns
    patterns = [
        (r"\b(user|auth|authentication)\b", "Authentication Service", "security"),
        (r"\b(payment|billing|checkout)\b", "Payment Service", "business"),
        (r"\b(notification|email|sms)\b", "Notification Service", "infrastructure"),
        (r"\b(product|catalog|inventory)\b", "Product Service", "business"),
        (r"\b(order|cart|shopping)\b", "Order Service", "business"),
        (r"\b(search|filter)\b", "Search Service", "infrastructure"),
        (r"\b(analytics|reporting|metrics)\b", "Analytics Service", "infrastructure"),
        (r"\b(api|gateway)\b", "API Gateway", "infrastructure"),
    ]

    desc_lower = description.lower()
    for pattern, name, comp_type in patterns:
        if re.search(pattern, desc_lower):
            components.append(
                {
                    "name": name,
                    "responsibility": f"Handles {name.lower().replace(' service', '')} functionality",
                    "type": comp_type,
                    "dependencies": [],
                }
            )

    return components


def _generate_architecture_diagram(pattern: str, components: List[Dict]) -> str:
    """Generate Mermaid architecture diagram."""
    lines = ["graph TB"]

    if pattern == "microservices":
        lines.append("    Client[Client Application]")
        lines.append("    Gateway[API Gateway]")
        lines.append("    Client --> Gateway")

        for comp in components:
            safe_name = comp["name"].replace(" ", "_")
            lines.append(f"    {safe_name}[{comp['name']}]")
            lines.append(f"    Gateway --> {safe_name}")
            lines.append(f"    {safe_name} --> {safe_name}_DB[({comp['name']} DB)]")

    elif pattern == "event_driven":
        lines.append("    Client[Client]")
        lines.append("    API[API Layer]")
        lines.append("    Queue[Message Queue]")
        lines.append("    Client --> API")
        lines.append("    API --> Queue")

        for comp in components:
            safe_name = comp["name"].replace(" ", "_")
            lines.append(f"    {safe_name}[{comp['name']}]")
            lines.append(f"    Queue --> {safe_name}")

    else:  # monolith/modular
        lines.append("    Client[Client]")
        lines.append("    App[Application]")
        lines.append("    DB[(Database)]")
        lines.append("    Client --> App")
        lines.append("    App --> DB")

    return "\n".join(lines)


def _analyze_codebase_structure(workspace_path: str) -> Dict:
    """Analyze codebase structure for architecture understanding."""
    structure = {
        "components": [],
        "dependencies": {},
        "layers": [],
        "type": "unknown",
    }

    # Check package.json
    package_json_path = os.path.join(workspace_path, "package.json")
    if os.path.exists(package_json_path):
        try:
            with open(package_json_path, "r") as f:
                pkg = json.load(f)
                structure["dependencies"] = pkg.get("dependencies", {})

                if "next" in structure["dependencies"]:
                    structure["type"] = "nextjs"
                elif "express" in structure["dependencies"]:
                    structure["type"] = "express"
        except (json.JSONDecodeError, IOError):
            pass

    # Scan directory structure
    for item in os.listdir(workspace_path):
        item_path = os.path.join(workspace_path, item)
        if os.path.isdir(item_path) and not item.startswith("."):
            if item in ("api", "routes", "controllers"):
                structure["layers"].append(("API", item))
                structure["components"].append({"name": "API Layer", "path": item})
            elif item in ("services", "business", "domain"):
                structure["layers"].append(("Business", item))
                structure["components"].append({"name": "Business Logic", "path": item})
            elif item in ("models", "entities", "schemas"):
                structure["layers"].append(("Data", item))
                structure["components"].append({"name": "Data Layer", "path": item})
            elif item in ("components", "views", "pages"):
                structure["layers"].append(("UI", item))
                structure["components"].append({"name": "UI Layer", "path": item})

    return structure


def _generate_mermaid_from_structure(structure: Dict) -> str:
    """Generate Mermaid diagram from structure analysis."""
    lines = ["graph TD"]

    lines.append("    Client[Client/Browser]")

    if structure["type"] == "nextjs":
        lines.append("    NextJS[Next.js Application]")
        lines.append("    API[API Routes]")
        lines.append("    DB[(Database)]")
        lines.append("    Client --> NextJS")
        lines.append("    NextJS --> API")
        lines.append("    API --> DB")
    else:
        lines.append("    App[Application]")
        lines.append("    DB[(Database)]")
        lines.append("    Client --> App")
        lines.append("    App --> DB")

    return "\n".join(lines)


def _generate_component_diagram(structure: Dict) -> str:
    """Generate component diagram."""
    lines = ["graph LR"]

    for comp in structure["components"]:
        safe_name = comp["name"].replace(" ", "_")
        lines.append(f"    {safe_name}[{comp['name']}]")

    # Connect layers
    if len(structure["components"]) >= 2:
        for i in range(len(structure["components"]) - 1):
            name1 = structure["components"][i]["name"].replace(" ", "_")
            name2 = structure["components"][i + 1]["name"].replace(" ", "_")
            lines.append(f"    {name1} --> {name2}")

    return "\n".join(lines)


def _generate_c4_diagram(structure: Dict) -> str:
    """Generate C4 context diagram in Mermaid."""
    lines = ["C4Context"]
    lines.append("    title System Context Diagram")
    lines.append("")
    lines.append('    Person(user, "User", "A user of the system")')
    lines.append('    System(system, "System", "The main application")')
    lines.append('    System_Ext(email, "Email Service", "Sends emails")')
    lines.append("")
    lines.append('    Rel(user, system, "Uses")')
    lines.append('    Rel(system, email, "Sends emails via")')

    return "\n".join(lines)


def _generate_plantuml_from_structure(structure: Dict) -> str:
    """Generate PlantUML diagram."""
    lines = ["@startuml"]
    lines.append(
        "!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml"
    )
    lines.append("")
    lines.append('Person(user, "User")')
    lines.append('System(system, "Application")')
    lines.append('Rel(user, system, "Uses")')
    lines.append("")
    lines.append("@enduml")

    return "\n".join(lines)


def _identify_bounded_contexts(structure: Dict, strategy: str) -> List[Dict]:
    """Identify bounded contexts for microservices."""
    contexts = []

    if strategy == "domain":
        # Domain-driven contexts
        contexts = [
            {
                "name": "User Management",
                "responsibility": "Handle user authentication, authorization, and profile management",
                "entities": ["User", "Role", "Permission"],
                "endpoints": ["/auth/*", "/users/*"],
            },
            {
                "name": "Core Business",
                "responsibility": "Main business logic and domain operations",
                "entities": ["Order", "Product", "Transaction"],
                "endpoints": ["/api/*"],
            },
            {
                "name": "Notification",
                "responsibility": "Handle all notifications (email, SMS, push)",
                "entities": ["Notification", "Template"],
                "endpoints": ["/notifications/*"],
            },
        ]
    elif strategy == "feature":
        contexts = [
            {
                "name": "Feature A Service",
                "responsibility": "Handle feature A",
                "entities": [],
                "endpoints": [],
            },
            {
                "name": "Feature B Service",
                "responsibility": "Handle feature B",
                "entities": [],
                "endpoints": [],
            },
        ]
    else:  # layer
        contexts = [
            {
                "name": "API Gateway",
                "responsibility": "Handle all incoming requests",
                "entities": [],
                "endpoints": ["/*"],
            },
            {
                "name": "Business Service",
                "responsibility": "Business logic",
                "entities": [],
                "endpoints": [],
            },
            {
                "name": "Data Service",
                "responsibility": "Data access",
                "entities": [],
                "endpoints": [],
            },
        ]

    return contexts


def _generate_microservices_diagram(contexts: List[Dict]) -> str:
    """Generate microservices architecture diagram."""
    lines = ["graph TB"]
    lines.append("    Client[Client]")
    lines.append("    Gateway[API Gateway]")
    lines.append("    Queue[Message Queue]")
    lines.append("")
    lines.append("    Client --> Gateway")
    lines.append("    Gateway --> Queue")

    for ctx in contexts:
        safe_name = ctx["name"].replace(" ", "_")
        lines.append(f"    {safe_name}[{ctx['name']}]")
        lines.append(f"    Gateway --> {safe_name}")
        lines.append(f"    Queue -.-> {safe_name}")
        lines.append(f"    {safe_name} --> {safe_name}_DB[({ctx['name']} DB)]")

    return "\n".join(lines)


def _get_lightweight_alternative(dep: str) -> str:
    """Get lightweight alternative for heavy dependencies."""
    alternatives = {
        "moment": "Use date-fns or dayjs (smaller bundle)",
        "lodash": "Use native ES6+ methods or lodash-es with tree-shaking",
        "jquery": "Use native DOM APIs or lightweight alternatives",
        "rxjs": "Consider using native Promises/async-await for simpler cases",
    }
    return alternatives.get(dep, "Consider if this dependency is necessary")


# Export tools for the agent dispatcher
ARCHITECTURE_TOOLS = {
    "arch_recommend_stack": recommend_tech_stack,
    "arch_design_system": design_system_architecture,
    "arch_generate_diagram": generate_architecture_diagram,
    "arch_decompose_microservices": decompose_to_microservices,
    "arch_generate_adr": generate_adr,
    "arch_analyze_dependencies": analyze_dependencies,
}
