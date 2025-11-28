"""
NAVI Memory Service

This service manages NAVI's conversational memory system - storing and
retrieving memories for profile, workspace, task, and interaction contexts.

Originally this was written for PostgreSQL + pgvector. This version is
safe to run on SQLite in local/dev while still working on Postgres in prod.
"""

import os
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv
from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.orm import Session
import structlog

# Load environment variables
load_dotenv()

logger = structlog.get_logger(__name__)

# Global OpenAI client (lazy-initialized)
_openai_client: Optional[AsyncOpenAI] = None


def _get_openai_client() -> AsyncOpenAI:
    """Get or initialize OpenAI client lazily."""
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable must be set for embedding generation"
            )
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


async def generate_embedding(
    text_value: str, model: str = "text-embedding-ada-002"
) -> List[float]:
    """
    Generate OpenAI embedding for text.

    Args:
        text_value: Text to embed
        model: OpenAI embedding model

    Returns:
        List of floats representing the embedding vector
    """
    try:
        client = _get_openai_client()
        response = await client.embeddings.create(
            input=text_value,
            model=model,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(
            "Failed to generate embedding", error=str(e), text_length=len(text_value)
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

        # Convert embedding to a string representation.
        # On Postgres this is cast to vector, on SQLite it is just stored as TEXT.
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        # Prepare metadata as proper JSON string
        import json
        meta_json = tags or {}
        meta_json_str = json.dumps(meta_json)

        result = db.execute(
            text(
                """
                INSERT INTO navi_memory 
                    (user_id, category, scope, title, content, 
                     embedding_vec, meta_json, importance, created_at, updated_at)
                VALUES 
                    (:user_id, :category, :scope, :title, :content, 
                     :embedding_vec, :meta_json, :importance, 
                     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
            ),
            {
                "user_id": user_id,
                "category": category,
                "scope": scope,
                "title": title,
                "content": content,
                "embedding_vec": embedding_str,
                "meta_json": meta_json_str,
                "importance": importance,
            },
        )

        # On SQLite result.lastrowid is populated; on Postgres it's usually None
        memory_id = getattr(result, "lastrowid", None) or 0
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
    Semantic / text search for memories.

    On Postgres with pgvector we use real vector similarity.
    On SQLite (your local dev case) we fall back to a simple LIKE-based search
    over title/content but keep the same return shape.
    """
    try:
        bind = db.get_bind()
        dialect = getattr(getattr(bind, "dialect", None), "name", "sqlite") if bind else "sqlite"

        # ----------------- Category filter -----------------
        category_filter = ""
        category_params: Dict[str, Any] = {}
        if categories:
            placeholders = []
            for idx, cat in enumerate(categories):
                key = f"cat_{idx}"
                placeholders.append(f":{key}")
                category_params[key] = cat
            category_filter = f"AND category IN ({', '.join(placeholders)})"

        params: Dict[str, Any] = {
            "user_id": user_id,
            "min_importance": min_importance,
            "limit": limit,
            **category_params,
        }

        # ----------------- SQLite path -----------------
        if dialect == "sqlite":
            # Simple text search on title/content; no pgvector.
            params["like_query"] = f"%{query}%"

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
                        updated_at
                    FROM navi_memory
                    WHERE user_id = :user_id
                      AND importance >= :min_importance
                      {category_filter}
                      AND (
                           title   LIKE :like_query
                        OR content LIKE :like_query
                      )
                    ORDER BY created_at DESC
                    LIMIT :limit
                """
                ),
                params,
            )

            memories: List[Dict[str, Any]] = []
            for row in result:
                created_at = row[8]
                if hasattr(created_at, "isoformat"):
                    created_at = created_at.isoformat()
                else:
                    created_at = str(created_at) if created_at else None

                updated_at = row[9]
                if hasattr(updated_at, "isoformat"):
                    updated_at = updated_at.isoformat()
                else:
                    updated_at = str(updated_at) if updated_at else None

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
                        "created_at": created_at,
                        "updated_at": updated_at,
                        # We don't have real similarity on SQLite; use dummy 1.0
                        "similarity": 1.0,
                    }
                )

            logger.info(
                "Searched NAVI memory (sqlite fallback)",
                user_id=user_id,
                query_length=len(query),
                categories=categories,
                results=len(memories),
            )
            return memories

        # ----------------- Postgres + pgvector path -----------------
        # Generate embedding for query
        query_embedding = await generate_embedding(query)
        query_embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
        # Inline the vector literal to avoid driver-specific param casting issues
        query_vec_literal = f"'{query_embedding_str}'::vector"

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
                    1 - (embedding_vec <=> {query_vec_literal}) as similarity
                FROM navi_memory
                WHERE user_id = :user_id
                  AND importance >= :min_importance
                  {category_filter}
                ORDER BY embedding_vec <=> {query_vec_literal}
                LIMIT :limit
            """
            ),
            params,
        )

        memories: List[Dict[str, Any]] = []
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
    """
    try:
        category_filter = ""
        if category:
            category_filter = "AND category = :category"

        query_params: Dict[str, Any] = {
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

        memories: List[Dict[str, Any]] = []
        for row in result:
            created_at = row[8]
            if hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()
            else:
                created_at = str(created_at) if created_at else None

            updated_at = row[9]
            if hasattr(updated_at, "isoformat"):
                updated_at = updated_at.isoformat()
            else:
                updated_at = str(updated_at) if updated_at else None

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
                    "created_at": created_at,
                    "updated_at": updated_at,
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


def list_jira_tasks_for_user(
    db: Session,
    user_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Return recent Jira *task* memories for this user from NAVI memory.

    In dev you only have Jira ingest, so we intentionally **do not** filter on
    meta_json->'source' = 'jira' to avoid JSON / dialect issues. We simply
    take all memories with category = 'task' for this user.

    Args:
        db: Database session
        user_id: User identifier
        limit: Maximum number of tasks to return

    Returns:
        List of Jira task memory dictionaries
    """
    try:
        result = db.execute(
            text(
                """
                SELECT 
                    id, user_id, category, scope, title, content,
                    meta_json, importance, created_at, updated_at
                FROM navi_memory
                WHERE user_id = :user_id
                  AND category = 'task'
                ORDER BY updated_at DESC
                LIMIT :limit
            """
            ),
            {"user_id": user_id, "limit": limit},
        )

        tasks: List[Dict[str, Any]] = []
        for row in result:
            # created_at / updated_at may be datetime or string (SQLite)
            created_at = row[8]
            if hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()
            else:
                created_at = str(created_at) if created_at else None

            updated_at = row[9]
            if hasattr(updated_at, "isoformat"):
                updated_at = updated_at.isoformat()
            else:
                updated_at = str(updated_at) if updated_at else None

            tags = row[6]
            # meta_json is stored as str(dict) in dev; parse it if possible
            if isinstance(tags, str):
                try:
                    import ast

                    tags = ast.literal_eval(tags) if tags else {}
                except Exception:
                    tags = {}

            tasks.append(
                {
                    "id": row[0],
                    "user_id": row[1],
                    "category": row[2],
                    "scope": row[3],
                    "title": row[4],
                    "content": row[5],
                    "tags": tags,
                    "importance": row[7],
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )

        logger.info(
            "Listed Jira tasks from memory",
            user_id=user_id,
            task_count=len(tasks),
        )

        return tasks

    except Exception as e:
        logger.error("Failed to list Jira tasks", error=str(e), user_id=user_id)
        raise
