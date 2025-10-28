"""Policy engine for fine-grained authorization guardrails."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    File-based policy engine for authorization guardrails.

    Loads policies from .aepolicy.json in repo root.
    Supports action-based rules with pattern matching.

    Example .aepolicy.json:
    {
      "version": "1.0",
      "policies": [
        {
          "action": "plan.add_step",
          "deny_if": {
            "step_name_contains": ["rm -rf", "sudo", "DROP TABLE"]
          },
          "reason": "Dangerous commands not allowed in plan steps"
        }
      ]
    }
    """

    def __init__(self, policy_file: Optional[Path] = None):
        """
        Initialize policy engine.

        Args:
            policy_file: Path to .aepolicy.json file. If None, searches for
                         .aepolicy.json in current working directory or
                         POLICY_FILE env var.
        """
        if policy_file is None:
            # Check env var first, then default to repo root
            policy_path_str = os.getenv("POLICY_FILE")
            if policy_path_str:
                policy_file = Path(policy_path_str)
            else:
                policy_file = Path.cwd() / ".aepolicy.json"

        self.policy_file = policy_file
        self.policies: dict[str, Any] = {"version": "1.0", "policies": []}
        self._load_policies()

    def _load_policies(self) -> None:
        """Load policies from JSON file."""
        if not self.policy_file.exists():
            logger.warning(
                f"Policy file not found: {self.policy_file}. "
                "Running with empty policy set."
            )
            return

        try:
            with open(self.policy_file, "r") as f:
                self.policies = json.load(f)
            logger.info(
                f"Loaded {len(self.policies.get('policies', []))} "
                f"policies from {self.policy_file}"
            )
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse policy file {self.policy_file}: {e}. "
                "Running with empty policy set."
            )
        except Exception as e:
            logger.error(
                f"Failed to load policy file {self.policy_file}: {e}. "
                "Running with empty policy set."
            )

    def check(self, action: str, context: dict[str, Any]) -> tuple[bool, str]:
        """
        Check if an action is allowed by policies.

        Args:
            action: Action identifier (e.g., "plan.add_step", "plan.publish")
            context: Context dictionary with action-specific data
                     (e.g., {"step_name": "deploy to prod", "plan_id": "123"})

        Returns:
            Tuple of (allowed: bool, reason: str)
            - (True, "") if allowed
            - (False, reason) if denied with explanation
        """
        for policy in self.policies.get("policies", []):
            if policy.get("action") != action:
                continue

            # Check deny conditions
            deny_if = policy.get("deny_if", {})

            # Pattern: step_name_contains
            if "step_name_contains" in deny_if:
                step_name = context.get("step_name", "")
                forbidden_patterns = deny_if["step_name_contains"]
                for pattern in forbidden_patterns:
                    if pattern.lower() in step_name.lower():
                        reason = policy.get(
                            "reason",
                            f"Step contains forbidden pattern: {pattern}",
                        )
                        logger.warning(
                            f"Policy denied action={action}: {reason} "
                            f"(matched pattern '{pattern}' in '{step_name}')"
                        )
                        return False, reason

            # Pattern: plan_id_matches (example for future extension)
            if "plan_id_matches" in deny_if:
                plan_id = context.get("plan_id", "")
                forbidden_ids = deny_if["plan_id_matches"]
                if plan_id in forbidden_ids:
                    reason = policy.get(
                        "reason",
                        f"Plan ID {plan_id} is restricted",
                    )
                    logger.warning(
                        f"Policy denied action={action}: {reason} "
                        f"(plan_id={plan_id})"
                    )
                    return False, reason

        # No policy denied → allow
        return True, ""


# Global singleton instance (can be dependency-injected in FastAPI)
_policy_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    """
    Get or create the global PolicyEngine singleton.

    Returns:
        Singleton PolicyEngine instance
    """
    global _policy_engine
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    return _policy_engine
