# backend/agent/task_grounder/deployGrounder.py

"""
DEPLOY Grounding Module - Phase 4.2 Architecture Only

This module provides intelligent grounding for deployment intents.
No execution is implemented yet - this is architectural setup for Phase 4.3.

Key principles:
- No guessing about deployment targets
- Require explicit configuration or detection
- Guide users through deployment setup
- Prevent deployment to unintended environments
"""

import logging
from typing import Dict, Any
from .types import GroundingResult, DeployTask, Clarification

logger = logging.getLogger(__name__)


def ground_deploy(intent: Any, context: Dict[str, Any]) -> GroundingResult:
    """
    Ground DEPLOY intent with intelligent validation and guidance.

    This is architecture-only implementation for Phase 4.2.
    Execution will be added in Phase 4.3.

    Args:
        intent: Classified intent from intent classifier
        context: Context including workspace, user preferences, etc.

    Returns:
        GroundingResult with rejection, clarification, or ready task
    """
    logger.info("Grounding DEPLOY intent (architecture-only Phase 4.2)")

    workspace = context.get("workspace")
    workspace_data = context.get("workspace_data", {})

    # Rejection: No repository
    if not workspace:
        return GroundingResult(
            type="rejected",
            reason="No repository found to deploy. Open a project workspace first.",
        )

    # Detection: Look for deployment configuration
    deploy_config_detected = _detect_deployment_config(workspace_data)

    # Clarification: No deployment method configured
    if not deploy_config_detected:
        return GroundingResult(
            type="clarification",
            clarification=Clarification(
                message="How would you like to deploy this project?",
                options=["Docker", "Vercel", "AWS", "Azure", "Manual"],
                context={
                    "required_field": "deployMethod",
                    "reason": "no_deploy_config_detected",
                },
            ),
        )

    # Clarification: Target environment not specified
    target_environment = _extract_target_environment(context)
    if not target_environment:
        return GroundingResult(
            type="clarification",
            clarification=Clarification(
                message="Which environment should I deploy to?",
                options=["dev", "staging", "prod"],
                context={
                    "required_field": "targetEnvironment",
                    "reason": "no_target_environment",
                },
            ),
        )

    # Ready: All requirements met
    task = DeployTask(
        inputs={
            "workspace": workspace,
            "deploy_method": deploy_config_detected.get("method"),
            "target_environment": target_environment,
            "config_files": deploy_config_detected.get("files", []),
            "detected_stack": deploy_config_detected.get("stack"),
        },
        requires_approval=True,  # Always require approval for deployment
        confidence=0.9,
        metadata={
            "workspace": workspace,
            "grounding_source": "config_detection",
            "phase": "4.2_architecture_only",
        },
    )

    logger.info(
        f"Successfully grounded DEPLOY: method={deploy_config_detected.get('method')}, target={target_environment}"
    )

    return GroundingResult(type="ready", task=task)


def _detect_deployment_config(workspace_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect deployment configuration from workspace.

    Returns dict with:
    - method: "docker", "vercel", "aws", etc.
    - files: List of config files found
    - stack: Detected technology stack
    """
    # Phase 4.2: Mock detection logic
    # Phase 4.3 will implement real file detection

    # Look for common deployment files
    files = workspace_data.get("files", [])
    if isinstance(files, list):
        file_names = [
            f.get("name", "") if isinstance(f, dict) else str(f) for f in files
        ]
    else:
        file_names = []

    config = {"method": None, "files": [], "stack": None}

    # Docker detection
    if "Dockerfile" in file_names or "docker-compose.yml" in file_names:
        config["method"] = "docker"
        config["files"].extend(["Dockerfile", "docker-compose.yml"])
        config["stack"] = "containerized"

    # Vercel detection
    elif "vercel.json" in file_names or "next.config.js" in file_names:
        config["method"] = "vercel"
        config["files"].extend(["vercel.json", "next.config.js"])
        config["stack"] = "frontend"

    # Package.json with scripts
    elif "package.json" in file_names:
        config["method"] = "npm"
        config["files"].append("package.json")
        config["stack"] = "node"

    return config if config["method"] else {}


def _extract_target_environment(context: Dict[str, Any]) -> str:
    """
    Extract target environment from context or user input.

    Phase 4.2: Basic extraction
    Phase 4.3: Will use intent analysis and user preferences
    """
    message = context.get("message", "").lower()

    # Simple keyword detection
    if any(word in message for word in ["prod", "production"]):
        return "prod"
    elif any(word in message for word in ["staging", "stage"]):
        return "staging"
    elif any(word in message for word in ["dev", "development"]):
        return "dev"

    # Default: require clarification
    return None


def _should_request_clarification(context: Dict[str, Any]) -> bool:
    """
    Determine if we need clarification for deployment.

    Phase 4.2: Always request clarification for safety
    Phase 4.3: Will be more intelligent based on user history
    """
    # For safety, always clarify deployment targets
    return True
