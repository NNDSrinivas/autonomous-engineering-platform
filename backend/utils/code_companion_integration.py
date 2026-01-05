"""
Integration utilities for migrating code-companion features to AEP
Provides helper functions and adapters for seamless integration
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CodeCompanionAdapter:
    """
    Adapter class to bridge code-companion functionality with AEP systems
    """

    @staticmethod
    def adapt_supabase_to_fastapi_response(
        supabase_response: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Adapt Supabase function responses to FastAPI format
        """
        if "error" in supabase_response:
            return {
                "success": False,
                "error": supabase_response["error"],
                "details": supabase_response.get("details", ""),
            }

        return {
            "success": True,
            "data": supabase_response,
            "timestamp": supabase_response.get("timestamp"),
        }

    @staticmethod
    def convert_memory_types(code_companion_type: str) -> str:
        """
        Convert code-companion memory types to AEP memory types
        """
        type_mapping = {
            "user_preference": "USER_PREFERENCE",
            "task_context": "TASK_CONTEXT",
            "code_snippet": "CODE_SNIPPET",
            "meeting_note": "MEETING_NOTE",
            "conversation": "CONVERSATION",
            "documentation": "DOCUMENTATION",
            "slack_message": "SLACK_MESSAGE",
            "jira_ticket": "JIRA_TICKET",
        }
        return type_mapping.get(code_companion_type, "UNKNOWN")

    @staticmethod
    def format_chat_message(
        message: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format chat messages for the enhanced NAVI system
        """
        return {
            "content": message,
            "context": context or {},
            "metadata": {"source": "code-companion-migration", "enhanced": True},
        }

    @staticmethod
    def extract_jira_task_info(task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and normalize Jira task information from code-companion format
        """
        return {
            "id": task_data.get("id"),
            "key": task_data.get("key"),
            "title": task_data.get("title") or task_data.get("summary"),
            "description": task_data.get("description"),
            "status": task_data.get("status"),
            "priority": task_data.get("priority"),
            "assignee": task_data.get("assignee"),
            "labels": task_data.get("labels", []),
            "type": task_data.get("type"),
            "project": task_data.get("project"),
            "created": task_data.get("created"),
            "updated": task_data.get("updated"),
            "due_date": task_data.get("dueDate"),
            "story_points": task_data.get("storyPoints"),
            "components": task_data.get("components", []),
        }


class UIComponentMapper:
    """
    Maps code-companion UI components to AEP component structure
    """

    @staticmethod
    def map_morning_briefing_props(props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map MorningBriefing component props from code-companion to AEP format
        """
        return {
            "userName": props.get("userName"),
            "jiraTasks": props.get("jiraTasks", []),
            "onTaskClick": props.get("onTaskClick"),
            "onDismiss": props.get("onDismiss"),
            "compact": props.get("compact", False),
            "enhanced": True,  # Mark as enhanced version
        }

    @staticmethod
    def map_universal_search_props(props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map UniversalSearch component props
        """
        return {
            "onSearch": props.get("onSearch"),
            "placeholder": props.get("placeholder", "Search across all platforms..."),
            "sources": props.get("sources", ["jira", "confluence", "slack", "github"]),
            "maxResults": props.get("maxResults", 50),
            "enhanced": True,
        }

    @staticmethod
    def map_workflow_props(props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Map workflow-related component props
        """
        return {
            "workflowId": props.get("workflowId"),
            "steps": props.get("steps", []),
            "currentStep": props.get("currentStep", 0),
            "onStepComplete": props.get("onStepComplete"),
            "onWorkflowComplete": props.get("onWorkflowComplete"),
            "approvalRequired": props.get("approvalRequired", True),
            "enhanced": True,
        }


class IntegrationHelper:
    """
    Helper functions for integration tasks
    """

    @staticmethod
    def merge_configurations(
        aep_config: Dict[str, Any], cc_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge AEP and code-companion configurations
        """
        merged = aep_config.copy()

        # Add code-companion specific configurations
        if "supabase" in cc_config:
            merged["integrations"]["supabase"] = cc_config["supabase"]

        if "ui_components" in cc_config:
            merged["ui"]["enhanced_components"] = cc_config["ui_components"]

        if "memory" in cc_config:
            merged["memory"]["enhanced_features"] = cc_config["memory"]

        return merged

    @staticmethod
    def validate_migration_compatibility(component_name: str, version: str) -> bool:
        """
        Validate if a component can be safely migrated
        """
        compatible_components = {
            "MorningBriefing": ["1.0.0", "1.1.0"],
            "UniversalSearch": ["1.0.0", "1.1.0"],
            "TaskCorrelationPanel": ["1.0.0"],
            "EndToEndWorkflowPanel": ["1.0.0"],
            "QuickActionsButton": ["1.0.0", "1.1.0"],
            "ApprovalDialog": ["1.0.0"],
        }

        return (
            component_name in compatible_components
            and version in compatible_components[component_name]
        )

    @staticmethod
    def log_migration_status(component: str, status: str, details: str = ""):
        """
        Log migration status for tracking
        """
        logger.info(f"Migration [{component}]: {status} - {details}")

    @staticmethod
    def create_migration_report() -> Dict[str, Any]:
        """
        Create a comprehensive migration report
        """
        return {
            "migration_date": "2026-01-01",
            "source": "code-companion",
            "target": "autonomous-engineering-platform",
            "components_migrated": [
                "MorningBriefing",
                "UniversalSearch",
                "TaskCorrelationPanel",
                "EndToEndWorkflowPanel",
                "QuickActionsButton",
                "ApprovalDialog",
            ],
            "backend_apis_migrated": ["navi-chat-enhanced", "memory-enhanced"],
            "hooks_migrated": ["useMemory", "useNaviChat", "useSmartPrompts"],
            "status": "in-progress",
            "next_steps": [
                "Update VS Code extension",
                "Test integration",
                "Deploy to staging",
            ],
        }


# Export commonly used functions
__all__ = ["CodeCompanionAdapter", "UIComponentMapper", "IntegrationHelper"]
