"""
Jira Execution Planner

Generates comprehensive engineering execution plans for Jira tasks.
This is the "senior architect brain" that proposes complete solutions.
"""

import logging
from typing import Dict, Any, Optional

from backend.ai.llm_router import complete_chat as call_llm

logger = logging.getLogger(__name__)


# ==============================================================================
# JIRA PLANNING SYSTEM PROMPT
# ==============================================================================

JIRA_PLAN_SYSTEM = """
You are NAVI, an autonomous engineering agent with senior architect-level understanding.

Your job: Given a Jira task with full organizational context, generate a complete engineering execution plan.

You will receive:
1. **Jira Issue**: Parsed issue with title, description, status, comments
2. **Enriched Context**: Related Slack conversations, Confluence docs, Zoom meetings, GitHub PRs
3. **Workspace Context**: Current codebase structure, relevant files, recent changes
4. **User Preferences**: Coding style, testing requirements, documentation standards

Generate a comprehensive plan with:

## 1. EXECUTIVE SUMMARY
- What this Jira is about (1-2 sentences)
- Why it matters
- Estimated complexity (Low/Medium/High)

## 2. ACCEPTANCE CRITERIA
- List clear, testable acceptance criteria
- If Jira lacks criteria, generate them based on description
- Format as numbered list

## 3. ARCHITECTURAL DECISIONS
- Key technical decisions to make
- Trade-offs to consider
- Recommended approach with reasoning

## 4. PROPOSED IMPLEMENTATION
- Step-by-step breakdown
- Files to create/modify
- Functions/classes to add
- Database changes (if any)
- API changes (if any)

## 5. CODE SCAFFOLDING
- Provide code structure (not full implementation)
- Show function signatures
- Show class definitions
- Show import statements
- Show test structure

## 6. TESTING STRATEGY
- Unit tests needed
- Integration tests needed
- Test scenarios to cover
- Edge cases to consider

## 7. DOCUMENTATION UPDATES
- README changes
- API documentation
- Code comments
- Confluence pages to update

## 8. RELATED CONTEXT
- Summarize relevant Slack discussions
- Reference key Confluence pages
- Link to related PRs
- Highlight meeting decisions

## 9. RISKS & CONSIDERATIONS
- Potential blockers
- Dependencies on other work
- Breaking changes
- Performance implications

## 10. SUGGESTED NEXT STEPS
1. First action to take
2. Second action
3. Third action
...

Be specific, actionable, and comprehensive.
Think like a senior engineer planning work for the team.
"""


