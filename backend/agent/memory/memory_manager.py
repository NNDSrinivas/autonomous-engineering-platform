"""
Memory Management System

Manages memory lifecycle: pruning old memories, merging duplicates, optimizing storage.
This keeps NAVI's memory efficient and relevant.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .memory_types import (
    MemoryEntry,
    MemoryType,
    should_prune_memory
)

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Memory lifecycle manager for pruning, merging, and optimization.
    """
    
    def __init__(self, db_session):
        """
        Initialize memory manager.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
    
    async def run_maintenance(self, user_id: Optional[str] = None) -> Dict[str, int]:
        """
        Run full memory maintenance cycle.
        
        Args:
            user_id: Optional user ID to limit maintenance scope
            
        Returns:
            Stats about maintenance operations
        """
        stats = {
            "pruned": 0,
            "merged": 0,
            "reindexed": 0
        }
        
        try:
            # Step 1: Prune old memories
            pruned = await prune_old_memories(user_id=user_id, db_session=self.db)
            stats["pruned"] = pruned
            
            # Step 2: Merge similar memories
            merged = await merge_similar_memories(user_id=user_id, db_session=self.db)
            stats["merged"] = merged
            
            # Step 3: Optimize storage
            await optimize_memory_store(db_session=self.db)
            stats["reindexed"] = 1
            
            logger.info(f"Memory maintenance complete: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error in memory maintenance: {e}", exc_info=True)
            return stats


async def prune_old_memories(
    user_id: Optional[str] = None,
    db_session = None
) -> int:
    """
    Remove old, unused, or low-value memories.
    
    Pruning rules:
    - Never prune conversational memories (user preferences)
    - Prune if not accessed in 90+ days AND access_count = 0
    - Prune if importance < 0.3 AND not accessed in 60+ days
    - Prune if confidence < 0.3
    
    Examples:
        pruned_count = await prune_old_memories(user_id="user@example.com")
        print(f"Pruned {pruned_count} old memories")
    
    Args:
        user_id: Optional user ID to limit scope
        db_session: Database session
        
    Returns:
        Number of memories pruned
    """
    
    try:
        # Fetch all memories for pruning evaluation
        # query = "SELECT * FROM navi_memory"
        # if user_id:
        #     query += f" WHERE user_id = '{user_id}'"
        # memories = await db_session.fetch_all(query)
        
        # Placeholder - will integrate with actual database
        memories: List[MemoryEntry] = []
        
        pruned_count = 0
        for memory in memories:
            if should_prune_memory(memory):
                # Delete from database
                # await db_session.execute(
                #     "DELETE FROM navi_memory WHERE id = $1", memory.id
                # )
                pruned_count += 1
                logger.debug(f"Pruned memory {memory.id}: {memory.content[:50]}...")
        
        logger.info(f"Pruned {pruned_count} memories")
        return pruned_count
        
    except Exception as e:
        logger.error(f"Error pruning memories: {e}", exc_info=True)
        return 0


async def merge_similar_memories(
    user_id: Optional[str] = None,
    similarity_threshold: float = 0.95,
    db_session = None
) -> int:
    """
    Merge duplicate or very similar memories.
    
    Uses vector similarity to find duplicates and merges them:
    - Keeps the memory with higher importance
    - Combines access counts
    - Merges metadata
    
    Examples:
        merged_count = await merge_similar_memories(
            user_id="user@example.com",
            similarity_threshold=0.95
        )
        print(f"Merged {merged_count} duplicate memories")
    
    Args:
        user_id: Optional user ID to limit scope
        similarity_threshold: Cosine similarity threshold (0-1)
        db_session: Database session
        
    Returns:
        Number of memories merged
    """
    
    try:
        # Find similar memory pairs using vector similarity
        # query = """
        #     SELECT m1.id as id1, m2.id as id2, 
        #            m1.embedding <-> m2.embedding as distance
        #     FROM navi_memory m1, navi_memory m2
        #     WHERE m1.id < m2.id
        #       AND m1.user_id = m2.user_id
        #       AND m1.memory_type = m2.memory_type
        #       AND m1.embedding <-> m2.embedding < $1
        # """
        # if user_id:
        #     query += f" AND m1.user_id = '{user_id}'"
        # 
        # similar_pairs = await db_session.fetch_all(
        #     query, 1.0 - similarity_threshold
        # )
        
        # Placeholder
        similar_pairs = []
        
        merged_count = 0
        for pair in similar_pairs:
            # Fetch full memory objects
            # memory1 = await _get_memory(pair["id1"], db_session)
            # memory2 = await _get_memory(pair["id2"], db_session)
            
            # Merge: keep higher importance, combine counts
            # merged = _merge_memory_pair(memory1, memory2)
            
            # Update database
            # await db_session.execute("UPDATE navi_memory SET ... WHERE id = $1", merged.id)
            # await db_session.execute("DELETE FROM navi_memory WHERE id = $1", other_id)
            
            merged_count += 1
        
        logger.info(f"Merged {merged_count} similar memories")
        return merged_count
        
    except Exception as e:
        logger.error(f"Error merging memories: {e}", exc_info=True)
        return 0


