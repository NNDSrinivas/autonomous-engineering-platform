"""
Jira Ingestor - Ingest Jira issues into memory graph

Creates memory nodes for:
- Jira issues (with description, comments, status)
- Users (assignee, reporter)

Creates edges for:
- issue → issue (links, blocks, relates to)
- issue → user (assigned to, reported by)
- issue → pr (implemented by)
"""

import logging
from typing import Dict, Any
from backend.services.memory_graph_service import MemoryGraphService

logger = logging.getLogger(__name__)


class JiraIngestor:
    """Ingest Jira issues into the organizational memory graph."""
    
    def __init__(self, memory_service: MemoryGraphService):
        self.mg = memory_service
    
    async def ingest_issue(self, issue: Dict[str, Any]) -> int:
        """
        Ingest a single Jira issue.
        
        Args:
            issue: Jira issue dict from API
            
        Returns:
            Node ID of the created issue node
        """
        try:
            # Extract key fields
            key = issue.get("key", "")
            fields = issue.get("fields", {})
            summary = fields.get("summary", "")
            description = fields.get("description", "") or ""
            status = fields.get("status", {}).get("name", "")
            issue_type = fields.get("issuetype", {}).get("name", "")
            assignee = fields.get("assignee", {})
            reporter = fields.get("reporter", {})
            
            # Build full text for embedding
            full_text = f"{summary}\n\n{description}"
            
            # Create issue node
            node_id = await self.mg.add_node(
                node_type="jira_issue",
                text=full_text,
                title=f"{key}: {summary}",
                meta={
                    "key": key,
                    "status": status,
                    "issue_type": issue_type,
                    "summary": summary,
                    "assignee": assignee.get("displayName") if assignee else None,
                    "reporter": reporter.get("displayName") if reporter else None,
                    "priority": fields.get("priority", {}).get("name"),
                    "url": f"https://your-domain.atlassian.net/browse/{key}"
                }
            )
            
            logger.info(f"Ingested Jira issue {key} as node {node_id}")
            
            # Create edges for issue links
            issue_links = fields.get("issuelinks", [])
            edges_created = 0
            
            for link in issue_links:
                link_type = link.get("type", {}).get("name", "relates to")
                
                # Inward link (this issue is linked FROM another)
                if "inwardIssue" in link:
                    inward_key = link["inwardIssue"].get("key")
                    # TODO: Look up node ID for inward_key
                    logger.debug(f"Issue {key} has inward link from {inward_key} ({link_type})")
                
                # Outward link (this issue links TO another)
                if "outwardIssue" in link:
                    outward_key = link["outwardIssue"].get("key")
                    # TODO: Look up node ID for outward_key
                    logger.debug(f"Issue {key} has outward link to {outward_key} ({link_type})")
            
            logger.info(f"Created {edges_created} edges for issue {key}")
            
            return node_id
            
        except Exception as e:
            logger.error(f"Failed to ingest Jira issue: {e}", exc_info=True)
            raise
    
    async def ingest_comment(self, issue_node_id: int, comment: Dict[str, Any]) -> int:
        """
        Ingest a Jira comment as a node linked to the issue.
        
        Args:
            issue_node_id: Node ID of the parent issue
            comment: Comment dict from Jira API
            
        Returns:
            Node ID of the created comment node
        """
        try:
            author = comment.get("author", {}).get("displayName", "Unknown")
            body = comment.get("body", "")
            created = comment.get("created", "")
            
            # Create comment node
            node_id = await self.mg.add_node(
                node_type="jira_comment",
                text=body,
                title=f"Comment by {author}",
                meta={
                    "author": author,
                    "created": created,
                    "comment_id": comment.get("id")
                }
            )
            
            # Link comment to issue
            self.mg.add_edge(
                from_id=node_id,
                to_id=issue_node_id,
                edge_type="comments_on"
            )
            
            logger.info(f"Ingested comment {comment.get('id')} as node {node_id}")
            
            return node_id
            
        except Exception as e:
            logger.error(f"Failed to ingest Jira comment: {e}", exc_info=True)
            raise
    
    async def link_issue_to_pr(self, issue_node_id: int, pr_node_id: int):
        """
        Create an edge linking a Jira issue to a GitHub PR.
        
        Args:
            issue_node_id: Node ID of the Jira issue
            pr_node_id: Node ID of the GitHub PR
        """
        self.mg.add_edge(
            from_id=pr_node_id,
            to_id=issue_node_id,
            edge_type="implements",
            meta={"source": "github_pr_description"}
        )
        logger.info(f"Linked PR node {pr_node_id} to Jira issue node {issue_node_id}")
