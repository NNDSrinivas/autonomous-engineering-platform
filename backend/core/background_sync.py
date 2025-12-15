"""
Background sync service for Jira and other integrations.

Automatically keeps Jira issues fresh without manual intervention.
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime, timedelta

import structlog

logger = structlog.get_logger(__name__)

# Global task reference for cleanup
_sync_task: Optional[asyncio.Task] = None


async def start_background_sync() -> Optional[asyncio.Task]:
    """
    Start background sync task that periodically refreshes Jira data.
    
    Returns:
        The background task for cleanup during shutdown
    """
    global _sync_task
    
    try:
        logger.info("[BACKGROUND-SYNC] Starting background sync service")
        _sync_task = asyncio.create_task(background_sync_loop())
        return _sync_task
    except Exception as e:
        logger.error("[BACKGROUND-SYNC] Failed to start background sync", error=str(e))
        return None


async def background_sync_loop():
    """
    Main background sync loop that runs periodically.
    
    Syncs Jira issues every 15 minutes to keep data fresh.
    """
    SYNC_INTERVAL = 15 * 60  # 15 minutes in seconds
    
    logger.info("[BACKGROUND-SYNC] Background sync loop started", interval_minutes=SYNC_INTERVAL/60)
    
    while True:
        try:
            await asyncio.sleep(SYNC_INTERVAL)
            
            logger.info("[BACKGROUND-SYNC] Running periodic Jira sync")
            await sync_all_jira_connections()
            
        except asyncio.CancelledError:
            logger.info("[BACKGROUND-SYNC] Background sync cancelled")
            break
        except Exception as e:
            logger.error("[BACKGROUND-SYNC] Error in sync loop", error=str(e))
            # Continue running even if one sync fails
            await asyncio.sleep(60)  # Wait 1 minute before retrying


async def sync_all_jira_connections():
    """
    Sync Jira issues for all active connections.
    
    This runs automatically to keep data fresh.
    """
    try:
        from backend.core.db import get_db
        from backend.services.org_ingestor import ingest_jira_for_user
        from sqlalchemy import text
        
        db = next(get_db())
        
        # Get all active Jira connections
        connections_query = """
            SELECT DISTINCT user_id, org_id 
            FROM jira_connection 
            WHERE access_token IS NOT NULL
        """
        connections = db.execute(text(connections_query)).fetchall()
        
        logger.info("[BACKGROUND-SYNC] Found Jira connections", count=len(connections))
        
        for conn in connections:
            user_id, org_id = conn
            try:
                logger.info("[BACKGROUND-SYNC] Syncing Jira for user", user_id=user_id, org_id=org_id)
                
                # Sync up to 50 issues for each user
                synced_keys = await ingest_jira_for_user(
                    db=db,
                    user_id=user_id,
                    max_issues=50
                )
                
                logger.info(
                    "[BACKGROUND-SYNC] Completed sync for user", 
                    user_id=user_id, 
                    synced_count=len(synced_keys)
                )
                
            except Exception as user_error:
                logger.error(
                    "[BACKGROUND-SYNC] Failed to sync for user",
                    user_id=user_id,
                    error=str(user_error)
                )
                # Continue with other users
                
        db.commit()
        
    except Exception as e:
        logger.error("[BACKGROUND-SYNC] Failed to sync Jira connections", error=str(e))


def stop_background_sync():
    """
    Stop the background sync task.
    """
    global _sync_task
    if _sync_task and not _sync_task.done():
        _sync_task.cancel()
        logger.info("[BACKGROUND-SYNC] Background sync stopped")