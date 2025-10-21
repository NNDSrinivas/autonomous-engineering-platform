"""
JIRA write service for posting comments and managing issue transitions
"""

import logging
import base64
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)


class JiraWriteService:
    """Service for JIRA write operations with proper authentication and error handling"""
    
    def __init__(self, base_url: str, token: str, email: str):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.email = email
        
        # Create basic auth string for JIRA API
        auth_string = f"{email}:{token}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        self.auth_header = f"Basic {encoded_auth}"
    
    async def _client(self) -> httpx.AsyncClient:
        """Create configured HTTP client for JIRA API
        
        Note: This client must be used with 'async with' context manager
        to ensure proper resource cleanup.
        """
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": self.auth_header,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "AutonomousEngineeringPlatform/1.0"
            },
            timeout=30.0
        )
    
    async def add_comment(
        self, 
        issue_key: str, 
        comment: str, 
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Add a comment to a JIRA issue
        
        Args:
            issue_key: JIRA issue key (e.g., 'AEP-27')
            comment: Comment text to post
            dry_run: If True, return preview without posting
            
        Returns:
            Dict with comment details or preview payload
        """
        try:
            # Prepare comment payload
            payload = {
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": comment
                                }
                            ]
                        }
                    ]
                }
            }
            
            if dry_run:
                return {
                    "preview": {
                        "endpoint": f"POST /rest/api/3/issue/{issue_key}/comment",
                        "payload": payload,
                        "description": f"Add comment to issue {issue_key}"
                    }
                }
            
            async with await self._client() as client:
                logger.info(f"Adding comment to JIRA issue: {issue_key}")
                
                response = await client.post(
                    f"/rest/api/3/issue/{issue_key}/comment",
                    json=payload
                )
                response.raise_for_status()
                
                comment_data = response.json()
                logger.info(f"Added comment to {issue_key}: {comment_data.get('id')}")
                
                return {
                    "url": f"{self.base_url}/browse/{issue_key}",
                    "comment_id": comment_data.get("id"),
                    "created": comment_data.get("created")
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"JIRA API error: {e.response.status_code} {e.response.text}")
            raise ValueError(f"JIRA API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error in add_comment: {e}")
            raise ValueError(f"Failed to add comment: {str(e)}")
    
    async def transition_issue(
        self, 
        issue_key: str, 
        transition_name: str, 
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Transition a JIRA issue to a new status
        
        Args:
            issue_key: JIRA issue key
            transition_name: Name of the transition (e.g., 'In Progress', 'Done')
            dry_run: If True, return preview without transitioning
            
        Returns:
            Dict with transition result or preview
        """
        try:
            if dry_run:
                return {
                    "preview": {
                        "endpoint": f"POST /rest/api/3/issue/{issue_key}/transitions",
                        "payload": {"transition": {"name": transition_name}},
                        "description": f"Transition {issue_key} to {transition_name}"
                    }
                }
            
            async with await self._client() as client:
                # First, get available transitions
                logger.info(f"Getting available transitions for {issue_key}")
                transitions_response = await client.get(
                    f"/rest/api/3/issue/{issue_key}/transitions"
                )
                transitions_response.raise_for_status()
                
                transitions_data = transitions_response.json()
                available_transitions = transitions_data.get("transitions", [])
                
                # Find the transition by name
                target_transition = None
                for transition in available_transitions:
                    if transition["name"].lower() == transition_name.lower():
                        target_transition = transition
                        break
                
                if not target_transition:
                    available_names = [t["name"] for t in available_transitions]
                    raise ValueError(
                        f"Transition '{transition_name}' not available. "
                        f"Available transitions: {', '.join(available_names)}"
                    )
                
                # Perform the transition
                logger.info(f"Transitioning {issue_key} to {transition_name}")
                transition_payload = {
                    "transition": {
                        "id": target_transition["id"]
                    }
                }
                
                transition_response = await client.post(
                    f"/rest/api/3/issue/{issue_key}/transitions",
                    json=transition_payload
                )
                transition_response.raise_for_status()
                
                logger.info(f"Successfully transitioned {issue_key} to {transition_name}")
                
                return {
                    "success": True,
                    "transition_id": target_transition["id"],
                    "transition_name": target_transition["name"],
                    "url": f"{self.base_url}/browse/{issue_key}"
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"JIRA API error during transition: {e.response.status_code} {e.response.text}")
            raise ValueError(f"JIRA transition error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Unexpected error in transition_issue: {e}")
            raise ValueError(f"Failed to transition issue: {str(e)}")
    
    async def get_issue_info(self, issue_key: str) -> Dict[str, Any]:
        """Get basic information about a JIRA issue"""
        try:
            async with await self._client() as client:
                response = await client.get(
                    f"/rest/api/3/issue/{issue_key}",
                    params={"fields": "summary,status,assignee,reporter"}
                )
                response.raise_for_status()
                
                issue_data = response.json()
                fields = issue_data.get("fields", {})
                
                return {
                    "key": issue_data.get("key"),
                    "summary": fields.get("summary"),
                    "status": fields.get("status", {}).get("name"),
                    "url": f"{self.base_url}/browse/{issue_key}"
                }
                
        except Exception as e:
            logger.error(f"Failed to get issue info: {e}")
            raise ValueError(f"Failed to get issue info: {str(e)}")