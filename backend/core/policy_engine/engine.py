"""Policy engine for fine-grained authorization guardrails."""

import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Default empty policy structure when no policy file is found
DEFAULT_POLICY_STRUCTURE: dict[str, Any] = {"version": "1.0", "policies": []}


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
        self.policies: dict[str, Any] = DEFAULT_POLICY_STRUCTURE.copy()
        # Cache for precompiled regex patterns to avoid recompilation on each check
        # Structure: {action: [(compiled_pattern, original_string, reason_template), ...]}
        self._compiled_patterns: dict[str, list[tuple[re.Pattern, str, str]]] = {}
        self._load_policies()

    def _load_policies(self) -> None:
        """Load policies from JSON file and precompile regex patterns."""
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

            # Precompile all regex patterns for performance
            self._precompile_patterns()
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

    def _precompile_patterns(self) -> None:
        """Precompile all regex patterns from policies for performance."""
        self._compiled_patterns.clear()

        for policy in self.policies.get("policies", []):
            action = policy.get("action")
            if not action:
                continue

            deny_if = policy.get("deny_if", {})

            # Precompile step_name_contains patterns
            if "step_name_contains" in deny_if:
                patterns = []
                reason_template = policy.get(
                    "reason", "Step contains forbidden pattern: {pattern}"
                )

                for pattern_str in deny_if["step_name_contains"]:
                    try:
                        # Note: Using re.IGNORECASE because malicious commands often use
                        # mixed case obfuscation (e.g., "Rm -RF", "DrOp TaBlE"). While
                        # Unix shells are case-sensitive, our policy aims to catch intent
                        # rather than exact syntax. This is a defense-in-depth measure.
                        compiled = re.compile(pattern_str, re.IGNORECASE)
                        # Store (compiled_pattern, original_string, reason) tuple
                        patterns.append((compiled, pattern_str, reason_template))
                    except re.error as e:
                        logger.error(
                            f"Invalid regex pattern '{pattern_str}' in policy "
                            f"for action '{action}': {e}"
                        )

                if patterns:
                    if action not in self._compiled_patterns:
                        self._compiled_patterns[action] = []
                    self._compiled_patterns[action].extend(patterns)

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
        # Use precompiled patterns for step_name_contains checks
        if action in self._compiled_patterns:
            step_name = context.get("step_name", "")

            # SECURITY: Normalize input to prevent obfuscation bypasses
            # 1. Unicode normalization (NFKC) - handles lookalike characters
            #    (e.g., Cyrillic 'р' U+0440 vs Latin 'r' U+0072)
            # 2. Remove zero-width characters (U+200B, U+FEFF, etc.)
            # 3. Collapse whitespace (tabs, newlines, multiple spaces to single space)
            # Without this, attacks like "r​m -rf" (zero-width space) or "гm -rf"
            # (Cyrillic 'г') could evade detection.
            step_name = unicodedata.normalize("NFKC", step_name)
            # Remove zero-width and non-printable characters
            step_name = "".join(
                ch
                for ch in step_name
                if unicodedata.category(ch)[0] != "C" or ch in "\t\n\r "
            )
            # Normalize whitespace
            step_name = re.sub(r"\s+", " ", step_name).strip()

            for (
                compiled_pattern,
                original_pattern,
                reason_template,
            ) in self._compiled_patterns[action]:
                if compiled_pattern.search(step_name):
                    reason = reason_template.replace("{pattern}", original_pattern)
                    logger.warning(
                        f"Policy denied action={action}: {reason} "
                        f"(matched pattern '{original_pattern}' in '{step_name}')"
                    )
                    return False, reason

        # Fallback: check other policy types that don't use precompiled patterns
        for policy in self.policies.get("policies", []):
            if policy.get("action") != action:
                continue

            deny_if = policy.get("deny_if", {})

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