async def generate_jira_plan(
    issue: Dict[str, Any],
    enriched_context: Dict[str, Any],
    workspace_context: Optional[str] = None,
    user_preferences: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate a comprehensive engineering execution plan for a Jira task.

    Args:
        issue: Normalized Jira issue from parser.parse_jira_issue()
        enriched_context: Enriched context from enricher.enrich_jira_context()
        workspace_context: Optional workspace/codebase context
        user_preferences: Optional user preferences (coding style, testing, etc.)

    Returns:
        Dict with:
        {
            "summary": "Executive summary...",
            "acceptance_criteria": ["criterion 1", "criterion 2"],
            "implementation": "Full implementation plan...",
            "code_scaffolding": "Code structure...",
            "testing": "Testing strategy...",
            "documentation": "Doc updates...",
            "risks": "Risks and considerations...",
            "next_steps": ["step 1", "step 2"],
            "full_plan": "Complete formatted plan for display"
        }

    Example:
        plan = await generate_jira_plan(issue, enriched, workspace)
        print(plan["full_plan"])  # Display to user
    """

    try:
        logger.info(f"Generating execution plan for Jira {issue.get('id')}")

        # Build prompt for LLM
        prompt_parts = []

        # Jira issue details
        prompt_parts.append("## JIRA ISSUE")
        prompt_parts.append(f"**ID**: {issue.get('id')}")
        prompt_parts.append(f"**Title**: {issue.get('title')}")
        prompt_parts.append(
            f"**Description**:\n{issue.get('description', 'No description')}"
        )
        prompt_parts.append(f"**Status**: {issue.get('status')}")
        prompt_parts.append(f"**Priority**: {issue.get('priority')}")
        prompt_parts.append(f"**Assignee**: {issue.get('assignee', 'Unassigned')}")

        if issue.get("labels"):
            prompt_parts.append(f"**Labels**: {', '.join(issue['labels'])}")

        if issue.get("comments"):
            prompt_parts.append(f"\n**Comments ({len(issue['comments'])}):**")
            for i, comment in enumerate(issue["comments"][:5], 1):  # Top 5 comments
                prompt_parts.append(f"{i}. {comment[:300]}...")

        prompt_parts.append("")

        # Enriched organizational context
        prompt_parts.append("## ORGANIZATIONAL CONTEXT")

        if enriched_context.get("slack"):
            prompt_parts.append(
                f"\n**Related Slack Discussions ({len(enriched_context['slack'])}):**"
            )
            for msg in enriched_context["slack"][:3]:  # Top 3
                prompt_parts.append(
                    f"- [{msg['channel']}] {msg['author']}: {msg['content'][:200]}..."
                )

        if enriched_context.get("docs"):
            prompt_parts.append(
                f"\n**Related Confluence Pages ({len(enriched_context['docs'])}):**"
            )
            for doc in enriched_context["docs"][:3]:
                prompt_parts.append(f"- {doc['title']}: {doc['content'][:200]}...")

        if enriched_context.get("meetings"):
            prompt_parts.append(
                f"\n**Related Meetings ({len(enriched_context['meetings'])}):**"
            )
            for meeting in enriched_context["meetings"]:
                prompt_parts.append(
                    f"- {meeting['topic']} ({meeting['date']}): {meeting['notes'][:200]}..."
                )

        if enriched_context.get("prs"):
            prompt_parts.append(
                f"\n**Related Pull Requests ({len(enriched_context['prs'])}):**"
            )
            for pr in enriched_context["prs"][:3]:
                prompt_parts.append(
                    f"- PR #{pr['number']}: {pr['title']} ({pr['state']})"
                )

        prompt_parts.append("")

        # Workspace context
        if workspace_context:
            prompt_parts.append("## WORKSPACE CONTEXT")
            prompt_parts.append(workspace_context[:2000])  # Limit size
            prompt_parts.append("")

        # User preferences
        if user_preferences:
            prompt_parts.append("## USER PREFERENCES")
            prompt_parts.append(
                f"- Coding style: {user_preferences.get('coding_style', 'Standard')}"
            )
            prompt_parts.append(
                f"- Testing: {user_preferences.get('testing', 'Required')}"
            )
            prompt_parts.append(
                f"- Documentation: {user_preferences.get('documentation', 'Required')}"
            )
            prompt_parts.append("")

        prompt = "\n".join(prompt_parts)

        # Call LLM
        llm_response = await call_llm(
            messages=[
                {"role": "system", "content": JIRA_PLAN_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            model="gpt-4o",  # Use best model for planning
            temperature=0.3,  # Lower temperature for more structured output
        )

        plan_text = llm_response.get("content", "")

        # Parse structured components (basic extraction)
        plan_dict = {
            "summary": _extract_section(plan_text, "EXECUTIVE SUMMARY"),
            "acceptance_criteria": _extract_list_section(
                plan_text, "ACCEPTANCE CRITERIA"
            ),
            "implementation": _extract_section(plan_text, "PROPOSED IMPLEMENTATION"),
            "code_scaffolding": _extract_section(plan_text, "CODE SCAFFOLDING"),
            "testing": _extract_section(plan_text, "TESTING STRATEGY"),
            "documentation": _extract_section(plan_text, "DOCUMENTATION UPDATES"),
            "risks": _extract_section(plan_text, "RISKS & CONSIDERATIONS"),
            "next_steps": _extract_list_section(plan_text, "SUGGESTED NEXT STEPS"),
            "full_plan": plan_text,
        }

        logger.info(f"Generated plan for {issue.get('id')} ({len(plan_text)} chars)")
        return plan_dict

    except Exception as e:
        logger.error(f"Error generating Jira plan: {e}", exc_info=True)
        return {
            "summary": f"Error generating plan: {str(e)}",
            "acceptance_criteria": [],
            "implementation": "",
            "code_scaffolding": "",
            "testing": "",
            "documentation": "",
            "risks": "",
            "next_steps": [],
            "full_plan": f"Error generating plan: {str(e)}",
        }


def _extract_section(text: str, section_title: str) -> str:
    """Extract content from a markdown section."""
    import re

    # Pattern: ## SECTION_TITLE followed by content until next ##
    pattern = rf"##\s*\d*\.?\s*{re.escape(section_title)}.*?\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)

    if match:
        return match.group(1).strip()

    return ""


def _extract_list_section(text: str, section_title: str) -> list:
    """Extract list items from a section."""
    section_text = _extract_section(text, section_title)

    if not section_text:
        return []

    # Extract numbered or bulleted list items
    import re

    items = re.findall(
        r"(?:^|\n)\s*(?:\d+\.|-|\*)\s+(.+?)(?=\n\s*(?:\d+\.|-|\*)|$)",
        section_text,
        re.MULTILINE,
    )

    return [item.strip() for item in items if item.strip()]


def format_plan_for_approval(plan: Dict[str, Any]) -> str:
    """
    Format plan for user approval display.

    Args:
        plan: Plan dict from generate_jira_plan()

    Returns:
        Formatted string for user to review and approve
    """

    lines = []
    lines.append("# 📋 Execution Plan")
    lines.append("")

    if plan.get("summary"):
        lines.append("## Summary")
        lines.append(plan["summary"])
        lines.append("")

    if plan.get("acceptance_criteria"):
        lines.append("## ✅ Acceptance Criteria")
        for i, criterion in enumerate(plan["acceptance_criteria"], 1):
            lines.append(f"{i}. {criterion}")
        lines.append("")

    if plan.get("next_steps"):
        lines.append("## 🚀 Next Steps")
        for i, step in enumerate(plan["next_steps"], 1):
            lines.append(f"{i}. {step}")
        lines.append("")

    if plan.get("risks"):
        lines.append("## ⚠️ Risks & Considerations")
        lines.append(plan["risks"])
        lines.append("")

    lines.append("---")
    lines.append("**Approve this plan?** (yes/no)")

    return "\n".join(lines)
