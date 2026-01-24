"""
Response Personalization Service for NAVI.

Personalizes NAVI responses based on user preferences, patterns,
and organization standards.

Features:
- Adjust response verbosity based on preferences
- Match user's communication style
- Apply organization coding standards
- Personalize code examples to user's stack
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.database.models.memory import (
    OrgStandard,
    UserPattern,
)
from backend.services.intelligence.preference_learner import get_preference_learner

logger = logging.getLogger(__name__)


class ResponsePersonalizer:
    """
    Service for personalizing NAVI responses.

    Applies user preferences, learned patterns, and organization
    standards to customize response format and content.
    """

    def __init__(self, db: Session):
        """
        Initialize the response personalizer.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.preference_learner = get_preference_learner(db)

    # =========================================================================
    # Personalization Context Building
    # =========================================================================

    def build_personalization_context(
        self,
        user_id: int,
        org_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Build complete personalization context for a user.

        Args:
            user_id: User ID
            org_id: Optional organization ID

        Returns:
            Dictionary containing personalization context
        """
        context = {
            "user_preferences": {},
            "org_standards": [],
            "style_guidelines": {},
            "response_format": {},
        }

        # Get effective user preferences (explicit + learned)
        context["user_preferences"] = self.preference_learner.get_effective_preferences(
            user_id
        )

        # Get organization standards if org_id provided
        if org_id:
            context["org_standards"] = self._get_org_standards(org_id)

        # Build style guidelines
        context["style_guidelines"] = self._build_style_guidelines(
            context["user_preferences"],
            context["org_standards"],
        )

        # Build response format preferences
        context["response_format"] = self._build_response_format(
            context["user_preferences"]
        )

        return context

    def _get_org_standards(self, org_id: int) -> List[Dict[str, Any]]:
        """Get enforced organization standards."""
        standards = (
            self.db.query(OrgStandard).filter(OrgStandard.org_id == org_id).all()
        )

        return [
            {
                "type": s.standard_type,
                "name": s.standard_name,
                "rules": s.rules,
                "enforced": s.enforced,
            }
            for s in standards
        ]

    def _build_style_guidelines(
        self,
        preferences: Dict[str, Any],
        standards: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build code style guidelines from preferences and standards."""
        guidelines = {
            "naming": {},
            "formatting": {},
            "patterns": [],
        }

        # Apply user code style preferences
        code_style = preferences.get("code_style", {})
        if code_style:
            guidelines["formatting"].update(code_style)

        # Apply organization standards
        for standard in standards:
            if standard["type"] == "naming":
                guidelines["naming"].update(standard["rules"])
            elif standard["type"] == "formatting":
                guidelines["formatting"].update(standard["rules"])
            elif standard["type"] == "pattern":
                guidelines["patterns"].append(
                    {
                        "name": standard["name"],
                        "rules": standard["rules"],
                    }
                )

        return guidelines

    def _build_response_format(
        self,
        preferences: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build response format preferences."""
        verbosity = preferences.get("response_verbosity", "balanced")
        explanation_level = preferences.get("explanation_level", "intermediate")

        format_prefs = {
            "verbosity": verbosity,
            "explanation_level": explanation_level,
            "include_examples": True,
            "include_explanations": True,
            "code_comments": "moderate",
        }

        # Adjust based on verbosity
        if verbosity == "brief":
            format_prefs["include_explanations"] = False
            format_prefs["code_comments"] = "minimal"
        elif verbosity == "detailed":
            format_prefs["include_explanations"] = True
            format_prefs["code_comments"] = "verbose"

        # Adjust based on explanation level
        if explanation_level == "beginner":
            format_prefs["include_examples"] = True
            format_prefs["explain_basics"] = True
        elif explanation_level == "expert":
            format_prefs["explain_basics"] = False
            format_prefs["assume_knowledge"] = True

        return format_prefs

    # =========================================================================
    # System Prompt Personalization
    # =========================================================================

    def create_personalized_system_prompt(
        self,
        base_prompt: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Create a personalized system prompt for NAVI.

        Args:
            base_prompt: The base system prompt
            context: Personalization context from build_personalization_context

        Returns:
            Personalized system prompt
        """
        additions = []

        # Add user preferences
        prefs = context.get("user_preferences", {})

        if prefs.get("preferred_language"):
            additions.append(
                f"The user prefers {prefs['preferred_language']} as their primary language. "
                f"Provide code examples in {prefs['preferred_language']} when applicable."
            )

        if prefs.get("preferred_framework"):
            additions.append(
                f"The user works with {prefs['preferred_framework']}. "
                f"Consider this framework in your suggestions."
            )

        # Add response format preferences
        format_prefs = context.get("response_format", {})

        if format_prefs.get("verbosity") == "brief":
            additions.append(
                "Keep responses concise and to the point. "
                "Avoid lengthy explanations unless asked."
            )
        elif format_prefs.get("verbosity") == "detailed":
            additions.append(
                "Provide detailed explanations with examples. "
                "Include context and reasoning for recommendations."
            )

        if format_prefs.get("explanation_level") == "beginner":
            additions.append(
                "Explain concepts in beginner-friendly terms. "
                "Include explanations for technical terms."
            )
        elif format_prefs.get("explanation_level") == "expert":
            additions.append(
                "The user is an experienced developer. "
                "You can assume familiarity with advanced concepts."
            )

        # Add organization standards
        standards = context.get("org_standards", [])
        enforced_standards = [s for s in standards if s.get("enforced")]

        if enforced_standards:
            standard_text = "Follow these organization coding standards:\n"
            for standard in enforced_standards[:5]:  # Limit to 5 most important
                standard_text += f"- {standard['name']}: {standard.get('rules', {})}\n"
            additions.append(standard_text)

        # Add style guidelines
        style = context.get("style_guidelines", {})
        naming = style.get("naming", {})
        if naming:
            naming_text = "Use these naming conventions:\n"
            for key, value in naming.items():
                naming_text += f"- {key}: {value}\n"
            additions.append(naming_text)

        # Combine base prompt with additions
        if additions:
            personalization_section = "\n\n## User Personalization\n" + "\n".join(
                additions
            )
            return base_prompt + personalization_section

        return base_prompt

    # =========================================================================
    # Response Adjustment
    # =========================================================================

    def adjust_response(
        self,
        response: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Post-process a response to match user preferences.

        Args:
            response: The original response
            context: Personalization context

        Returns:
            Adjusted response
        """
        format_prefs = context.get("response_format", {})

        # Apply verbosity adjustments
        if format_prefs.get("verbosity") == "brief":
            response = self._make_brief(response)

        return response

    def _make_brief(self, response: str) -> str:
        """Make a response more concise."""
        # This is a simple implementation - could be enhanced with LLM
        lines = response.split("\n")
        filtered_lines = []

        for line in lines:
            # Keep code blocks
            if line.strip().startswith("```") or line.strip().startswith("    "):
                filtered_lines.append(line)
                continue

            # Remove verbose phrases
            if any(
                phrase in line.lower()
                for phrase in [
                    "in other words",
                    "to elaborate",
                    "let me explain",
                    "as you can see",
                    "it's worth noting",
                ]
            ):
                continue

            filtered_lines.append(line)

        return "\n".join(filtered_lines)

    # =========================================================================
    # Code Example Personalization
    # =========================================================================

    def personalize_code_example(
        self,
        code: str,
        language: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Personalize a code example to match user preferences.

        Args:
            code: The code example
            language: Programming language
            context: Personalization context

        Returns:
            Personalized code example
        """
        prefs = context.get("user_preferences", {})
        style = context.get("style_guidelines", {})

        # Apply code style preferences
        code_style = prefs.get("code_style", {})

        # Apply indentation preference
        indent = code_style.get("indentation", "  ")
        if indent == "tabs":
            code = code.replace("    ", "\t")
        elif indent == "4spaces":
            code = code.replace("  ", "    ")

        # Apply formatting rules
        formatting = style.get("formatting", {})

        if formatting.get("trailing_comma") and language in [
            "python",
            "javascript",
            "typescript",
        ]:
            # Add trailing commas (simplified implementation)
            pass

        return code

    # =========================================================================
    # Preference-Aware Suggestions
    # =========================================================================

    def get_personalized_suggestions(
        self,
        user_id: int,
        query_type: str,
    ) -> List[Dict[str, Any]]:
        """
        Get personalized suggestions based on user patterns.

        Args:
            user_id: User ID
            query_type: Type of query

        Returns:
            List of personalized suggestions
        """
        suggestions = []

        # Get user patterns
        patterns = (
            self.db.query(UserPattern)
            .filter(
                UserPattern.user_id == user_id,
                UserPattern.confidence >= 0.6,
            )
            .all()
        )

        for pattern in patterns:
            if pattern.pattern_type == "workflow":
                # Suggest based on workflow patterns
                if "test" in pattern.pattern_key and query_type == "implement":
                    suggestions.append(
                        {
                            "type": "workflow",
                            "content": "Based on your workflow, you typically write tests after implementing. Would you like me to generate tests?",
                            "confidence": pattern.confidence,
                        }
                    )

            elif pattern.pattern_type == "coding_style":
                # Suggest based on coding patterns
                suggestions.append(
                    {
                        "type": "style",
                        "content": f"I'll follow your {pattern.pattern_key} pattern.",
                        "confidence": pattern.confidence,
                    }
                )

        return suggestions[:3]  # Limit suggestions


def get_response_personalizer(db: Session) -> ResponsePersonalizer:
    """Factory function to create ResponsePersonalizer."""
    return ResponsePersonalizer(db)
