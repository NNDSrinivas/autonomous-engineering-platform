"""
GitHub write service for creating draft PRs and managing repository operations
"""

import logging
import re
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import httpx

# GitHub username/organization validation pattern
# Allows: alphanumeric at start, hyphens anywhere (including start/end for legacy), max 39 chars total
# See: https://github.com/shinnn/github-username-regex and GitHub docs for details
GITHUB_OWNER_PATTERN = r'^[a-zA-Z0-9][a-zA-Z0-9-]{0,38}$'

logger = logging.getLogger(__name__)


class GitHubWriteService:
    """Service for GitHub write operations with proper error handling and dry-run support"""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
    
    def _extract_branch_name(self, head: str) -> str:
        """
        Extract branch name from head, handling complex edge cases:
        
        1. Cross-repo PRs use format 'owner:branch' where owner is GitHub username/org
        2. Branch names themselves may contain colons (e.g., 'feature:v1.2:hotfix')
        3. Must distinguish between these cases to extract correct branch name
        
        Strategy: If exactly one colon exists, validate if left side matches GitHub
        owner naming rules (alphanumeric, hyphens, max 39 chars).
        If valid owner format, treat as cross-repo and extract branch after colon.
        Otherwise, treat entire string as branch name to preserve colon-containing branches.
        
        Args:
            head: The head reference from PR (e.g., 'owner:branch' or 'feature:v1.2:hotfix')
            
        Returns:
            The extracted branch name
        """
        if head.count(':') == 1:
            owner_candidate, branch_candidate = head.split(':', 1)
            # Validate against GitHub username/org naming rules
            if re.fullmatch(GITHUB_OWNER_PATTERN, owner_candidate):
                return branch_candidate
        return head
    
    @asynccontextmanager
    async def _client(self):
        """Create configured HTTP client for GitHub API with automatic resource cleanup"""
        async with httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "AutonomousEngineeringPlatform/1.0"
            },
            timeout=30.0
        ) as client:
            yield client
    
    def _format_pr_title(self, title: str, ticket_key: Optional[str] = None) -> str:
        """Format PR title with optional ticket linking"""
        if ticket_key and ticket_key not in title:
            return f"{title} ({ticket_key})"
        return title
    
    def _format_pr_body(self, body: str, ticket_key: Optional[str] = None) -> str:
        """Format PR body with optional ticket references"""
        formatted_body = body
        if ticket_key:
            # Add ticket reference if not already present
            if ticket_key not in body:
                formatted_body = f"{body}\n\nRelated: {ticket_key}"
        return formatted_body
    
    async def draft_pr(
        self, 
        repo_full_name: str, 
        base: str, 
        head: str, 
        title: str, 
        body: str, 
        ticket_key: Optional[str] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Create a draft PR or return existing PR if found
        
        Args:
            repo_full_name: Repository in format 'owner/repo'
            base: Base branch (target)
            head: Head branch (source)
            title: PR title
            body: PR description
            ticket_key: Optional ticket key for linking
            dry_run: If True, return preview without creating
            
        Returns:
            Dict with PR details or preview payload
        """
        try:
            # Format title and body with ticket linking
            formatted_title = self._format_pr_title(title, ticket_key)
            formatted_body = self._format_pr_body(body, ticket_key)
            
            # Prepare payload
            payload = {
                "title": formatted_title,
                "head": head,
                "base": base,
                "body": formatted_body,
                "draft": True
            }
            
            if dry_run:
                return {
                    "preview": {
                        "endpoint": f"POST /repos/{repo_full_name}/pulls",
                        "payload": payload,
                        "description": f"Create draft PR from {head} to {base}"
                    }
                }
            
            async with self._client() as client:
                # Check for existing PR with same head/base
                logger.info(f"Checking for existing PR: {head} -> {base}")
                
                # Extract branch name handling cross-repo format and branch names with colons
                head_branch = self._extract_branch_name(head)
                
                response = await client.get(
                    f"/repos/{repo_full_name}/pulls",
                    params={
                        "state": "open",
                        "head": head,  # Use full owner:branch for cross-repo PRs
                        "base": base
                    }
                )
                response.raise_for_status()
                
                existing_prs = response.json()
                if existing_prs:
                    pr = existing_prs[0]  # Take first match
                    logger.info(f"Found existing PR #{pr['number']}")
                    return {
                        "existed": True,
                        "url": pr["html_url"],
                        "number": pr["number"]
                    }
                
                # Create new PR
                logger.info(f"Creating new draft PR: {formatted_title}")
                create_response = await client.post(
                    f"/repos/{repo_full_name}/pulls",
                    json=payload
                )
                create_response.raise_for_status()
                
                pr_data = create_response.json()
                logger.info(f"Created PR #{pr_data['number']}: {pr_data['html_url']}")
                
                return {
                    "existed": False,
                    "url": pr_data["html_url"],
                    "number": pr_data["number"]
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e.response.status_code} {e.response.text}")
            raise ValueError(f"GitHub API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error in draft_pr: {e}")
            raise ValueError(f"Failed to create PR: {str(e)}")
    
    async def get_pr_status(self, repo_full_name: str, pr_number: int) -> Dict[str, Any]:
        """Get status of existing PR"""
        try:
            async with self._client() as client:
                response = await client.get(f"/repos/{repo_full_name}/pulls/{pr_number}")
                response.raise_for_status()
                
                pr_data = response.json()
                return {
                    "number": pr_data["number"],
                    "title": pr_data["title"],
                    "state": pr_data["state"],
                    "draft": pr_data["draft"],
                    "url": pr_data["html_url"],
                    "head": pr_data["head"]["ref"],
                    "base": pr_data["base"]["ref"]
                }
        except Exception as e:
            logger.error(f"Failed to get PR status: {e}")
            raise ValueError(f"Failed to get PR status: {str(e)}")