async def optimize_memory_store(db_session = None) -> bool:
    """
    Optimize memory storage and indexes.
    
    - Rebuild vector indexes
    - Analyze tables for query optimization
    - Vacuum deleted records
    
    Examples:
        await optimize_memory_store()
    
    Args:
        db_session: Database session
        
    Returns:
        True if successful
    """
    
    try:
        # Reindex vector embeddings for faster search
        # await db_session.execute("REINDEX INDEX navi_memory_embedding_idx")
        
        # Analyze tables
        # await db_session.execute("ANALYZE navi_memory")
        
        # Vacuum (cleanup deleted records)
        # await db_session.execute("VACUUM navi_memory")
        
        logger.info("Memory store optimized")
        return True
        
    except Exception as e:
        logger.error(f"Error optimizing memory store: {e}", exc_info=True)
        return False


async def get_memory_stats(
    user_id: Optional[str] = None,
    db_session = None
) -> Dict[str, Any]:
    """
    Get statistics about memory usage.
    
    Examples:
        stats = await get_memory_stats(user_id="user@example.com")
        # Returns:
        # {
        #   "total_memories": 1250,
        #   "by_type": {
        #     "conversational": 300,
        #     "workspace": 450,
        #     "organizational": 350,
        #     "task": 150
        #   },
        #   "avg_importance": 0.65,
        #   "oldest_memory": "2024-01-15",
        #   "most_accessed": {...}
        # }
    
    Args:
        user_id: Optional user ID to limit scope
        db_session: Database session
        
    Returns:
        Dictionary of memory statistics
    """
    
    stats = {
        "total_memories": 0,
        "by_type": {},
        "avg_importance": 0.0,
        "oldest_memory": None,
        "most_accessed": None
    }
    
    try:
        
        # Count total memories
        # query = "SELECT COUNT(*) FROM navi_memory"
        # if user_id:
        #     query += f" WHERE user_id = '{user_id}'"
        # stats["total_memories"] = await db_session.fetch_val(query)
        
        # Count by type
        # for memory_type in MemoryType:
        #     query = f"SELECT COUNT(*) FROM navi_memory WHERE memory_type = '{memory_type.value}'"
        #     if user_id:
        #         query += f" AND user_id = '{user_id}'"
        #     stats["by_type"][memory_type.value] = await db_session.fetch_val(query)
        
        # Average importance
        # query = "SELECT AVG(importance) FROM navi_memory"
        # if user_id:
        #     query += f" WHERE user_id = '{user_id}'"
        # stats["avg_importance"] = await db_session.fetch_val(query) or 0.0
        
        # Oldest memory
        # query = "SELECT MIN(created_at) FROM navi_memory"
        # if user_id:
        #     query += f" WHERE user_id = '{user_id}'"
        # oldest = await db_session.fetch_val(query)
        # stats["oldest_memory"] = oldest.isoformat() if oldest else None
        
        # Most accessed memory
        # query = "SELECT * FROM navi_memory ORDER BY access_count DESC LIMIT 1"
        # if user_id:
        #     query = query.replace("FROM", f"FROM WHERE user_id = '{user_id}'")
        # most_accessed = await db_session.fetch_one(query)
        # stats["most_accessed"] = most_accessed
        
        logger.info(f"Memory stats: {stats['total_memories']} total memories")
        return stats
        
    except Exception as e:
        logger.error(f"Error getting memory stats: {e}", exc_info=True)
        return stats


async def archive_old_memories(
    user_id: Optional[str] = None,
    days_old: int = 180,
    db_session = None
) -> int:
    """
    Archive very old memories to cold storage.
    
    Instead of deleting, move to archive table for potential future retrieval.
    
    Examples:
        archived = await archive_old_memories(
            user_id="user@example.com",
            days_old=180
        )
    
    Args:
        user_id: Optional user ID to limit scope
        days_old: Archive memories older than this many days
        db_session: Database session
        
    Returns:
        Number of memories archived
    """
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Move to archive table
        # query = """
        #     INSERT INTO navi_memory_archive 
        #     SELECT * FROM navi_memory 
        #     WHERE created_at < $1
        #       AND memory_type != 'conversational'
        # """
        # if user_id:
        #     query += f" AND user_id = '{user_id}'"
        # 
        # result = await db_session.execute(query, cutoff_date)
        # archived_count = result.rowcount
        
        # Delete from main table
        # await db_session.execute(
        #     "DELETE FROM navi_memory WHERE created_at < $1 AND memory_type != 'conversational'",
        #     cutoff_date
        # )
        
        archived_count = 0  # Placeholder
        
        logger.info(f"Archived {archived_count} old memories")
        return archived_count
        
    except Exception as e:
        logger.error(f"Error archiving memories: {e}", exc_info=True)
        return 0


def _merge_memory_pair(memory1: MemoryEntry, memory2: MemoryEntry) -> MemoryEntry:
    """
    Merge two similar memories into one.
    
    Strategy:
    - Keep memory with higher importance
    - Combine access counts
    - Merge tags
    - Keep most recent timestamp
    
    Args:
        memory1: First memory
        memory2: Second memory
        
    Returns:
        Merged memory
    """
    from copy import deepcopy
    
    # Choose primary memory (higher importance)
    if memory1.importance >= memory2.importance:
        primary = deepcopy(memory1)
        secondary = memory2
    else:
        primary = deepcopy(memory2)
        secondary = memory1
    
    # Merge access counts
    primary.access_count += secondary.access_count
    
    # Merge tags
    primary.tags = list(set(primary.tags + secondary.tags))
    
    # Update timestamp to most recent
    if secondary.updated_at > primary.updated_at:
        primary.updated_at = secondary.updated_at
    
    # Average confidence
    primary.confidence = (primary.confidence + secondary.confidence) / 2
    
    return primary
