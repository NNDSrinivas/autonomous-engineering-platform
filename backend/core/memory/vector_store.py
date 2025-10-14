"""
Engineering-focused vector memory service for autonomous platform
Stores code knowledge, team interactions, and project context
"""

import os
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    CHROMA_AVAILABLE = True
except ImportError:
    chromadb = None
    ChromaSettings = None
    CHROMA_AVAILABLE = False

import structlog
from backend.core.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class SearchResult:
    """Search result from vector store"""

    content: str
    metadata: Dict[str, Any]
    score: float
    id: str


@dataclass
class KnowledgeEntry:
    """Knowledge entry for engineering context"""

    id: str
    content: str
    type: str  # 'code', 'discussion', 'documentation', 'decision'
    project: str
    timestamp: datetime
    metadata: Dict[str, Any]


class VectorStore:
    """
    Engineering-focused vector store for team knowledge and code context
    """

    def __init__(self, persist_dir: Optional[str] = None):
        settings = get_settings()
        self.persist_dir = persist_dir or settings.vector_db_path
        os.makedirs(self.persist_dir, exist_ok=True)

        self.client = None
        self.collections = {}

        if CHROMA_AVAILABLE:
            try:
                self.client = chromadb.PersistentClient(path=self.persist_dir)
                self._init_collections()
                logger.info(
                    "ChromaDB initialized for engineering platform",
                    path=self.persist_dir,
                )
            except Exception as e:
                logger.error("Failed to initialize ChromaDB", error=str(e))
                self.client = None
        else:
            logger.warning("ChromaDB not available, vector search disabled")

    def _init_collections(self):
        """Initialize collections for different types of engineering knowledge"""
        if not self.client:
            return

        collection_configs = {
            "code_knowledge": "Code snippets, functions, and implementation patterns",
            "team_discussions": "Team conversations, decisions, and context",
            "project_documentation": "Project docs, architecture decisions, and specs",
            "issue_context": "Bug reports, feature requests, and their solutions",
            "deployment_knowledge": "Infrastructure, deployment, and operational knowledge",
        }

        for name, description in collection_configs.items():
            try:
                self.collections[name] = self.client.get_or_create_collection(
                    name=name, metadata={"description": description}
                )
            except Exception as e:
                logger.error(f"Failed to create collection {name}", error=str(e))

    async def add_knowledge(
        self,
        content: str,
        knowledge_type: str,
        project: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add engineering knowledge to the vector store"""
        if not self.client:
            logger.warning("Vector store not available, skipping knowledge addition")
            return ""

        entry_id = f"{knowledge_type}_{project}_{datetime.now().isoformat()}"

        # Determine collection based on knowledge type
        collection_map = {
            "code": "code_knowledge",
            "discussion": "team_discussions",
            "documentation": "project_documentation",
            "issue": "issue_context",
            "deployment": "deployment_knowledge",
        }

        collection_name = collection_map.get(knowledge_type, "team_discussions")
        collection = self.collections.get(collection_name)

        if not collection:
            logger.error(f"Collection {collection_name} not available")
            return ""

        # Prepare metadata
        entry_metadata = {
            "type": knowledge_type,
            "project": project,
            "timestamp": datetime.now().isoformat(),
            **(metadata or {}),
        }

        try:
            collection.add(
                documents=[content], metadatas=[entry_metadata], ids=[entry_id]
            )

            logger.info(
                "Added knowledge to vector store",
                type=knowledge_type,
                project=project,
                id=entry_id,
            )
            return entry_id

        except Exception as e:
            logger.error("Failed to add knowledge", error=str(e))
            return ""

    async def search(
        self,
        query: str,
        knowledge_types: Optional[List[str]] = None,
        project: Optional[str] = None,
        limit: int = 5,
    ) -> List[SearchResult]:
        """Search for relevant engineering knowledge"""
        if not self.client:
            return []

        results = []

        # Determine which collections to search
        if knowledge_types:
            collection_map = {
                "code": "code_knowledge",
                "discussion": "team_discussions",
                "documentation": "project_documentation",
                "issue": "issue_context",
                "deployment": "deployment_knowledge",
            }
            collections_to_search = [
                self.collections.get(collection_map.get(kt))
                for kt in knowledge_types
                if collection_map.get(kt) in self.collections
            ]
        else:
            collections_to_search = list(self.collections.values())

        for collection in collections_to_search:
            if not collection:
                continue

            try:
                # Build where clause for filtering
                where_clause = {}
                if project:
                    where_clause["project"] = project

                search_results = collection.query(
                    query_texts=[query],
                    n_results=limit,
                    where=where_clause if where_clause else None,
                )

                if search_results and search_results["documents"]:
                    for i, doc in enumerate(search_results["documents"][0]):
                        metadata = (
                            search_results["metadatas"][0][i]
                            if search_results["metadatas"]
                            else {}
                        )
                        distance = (
                            search_results["distances"][0][i]
                            if search_results["distances"]
                            else 0.0
                        )
                        doc_id = (
                            search_results["ids"][0][i]
                            if search_results["ids"]
                            else f"unknown_{i}"
                        )

                        results.append(
                            SearchResult(
                                content=doc,
                                metadata=metadata,
                                score=1.0
                                - distance,  # Convert distance to similarity score
                                id=doc_id,
                            )
                        )

            except Exception as e:
                logger.error("Error searching collection", error=str(e))

        # Sort by score and limit results
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    async def get_recent_knowledge(
        self,
        hours: int = 24,
        knowledge_types: Optional[List[str]] = None,
        project: Optional[str] = None,
        limit: int = 10,
    ) -> List[SearchResult]:
        """Get recent engineering knowledge entries"""
        if not self.client:
            return []

        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        results = []

        collections_to_search = list(self.collections.values())

        for collection in collections_to_search:
            if not collection:
                continue

            try:
                # Build where clause
                where_clause = {"timestamp": {"$gte": cutoff_time}}
                if project:
                    where_clause["project"] = project
                if knowledge_types:
                    where_clause["type"] = {"$in": knowledge_types}

                search_results = collection.get(where=where_clause, limit=limit)

                if search_results and search_results["documents"]:
                    for i, doc in enumerate(search_results["documents"]):
                        metadata = (
                            search_results["metadatas"][i]
                            if search_results["metadatas"]
                            else {}
                        )
                        doc_id = (
                            search_results["ids"][i]
                            if search_results["ids"]
                            else f"recent_{i}"
                        )

                        results.append(
                            SearchResult(
                                content=doc,
                                metadata=metadata,
                                score=1.0,  # Recent items get full score
                                id=doc_id,
                            )
                        )

            except Exception as e:
                logger.error("Error getting recent knowledge", error=str(e))

        # Sort by timestamp (most recent first)
        results.sort(key=lambda x: x.metadata.get("timestamp", ""), reverse=True)
        return results[:limit]

    async def add_code_context(
        self,
        code: str,
        language: str,
        file_path: str,
        project: str,
        description: Optional[str] = None,
    ) -> str:
        """Add code context to knowledge base"""
        metadata = {
            "language": language,
            "file_path": file_path,
            "description": description or f"Code from {file_path}",
        }

        return await self.add_knowledge(
            content=code, knowledge_type="code", project=project, metadata=metadata
        )

    async def add_team_discussion(
        self,
        discussion: str,
        participants: List[str],
        project: str,
        topic: Optional[str] = None,
    ) -> str:
        """Add team discussion to knowledge base"""
        metadata = {
            "participants": participants,
            "topic": topic or "General discussion",
        }

        return await self.add_knowledge(
            content=discussion,
            knowledge_type="discussion",
            project=project,
            metadata=metadata,
        )

    async def close(self):
        """Cleanup vector store resources"""
        if self.client:
            # ChromaDB automatically persists, no explicit close needed
            logger.info("Vector store cleanup complete")
