"""
PR Comment Fetcher - Phase 4.6

Fetches and parses PR comments from GitHub API for analysis.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from .review_types import PrComment, ReviewContext

logger = logging.getLogger(__name__)


class PrCommentFetcher:
    """
    Fetches PR comments and review data from GitHub API.
    
    Handles both issue comments and review comments with proper context.
    """
    
    def __init__(self, github_service=None):
        self.github_service = github_service
        
    async def fetch_pr_context(self, repository: str, pr_number: int) -> Optional[ReviewContext]:
        """
        Fetch full PR context including metadata and file changes.
        
        Args:
            repository: Repository name (owner/repo)
            pr_number: Pull request number
            
        Returns:
            ReviewContext with PR details
        """
        if not self.github_service:
            logger.error("GitHub service not available")
            return None
            
        try:
            # Get PR details
            pr_data = await self.github_service.get_pull_request(repository, pr_number)
            
            if not pr_data:
                logger.error(f"PR #{pr_number} not found in {repository}")
                return None
                
            # Get list of changed files
            files_changed = await self.github_service.get_pr_files(repository, pr_number)
            file_paths = [f.get("filename", "") for f in files_changed] if files_changed else []
            
            return ReviewContext(
                repository=repository,
                pr_number=pr_number,
                pr_title=pr_data.get("title", ""),
                pr_body=pr_data.get("body", ""),
                author=pr_data.get("user", {}).get("login", ""),
                files_changed=file_paths,
                base_branch=pr_data.get("base", {}).get("ref", "main"),
                head_branch=pr_data.get("head", {}).get("ref", "")
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch PR context for {repository}#{pr_number}: {e}")
            return None
            
    async def fetch_pr_comments(self, repository: str, pr_number: int) -> List[PrComment]:
        """
        Fetch all comments on a PR (both issue comments and review comments).
        
        Args:
            repository: Repository name (owner/repo)
            pr_number: Pull request number
            
        Returns:
            List of PrComment objects
        """
        if not self.github_service:
            logger.error("GitHub service not available")
            return []
            
        try:
            comments = []
            
            # Get issue comments (general PR comments)
            issue_comments = await self.github_service.get_pr_comments(repository, pr_number)
            
            for comment in issue_comments or []:
                pr_comment = self._parse_issue_comment(comment)
                if pr_comment:
                    comments.append(pr_comment)
                    
            # Get review comments (inline code comments)
            review_comments = await self.github_service.get_pr_review_comments(repository, pr_number)
            
            for comment in review_comments or []:
                pr_comment = self._parse_review_comment(comment)
                if pr_comment:
                    comments.append(pr_comment)
                    
            logger.info(f"Fetched {len(comments)} comments for PR #{pr_number}")
            return comments
            
        except Exception as e:
            logger.error(f"Failed to fetch PR comments for {repository}#{pr_number}: {e}")
            return []
            
    async def fetch_new_comments_since(
        self, 
        repository: str, 
        pr_number: int, 
        since: datetime
    ) -> List[PrComment]:
        """
        Fetch only new comments since a specific timestamp.
        
        Args:
            repository: Repository name (owner/repo)
            pr_number: Pull request number
            since: Only return comments newer than this
            
        Returns:
            List of new PrComment objects
        """
        all_comments = await self.fetch_pr_comments(repository, pr_number)
        
        new_comments = [
            comment for comment in all_comments 
            if comment.created_at > since
        ]
        
        logger.info(f"Found {len(new_comments)} new comments since {since}")
        return new_comments
        
    async def fetch_unresolved_comments(self, repository: str, pr_number: int) -> List[PrComment]:
        """
        Fetch only unresolved comments on a PR.
        
        Args:
            repository: Repository name (owner/repo)
            pr_number: Pull request number
            
        Returns:
            List of unresolved PrComment objects
        """
        all_comments = await self.fetch_pr_comments(repository, pr_number)
        
        unresolved_comments = [
            comment for comment in all_comments 
            if not comment.is_resolved
        ]
        
        logger.info(f"Found {len(unresolved_comments)} unresolved comments")
        return unresolved_comments
        
    def _parse_issue_comment(self, comment_data: Dict[str, Any]) -> Optional[PrComment]:
        """Parse GitHub issue comment data into PrComment"""
        try:
            created_at = self._parse_github_datetime(comment_data.get("created_at"))
            updated_at = self._parse_github_datetime(comment_data.get("updated_at"))
            
            return PrComment(
                id=str(comment_data.get("id", "")),
                author=comment_data.get("user", {}).get("login", ""),
                body=comment_data.get("body", ""),
                created_at=created_at or datetime.now(),
                updated_at=updated_at or datetime.now(),
                file_path=None,  # Issue comments are not on specific files
                line_number=None,
                is_resolved=False,  # Issue comments don't have resolved status
                reply_to=None
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse issue comment: {e}")
            return None
            
    def _parse_review_comment(self, comment_data: Dict[str, Any]) -> Optional[PrComment]:
        """Parse GitHub review comment data into PrComment"""
        try:
            created_at = self._parse_github_datetime(comment_data.get("created_at"))
            updated_at = self._parse_github_datetime(comment_data.get("updated_at"))
            
            return PrComment(
                id=str(comment_data.get("id", "")),
                author=comment_data.get("user", {}).get("login", ""),
                body=comment_data.get("body", ""),
                created_at=created_at or datetime.now(),
                updated_at=updated_at or datetime.now(),
                file_path=comment_data.get("path"),
                line_number=comment_data.get("line"),
                is_resolved=comment_data.get("resolved", False),
                reply_to=comment_data.get("in_reply_to_id")
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse review comment: {e}")
            return None
            
    def _parse_github_datetime(self, dt_string: Optional[str]) -> Optional[datetime]:
        """Parse GitHub datetime string to datetime object"""
        if not dt_string:
            return None
            
        try:
            # GitHub returns ISO format: 2023-10-01T10:00:00Z
            return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"Failed to parse datetime '{dt_string}': {e}")
            return None
            
    async def post_comment_reply(
        self, 
        repository: str, 
        pr_number: int, 
        comment_id: str,
        reply_text: str
    ) -> bool:
        """
        Post a reply to a specific comment.
        
        Args:
            repository: Repository name (owner/repo)
            pr_number: Pull request number
            comment_id: ID of comment to reply to
            reply_text: Reply message
            
        Returns:
            True if reply was posted successfully
        """
        if not self.github_service:
            logger.error("GitHub service not available")
            return False
            
        try:
            # Use GitHub service to post comment reply
            result = await self.github_service.add_pr_comment(repository, pr_number, reply_text)
            
            if result:
                logger.info(f"Posted reply to comment {comment_id} on PR #{pr_number}")
                return True
            else:
                logger.error(f"Failed to post reply to comment {comment_id}")
                return False
                
        except Exception as e:
            logger.error(f"Exception posting comment reply: {e}")
            return False
            
    async def resolve_comment(
        self, 
        repository: str, 
        pr_number: int, 
        comment_id: str
    ) -> bool:
        """
        Mark a review comment as resolved.
        
        Args:
            repository: Repository name (owner/repo)
            pr_number: Pull request number
            comment_id: ID of comment to resolve
            
        Returns:
            True if comment was resolved successfully
        """
        if not self.github_service:
            logger.error("GitHub service not available")
            return False
            
        try:
            # GitHub API call to resolve comment
            result = await self.github_service.resolve_review_comment(repository, comment_id)
            
            if result:
                logger.info(f"Resolved comment {comment_id} on PR #{pr_number}")
                return True
            else:
                logger.error(f"Failed to resolve comment {comment_id}")
                return False
                
        except Exception as e:
            logger.error(f"Exception resolving comment: {e}")
            return False