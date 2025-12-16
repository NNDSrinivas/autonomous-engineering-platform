"""
Jira Context Enricher

Links Jira issues with organizational context from Slack, Confluence, Zoom, and GitHub.
This is what makes NAVI truly understand the FULL context of a task.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


async def enrich_jira_context(
    issue: Dict[str, Any], org_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Given a Jira issue, find all related organizational artifacts:
    - Slack conversations
    - Confluence pages
    - GitHub PRs
    - Zoom meeting notes

    This creates a complete picture of the task beyond just the Jira description.

    Args:
        issue: Normalized Jira issue from parser.parse_jira_issue()
        org_context: Full organizational context from org_retriever

    Returns:
        Dict with related artifacts:
        {
            "slack": [...],
            "docs": [...],
            "meetings": [...],
            "prs": [...],
            "code_files": [...]
        }

    Example output:
        {
            "slack": [
                {"content": "Discussion about auth approach...", "channel": "#backend", "timestamp": "..."}
            ],
            "docs": [
                {"title": "OAuth2 Implementation Guide", "url": "...", "content": "..."}
            ],
            "meetings": [
                {"title": "Architecture Review", "date": "...", "notes": "..."}
            ],
            "prs": [
                {"title": "Add JWT auth", "number": 42, "url": "..."}
            ]
        }
    """

    try:
        title = issue.get("title", "")
        issue_id = issue.get("id", "")
        description = issue.get("description", "")
        labels = issue.get("labels", [])

        # Combine search terms
        search_terms = [issue_id.lower(), title.lower()]
        search_terms.extend([label.lower() for label in labels])
        if description:
            search_terms.append(description.lower())

        # Remove empty terms
        search_terms = [term for term in search_terms if term]

        logger.info(
            f"Enriching Jira {issue_id} with org context using terms: {search_terms}"
        )

        # ==============================================================================
        # SLACK ENRICHMENT
        # ==============================================================================

        related_slack = []
        slack_artifacts = org_context.get("slack", [])

        for artifact in slack_artifacts:
            content = artifact.get("content", "").lower()

            # Check if any search term appears in Slack message
            for term in search_terms:
                if term in content:
                    related_slack.append(
                        {
                            "content": artifact.get("content", ""),
                            "channel": artifact.get("metadata", {}).get(
                                "channel", "Unknown"
                            ),
                            "author": artifact.get("metadata", {}).get(
                                "author", "Unknown"
                            ),
                            "timestamp": artifact.get("metadata", {}).get(
                                "timestamp", ""
                            ),
                            "relevance_score": _calculate_relevance(
                                content, search_terms
                            ),
                        }
                    )
                    break  # Don't add same message multiple times

        # Sort by relevance
        related_slack.sort(key=lambda x: x["relevance_score"], reverse=True)

        # ==============================================================================
        # CONFLUENCE ENRICHMENT
        # ==============================================================================

        related_docs = []
        confluence_artifacts = org_context.get("confluence", [])

        for artifact in confluence_artifacts:
            content = artifact.get("content", "").lower()
            title_match = artifact.get("metadata", {}).get("title", "").lower()

            # Check content and title
            for term in search_terms:
                if term in content or term in title_match:
                    related_docs.append(
                        {
                            "title": artifact.get("metadata", {}).get(
                                "title", "Untitled"
                            ),
                            "url": artifact.get("metadata", {}).get("url", ""),
                            "content": artifact.get("content", "")[:500],  # Truncate
                            "space": artifact.get("metadata", {}).get(
                                "space", "Unknown"
                            ),
                            "relevance_score": _calculate_relevance(
                                content + " " + title_match, search_terms
                            ),
                        }
                    )
                    break

        related_docs.sort(key=lambda x: x["relevance_score"], reverse=True)

        # ==============================================================================
        # ZOOM ENRICHMENT
        # ==============================================================================

        related_meetings = []
        zoom_artifacts = org_context.get("zoom", [])

        for artifact in zoom_artifacts:
            content = artifact.get("content", "").lower()
            title_match = artifact.get("metadata", {}).get("topic", "").lower()

            for term in search_terms:
                if term in content or term in title_match:
                    related_meetings.append(
                        {
                            "topic": artifact.get("metadata", {}).get(
                                "topic", "Untitled Meeting"
                            ),
                            "date": artifact.get("metadata", {}).get("start_time", ""),
                            "notes": artifact.get("content", "")[:500],  # Truncate
                            "relevance_score": _calculate_relevance(
                                content + " " + title_match, search_terms
                            ),
                        }
                    )
                    break

        related_meetings.sort(key=lambda x: x["relevance_score"], reverse=True)

        # ==============================================================================
        # GITHUB PR ENRICHMENT
        # ==============================================================================

        related_prs = []
        github_artifacts = org_context.get("github", [])

        for artifact in github_artifacts:
            content = artifact.get("content", "").lower()
            title_match = artifact.get("metadata", {}).get("title", "").lower()

            for term in search_terms:
                if term in content or term in title_match:
                    related_prs.append(
                        {
                            "title": artifact.get("metadata", {}).get(
                                "title", "Untitled PR"
                            ),
                            "number": artifact.get("metadata", {}).get("number", ""),
                            "url": artifact.get("metadata", {}).get("url", ""),
                            "state": artifact.get("metadata", {}).get(
                                "state", "unknown"
                            ),
                            "author": artifact.get("metadata", {}).get(
                                "author", "Unknown"
                            ),
                            "relevance_score": _calculate_relevance(
                                content + " " + title_match, search_terms
                            ),
                        }
                    )
                    break

        related_prs.sort(key=lambda x: x["relevance_score"], reverse=True)

        # ==============================================================================
        # RETURN ENRICHED CONTEXT
        # ==============================================================================

        enriched = {
            "slack": related_slack[:10],  # Top 10 most relevant
            "docs": related_docs[:5],  # Top 5 docs
            "meetings": related_meetings[:3],  # Top 3 meetings
            "prs": related_prs[:5],  # Top 5 PRs
        }

        # Log enrichment summary
        logger.info(
            f"Enriched {issue_id}: "
            f"{len(enriched['slack'])} Slack, "
            f"{len(enriched['docs'])} Docs, "
            f"{len(enriched['meetings'])} Meetings, "
            f"{len(enriched['prs'])} PRs"
        )

        return enriched

    except Exception as e:
        logger.error(f"Error enriching Jira context: {e}", exc_info=True)
        return {
            "slack": [],
            "docs": [],
            "meetings": [],
            "prs": [],
        }


