"""
Long-Term Memory Layer for Navi

This gives Navi persistent project awareness across all chats, sprints, repos, PRs.
Stores and retrieves memories such as:
- Architecture decisions and rationale
- API contracts and breaking changes
- Key business rules and constraints
- Technical debt patterns and solutions
- Recurring bugs and their fixes
- Knowledge of preferred coding styles
- Known unsafe patterns in codebase
- User-specific preferences and workflows
- Historical performance data
- Team dynamics and expertise areas
"""

import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

try:
    from ..services.llm_router import LLMRouter
    from ..services.database_service import DatabaseService
    from ..memory.vector_store import VectorStore
    from ..core.config import get_settings
except ImportError:
    from backend.services.llm_router import LLMRouter
    from backend.services.database_service import DatabaseService
    from backend.memory.vector_store import VectorStore
    from backend.core.config import get_settings


class MemoryType(Enum):
    """Types of memories Navi can store."""

    ARCHITECTURE_DECISION = "architecture_decision"
    API_CONTRACT = "api_contract"
    BUSINESS_RULE = "business_rule"
    TECHNICAL_DEBT = "technical_debt"
    BUG_PATTERN = "bug_pattern"
    CODING_STYLE = "coding_style"
    UNSAFE_PATTERN = "unsafe_pattern"
    USER_PREFERENCE = "user_preference"
    TEAM_KNOWLEDGE = "team_knowledge"
    PERFORMANCE_INSIGHT = "performance_insight"
    PROCESS_LEARNING = "process_learning"
    TOOLING_CONFIG = "tooling_config"
    VALIDATION_RESULT = "validation_result"
    ROLLOUT_EXECUTION = "rollout_execution"
    COMPLIANCE_REPORT = "compliance_report"
    REASONING_GRAPH = "reasoning_graph"
    ROLLBACK_EXECUTION = "rollback_execution"
    ACTION_TRACE = "action_trace"
    VERIFICATION_SESSION = "verification_session"
    SKILL_EXECUTION = "skill_execution"


class MemoryImportance(Enum):
    """Importance levels for memory prioritization."""

    CRITICAL = 1  # Core architectural decisions, security patterns
    HIGH = 2  # Important business rules, major technical debt
    MEDIUM = 3  # Coding preferences, minor patterns
    LOW = 4  # Temporary insights, experimental findings
    ARCHIVE = 5  # Historical data for reference


@dataclass
class Memory:
    """Individual memory item."""

    id: str
    memory_type: MemoryType
    title: str
    content: str
    importance: MemoryImportance
    tags: List[str]
    related_files: List[str]
    related_memories: List[str]
    context: Dict[str, Any]
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    confidence_score: float = 1.0
    user_id: Optional[str] = None
    team_id: Optional[str] = None

    def __post_init__(self):
        if not self.tags:
            self.tags = []
        if not self.related_files:
            self.related_files = []
        if not self.related_memories:
            self.related_memories = []
        if not self.context:
            self.context = {}


@dataclass
class MemoryQuery:
    """Query for memory retrieval."""

    query_text: str
    memory_types: Optional[List[MemoryType]] = None
    tags: Optional[List[str]] = None
    importance_threshold: Optional[MemoryImportance] = None
    recency_bias: bool = True
    max_results: int = 10
    user_id: Optional[str] = None
    team_id: Optional[str] = None


@dataclass
class MemoryInsight:
    """Generated insight from memory analysis."""

    insight_type: str
    title: str
    description: str
    supporting_memories: List[str]
    confidence: float
    actionable_recommendations: List[str]


