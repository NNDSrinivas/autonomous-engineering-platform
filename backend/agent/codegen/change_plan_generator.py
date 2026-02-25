from typing import Dict, Any, List, Optional
import logging
import uuid
from datetime import datetime

from .types import (
    ChangePlan,
    ChangeIntent,
    ChangeType,
    PlannedFileChange,
    CodeChange,
    ValidationLevel,
)

try:
    from ..intent_schema import NaviIntent
    from ...services.llm_router import LLMRouter
    from ...core.config import get_settings
except ImportError:
    from backend.agent.intent_schema import NaviIntent
    from backend.services.llm_router import LLMRouter
    from backend.core.config import get_settings


logger = logging.getLogger(__name__)


class ChangePlanGenerator:
    """
    Phase 3.3 - Core engine for generating detailed change plans.

    This is the authoritative code generation planner that converts
    user requests and NaviIntents into executable ChangePlans.

    Integration:
    - Called by planner_v3.py when intent.kind indicates code generation
    - Provides detailed file-by-file change specifications
    - Output feeds into existing tool_executor via apply_diff tools
    """

    def __init__(self, llm_router: Optional[LLMRouter] = None):
        self.llm_router = llm_router or LLMRouter()
        self.settings = get_settings()

    async def generate_plan(
        self,
        intent: NaviIntent,
        user_request: str,
        workspace_root: str,
        repo_context: Dict[str, Any],
        user_preferences: Dict[str, Any] = None,
    ) -> ChangePlan:
        """
        Generate a comprehensive ChangePlan from user intent.

        Args:
            intent: Classified user intent
            user_request: Original user request
            workspace_root: Path to workspace root
            repo_context: Repository analysis and context
            user_preferences: User preferences for validation, etc.

        Returns:
            Detailed ChangePlan ready for execution
        """
        logger.info(f"[CODEGEN] Generating change plan for intent: {intent.kind}")

        # Create base plan structure
        plan = ChangePlan(
            plan_id=str(uuid.uuid4()),
            intent=self._map_intent(intent),
            description=f"Implement: {user_request}",
            user_request=user_request,
            workspace_root=workspace_root,
            repo_context=repo_context,
            user_preferences=user_preferences or {},
        )

        # Generate detailed analysis prompt
        analysis_prompt = self._build_analysis_prompt(
            intent, user_request, repo_context
        )

        try:
            # Get LLM analysis of required changes
            analysis_response = await self.llm_router.run(
                prompt=analysis_prompt, use_smart_auto=True
            )

            # Parse LLM response into structured changes
            file_changes = await self._parse_analysis_to_changes(
                analysis_response.text, repo_context, workspace_root
            )

            # Add file changes to plan
            for file_change in file_changes:
                plan.add_file_change(file_change)

            # Optimize execution order based on dependencies
            plan.optimize_execution_order()

            # Set validation level based on user preferences and risk
            plan.validation_level = self._determine_validation_level(
                plan, user_preferences
            )

            logger.info(
                f"[CODEGEN] Generated plan with {plan.total_files_affected} files, "
                f"{plan.total_lines_affected} lines affected"
            )

            return plan

        except Exception as e:
            logger.error(f"[CODEGEN] Failed to generate change plan: {e}")
            # Return minimal plan with error context
            return self._create_error_plan(plan, str(e))

    def _map_intent(self, intent: NaviIntent) -> ChangeIntent:
        """Map NaviIntent to ChangeIntent."""
        intent_mapping = {
            "GENERATE_CODE": ChangeIntent.IMPLEMENT_FEATURE,
            "IMPLEMENT_FEATURE": ChangeIntent.IMPLEMENT_FEATURE,
            "FIX_CODE": ChangeIntent.FIX_BUG,
            "FIX_BUG": ChangeIntent.FIX_BUG,
            "REFACTOR": ChangeIntent.REFACTOR,
            "ADD_TESTS": ChangeIntent.ADD_TESTS,
            "IMPROVE_PERFORMANCE": ChangeIntent.IMPROVE_PERFORMANCE,
            "ENHANCE_SECURITY": ChangeIntent.ENHANCE_SECURITY,
            "ADD_DOCUMENTATION": ChangeIntent.ADD_DOCUMENTATION,
        }

        intent_str = (
            str(intent.kind.value).upper()
            if hasattr(intent, "kind")
            else "IMPLEMENT_FEATURE"
        )
        return intent_mapping.get(intent_str, ChangeIntent.IMPLEMENT_FEATURE)

    def _build_analysis_prompt(
        self, intent: NaviIntent, user_request: str, repo_context: Dict[str, Any]
    ) -> str:
        """
        Build comprehensive analysis prompt for LLM.

        This prompt is designed to extract:
        1. Files that need to be created/modified
        2. Specific changes within each file
        3. Dependencies between changes
        4. Risk assessment
        """

        # Extract relevant repo context
        repo_context.get("file_structure", {})
        key_files = repo_context.get("key_files", [])
        languages = repo_context.get("languages", [])
        frameworks = repo_context.get("frameworks", [])

        prompt = f"""
You are an expert software engineer analyzing a code change request.

USER REQUEST:
{user_request}

INTENT: {intent.kind if hasattr(intent, "kind") else "IMPLEMENT_FEATURE"}

REPOSITORY CONTEXT:
- Primary languages: {", ".join(languages) if languages else "Unknown"}
- Frameworks: {", ".join(frameworks) if frameworks else "Unknown"}
- Key files: {", ".join(key_files[:10]) if key_files else "None identified"}

TASK:
Analyze this request and provide a detailed implementation plan.

RESPOND WITH JSON in this exact structure:
{{
  "summary": "Brief description of changes needed",
  "estimated_complexity": 0.7,  // 0.0-1.0 scale
  "estimated_duration_minutes": 15,
  "file_changes": [
    {{
      "file_path": "relative/path/to/file.py",
      "change_type": "create_file" | "modify_file" | "delete_file",
      "reasoning": "Why this file needs changes",
      "risk_level": "low" | "medium" | "high",
      "dependencies": ["other/file/paths.py"],
      "changes": [
        {{
          "line_start": 10,
          "line_end": 15,
          "change_type": "insert" | "replace" | "delete",
          "original_code": "existing code (if replace/delete)",
          "new_code": "new code to add (if insert/replace)",
          "reasoning": "Why this specific change",
          "confidence": 0.9
        }}
      ],
      "new_file_content": "complete file content for new files"
    }}
  ]
}}

IMPORTANT:
1. Be specific about line numbers and exact code changes
2. Consider file dependencies and order of changes
3. Assess risk realistically (config files = high risk)
4. For new files, provide complete content
5. For modifications, be precise about what to change
6. Include reasoning for each change
"""

        return prompt

    async def _parse_analysis_to_changes(
        self, llm_response: str, repo_context: Dict[str, Any], workspace_root: str
    ) -> List[PlannedFileChange]:
        """
        Parse LLM analysis response into PlannedFileChange objects.
        """
        import json

        try:
            # Parse JSON response
            analysis = json.loads(llm_response)
            file_changes = []

            for fc_data in analysis.get("file_changes", []):
                # Parse individual code changes
                changes = []
                for change_data in fc_data.get("changes", []):
                    changes.append(
                        CodeChange(
                            line_start=change_data.get("line_start", 1),
                            line_end=change_data.get("line_end", 1),
                            original_code=change_data.get("original_code", ""),
                            new_code=change_data.get("new_code", ""),
                            change_type=change_data.get("change_type", "insert"),
                            reasoning=change_data.get("reasoning", ""),
                            confidence=change_data.get("confidence", 0.8),
                        )
                    )

                # Create PlannedFileChange
                file_change = PlannedFileChange(
                    file_path=fc_data["file_path"],
                    change_type=ChangeType(fc_data.get("change_type", "modify_file")),
                    changes=changes,
                    new_file_content=fc_data.get("new_file_content"),
                    reasoning=fc_data.get("reasoning", ""),
                    dependencies=fc_data.get("dependencies", []),
                    estimated_complexity=fc_data.get("estimated_complexity", 0.5),
                    risk_level=fc_data.get("risk_level", "medium"),
                    requires_review=fc_data.get("risk_level", "medium") != "low",
                )

                file_changes.append(file_change)

            return file_changes

        except json.JSONDecodeError as e:
            logger.error(f"[CODEGEN] Failed to parse LLM response as JSON: {e}")
            logger.error(f"[CODEGEN] Raw response: {llm_response[:500]}...")
            return self._create_fallback_changes(workspace_root)

        except Exception as e:
            logger.error(f"[CODEGEN] Error parsing analysis: {e}")
            return self._create_fallback_changes(workspace_root)

    def _create_fallback_changes(self, workspace_root: str) -> List[PlannedFileChange]:
        """Create minimal fallback changes when LLM parsing fails."""
        return [
            PlannedFileChange(
                file_path="README.md",
                change_type=ChangeType.MODIFY_FILE,
                changes=[
                    CodeChange(
                        line_start=1,
                        line_end=1,
                        original_code="",
                        new_code="# Updated by Navi\n",
                        change_type="insert",
                        reasoning="Fallback change - LLM analysis failed",
                        confidence=0.1,
                    )
                ],
                reasoning="Fallback change due to analysis parsing failure",
                risk_level="low",
            )
        ]

    def _determine_validation_level(
        self, plan: ChangePlan, user_preferences: Optional[Dict[str, Any]]
    ) -> ValidationLevel:
        """Determine appropriate validation level based on plan risk and user preferences."""
        if not user_preferences:
            return ValidationLevel.FULL

        # Check user preference
        pref_level = user_preferences.get("validation_level")
        if pref_level:
            try:
                return ValidationLevel(pref_level)
            except ValueError:
                pass

        # Determine based on risk
        if plan.overall_risk == "high":
            return ValidationLevel.FULL
        elif plan.overall_risk == "medium":
            return ValidationLevel.TYPE_CHECK
        else:
            return ValidationLevel.SYNTAX_ONLY

    def _create_error_plan(
        self, base_plan: ChangePlan, error_message: str
    ) -> ChangePlan:
        """Create an error plan when generation fails."""
        base_plan.description = f"Error: {error_message}"
        base_plan.overall_risk = "high"
        base_plan.validation_level = ValidationLevel.NONE

        # Add a comment change to indicate the error
        error_change = PlannedFileChange(
            file_path=".navi_error.md",
            change_type=ChangeType.CREATE_FILE,
            new_file_content=f"""
# Navi Code Generation Error

**Request:** {base_plan.user_request}
**Error:** {error_message}
**Timestamp:** {datetime.now().isoformat()}

This file was created to indicate a code generation failure.
Please review the request and try again.
""",
            reasoning=f"Created due to generation error: {error_message}",
            risk_level="low",
            requires_review=True,
        )

        base_plan.add_file_change(error_change)
        return base_plan