def _calculate_relevance(content: str, search_terms: List[str]) -> float:
    """
    Calculate relevance score based on how many search terms appear.

    Args:
        content: Text to search in
        search_terms: List of terms to search for

    Returns:
        Relevance score (0.0 to 1.0)
    """
    if not search_terms:
        return 0.0

    matches = sum(1 for term in search_terms if term in content)
    return matches / len(search_terms)


def format_enriched_context_for_llm(enriched: Dict[str, Any]) -> str:
    """
    Format enriched context for LLM consumption.

    Args:
        enriched: Output from enrich_jira_context()

    Returns:
        Human-readable formatted string for LLM
    """

    sections = []

    # Slack discussions
    if enriched.get("slack"):
        sections.append("**Related Slack Discussions:**")
        for msg in enriched["slack"][:5]:  # Top 5
            sections.append(
                f"- [{msg['channel']}] {msg['author']}: {msg['content'][:200]}..."
            )
        sections.append("")

    # Confluence docs
    if enriched.get("docs"):
        sections.append("**Related Documentation:**")
        for doc in enriched["docs"][:3]:  # Top 3
            sections.append(f"- {doc['title']} ({doc['space']})")
            sections.append(f"  {doc['content'][:150]}...")
        sections.append("")

    # Zoom meetings
    if enriched.get("meetings"):
        sections.append("**Related Meetings:**")
        for meeting in enriched["meetings"]:
            sections.append(f"- {meeting['topic']} ({meeting['date']})")
            sections.append(f"  {meeting['notes'][:150]}...")
        sections.append("")

    # GitHub PRs
    if enriched.get("prs"):
        sections.append("**Related Pull Requests:**")
        for pr in enriched["prs"]:
            sections.append(
                f"- PR #{pr['number']}: {pr['title']} ({pr['state']}) by {pr['author']}"
            )
        sections.append("")

    if not sections:
        return "No related organizational artifacts found."

    return "\n".join(sections)
