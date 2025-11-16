"""NAVI Memory Service

This service manages NAVI's conversational memory system - storing and
retrieving memories for profile, workspace, task, and interaction contexts.

Uses pgvector for semantic search with OpenAI embeddings.
"""

from typing import List, Dict, Any, Optional

from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.orm import Session
import structlog

logger = structlog.get_logger(__name__)

# Initialize OpenAI client for embeddings
openai_client = AsyncOpenAI()


async def generate_embedding(
    text: str, model: str = "text-embedding-3-large"
) -> List[float]:
    """
    Generate OpenAI embedding for text.

    Args:
        text: Text to embed
        model: OpenAI embedding model

    Returns:
        List of floats representing the embedding vector
    """
    try:
        response = await openai_client.embeddings.create(
            input=text,
            model=model,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(
            "Failed to generate embedding", error=str(e), text_length=len(text)
        )
        raise


async def store_memory(
    db: Session,
    user_id: str,
    category: str,
    content: str,
    scope: Optional[str] = None,
    title: Optional[str] = None,
    tags: Optional[Dict[str, Any]] = None,
    importance: int = 3,
) -> int:
    """
    Store a memory in the navi_memory table.

    Args:
        db: Database session
        user_id: User identifier
        category: Memory category (profile|workspace|task|interaction)
        content: Human-readable memory content
        scope: Optional scope identifier (workspace path, task ID, etc.)
        title: Optional human-readable title
        tags: Optional metadata dictionary
        importance: Importance score 1-5 (default: 3)

    Returns:
        ID of the created memory
    """
    try:
        # Generate embedding
        embedding = await generate_embedding(content)

        # Convert embedding to PostgreSQL vector format
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # Prepare metadata
        meta_json = tags or {}

        # Insert memory
        result = db.execute(
            text(
                """
                INSERT INTO navi_memory 
                (user_id, category, scope, title, content, embedding_vec, meta_json, importance, created_at, updated_at)
                VALUES 
                (:user_id, :category, :scope, :title, :content, :embedding_vec::vector, :meta_json::json, :importance, now(), now())
                RETURNING id
            """
            ),
            {
                "user_id": user_id,
                "category": category,
                "scope": scope,
                "title": title,
                "content": content,
                "embedding_vec": embedding_str,
                "meta_json": str(meta_json),
                "importance": importance,
            },
        )

        row = result.fetchone()
        if not row:
            raise RuntimeError("Failed to insert memory: no ID returned")
        memory_id = row[0]
        db.commit()

        logger.info(
            "Stored NAVI memory",
            memory_id=memory_id,
            user_id=user_id,
            category=category,
            scope=scope,
            importance=importance,
        )

        return memory_id

    except Exception as e:
        db.rollback()
        logger.error(
            "Failed to store memory", error=str(e), user_id=user_id, category=category
        )
        raise


async def search_memory(
    db: Session,
    user_id: str,
    query: str,
    categories: Optional[List[str]] = None,
    limit: int = 10,
    min_importance: int = 1,
) -> List[Dict[str, Any]]:
    """
    Semantic search for memories using cosine similarity.

    Args:
        db: Database session
        user_id: User identifier
        query: Search query text
        categories: Optional list of categories to filter (e.g., ["task", "workspace"])
        limit: Maximum number of results
        min_importance: Minimum importance score to include

    Returns:
        List of memory dictionaries with similarity scores
    """
    try:
        # Generate embedding for query
        query_embedding = await generate_embedding(query)
        query_embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Build category filter
        category_filter = ""
        if categories:
            category_list = "','".join(categories)
            category_filter = f"AND category IN ('{category_list}')"

        # Search using pgvector cosine similarity
        result = db.execute(
            text(
                f"""
                SELECT 
                    id,
                    user_id,
                    category,
                    scope,
                    title,
                    content,
                    meta_json,
                    importance,
                    created_at,
                    updated_at,
                    1 - (embedding_vec <=> :query_vec::vector) as similarity
                FROM navi_memory
                WHERE user_id = :user_id
                  AND importance >= :min_importance
                  {category_filter}
                ORDER BY embedding_vec <=> :query_vec::vector
                LIMIT :limit
            """
            ),
            {
                "user_id": user_id,
                "query_vec": query_embedding_str,
                "min_importance": min_importance,
                "limit": limit,
            },
        )

        memories = []
        for row in result:
            memories.append(
                {
                    "id": row[0],
                    "user_id": row[1],
                    "category": row[2],
                    "scope": row[3],
                    "title": row[4],
                    "content": row[5],
                    "meta": row[6],
                    "importance": row[7],
                    "created_at": row[8].isoformat() if row[8] else None,
                    "updated_at": row[9].isoformat() if row[9] else None,
                    "similarity": float(row[10]),
                }
            )

        logger.info(
            "Searched NAVI memory",
            user_id=user_id,
            query_length=len(query),
            categories=categories,
            results=len(memories),
        )

        return memories

    except Exception as e:
        logger.error("Failed to search memory", error=str(e), user_id=user_id)
        raise


async def get_recent_memories(
    db: Session,
    user_id: str,
    category: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Get recent memories ordered by creation time.

    Args:
        db: Database session
        user_id: User identifier
        category: Optional category filter
        limit: Maximum number of results

    Returns:
        List of memory dictionaries
    """
    try:
        category_filter = ""
        if category:
            category_filter = "AND category = :category"

        query_params = {
            "user_id": user_id,
            "limit": limit,
        }
        if category:
            query_params["category"] = category

        result = db.execute(
            text(
                f"""
                SELECT 
                    id, user_id, category, scope, title, content, 
                    meta_json, importance, created_at, updated_at
                FROM navi_memory
                WHERE user_id = :user_id
                  {category_filter}
                ORDER BY created_at DESC
                LIMIT :limit
            """
            ),
            query_params,
        )

        memories = []
        for row in result:
            memories.append(
                {
                    "id": row[0],
                    "user_id": row[1],
                    "category": row[2],
                    "scope": row[3],
                    "title": row[4],
                    "content": row[5],
                    "meta": row[6],
                    "importance": row[7],
                    "created_at": row[8].isoformat() if row[8] else None,
                    "updated_at": row[9].isoformat() if row[9] else None,
                }
            )

        logger.info(
            "Retrieved recent memories",
            user_id=user_id,
            category=category,
            results=len(memories),
        )

        return memories

    except Exception as e:
        logger.error("Failed to get recent memories", error=str(e), user_id=user_id)
        raise


async def delete_memory(db: Session, memory_id: int, user_id: str) -> bool:
    """
    Delete a memory (with user_id verification).

    Args:
        db: Database session
        memory_id: Memory ID to delete
        user_id: User identifier (for authorization)

    Returns:
        True if deleted, False if not found or unauthorized
    """
    try:
        result = db.execute(
            text(
                """
                DELETE FROM navi_memory
                WHERE id = :memory_id AND user_id = :user_id
                RETURNING id
            """
            ),
            {"memory_id": memory_id, "user_id": user_id},
        )

        deleted = result.fetchone() is not None
        db.commit()

        if deleted:
            logger.info("Deleted memory", memory_id=memory_id, user_id=user_id)
        else:
            logger.warning(
                "Memory not found or unauthorized", memory_id=memory_id, user_id=user_id
            )

        return deleted

    except Exception as e:
        db.rollback()
        logger.error("Failed to delete memory", error=str(e), memory_id=memory_id)
        raise
