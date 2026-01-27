"""
Checkpoint Gate Detector for Enterprise NAVI.

Detects when human checkpoint gates should be triggered based on:
- Architecture decisions (new major components, database choices)
- Security-sensitive operations (auth, payment, PII handling)
- Cost implications (expensive cloud resources)
- Deployment decisions (production deployments)
- Milestone completions

This enables human-in-the-loop oversight for enterprise projects.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class GateTrigger:
    """A detected gate trigger with context."""

    gate_type: str
    title: str
    description: str
    trigger_context: Dict[str, Any]
    options: List[Dict[str, Any]]
    priority: str = "normal"
    blocks_progress: bool = True


class CheckpointGateDetector:
    """
    Detects when to trigger human checkpoint gates.

    Analyzes LLM outputs, tool calls, and context to determine if a human
    checkpoint gate should be created before proceeding.
    """

    # Architecture decision patterns
    ARCHITECTURE_PATTERNS = [
        # Database choices
        (r"(?:choosing|selecting|using|implementing)\s+(?:postgres|mysql|mongodb|redis|dynamodb|sqlite)", "database_choice"),
        (r"(?:create|setup|configure)\s+(?:database|db)\s+(?:schema|tables?|models?)", "database_schema"),
        # Framework choices
        (r"(?:using|implementing|choosing)\s+(?:react|vue|angular|next\.?js|express|fastapi|django|flask)", "framework_choice"),
        # Infrastructure choices
        (r"(?:deploying to|using|setting up)\s+(?:aws|gcp|azure|kubernetes|docker|terraform)", "infrastructure_choice"),
        # Authentication choices
        (r"(?:implementing|adding|using)\s+(?:oauth|jwt|auth0|cognito|firebase auth|authentication)", "auth_choice"),
        # Major architectural patterns
        (r"(?:implementing|using)\s+(?:microservices?|monolith|serverless|event[- ]?driven|cqrs)", "architecture_pattern"),
    ]

    # Security-sensitive patterns
    SECURITY_PATTERNS = [
        # Payment processing
        (r"(?:stripe|paypal|braintree|payment|billing|credit card|checkout)", "payment_processing"),
        # User authentication
        (r"(?:password|login|signup|register|authentication|authorization)", "user_auth"),
        # Personal data handling
        (r"(?:pii|personal\s+(?:data|information)|gdpr|ccpa|user\s+data|email|phone|address)", "personal_data"),
        # API keys and secrets
        (r"(?:api[_\s]?key|secret|credential|token|password)\s*(?:=|:)", "secrets_handling"),
        # Encryption
        (r"(?:encrypt|decrypt|hash|bcrypt|argon2|aes|rsa)", "encryption"),
    ]

    # Cost-sensitive patterns
    COST_PATTERNS = [
        # Expensive cloud resources
        (r"(?:provision|create|launch)\s+(?:rds|aurora|redshift|bigquery|elasticsearch)", "expensive_database"),
        (r"(?:provision|create|launch)\s+(?:eks|ecs|gke|aks|kubernetes cluster)", "kubernetes_cluster"),
        (r"(?:ml|machine learning|ai|gpu|sagemaker|vertex)", "ml_resources"),
        # Storage
        (r"(?:s3|gcs|azure blob)\s+(?:bucket|storage)", "cloud_storage"),
        # High-tier instances
        (r"(?:m5|c5|r5|p3|g4)\.(?:xlarge|2xlarge|4xlarge|8xlarge|metal)", "large_instances"),
    ]

    # Deployment patterns
    DEPLOYMENT_PATTERNS = [
        (r"(?:deploy|release|push)\s+(?:to|into)\s+(?:prod|production)", "production_deploy"),
        (r"(?:kubectl apply|helm install|terraform apply)\s+.*(?:prod|production)", "infra_deploy"),
        (r"(?:merge|push)\s+(?:to|into)\s+(?:main|master|release)", "main_branch_merge"),
    ]

    def __init__(self, enterprise_project_id: Optional[str] = None):
        """Initialize detector with optional enterprise project link."""
        self.enterprise_project_id = enterprise_project_id
        self._detected_gates: List[str] = []  # Track already detected gates to avoid duplicates

    def detect_gates(
        self,
        llm_output: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        files_to_create: Optional[List[str]] = None,
        files_to_modify: Optional[List[str]] = None,
        commands_to_run: Optional[List[str]] = None,
        current_task: Optional[str] = None,
    ) -> List[GateTrigger]:
        """
        Detect all applicable checkpoint gates based on the provided context.

        Returns list of GateTriggers, ordered by priority.
        """
        triggers: List[GateTrigger] = []

        # Combine all text for pattern matching
        text_to_analyze = ""
        if llm_output:
            text_to_analyze += llm_output.lower() + " "
        if current_task:
            text_to_analyze += current_task.lower() + " "
        if commands_to_run:
            text_to_analyze += " ".join(commands_to_run).lower() + " "

        # Check architecture patterns
        arch_trigger = self._check_architecture_gates(text_to_analyze, files_to_create)
        if arch_trigger:
            triggers.append(arch_trigger)

        # Check security patterns
        security_trigger = self._check_security_gates(text_to_analyze, files_to_create, files_to_modify)
        if security_trigger:
            triggers.append(security_trigger)

        # Check cost patterns
        cost_trigger = self._check_cost_gates(text_to_analyze, commands_to_run)
        if cost_trigger:
            triggers.append(cost_trigger)

        # Check deployment patterns
        deploy_trigger = self._check_deployment_gates(text_to_analyze, commands_to_run)
        if deploy_trigger:
            triggers.append(deploy_trigger)

        # Sort by priority (critical > high > normal > low)
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        triggers.sort(key=lambda t: priority_order.get(t.priority, 2))

        return triggers

    def _check_architecture_gates(
        self,
        text: str,
        files_to_create: Optional[List[str]] = None,
    ) -> Optional[GateTrigger]:
        """Check for architecture decision gates."""
        matches = []
        for pattern, pattern_type in self.ARCHITECTURE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                matches.append(pattern_type)

        # Also check file patterns for architecture indicators
        if files_to_create:
            for file in files_to_create:
                file_lower = file.lower()
                if any(x in file_lower for x in ["schema", "migration", "models.py", "entities"]):
                    matches.append("database_schema")
                if any(x in file_lower for x in ["docker", "kubernetes", "k8s", "terraform", "helm"]):
                    matches.append("infrastructure_choice")

        if not matches:
            return None

        # Avoid duplicate gates
        gate_key = f"architecture_{sorted(set(matches))}"
        if gate_key in self._detected_gates:
            return None
        self._detected_gates.append(gate_key)

        # Determine specific gate based on matches
        if "database_choice" in matches or "database_schema" in matches:
            return GateTrigger(
                gate_type="architecture_review",
                title="Database Architecture Decision",
                description="A database architecture decision is being made. Please review and approve the approach.",
                trigger_context={"detected_patterns": matches},
                options=[
                    {
                        "id": "approve",
                        "label": "Approve",
                        "description": "Proceed with the proposed database architecture",
                        "recommended": True,
                    },
                    {
                        "id": "modify",
                        "label": "Request Changes",
                        "description": "Pause and discuss alternative approaches",
                    },
                    {
                        "id": "reject",
                        "label": "Reject",
                        "description": "Stop and reconsider the database strategy",
                    },
                ],
                priority="high",
            )

        if "infrastructure_choice" in matches:
            return GateTrigger(
                gate_type="architecture_review",
                title="Infrastructure Architecture Decision",
                description="An infrastructure/deployment architecture decision is being made.",
                trigger_context={"detected_patterns": matches},
                options=[
                    {
                        "id": "approve",
                        "label": "Approve",
                        "description": "Proceed with the proposed infrastructure",
                        "recommended": True,
                    },
                    {
                        "id": "modify",
                        "label": "Request Changes",
                        "description": "Discuss alternative infrastructure approaches",
                    },
                ],
                priority="high",
            )

        # Generic architecture review
        return GateTrigger(
            gate_type="architecture_review",
            title="Architecture Decision Required",
            description=f"Architecture decisions detected: {', '.join(set(matches))}. Please review.",
            trigger_context={"detected_patterns": matches},
            options=[
                {"id": "approve", "label": "Approve", "description": "Proceed with the approach", "recommended": True},
                {"id": "discuss", "label": "Discuss", "description": "Pause for discussion"},
            ],
            priority="normal",
        )

    def _check_security_gates(
        self,
        text: str,
        files_to_create: Optional[List[str]] = None,
        files_to_modify: Optional[List[str]] = None,
    ) -> Optional[GateTrigger]:
        """Check for security-sensitive gates."""
        matches = []
        for pattern, pattern_type in self.SECURITY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                matches.append(pattern_type)

        # Check file patterns for security indicators
        all_files = (files_to_create or []) + (files_to_modify or [])
        for file in all_files:
            file_lower = file.lower()
            if any(x in file_lower for x in ["auth", "login", "password", "security"]):
                matches.append("user_auth")
            if any(x in file_lower for x in ["payment", "billing", "checkout", "stripe"]):
                matches.append("payment_processing")

        if not matches:
            return None

        # Avoid duplicate gates
        gate_key = f"security_{sorted(set(matches))}"
        if gate_key in self._detected_gates:
            return None
        self._detected_gates.append(gate_key)

        # Payment is highest priority
        if "payment_processing" in matches:
            return GateTrigger(
                gate_type="security_review",
                title="Payment Integration Security Review",
                description="Payment processing code is being modified. This requires security review before proceeding.",
                trigger_context={"detected_patterns": matches},
                options=[
                    {
                        "id": "approve",
                        "label": "Approve After Review",
                        "description": "I've reviewed the payment integration approach",
                    },
                    {
                        "id": "security_audit",
                        "label": "Request Security Audit",
                        "description": "Require formal security audit before proceeding",
                    },
                    {
                        "id": "reject",
                        "label": "Stop",
                        "description": "Do not proceed with payment integration",
                    },
                ],
                priority="critical",
                blocks_progress=True,
            )

        if "secrets_handling" in matches:
            return GateTrigger(
                gate_type="security_review",
                title="Secrets Handling Review",
                description="Code handling secrets/credentials detected. Please verify secure practices.",
                trigger_context={"detected_patterns": matches},
                options=[
                    {"id": "approve", "label": "Approve", "description": "Secrets handling is secure"},
                    {"id": "modify", "label": "Improve Security", "description": "Request more secure approach"},
                ],
                priority="high",
            )

        # Generic security review
        return GateTrigger(
            gate_type="security_review",
            title="Security-Sensitive Code Review",
            description=f"Security-sensitive operations detected: {', '.join(set(matches))}.",
            trigger_context={"detected_patterns": matches},
            options=[
                {"id": "approve", "label": "Approve", "description": "Security approach is acceptable", "recommended": True},
                {"id": "review", "label": "Request Review", "description": "Need security team review"},
            ],
            priority="high",
        )

    def _check_cost_gates(
        self,
        text: str,
        commands_to_run: Optional[List[str]] = None,
    ) -> Optional[GateTrigger]:
        """Check for cost-sensitive gates."""
        matches = []
        for pattern, pattern_type in self.COST_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                matches.append(pattern_type)

        # Check commands for cost indicators
        if commands_to_run:
            for cmd in commands_to_run:
                cmd_lower = cmd.lower()
                if any(x in cmd_lower for x in ["terraform apply", "pulumi up", "aws create", "gcloud create"]):
                    matches.append("infrastructure_provision")

        if not matches:
            return None

        # Avoid duplicate gates
        gate_key = f"cost_{sorted(set(matches))}"
        if gate_key in self._detected_gates:
            return None
        self._detected_gates.append(gate_key)

        # Kubernetes clusters and ML resources are expensive
        if "kubernetes_cluster" in matches or "ml_resources" in matches:
            return GateTrigger(
                gate_type="cost_approval",
                title="Expensive Resource Provisioning",
                description="About to provision expensive cloud resources. Please approve the cost.",
                trigger_context={"detected_patterns": matches},
                options=[
                    {
                        "id": "approve",
                        "label": "Approve Cost",
                        "description": "Proceed with provisioning these resources",
                    },
                    {
                        "id": "estimate",
                        "label": "Get Cost Estimate",
                        "description": "Show estimated monthly cost before proceeding",
                    },
                    {
                        "id": "reduce",
                        "label": "Use Smaller Resources",
                        "description": "Use smaller/cheaper resource options",
                    },
                    {
                        "id": "reject",
                        "label": "Do Not Provision",
                        "description": "Skip this infrastructure for now",
                    },
                ],
                priority="high",
                blocks_progress=True,
            )

        return GateTrigger(
            gate_type="cost_approval",
            title="Cloud Resource Provisioning",
            description=f"Cloud resources being provisioned: {', '.join(set(matches))}.",
            trigger_context={"detected_patterns": matches},
            options=[
                {"id": "approve", "label": "Approve", "description": "Proceed with provisioning", "recommended": True},
                {"id": "review", "label": "Review Costs", "description": "Review cost implications first"},
            ],
            priority="normal",
        )

    def _check_deployment_gates(
        self,
        text: str,
        commands_to_run: Optional[List[str]] = None,
    ) -> Optional[GateTrigger]:
        """Check for deployment-related gates."""
        matches = []
        for pattern, pattern_type in self.DEPLOYMENT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                matches.append(pattern_type)

        # Check commands for deployment indicators
        if commands_to_run:
            for cmd in commands_to_run:
                cmd_lower = cmd.lower()
                if any(x in cmd_lower for x in ["deploy", "release", "publish"]) and any(
                    x in cmd_lower for x in ["prod", "production", "live"]
                ):
                    matches.append("production_deploy")

        if not matches:
            return None

        # Avoid duplicate gates
        gate_key = f"deploy_{sorted(set(matches))}"
        if gate_key in self._detected_gates:
            return None
        self._detected_gates.append(gate_key)

        if "production_deploy" in matches:
            return GateTrigger(
                gate_type="deployment_approval",
                title="Production Deployment Approval",
                description="About to deploy to production. This requires explicit approval.",
                trigger_context={"detected_patterns": matches},
                options=[
                    {
                        "id": "approve",
                        "label": "Deploy to Production",
                        "description": "Proceed with production deployment",
                    },
                    {
                        "id": "staging",
                        "label": "Deploy to Staging First",
                        "description": "Deploy to staging environment instead",
                        "recommended": True,
                    },
                    {
                        "id": "reject",
                        "label": "Cancel Deployment",
                        "description": "Do not deploy at this time",
                    },
                ],
                priority="critical",
                blocks_progress=True,
            )

        return GateTrigger(
            gate_type="deployment_approval",
            title="Deployment Review",
            description=f"Deployment actions detected: {', '.join(set(matches))}.",
            trigger_context={"detected_patterns": matches},
            options=[
                {"id": "approve", "label": "Approve", "description": "Proceed with deployment", "recommended": True},
                {"id": "review", "label": "Review First", "description": "Review deployment plan"},
            ],
            priority="high",
        )

    def create_milestone_gate(
        self,
        milestone_name: str,
        completed_tasks: List[str],
        next_tasks: List[str],
    ) -> GateTrigger:
        """Create a milestone review gate."""
        return GateTrigger(
            gate_type="milestone_review",
            title=f"Milestone Complete: {milestone_name}",
            description=f"Milestone '{milestone_name}' has been completed with {len(completed_tasks)} tasks. Review before proceeding.",
            trigger_context={
                "milestone_name": milestone_name,
                "completed_tasks": completed_tasks[:10],  # First 10
                "next_tasks": next_tasks[:5],  # First 5
            },
            options=[
                {
                    "id": "approve",
                    "label": "Continue to Next Milestone",
                    "description": "Milestone looks good, proceed to next phase",
                    "recommended": True,
                },
                {
                    "id": "review",
                    "label": "Review Completed Work",
                    "description": "Review the completed tasks before proceeding",
                },
                {
                    "id": "pause",
                    "label": "Pause Project",
                    "description": "Pause the project for manual testing/review",
                },
            ],
            priority="normal",
            blocks_progress=True,
        )

    def reset(self):
        """Reset detected gates for a new task/iteration."""
        self._detected_gates.clear()
