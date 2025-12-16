"""
Jira Resolver

Automatically determines which Jira issue the user is referring to.
Handles vague references like "this", "that", "the issue", etc.
"""

import logging
from typing import Dict, Any, Optional, List
import re

logger = logging.getLogger(__name__)


def resolve_jira_target(
    user_message: str, org_context: Dict[str, Any], user_state: Dict[str, Any]
) -> Optional[str]:
    """
    Decide which Jira issue the user refers to.

    Resolution strategy (in priority order):
    1. Explicit Jira key in message (SCRUM-123)
    2. Previous active task from user state
    3. Jira mentioned in recent conversation
    4. Most relevant Jira from organizational context
    5. Highest priority unassigned Jira

    Args:
        user_message: User's message
        org_context: Full organizational context (with Jira issues)
        user_state: Current user state (with active_jira, etc.)

    Returns:
        Jira issue key (e.g., "SCRUM-123") or None if unresolved

    Example:
        resolve_jira_target("start working on this", org_context, state)
        → "SCRUM-123" (from state.active_jira)
    """

    try:
        msg_lower = user_message.lower()

        # ==============================================================================
        # STRATEGY 1: Explicit Jira key in message
        # ==============================================================================

        explicit_key = extract_jira_key_from_message(user_message)
        if explicit_key:
            logger.info(f"Resolved Jira from explicit key: {explicit_key}")
            return explicit_key

        # ==============================================================================
        # STRATEGY 2: Previous active task
        # ==============================================================================

        # Check for vague references that indicate continuation
        vague_references = [
            "this",
            "that",
            "the issue",
            "the ticket",
            "the task",
            "the story",
            "it",
            "this one",
            "current",
            "active",
        ]

        has_vague_reference = any(ref in msg_lower for ref in vague_references)

        if has_vague_reference and user_state.get("active_jira"):
            active_jira = user_state["active_jira"]
            logger.info(f"Resolved Jira from active task: {active_jira}")
            return active_jira

        # ==============================================================================
        # STRATEGY 3: Jira from recent conversation
        # ==============================================================================

        # Check if any Jira was mentioned in recent memory
        recent_memories = user_state.get("recent_memories", [])
        for memory in recent_memories[-5:]:  # Last 5 memories
            memory_text = str(memory.get("content", ""))
            jira_key = extract_jira_key_from_message(memory_text)
            if jira_key:
                logger.info(f"Resolved Jira from recent memory: {jira_key}")
                return jira_key

        # ==============================================================================
        # STRATEGY 4: Most relevant Jira from org context
        # ==============================================================================

        jira_issues = org_context.get("jira", [])

        if not jira_issues:
            logger.warning("No Jira issues in org context")
            return None

        # Score each Jira by relevance to message
        scored_issues = []

        for issue in jira_issues:
            score = _calculate_jira_relevance(issue, user_message, user_state)
            scored_issues.append((issue, score))

        # Sort by score (highest first)
        scored_issues.sort(key=lambda x: x[1], reverse=True)

        # If top score is high enough, use it
        if scored_issues and scored_issues[0][1] > 0.3:
            best_issue = scored_issues[0][0]
            issue_key = best_issue.get("key")
            logger.info(
                f"Resolved Jira from relevance scoring: {issue_key} (score: {scored_issues[0][1]:.2f})"
            )
            return issue_key

        # ==============================================================================
        # STRATEGY 5: Fallback - Highest priority unassigned or assigned to user
        # ==============================================================================

        user_email = user_state.get("user_email", "")

        # First try user's assigned issues
        user_issues = [
            issue
            for issue in jira_issues
            if issue.get("fields", {}).get("assignee", {}).get("emailAddress")
            == user_email
        ]

        if user_issues:
            # Return highest priority
            issue_key = user_issues[0].get("key")
            logger.info(f"Resolved Jira from user assignments: {issue_key}")
            return issue_key

        # Finally, just return first issue (highest priority in org context)
        if jira_issues:
            issue_key = jira_issues[0].get("key")
            logger.info(f"Resolved Jira from fallback (first issue): {issue_key}")
            return issue_key

        logger.warning("Could not resolve Jira target")
        return None

    except Exception as e:
        logger.error(f"Error resolving Jira target: {e}", exc_info=True)
        return None


def extract_jira_key_from_message(message: str) -> Optional[str]:
    """
    Extract Jira issue key from message.

    Pattern: PROJECT-NUMBER (e.g., SCRUM-123, ENG-54)

    Args:
        message: Text to search

    Returns:
        Jira key if found, None otherwise
    """

    # Pattern: 2-10 uppercase letters, hyphen, 1+ digits
    pattern = r"\b([A-Z]{2,10}-\d+)\b"
    match = re.search(pattern, message, re.IGNORECASE)

    if match:
        return match.group(1).upper()

    return None


def _calculate_jira_relevance(
    issue: Dict[str, Any], user_message: str, user_state: Dict[str, Any]
) -> float:
    """
    Calculate relevance score for a Jira issue given user message.

    Args:
        issue: Jira issue dict from org context
        user_message: User's message
        user_state: User state

    Returns:
        Relevance score (0.0 to 1.0)
    """

    score = 0.0
    msg_lower = user_message.lower()

    fields = issue.get("fields", {})

    # Check title match
    title = fields.get("summary", "").lower()
    if title:
        # Word overlap
        title_words = set(title.split())
        msg_words = set(msg_lower.split())
        overlap = len(title_words & msg_words)
        if overlap > 0:
            score += 0.4 * (overlap / len(title_words))

    # Check description match
    description = fields.get("description", "").lower()
    if description and len(msg_lower) > 10:
        # Substring match
        if any(word in description for word in msg_lower.split() if len(word) > 4):
            score += 0.2

    # Check labels match
    labels = fields.get("labels", [])
    for label in labels:
        if label.lower() in msg_lower:
            score += 0.1

    # Bonus for assigned to user
    assignee_email = fields.get("assignee", {}).get("emailAddress", "")
    user_email = user_state.get("user_email", "")
    if assignee_email and assignee_email == user_email:
        score += 0.2

    # Bonus for high priority
    priority = fields.get("priority", {}).get("name", "")
    if priority in ["Critical", "Blocker"]:
        score += 0.1

    return min(score, 1.0)  # Cap at 1.0


def get_jira_summary_for_display(
    issue_key: str, org_context: Dict[str, Any]
) -> Optional[str]:
    """
    Get a quick summary of a Jira issue for display.

    Args:
        issue_key: Jira key (e.g., "SCRUM-123")
        org_context: Organizational context

    Returns:
        Formatted summary string or None if not found
    """

    jira_issues = org_context.get("jira", [])

    for issue in jira_issues:
        if issue.get("key") == issue_key:
            fields = issue.get("fields", {})
            title = fields.get("summary", "No title")
            status = fields.get("status", {}).get("name", "Unknown")

            return f"**{issue_key}**: {title} ({status})"

    return None


def list_available_jira_issues(org_context: Dict[str, Any]) -> List[str]:
    """
    List all available Jira issues in org context.

    Args:
        org_context: Organizational context

    Returns:
        List of Jira keys
    """

    jira_issues = org_context.get("jira", [])
    return [issue.get("key") for issue in jira_issues if issue.get("key")]
