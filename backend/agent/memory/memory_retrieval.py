"""
Memory Retrieval System

Retrieves relevant memories using vector similarity search.
This is how NAVI remembers context and personalizes responses.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .memory_types import (
    MemoryEntry,
    MemoryType,
    MemoryCategory,
    ConversationalMemory,
    WorkspaceMemory,
    OrganizationalMemory,
    TaskMemory
)

logger = logging.getLogger(__name__)


class MemoryRetrieval:
    """
    Memory retrieval engine using vector similarity search.
    """
    
    def __init__(self, db_session):
        """
        Initialize memory retrieval.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
    
    async def _vector_search(
        self,
        query_embedding: List[float],
        memory_type: Optional[MemoryType] = None,
        category: Optional[MemoryCategory] = None,
        user_id: Optional[str] = None,
        limit: int = 15
    ) -> List[MemoryEntry]:
        """
        Perform vector similarity search.
        
        Args:
            query_embedding: Query vector
            memory_type: Optional filter by memory type
            category: Optional filter by category
            user_id: Optional filter by user
            limit: Maximum results
            
        Returns:
            List of relevant memories
        """
        # Pseudo-code for vector search with pgvector
        # query = "SELECT * FROM navi_memory WHERE "
        # filters = []
        # if memory_type:
        #     filters.append(f"memory_type = '{memory_type.value}'")
        # if category:
        #     filters.append(f"category = '{category.value}'")
        # if user_id:
        #     filters.append(f"user_id = '{user_id}'")
        # 
        # if filters:
        #     query += " AND ".join(filters) + " "
        # 
        # query += f"ORDER BY embedding <-> '{query_embedding}' LIMIT {limit}"
        # 
        # results = await self.db.fetch_all(query)
        # return [self._parse_memory_entry(row) for row in results]
        
        # TODO: Implement vector search with pgvector once database is ready
        # For now, returning empty list - memory retrieval will be populated in future
        return []
    
    async def _generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for query."""
        # Placeholder - integrate with OpenAI embeddings
        return [0.0] * 1536
    
    def _parse_memory_entry(self, row: Dict[str, Any]) -> MemoryEntry:
        """Parse database row into appropriate memory type."""
        memory_type = MemoryType(row["memory_type"])
        
        if memory_type == MemoryType.CONVERSATIONAL:
            return ConversationalMemory(**row)
        elif memory_type == MemoryType.WORKSPACE:
            return WorkspaceMemory(**row)
        elif memory_type == MemoryType.ORGANIZATIONAL:
            return OrganizationalMemory(**row)
        elif memory_type == MemoryType.TASK:
            return TaskMemory(**row)
        else:
            return MemoryEntry(**row)


async def retrieve_user_memories(
    user_id: str,
    query: str,
    limit: int = 10,
    db_session = None
) -> List[ConversationalMemory]:
    """
    Retrieve user preferences and coding style memories.
    
    Examples:
        memories = await retrieve_user_memories(
            user_id="user@example.com",
            query="How does this user prefer to handle errors?"
        )
        
        for memory in memories:
            print(f"{memory.preference_key}: {memory.preference_value}")
    
    Args:
        user_id: User ID
        query: Natural language query
        limit: Max results
        db_session: Database session
        
    Returns:
        List of conversational memories
    """
    
    retrieval = MemoryRetrieval(db_session)
    query_embedding = await retrieval._generate_query_embedding(query)
    
    memories = await retrieval._vector_search(
        query_embedding=query_embedding,
        memory_type=MemoryType.CONVERSATIONAL,
        user_id=user_id,
        limit=limit
    )
    
    # Update access tracking and cast to proper type
    result = []
    for memory in memories:
        memory.update_access()
        if isinstance(memory, ConversationalMemory):
            result.append(memory)
        # Save updated access info to DB
    
    return result


async def retrieve_workspace_memories(
    user_id: str,
    query: str,
    file_path: Optional[str] = None,
    limit: int = 10,
    db_session = None
) -> List[WorkspaceMemory]:
    """
    Retrieve workspace patterns and architecture memories.
    
    Examples:
        memories = await retrieve_workspace_memories(
            user_id="user@example.com",
            query="authentication patterns in this codebase",
            file_path="backend/auth/"
        )
    
    Args:
        user_id: User ID
        query: Natural language query
        file_path: Optional file/folder filter
        limit: Max results
        db_session: Database session
        
    Returns:
        List of workspace memories
    """
    
    retrieval = MemoryRetrieval(db_session)
    
    # Add file path to query for better matching
    search_query = query
    if file_path:
        search_query = f"{query} in {file_path}"
    
    query_embedding = await retrieval._generate_query_embedding(search_query)
    
    memories = await retrieval._vector_search(
        query_embedding=query_embedding,
        memory_type=MemoryType.WORKSPACE,
        user_id=user_id,
        limit=limit
    )
    
    # Filter and cast to proper type
    result = []
    for memory in memories:
        if isinstance(memory, WorkspaceMemory):
            # Filter by file path if specified
            if file_path:
                if memory.file_path and file_path in memory.file_path:
                    result.append(memory)
            else:
                result.append(memory)
            memory.update_access()
    
    return result


async def retrieve_org_memories(
    user_id: str,
    query: str,
    org_system: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 10,
    db_session = None
) -> List[OrganizationalMemory]:
    """
    Retrieve organizational context from Jira, Slack, etc.
    
    Examples:
        # Find recent Slack discussions about authentication
        memories = await retrieve_org_memories(
            user_id="user@example.com",
            query="authentication discussion",
            org_system="slack",
            since=datetime.now() - timedelta(days=30)
        )
    
    Args:
        user_id: User ID
        query: Natural language query
        org_system: Optional filter (jira, slack, confluence, etc.)
        since: Optional time filter
        limit: Max results
        db_session: Database session
        
    Returns:
        List of organizational memories
    """
    
    retrieval = MemoryRetrieval(db_session)
    query_embedding = await retrieval._generate_query_embedding(query)
    
    memories = await retrieval._vector_search(
        query_embedding=query_embedding,
        memory_type=MemoryType.ORGANIZATIONAL,
        user_id=user_id,
        limit=limit * 2  # Get more for filtering
    )
    
    # Apply filters and cast to proper type
    result = []
    for memory in memories:
        if isinstance(memory, OrganizationalMemory):
            # Apply org_system filter
            if org_system and memory.org_system != org_system:
                continue
            # Apply time filter
            if since and memory.created_at < since:
                continue
            result.append(memory)
    
    # Sort by relevance and recency
    result = sorted(
        result[:limit],
        key=lambda m: (m.importance, m.created_at),
        reverse=True
    )
    
    # Update access tracking
    for memory in result:
        memory.update_access()
    
    return result


async def retrieve_task_memories(
    user_id: str,
    task_id: Optional[str] = None,
    query: Optional[str] = None,
    approved_only: bool = False,
    limit: int = 10,
    db_session = None
) -> List[TaskMemory]:
    """
    Retrieve task execution history.
    
    Examples:
        # Get approved changes for a specific task
        memories = await retrieve_task_memories(
            user_id="user@example.com",
            task_id="SCRUM-123",
            approved_only=True
        )
        
        # Find similar past executions
        memories = await retrieve_task_memories(
            user_id="user@example.com",
            query="adding null checks to API endpoints"
        )
    
    Args:
        user_id: User ID
        task_id: Optional specific task
        query: Optional search query
        approved_only: Only return user-approved actions
        limit: Max results
        db_session: Database session
        
    Returns:
        List of task memories
    """
    
    retrieval = MemoryRetrieval(db_session)
    
    # If searching by task_id, use exact match
    if task_id:
        # Direct query by task_id
        # results = await db_session.fetch_all(
        #     "SELECT * FROM navi_memory WHERE task_id = $1", task_id
        # )
        memories = []  # Placeholder
    else:
        # Vector search
        if query:
            query_embedding = await retrieval._generate_query_embedding(query)
            memories = await retrieval._vector_search(
                query_embedding=query_embedding,
                memory_type=MemoryType.TASK,
                user_id=user_id,
                limit=limit
            )
        else:
            memories = []
    
    # Filter and cast to proper type
    result = []
    for memory in memories:
        if isinstance(memory, TaskMemory):
            # Filter approved only if requested
            if approved_only and not memory.user_approved:
                continue
            result.append(memory)
            memory.update_access()
    
    return result


async def retrieve_relevant_context(
    user_id: str,
    query: str,
    include_types: Optional[List[MemoryType]] = None,
    limit_per_type: int = 5,
    db_session = None
) -> Dict[str, List[MemoryEntry]]:
    """
    Unified retrieval across all memory types.
    
    This is the main function used by the agent loop to gather context.
    
    Examples:
        context = await retrieve_relevant_context(
            user_id="user@example.com",
            query="implement authentication for the API"
        )
        
        # Returns:
        # {
        #   "conversational": [memory1, memory2],  # User preferences
        #   "workspace": [memory3, memory4],       # Code patterns
        #   "organizational": [memory5],           # Related Jira/Slack
        #   "task": [memory6]                      # Past similar tasks
        # }
    
    Args:
        user_id: User ID
        query: User's message/request
        include_types: Optional list of memory types to include
        limit_per_type: Max results per type
        db_session: Database session
        
    Returns:
        Dictionary mapping memory type to relevant memories
    """
    
    if include_types is None:
        include_types = [
            MemoryType.CONVERSATIONAL,
            MemoryType.WORKSPACE,
            MemoryType.ORGANIZATIONAL,
            MemoryType.TASK
        ]
    
    context = {}
    
    # Retrieve from each memory type
    if MemoryType.CONVERSATIONAL in include_types:
        context["conversational"] = await retrieve_user_memories(
            user_id=user_id,
            query=query,
            limit=limit_per_type,
            db_session=db_session
        )
    
    if MemoryType.WORKSPACE in include_types:
        context["workspace"] = await retrieve_workspace_memories(
            user_id=user_id,
            query=query,
            limit=limit_per_type,
            db_session=db_session
        )
    
    if MemoryType.ORGANIZATIONAL in include_types:
        context["organizational"] = await retrieve_org_memories(
            user_id=user_id,
            query=query,
            limit=limit_per_type,
            db_session=db_session
        )
    
    if MemoryType.TASK in include_types:
        context["task"] = await retrieve_task_memories(
            user_id=user_id,
            query=query,
            limit=limit_per_type,
            db_session=db_session
        )
    
    # Log context summary
    total_memories = sum(len(memories) for memories in context.values())
    logger.info(f"Retrieved {total_memories} relevant memories for query: {query[:50]}...")
    
    return context


async def format_context_for_llm(
    context: Dict[str, List[MemoryEntry]],
    max_length: int = 2000
) -> str:
    """
    Format retrieved memories into a context string for the LLM.
    
    Args:
        context: Dictionary of memories by type
        max_length: Maximum character length
        
    Returns:
        Formatted context string
    """
    
    sections = []
    
    # User preferences
    if context.get("conversational"):
        prefs = []
        for memory in context["conversational"][:3]:  # Top 3
            if isinstance(memory, ConversationalMemory):
                prefs.append(f"- {memory.preference_key}: {memory.preference_value}")
        if prefs:
            sections.append("User Preferences:\n" + "\n".join(prefs))
    
    # Workspace patterns
    if context.get("workspace"):
        patterns = []
        for memory in context["workspace"][:3]:
            if isinstance(memory, WorkspaceMemory):
                patterns.append(f"- {memory.pattern_type}: {memory.content[:100]}")
        if patterns:
            sections.append("Code Patterns:\n" + "\n".join(patterns))
    
    # Organizational context
    if context.get("organizational"):
        org = []
        for memory in context["organizational"][:2]:
            if isinstance(memory, OrganizationalMemory):
                org.append(f"- [{memory.org_system}] {memory.content[:100]}")
        if org:
            sections.append("Related Context:\n" + "\n".join(org))
    
    # Task history
    if context.get("task"):
        tasks = []
        for memory in context["task"][:2]:
            if isinstance(memory, TaskMemory):
                approval = "✓" if memory.user_approved else "✗"
                action_preview = memory.action_taken[:80] if memory.action_taken else ""
                tasks.append(f"- {approval} {memory.step}: {action_preview}")
        if tasks:
            sections.append("Similar Past Actions:\n" + "\n".join(tasks))
    
    # Combine sections
    formatted = "\n\n".join(sections)
    
    # Truncate if too long
    if len(formatted) > max_length:
        formatted = formatted[:max_length] + "..."
    
    return formatted
