"""
Link Enricher Service

Helps other connectors (Slack, Zoom, Teams, Confluence) add related links
to existing Jira memories in NAVI. This creates the rich References section
that NAVI can show to users.

Example usage:
    await enrich_jira_memory_with_link(
        db=db,
        user_id="default_user", 
        jira_key="SCRUM-1",
        link_type="slack",
        url="https://slack.com/app_redirect?channel=C123&message_ts=1234"
    )
"""

from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
import json

logger = logging.getLogger(__name__)


async def enrich_jira_memory_with_link(
    db: Session,
    user_id: str,
    jira_key: str,
    link_type: str,
    url: str,
    description: Optional[str] = None,
) -> bool:
    """
    Add a related link to an existing Jira memory in NAVI.
    
    This allows other connectors to associate their resources with Jira tickets,
    creating rich References sections that NAVI can show to users.
    
    Args:
        db: Database session
        user_id: User identifier
        jira_key: Jira ticket key (e.g., "SCRUM-1")
        link_type: Type of link ("slack", "zoom", "teams", "confluence", "jenkins", etc.)
        url: The URL to add
        description: Optional description of the link
        
    Returns:
        True if link was added successfully, False if memory not found
    """
    try:
        # Find the Jira memory for this user and key
        result = db.execute(
            text("""
                SELECT id, meta_json 
                FROM navi_memory 
                WHERE user_id = :user_id 
                  AND category = 'task'
                  AND scope = :jira_key
                  AND CAST(meta_json AS TEXT) LIKE '%"source": "jira"%'
                LIMIT 1
            """),
            {"user_id": user_id, "jira_key": jira_key}
        ).fetchone()
        
        if not result:
            logger.warning(
                "[LINK-ENRICHER] No Jira memory found for %s/%s", 
                user_id, jira_key
            )
            return False
            
        memory_id, meta_json_str = result
        
        # Parse existing metadata
        try:
            if isinstance(meta_json_str, str):
                meta_json = json.loads(meta_json_str)
            else:
                meta_json = dict(meta_json_str)
        except (json.JSONDecodeError, TypeError):
            meta_json = {}
            
        # Ensure links structure exists
        if "links" not in meta_json:
            meta_json["links"] = {}
            
        links = meta_json["links"]
        if link_type not in links:
            links[link_type] = []
            
        # Add the new link if it's not already there
        if url not in links[link_type]:
            links[link_type].append(url)
            
            # Update the memory with enriched metadata
            updated_meta_json = json.dumps(meta_json)
            db.execute(
                text("""
                    UPDATE navi_memory 
                    SET meta_json = :meta_json,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :memory_id
                """),
                {"memory_id": memory_id, "meta_json": updated_meta_json}
            )
            db.commit()
            
            logger.info(
                "[LINK-ENRICHER] Added %s link to %s/%s: %s",
                link_type, user_id, jira_key, url
            )
            return True
        else:
            logger.debug(
                "[LINK-ENRICHER] Link already exists for %s/%s: %s",
                user_id, jira_key, url
            )
            return True
            
    except Exception as e:
        logger.error(
            "[LINK-ENRICHER] Failed to add link: %s", 
            e, exc_info=True
        )
        db.rollback()
        return False


async def get_jira_memories_mentioning_key(
    db: Session,
    jira_key: str,
    user_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Find all NAVI memories that mention a specific Jira key.
    
    Useful for finding related discussions, meetings, or docs that reference
    a ticket, even if they're stored as separate memories.
    
    Args:
        db: Database session
        jira_key: Jira ticket key to search for
        user_id: Optional user filter
        
    Returns:
        List of memory dictionaries
    """
    try:
        # Build query conditions
        conditions = [
            "CAST(content AS TEXT) LIKE :jira_key_pattern",
            "category != 'task'"  # Exclude the Jira task memory itself
        ]
        params = {"jira_key_pattern": f"%{jira_key}%"}
        
        if user_id:
            conditions.append("user_id = :user_id")
            params["user_id"] = user_id
            
        where_clause = " AND ".join(conditions)
        
        result = db.execute(
            text(f"""
                SELECT 
                    id, user_id, category, scope, title, content,
                    meta_json, importance, created_at, updated_at
                FROM navi_memory
                WHERE {where_clause}
                ORDER BY updated_at DESC
                LIMIT 10
            """),
            params
        )
        
        memories = []
        for row in result:
            memory = {
                "id": row[0],
                "user_id": row[1], 
                "category": row[2],
                "scope": row[3],
                "title": row[4],
                "content": row[5],
                "meta_json": row[6],
                "importance": row[7],
                "created_at": row[8],
                "updated_at": row[9],
            }
            
            # Parse tags if available
            try:
                if isinstance(memory["meta_json"], str):
                    memory["tags"] = json.loads(memory["meta_json"])
                else:
                    memory["tags"] = dict(memory["meta_json"])
            except:
                memory["tags"] = {}
                
            memories.append(memory)
            
        logger.info(
            "[LINK-ENRICHER] Found %d memories mentioning %s",
            len(memories), jira_key
        )
        return memories
        
    except Exception as e:
        logger.error(
            "[LINK-ENRICHER] Failed to search for Jira key mentions: %s",
            e, exc_info=True
        )
        return []


# Common link types for validation
VALID_LINK_TYPES = [
    "confluence",
    "slack", 
    "zoom",
    "teams",
    "gmeet",
    "jenkins",
    "devops",
    "github",
    "gitlab",
    "notion",
    "linear",
    "figma",
    "miro",
    "other"
]


def validate_link_type(link_type: str) -> bool:
    """Validate that link_type is one of the expected types."""
    return link_type.lower() in VALID_LINK_TYPES