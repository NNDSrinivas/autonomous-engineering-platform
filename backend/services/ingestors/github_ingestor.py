"""
GitHub Ingestor - Ingest GitHub PRs and issues into memory graph

Creates memory nodes for:
- Pull requests
- GitHub issues
- Code files/diffs
- Users

Creates edges for:
- PR → issue (implements, fixes, closes)
- PR → PR (depends on)
- PR → user (authored by, reviewed by)
"""

import logging
from typing import Dict, Any, List, Optional
from backend.services.memory_graph_service import MemoryGraphService

logger = logging.getLogger(__name__)


class GitHubIngestor:
    """Ingest GitHub data into the organizational memory graph."""
    
    def __init__(self, memory_service: MemoryGraphService):
        self.mg = memory_service
    
    async def ingest_pr(self, pr: Dict[str, Any], repo_name: str) -> int:
        """
        Ingest a GitHub pull request.
        
        Args:
            pr: PR dict from GitHub API
            repo_name: Repository name
            
        Returns:
            Node ID of the created PR node
        """
        try:
            pr_number = pr.get("number", 0)
            title = pr.get("title", "")
            body = pr.get("body", "") or ""
            state = pr.get("state", "")
            author = pr.get("user", {}).get("login", "Unknown")
            base_branch = pr.get("base", {}).get("ref", "")
            head_branch = pr.get("head", {}).get("ref", "")
            
            # Build full text
            full_text = f"{title}\n\n{body}"
            
            # Create PR node
            node_id = await self.mg.add_node(
                node_type="github_pr",
                text=full_text,
                title=f"PR #{pr_number}: {title}",
                meta={
                    "pr_number": pr_number,
                    "repo": repo_name,
                    "state": state,
                    "author": author,
                    "base_branch": base_branch,
                    "head_branch": head_branch,
                    "url": pr.get("html_url", ""),
                    "created_at": pr.get("created_at"),
                    "merged_at": pr.get("merged_at")
                }
            )
            
            logger.info(f"Ingested GitHub PR #{pr_number} as node {node_id}")
            
            # Extract Jira issue keys from PR body/title
            import re
            jira_pattern = r'([A-Z]+-\d+)'
            jira_keys = re.findall(jira_pattern, f"{title} {body}")
            
            if jira_keys:
                logger.info(f"PR #{pr_number} references Jira issues: {jira_keys}")
                # TODO: Link to Jira issue nodes
            
            return node_id
            
        except Exception as e:
            logger.error(f"Failed to ingest GitHub PR: {e}", exc_info=True)
            raise
    
    async def ingest_github_issue(self, issue: Dict[str, Any], repo_name: str) -> int:
        """Ingest a GitHub issue."""
        try:
            issue_number = issue.get("number", 0)
            title = issue.get("title", "")
            body = issue.get("body", "") or ""
            state = issue.get("state", "")
            author = issue.get("user", {}).get("login", "Unknown")
            
            full_text = f"{title}\n\n{body}"
            
            node_id = await self.mg.add_node(
                node_type="github_issue",
                text=full_text,
                title=f"Issue #{issue_number}: {title}",
                meta={
                    "issue_number": issue_number,
                    "repo": repo_name,
                    "state": state,
                    "author": author,
                    "url": issue.get("html_url", ""),
                    "created_at": issue.get("created_at")
                }
            )
            
            logger.info(f"Ingested GitHub issue #{issue_number} as node {node_id}")
            
            return node_id
            
        except Exception as e:
            logger.error(f"Failed to ingest GitHub issue: {e}", exc_info=True)
            raise