class MemoryLayer:
    """
    Long-term memory system that gives Navi persistent project awareness.
    Stores, retrieves, and synthesizes knowledge across engineering contexts.
    """

    def __init__(self):
        """Initialize the Memory Layer."""
        self.llm = LLMRouter()
        self.db = DatabaseService()
        self.vector_store = VectorStore()
        self.settings = get_settings()

        # Memory management parameters
        self.max_memories_per_type = 1000
        self.memory_decay_days = 180
        self.similarity_threshold = 0.7
        self.consolidation_batch_size = 50

    async def store_memory(
        self,
        memory_type: MemoryType,
        title: str,
        content: str,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        tags: Optional[List[str]] = None,
        related_files: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        team_id: Optional[str] = None,
    ) -> Memory:
        """
        Store a new memory with intelligent processing.

        Args:
            memory_type: Type of memory being stored
            title: Brief title for the memory
            content: Detailed content
            importance: Importance level for prioritization
            tags: Relevant tags for categorization
            related_files: Files associated with this memory
            context: Additional context metadata
            user_id: User who created the memory
            team_id: Team associated with the memory

        Returns:
            Created memory object
        """

        # Generate unique ID
        memory_id = hashlib.md5(
            f"{title}_{content}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        # Check for similar existing memories
        similar_memories = await self._find_similar_memories(content, memory_type)

        if similar_memories:
            # Consolidate with existing memory
            return await self._consolidate_memories(
                similar_memories[0],
                {
                    "title": title,
                    "content": content,
                    "importance": importance,
                    "tags": tags or [],
                    "related_files": related_files or [],
                    "context": context or {},
                },
            )

        # Enhance memory with AI analysis
        enhanced_memory = await self._enhance_memory_content(
            memory_type, title, content, tags or [], context or {}
        )

        # Create memory object
        memory = Memory(
            id=memory_id,
            memory_type=memory_type,
            title=enhanced_memory.get("title", title),
            content=enhanced_memory.get("content", content),
            importance=importance,
            tags=enhanced_memory.get("tags", tags or []),
            related_files=related_files or [],
            related_memories=[],
            context=enhanced_memory.get("context", context or {}),
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            user_id=user_id,
            team_id=team_id,
        )

        # Find related memories
        memory.related_memories = await self._find_related_memories(memory)

        # Store in database
        await self._save_memory(memory)

        # Store in vector store for similarity search
        self.vector_store.add(
            text=f"{title} {content}",
            metadata={
                "memory_id": memory_id,
                "memory_type": memory_type.value,
                "importance": importance.value,
                "tags": tags or [],
                "user_id": user_id,
                "team_id": team_id,
            },
        )

        return memory

    async def recall_memories(self, query: MemoryQuery) -> List[Tuple[Memory, float]]:
        """
        Recall relevant memories based on query.

        Args:
            query: Memory query with search criteria

        Returns:
            List of (memory, relevance_score) tuples sorted by relevance
        """

        # Perform vector similarity search
        similar_docs = self.vector_store.search(
            query=query.query_text,
            k=query.max_results * 2,  # Get more candidates for filtering
            filters={
                "memory_type": (
                    [mt.value for mt in query.memory_types]
                    if query.memory_types
                    else None
                ),
                "user_id": query.user_id,
                "team_id": query.team_id,
            },
        )

        # Load full memory objects
        memories_with_scores = []
        for doc in similar_docs:
            memory = await self._load_memory(doc["id"])
            if memory:
                # Apply additional filters
                if self._passes_query_filters(memory, query):
                    # Calculate combined relevance score
                    relevance_score = self._calculate_relevance_score(
                        memory, query, doc["similarity"]
                    )
                    memories_with_scores.append((memory, relevance_score))

                    # Update access statistics
                    memory.access_count += 1
                    memory.last_accessed = datetime.now()
                    await self._update_memory_access(memory)

        # Sort by relevance score
        memories_with_scores.sort(key=lambda x: x[1], reverse=True)

        return memories_with_scores[: query.max_results]

    async def generate_insights(
        self,
        context: str,
        focus_area: Optional[str] = None,
        user_id: Optional[str] = None,
        team_id: Optional[str] = None,
    ) -> List[MemoryInsight]:
        """
        Generate insights by analyzing stored memories.

        Args:
            context: Current context for insight generation
            focus_area: Specific area to focus insights on
            user_id: User requesting insights
            team_id: Team context for insights

        Returns:
            List of generated insights
        """

        # Retrieve relevant memories for analysis
        query = MemoryQuery(
            query_text=context,
            importance_threshold=MemoryImportance.HIGH,
            max_results=20,
            user_id=user_id,
            team_id=team_id,
        )

        relevant_memories = await self.recall_memories(query)

        if not relevant_memories:
            return []

        # Generate insights using LLM
        insight_prompt = f"""
        You are Navi-MemoryAnalyst, an expert at synthesizing engineering knowledge.
        
        Analyze these project memories and generate actionable insights:
        
        CURRENT CONTEXT: {context}
        FOCUS AREA: {focus_area or "General"}
        
        RELEVANT MEMORIES:
        {
            json.dumps(
                [
                    {
                        "type": mem.memory_type.value,
                        "title": mem.title,
                        "content": mem.content[:200] + "..."
                        if len(mem.content) > 200
                        else mem.content,
                        "importance": mem.importance.value,
                        "tags": mem.tags,
                    }
                    for mem, _ in relevant_memories[:10]
                ],
                indent=2,
            )
        }
        
        Generate insights in these categories:
        1. **Patterns**: Recurring themes or issues
        2. **Risks**: Potential problems based on history  
        3. **Opportunities**: Areas for improvement
        4. **Recommendations**: Specific actionable steps
        5. **Knowledge Gaps**: Missing information or documentation
        
        Return JSON array with insights:
        [
            {{
                "insight_type": "pattern|risk|opportunity|recommendation|knowledge_gap",
                "title": "Brief insight title",
                "description": "Detailed explanation",
                "supporting_memories": ["memory_id_1", "memory_id_2"],
                "confidence": 0.85,
                "actionable_recommendations": ["Action 1", "Action 2"]
            }}
        ]
        """

        try:
            response = await self.llm.run(prompt=insight_prompt, use_smart_auto=True)
            insights_data = json.loads(response.text)

            insights = []
            for insight_data in insights_data:
                insight = MemoryInsight(
                    insight_type=insight_data["insight_type"],
                    title=insight_data["title"],
                    description=insight_data["description"],
                    supporting_memories=insight_data.get("supporting_memories", []),
                    confidence=insight_data.get("confidence", 0.5),
                    actionable_recommendations=insight_data.get(
                        "actionable_recommendations", []
                    ),
                )
                insights.append(insight)

            return insights

        except Exception:
            # Fallback insight generation
            return [
                MemoryInsight(
                    insight_type="general",
                    title="Memory Analysis Available",
                    description=f"Found {len(relevant_memories)} relevant memories for context analysis.",
                    supporting_memories=[mem.id for mem, _ in relevant_memories[:5]],
                    confidence=0.7,
                    actionable_recommendations=[
                        "Review stored memories for relevant patterns"
                    ],
                )
            ]

    async def consolidate_memories(
        self, memory_type: Optional[MemoryType] = None, days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Consolidate similar memories to reduce duplication and improve organization.

        Args:
            memory_type: Type of memories to consolidate
            days_back: How far back to look for consolidation

        Returns:
            Consolidation report
        """

        # Get memories for consolidation
        since_date = datetime.now() - timedelta(days=days_back)
        memories = await self._get_memories_since(since_date, memory_type)

        if len(memories) < 2:
            return {
                "consolidated": 0,
                "message": "Insufficient memories for consolidation",
            }

        consolidation_prompt = f"""
        You are Navi-MemoryOrganizer, an expert at consolidating knowledge.
        
        Analyze these memories and identify consolidation opportunities:
        
        MEMORIES:
        {
            json.dumps(
                [
                    {
                        "id": mem.id,
                        "title": mem.title,
                        "content": mem.content[:150] + "..."
                        if len(mem.content) > 150
                        else mem.content,
                        "type": mem.memory_type.value,
                        "tags": mem.tags,
                    }
                    for mem in memories[:20]
                ],
                indent=2,
            )
        }
        
        Identify groups of memories that should be consolidated because they:
        - Contain duplicate information
        - Cover the same topic from different angles
        - Can be combined into a more comprehensive memory
        
        Return JSON with consolidation plan:
        {{
            "consolidation_groups": [
                {{
                    "memory_ids": ["id1", "id2", "id3"],
                    "consolidated_title": "New title",
                    "consolidated_content": "Combined content",
                    "reasoning": "Why these should be consolidated"
                }}
            ]
        }}
        """

        try:
            response = await self.llm.run(
                prompt=consolidation_prompt, use_smart_auto=True
            )
            consolidation_plan = json.loads(response.text)

            consolidated_count = 0
            for group in consolidation_plan.get("consolidation_groups", []):
                memory_ids = group["memory_ids"]
                if len(memory_ids) >= 2:
                    # Create consolidated memory
                    base_memory = await self._load_memory(memory_ids[0])
                    if base_memory:
                        base_memory.title = group["consolidated_title"]
                        base_memory.content = group["consolidated_content"]
                        base_memory.context["consolidation_reason"] = group["reasoning"]
                        base_memory.context["original_ids"] = memory_ids

                        await self._save_memory(base_memory)

                        # Remove other memories in the group
                        for memory_id in memory_ids[1:]:
                            await self._delete_memory(memory_id)

                        consolidated_count += len(memory_ids) - 1

            return {
                "consolidated": consolidated_count,
                "groups_processed": len(
                    consolidation_plan.get("consolidation_groups", [])
                ),
                "memories_analyzed": len(memories),
            }

        except Exception as e:
            return {"error": f"Consolidation failed: {str(e)}"}

    async def cleanup_old_memories(
        self, max_age_days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Clean up old, unused memories to maintain system performance.

        Args:
            max_age_days: Maximum age for memories before cleanup consideration

        Returns:
            Cleanup report
        """

        age_threshold = max_age_days or self.memory_decay_days
        cutoff_date = datetime.now() - timedelta(days=age_threshold)

        # Find candidate memories for cleanup
        old_memories = await self._get_old_memories(cutoff_date)

        cleanup_candidates = []
        for memory in old_memories:
            # Keep memories that are:
            # - High importance
            # - Recently accessed
            # - Frequently accessed
            if (
                memory.importance in [MemoryImportance.CRITICAL, MemoryImportance.HIGH]
                or memory.last_accessed > cutoff_date
                or memory.access_count > 10
            ):
                continue

            cleanup_candidates.append(memory)

        # Archive low-value memories
        archived_count = 0
        deleted_count = 0

        for memory in cleanup_candidates:
            if memory.importance == MemoryImportance.LOW and memory.access_count == 0:
                # Delete unused low-importance memories
                await self._delete_memory(memory.id)
                deleted_count += 1
            else:
                # Archive other candidates
                await self._archive_memory(memory.id)
                archived_count += 1

        return {
            "memories_analyzed": len(old_memories),
            "archived": archived_count,
            "deleted": deleted_count,
            "age_threshold_days": age_threshold,
        }

    async def _enhance_memory_content(
        self,
        memory_type: MemoryType,
        title: str,
        content: str,
        tags: List[str],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Enhance memory content with AI analysis."""

        enhancement_prompt = f"""
        You are Navi-MemoryEnhancer, expert at organizing and structuring knowledge.
        
        Enhance this memory for better retrieval and understanding:
        
        MEMORY TYPE: {memory_type.value}
        TITLE: {title}
        CONTENT: {content}
        EXISTING TAGS: {tags}
        CONTEXT: {json.dumps(context)}
        
        Enhance by:
        1. Improving title clarity and searchability
        2. Structuring content for better comprehension
        3. Adding relevant tags for categorization
        4. Extracting key metadata
        
        Return JSON with enhanced memory:
        {{
            "title": "Enhanced title",
            "content": "Structured content with key points highlighted",
            "tags": ["tag1", "tag2", ...],
            "context": {{
                "key_concepts": ["concept1", "concept2"],
                "related_technologies": ["tech1", "tech2"],
                "impact_level": "low|medium|high",
                "actionable_items": ["action1", "action2"]
            }}
        }}
        """

        try:
            response = await self.llm.run(
                prompt=enhancement_prompt, use_smart_auto=True
            )
            return json.loads(response.text)
        except Exception:
            return {
                "title": title,
                "content": content,
                "tags": tags,
                "context": context,
            }

    async def _find_similar_memories(
        self, content: str, memory_type: MemoryType
    ) -> List[Memory]:
        """Find memories similar to the given content."""

        # Use vector search to find similar content
        similar_docs = self.vector_store.search(
            query=content, k=5, filters={"memory_type": [memory_type.value]}
        )

        similar_memories = []
        for doc in similar_docs:
            if doc["similarity"] > self.similarity_threshold:
                memory = await self._load_memory(doc["id"])
                if memory:
                    similar_memories.append(memory)

        return similar_memories

    async def _find_related_memories(self, memory: Memory) -> List[str]:
        """Find memories related to the given memory."""

        # Search for memories with overlapping tags or content
        related_docs = self.vector_store.search(
            query=memory.content,
            k=10,
            filters={"memory_type": None},  # Search across all types
        )

        related_ids = []
        for doc in related_docs:
            if doc["id"] != memory.id and doc["similarity"] > 0.6:
                related_ids.append(doc["id"])

        return related_ids[:5]  # Limit to top 5 related memories

    def _passes_query_filters(self, memory: Memory, query: MemoryQuery) -> bool:
        """Check if memory passes query filters."""

        # Type filter
        if query.memory_types and memory.memory_type not in query.memory_types:
            return False

        # Tags filter
        if query.tags:
            if not any(tag in memory.tags for tag in query.tags):
                return False

        # Importance filter
        if query.importance_threshold:
            if memory.importance.value > query.importance_threshold.value:
                return False

        return True

    def _calculate_relevance_score(
        self, memory: Memory, query: MemoryQuery, similarity_score: float
    ) -> float:
        """Calculate combined relevance score for memory."""

        score = similarity_score * 0.6  # Base similarity

        # Importance boost
        importance_boost = (6 - memory.importance.value) / 5 * 0.2
        score += importance_boost

        # Recency boost
        if query.recency_bias:
            days_old = (datetime.now() - memory.last_accessed).days
            recency_boost = max(0, (30 - days_old) / 30) * 0.1
            score += recency_boost

        # Access frequency boost
        access_boost = min(memory.access_count / 100, 1.0) * 0.1
        score += access_boost

        return min(score, 1.0)

    async def _consolidate_memories(
        self, existing_memory: Memory, new_data: Dict[str, Any]
    ) -> Memory:
        """Consolidate new data with existing memory."""

        # Update existing memory with new information
        existing_memory.content += (
            f"\n\n--- Additional Information ---\n{new_data['content']}"
        )
        existing_memory.tags = list(
            set(existing_memory.tags + new_data.get("tags", []))
        )
        existing_memory.related_files = list(
            set(existing_memory.related_files + new_data.get("related_files", []))
        )
        existing_memory.context.update(new_data.get("context", {}))
        existing_memory.last_accessed = datetime.now()
        existing_memory.access_count += 1

        await self._save_memory(existing_memory)
        return existing_memory

    # Database operations
    async def _save_memory(self, memory: Memory) -> None:
        """Save memory to database."""
        try:
            query = """
            INSERT OR REPLACE INTO memories 
            (id, memory_type, title, content, importance, tags, related_files, 
             related_memories, context, created_at, last_accessed, access_count, 
             confidence_score, user_id, team_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            await self.db.execute(
                query,
                [
                    memory.id,
                    memory.memory_type.value,
                    memory.title,
                    memory.content,
                    memory.importance.value,
                    json.dumps(memory.tags),
                    json.dumps(memory.related_files),
                    json.dumps(memory.related_memories),
                    json.dumps(memory.context, default=str),
                    memory.created_at.isoformat(),
                    memory.last_accessed.isoformat(),
                    memory.access_count,
                    memory.confidence_score,
                    memory.user_id,
                    memory.team_id,
                ],
            )

        except Exception:
            # Create table if doesn't exist
            create_query = """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                memory_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                importance INTEGER NOT NULL,
                tags TEXT,
                related_files TEXT,
                related_memories TEXT,
                context TEXT,
                created_at TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                confidence_score REAL DEFAULT 1.0,
                user_id TEXT,
                team_id TEXT,
                archived BOOLEAN DEFAULT 0
            )
            """
            await self.db.execute(create_query, [])
            # Retry insert
            await self.db.execute(
                query,
                [
                    memory.id,
                    memory.memory_type.value,
                    memory.title,
                    memory.content,
                    memory.importance.value,
                    json.dumps(memory.tags),
                    json.dumps(memory.related_files),
                    json.dumps(memory.related_memories),
                    json.dumps(memory.context, default=str),
                    memory.created_at.isoformat(),
                    memory.last_accessed.isoformat(),
                    memory.access_count,
                    memory.confidence_score,
                    memory.user_id,
                    memory.team_id,
                ],
            )

    async def _load_memory(self, memory_id: str) -> Optional[Memory]:
        """Load memory from database."""
        try:
            query = "SELECT * FROM memories WHERE id = ? AND archived = 0"
            result = await self.db.fetch_one(query, [memory_id])

            if result:
                return Memory(
                    id=result["id"],
                    memory_type=MemoryType(result["memory_type"]),
                    title=result["title"],
                    content=result["content"],
                    importance=MemoryImportance(result["importance"]),
                    tags=json.loads(result["tags"] or "[]"),
                    related_files=json.loads(result["related_files"] or "[]"),
                    related_memories=json.loads(result["related_memories"] or "[]"),
                    context=json.loads(result["context"] or "{}"),
                    created_at=datetime.fromisoformat(result["created_at"]),
                    last_accessed=datetime.fromisoformat(result["last_accessed"]),
                    access_count=result["access_count"],
                    confidence_score=result["confidence_score"],
                    user_id=result["user_id"],
                    team_id=result["team_id"],
                )
            return None

        except Exception:
            return None

    async def _update_memory_access(self, memory: Memory) -> None:
        """Update memory access statistics."""
        try:
            query = """
            UPDATE memories 
            SET last_accessed = ?, access_count = ?
            WHERE id = ?
            """
            await self.db.execute(
                query,
                [memory.last_accessed.isoformat(), memory.access_count, memory.id],
            )
        except Exception:
            pass

    async def _get_memories_since(
        self, since_date: datetime, memory_type: Optional[MemoryType] = None
    ) -> List[Memory]:
        """Get memories created since a date."""
        try:
            query = "SELECT * FROM memories WHERE created_at >= ? AND archived = 0"
            params = [since_date.isoformat()]

            if memory_type:
                query += " AND memory_type = ?"
                params.append(memory_type.value)

            query += " ORDER BY created_at DESC"

            results = await self.db.fetch_all(query, params)

            memories = []
            for result in results or []:
                memory = Memory(
                    id=result["id"],
                    memory_type=MemoryType(result["memory_type"]),
                    title=result["title"],
                    content=result["content"],
                    importance=MemoryImportance(result["importance"]),
                    tags=json.loads(result["tags"] or "[]"),
                    related_files=json.loads(result["related_files"] or "[]"),
                    related_memories=json.loads(result["related_memories"] or "[]"),
                    context=json.loads(result["context"] or "{}"),
                    created_at=datetime.fromisoformat(result["created_at"]),
                    last_accessed=datetime.fromisoformat(result["last_accessed"]),
                    access_count=result["access_count"],
                    confidence_score=result["confidence_score"],
                    user_id=result["user_id"],
                    team_id=result["team_id"],
                )
                memories.append(memory)

            return memories

        except Exception:
            return []

    async def _get_old_memories(self, cutoff_date: datetime) -> List[Memory]:
        """Get memories older than cutoff date."""
        try:
            query = """
            SELECT * FROM memories 
            WHERE created_at < ? AND archived = 0
            ORDER BY last_accessed ASC, access_count ASC
            """
            results = await self.db.fetch_all(query, [cutoff_date.isoformat()])

            memories = []
            for result in results or []:
                memory = Memory(
                    id=result["id"],
                    memory_type=MemoryType(result["memory_type"]),
                    title=result["title"],
                    content=result["content"],
                    importance=MemoryImportance(result["importance"]),
                    tags=json.loads(result["tags"] or "[]"),
                    related_files=json.loads(result["related_files"] or "[]"),
                    related_memories=json.loads(result["related_memories"] or "[]"),
                    context=json.loads(result["context"] or "{}"),
                    created_at=datetime.fromisoformat(result["created_at"]),
                    last_accessed=datetime.fromisoformat(result["last_accessed"]),
                    access_count=result["access_count"],
                    confidence_score=result["confidence_score"],
                    user_id=result["user_id"],
                    team_id=result["team_id"],
                )
                memories.append(memory)

            return memories

        except Exception:
            return []

    async def _delete_memory(self, memory_id: str) -> None:
        """Delete memory from database."""
        try:
            await self.db.execute("DELETE FROM memories WHERE id = ?", [memory_id])
            # Note: VectorStore doesn't have delete_document, using cleanup instead
            pass  # TODO: Implement proper deletion when VectorStore supports it
        except Exception:
            pass

    async def _archive_memory(self, memory_id: str) -> None:
        """Archive memory."""
        try:
            query = "UPDATE memories SET archived = 1 WHERE id = ?"
            await self.db.execute(query, [memory_id])
        except Exception:
            pass
