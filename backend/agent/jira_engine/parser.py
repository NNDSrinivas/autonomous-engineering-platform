"""
Jira Issue Parser

Normalizes Jira API responses into clean, structured format for NAVI's consumption.
Handles different Jira response formats and extracts key information consistently.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def parse_jira_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize Jira issue into a clean structured format.

    Args:
        issue: Raw Jira issue dict from API

    Returns:
        Cleaned, normalized issue dict with consistent structure

    Example output:
        {
            "id": "SCRUM-123",
            "title": "Implement user authentication",
            "description": "Add OAuth2 support...",
            "status": "In Progress",
            "assignee": "user@example.com",
            "reporter": "manager@example.com",
            "priority": "High",
            "story_points": 5,
            "labels": ["backend", "security"],
            "comments": ["Comment 1...", "Comment 2..."],
            "created": "2025-11-01T10:00:00Z",
            "updated": "2025-11-17T14:30:00Z",
            "issue_type": "Story"
        }
    """

    try:
        fields = issue.get("fields", {})

        # Extract assignee
        assignee = None
        if fields.get("assignee"):
            assignee = (
                fields["assignee"].get("emailAddress")
                or fields["assignee"].get("displayName")
                or fields["assignee"].get("name")
            )

        # Extract reporter
        reporter = None
        if fields.get("reporter"):
            reporter = (
                fields["reporter"].get("emailAddress")
                or fields["reporter"].get("displayName")
                or fields["reporter"].get("name")
            )

        # Extract status
        status = None
        if fields.get("status"):
            status = fields["status"].get("name")

        # Extract priority
        priority = None
        if fields.get("priority"):
            priority = fields["priority"].get("name")

        # Extract issue type
        issue_type = None
        if fields.get("issuetype"):
            issue_type = fields["issuetype"].get("name")

        # Extract comments
        comments = []
        comment_data = fields.get("comment", {})
        if isinstance(comment_data, dict):
            comment_list = comment_data.get("comments", [])
            comments = [c.get("body", "") for c in comment_list if c.get("body")]

        # Extract labels
        labels = fields.get("labels", [])
        if not isinstance(labels, list):
            labels = []

        # Extract story points (custom field, may vary)
        story_points = None
        for key, value in fields.items():
            if "story" in key.lower() and "point" in key.lower():
                story_points = value
                break

        # Build normalized issue
        normalized = {
            "id": issue.get("key"),
            "title": fields.get("summary", ""),
            "description": fields.get("description", ""),
            "status": status,
            "assignee": assignee,
            "reporter": reporter,
            "priority": priority,
            "story_points": story_points,
            "labels": labels,
            "comments": comments,
            "created": fields.get("created"),
            "updated": fields.get("updated"),
            "issue_type": issue_type,
            # Additional useful fields
            "url": (
                f"https://jira.company.com/browse/{issue.get('key')}"
                if issue.get("key")
                else None
            ),
            "raw": issue,  # Keep raw data for advanced use cases
        }

        logger.info(f"Parsed Jira issue: {normalized['id']} - {normalized['title']}")
        return normalized

    except Exception as e:
        logger.error(f"Error parsing Jira issue: {e}", exc_info=True)
        # Return minimal valid structure on error
        return {
            "id": issue.get("key", "UNKNOWN"),
            "title": "Error parsing issue",
            "description": str(e),
            "status": None,
            "assignee": None,
            "reporter": None,
            "priority": None,
            "story_points": None,
            "labels": [],
            "comments": [],
            "created": None,
            "updated": None,
            "issue_type": None,
            "url": None,
            "raw": issue,
        }


def extract_jira_key_from_text(text: str) -> Optional[str]:
    """
    Extract Jira issue key from arbitrary text.

    Args:
        text: Text that may contain Jira key (e.g., "Check SCRUM-123 for details")

    Returns:
        Jira key if found, None otherwise

    Example:
        extract_jira_key_from_text("Let's work on ENG-542") → "ENG-542"
    """
    import re

    # Pattern: PROJECT-NUMBER (e.g., SCRUM-123, ENG-54, PROJ-1)
    pattern = r"\b([A-Z]{2,10}-\d+)\b"
    match = re.search(pattern, text, re.IGNORECASE)

    if match:
        return match.group(1).upper()

    return None


def format_jira_for_display(issue: Dict[str, Any]) -> str:
    """
    Format parsed Jira issue for human-readable display.

    Args:
        issue: Normalized Jira issue from parse_jira_issue()

    Returns:
        Formatted string for display to user
    """

    lines = []
    lines.append(f"**{issue['id']}: {issue['title']}**")
    lines.append("")

    # Metadata
    metadata = []
    if issue.get("status"):
        metadata.append(f"Status: {issue['status']}")
    if issue.get("assignee"):
        metadata.append(f"Assignee: {issue['assignee']}")
    if issue.get("priority"):
        metadata.append(f"Priority: {issue['priority']}")
    if issue.get("story_points"):
        metadata.append(f"Story Points: {issue['story_points']}")

    if metadata:
        lines.append(" | ".join(metadata))
        lines.append("")

    # Description
    if issue.get("description"):
        lines.append("**Description:**")
        lines.append(issue["description"][:500])  # Truncate long descriptions
        if len(issue["description"]) > 500:
            lines.append("...(truncated)")
        lines.append("")

    # Labels
    if issue.get("labels"):
        lines.append(f"**Labels:** {', '.join(issue['labels'])}")
        lines.append("")

    # Comments count
    if issue.get("comments"):
        lines.append(f"**Comments:** {len(issue['comments'])} comment(s)")
        lines.append("")

    return "\n".join(lines)
