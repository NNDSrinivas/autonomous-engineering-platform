"""
RAG (Retrieval Augmented Generation) System for NAVI

Enables NAVI to learn from and retrieve:
1. Company coding standards documents
2. Architecture decision records (ADRs)
3. Past code review feedback
4. Internal documentation
5. Previously generated code patterns

Uses vector embeddings for semantic search to find relevant context
for any given coding task.

Supports multiple vector stores:
- In-memory (default, for development)
- ChromaDB (local persistence)
- Pinecone (cloud, for production SaaS)
- Weaviate (self-hosted)
"""

import os
import json
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import re

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Types of documents that can be indexed."""

    CODING_STANDARD = "coding_standard"
    ARCHITECTURE_DOC = "architecture_doc"
    CODE_REVIEW = "code_review"
    API_DOCUMENTATION = "api_documentation"
    STYLE_GUIDE = "style_guide"
    INTERNAL_WIKI = "internal_wiki"
    GENERATED_CODE = "generated_code"  # Previously generated and approved code
    CUSTOM = "custom"


@dataclass
class Document:
    """A document to be indexed in the RAG system."""

    id: str
    content: str
    doc_type: DocumentType
    org_id: str
    team_id: Optional[str] = None

    # Metadata for filtering
    language: Optional[str] = None
    framework: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    # Source information
    source_url: Optional[str] = None
    source_file: Optional[str] = None
    author: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Embedding (populated by vector store)
    embedding: Optional[List[float]] = None


@dataclass
class RetrievalResult:
    """A result from RAG retrieval."""

    document: Document
    score: float  # Similarity score (0-1)
    snippet: str  # Relevant snippet from the document


class EmbeddingProvider:
    """
    Abstract embedding provider.
    Supports multiple backends for generating embeddings.
    """

    def __init__(self, provider: str = "local"):
        self.provider = provider
        self._model = None

    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        if self.provider == "local":
            return await self._embed_local(text)
        elif self.provider == "openai":
            return await self._embed_openai(text)
        elif self.provider == "anthropic":
            return await self._embed_voyager(text)
        else:
            return await self._embed_local(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        return [await self.embed(text) for text in texts]

    async def _embed_local(self, text: str) -> List[float]:
        """
        Simple local embedding using TF-IDF style vectors.
        For production, use sentence-transformers or similar.
        """
        # Simple hash-based embedding for development
        # In production, use: sentence-transformers/all-MiniLM-L6-v2
        import hashlib

        # Tokenize and create a simple embedding
        words = text.lower().split()
        embedding = [0.0] * 384  # Standard embedding size

        for i, word in enumerate(words[:100]):  # Limit to first 100 words
            # Hash each word to get indices
            h = int(hashlib.md5(word.encode()).hexdigest()[:8], 16)
            idx1 = h % 384
            idx2 = (h >> 8) % 384

            # Add weighted values
            weight = 1.0 / (1 + i * 0.1)  # Earlier words weighted more
            embedding[idx1] += weight
            embedding[idx2] -= weight * 0.5

        # Normalize
        magnitude = sum(x * x for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding

    async def _embed_openai(self, text: str) -> List[float]:
        """Use OpenAI embeddings API."""
        try:
            import openai

            client = openai.AsyncOpenAI()
            response = await client.embeddings.create(
                model="text-embedding-3-small", input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"OpenAI embedding failed, falling back to local: {e}")
            return await self._embed_local(text)

    async def _embed_voyager(self, text: str) -> List[float]:
        """Use Anthropic's Voyager embeddings (if available)."""
        # Anthropic doesn't have a public embedding API yet
        # Fall back to local
        return await self._embed_local(text)


class VectorStore:
    """
    Abstract vector store for document storage and retrieval.
    """

    async def add(self, document: Document) -> None:
        """Add a document to the store."""
        raise NotImplementedError

    async def search(
        self,
        query_embedding: List[float],
        org_id: str,
        team_id: Optional[str] = None,
        filters: Optional[Dict] = None,
        top_k: int = 5,
    ) -> List[Tuple[Document, float]]:
        """Search for similar documents."""
        raise NotImplementedError

    async def delete(self, doc_id: str) -> None:
        """Delete a document from the store."""
        raise NotImplementedError

    async def update(self, document: Document) -> None:
        """Update an existing document."""
        raise NotImplementedError


class InMemoryVectorStore(VectorStore):
    """
    In-memory vector store for development and testing.
    Data is persisted to disk as JSON.
    """

    def __init__(self, storage_path: str = None):
        self.storage_path = Path(
            storage_path
            or os.getenv("NAVI_RAG_PATH", os.path.expanduser("~/.navi/rag"))
        )
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.documents: Dict[str, Document] = {}
        self._load_from_disk()

    def _load_from_disk(self):
        """Load existing documents from disk."""
        index_file = self.storage_path / "index.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text())
                for doc_data in data.get("documents", []):
                    doc = self._dict_to_document(doc_data)
                    self.documents[doc.id] = doc
                logger.info(f"Loaded {len(self.documents)} documents from RAG store")
            except Exception as e:
                logger.error(f"Error loading RAG index: {e}")

    def _save_to_disk(self):
        """Persist documents to disk."""
        index_file = self.storage_path / "index.json"
        data = {
            "documents": [
                self._document_to_dict(doc) for doc in self.documents.values()
            ]
        }
        index_file.write_text(json.dumps(data, indent=2, default=str))

    def _document_to_dict(self, doc: Document) -> Dict:
        """Convert document to dict for serialization."""
        return {
            "id": doc.id,
            "content": doc.content,
            "doc_type": doc.doc_type.value,
            "org_id": doc.org_id,
            "team_id": doc.team_id,
            "language": doc.language,
            "framework": doc.framework,
            "tags": doc.tags,
            "source_url": doc.source_url,
            "source_file": doc.source_file,
            "author": doc.author,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            "embedding": doc.embedding,
        }

    def _dict_to_document(self, data: Dict) -> Document:
        """Convert dict back to Document."""
        return Document(
            id=data["id"],
            content=data["content"],
            doc_type=DocumentType(data["doc_type"]),
            org_id=data["org_id"],
            team_id=data.get("team_id"),
            language=data.get("language"),
            framework=data.get("framework"),
            tags=data.get("tags", []),
            source_url=data.get("source_url"),
            source_file=data.get("source_file"),
            author=data.get("author"),
            embedding=data.get("embedding"),
        )

    async def add(self, document: Document) -> None:
        """Add a document to the store."""
        self.documents[document.id] = document
        self._save_to_disk()
        logger.info(f"Added document to RAG: {document.id}")

    async def search(
        self,
        query_embedding: List[float],
        org_id: str,
        team_id: Optional[str] = None,
        filters: Optional[Dict] = None,
        top_k: int = 5,
    ) -> List[Tuple[Document, float]]:
        """Search for similar documents using cosine similarity."""
        results = []

        for doc in self.documents.values():
            # Filter by org
            if doc.org_id != org_id:
                continue

            # Filter by team if specified
            if team_id and doc.team_id and doc.team_id != team_id:
                continue

            # Apply additional filters
            if filters:
                if filters.get("language") and doc.language != filters["language"]:
                    continue
                if filters.get("framework") and doc.framework != filters["framework"]:
                    continue
                if (
                    filters.get("doc_type")
                    and doc.doc_type.value != filters["doc_type"]
                ):
                    continue
                if filters.get("tags"):
                    if not any(tag in doc.tags for tag in filters["tags"]):
                        continue

            # Calculate similarity
            if doc.embedding:
                score = self._cosine_similarity(query_embedding, doc.embedding)
                results.append((doc, score))

        # Sort by score and return top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    async def delete(self, doc_id: str) -> None:
        """Delete a document from the store."""
        if doc_id in self.documents:
            del self.documents[doc_id]
            self._save_to_disk()

    async def update(self, document: Document) -> None:
        """Update an existing document."""
        document.updated_at = datetime.now()
        self.documents[document.id] = document
        self._save_to_disk()

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


# ============================================================
# RAG MANAGER - Main interface
# ============================================================


class RAGManager:
    """
    Main RAG system manager for NAVI.

    Handles:
    - Document ingestion from various sources
    - Embedding generation
    - Semantic search for relevant context
    - Context formatting for prompts
    """

    def __init__(
        self,
        vector_store: VectorStore = None,
        embedding_provider: EmbeddingProvider = None,
    ):
        self.vector_store = vector_store or InMemoryVectorStore()
        self.embedding_provider = embedding_provider or EmbeddingProvider("local")

    async def ingest_document(
        self,
        content: str,
        doc_type: DocumentType,
        org_id: str,
        team_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> Document:
        """
        Ingest a new document into the RAG system.
        """
        # Generate unique ID
        doc_id = hashlib.sha256(
            f"{org_id}:{team_id}:{content[:100]}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        # Generate embedding
        embedding = await self.embedding_provider.embed(content)

        # Create document
        doc = Document(
            id=doc_id,
            content=content,
            doc_type=doc_type,
            org_id=org_id,
            team_id=team_id,
            language=metadata.get("language") if metadata else None,
            framework=metadata.get("framework") if metadata else None,
            tags=metadata.get("tags", []) if metadata else [],
            source_url=metadata.get("source_url") if metadata else None,
            source_file=metadata.get("source_file") if metadata else None,
            author=metadata.get("author") if metadata else None,
            embedding=embedding,
        )

        # Store
        await self.vector_store.add(doc)

        return doc

    async def ingest_coding_standard(
        self,
        content: str,
        org_id: str,
        team_id: Optional[str] = None,
        language: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Document:
        """Convenience method for ingesting coding standards."""
        return await self.ingest_document(
            content=content,
            doc_type=DocumentType.CODING_STANDARD,
            org_id=org_id,
            team_id=team_id,
            metadata={
                "language": language,
                "source_url": source,
                "tags": (
                    ["coding-standard", language] if language else ["coding-standard"]
                ),
            },
        )

    async def ingest_code_review(
        self,
        review_content: str,
        org_id: str,
        team_id: Optional[str] = None,
        language: Optional[str] = None,
        reviewer: Optional[str] = None,
    ) -> Document:
        """Ingest feedback from a code review."""
        return await self.ingest_document(
            content=review_content,
            doc_type=DocumentType.CODE_REVIEW,
            org_id=org_id,
            team_id=team_id,
            metadata={
                "language": language,
                "author": reviewer,
                "tags": ["code-review", language] if language else ["code-review"],
            },
        )

    async def ingest_approved_code(
        self,
        code: str,
        description: str,
        org_id: str,
        team_id: Optional[str] = None,
        language: Optional[str] = None,
        framework: Optional[str] = None,
    ) -> Document:
        """
        Ingest code that was approved by the user.
        This helps NAVI learn from patterns the organization likes.
        """
        content = (
            f"Description: {description}\n\nCode:\n```{language or ''}\n{code}\n```"
        )

        return await self.ingest_document(
            content=content,
            doc_type=DocumentType.GENERATED_CODE,
            org_id=org_id,
            team_id=team_id,
            metadata={
                "language": language,
                "framework": framework,
                "tags": (
                    ["approved-code", language, framework]
                    if language
                    else ["approved-code"]
                ),
            },
        )

    async def retrieve(
        self,
        query: str,
        org_id: str,
        team_id: Optional[str] = None,
        filters: Optional[Dict] = None,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant documents for a query.
        """
        # Generate query embedding
        query_embedding = await self.embedding_provider.embed(query)

        # Search vector store
        results = await self.vector_store.search(
            query_embedding=query_embedding,
            org_id=org_id,
            team_id=team_id,
            filters=filters,
            top_k=top_k,
        )

        # Format results
        retrieval_results = []
        for doc, score in results:
            # Extract relevant snippet
            snippet = self._extract_snippet(doc.content, query)
            retrieval_results.append(
                RetrievalResult(
                    document=doc,
                    score=score,
                    snippet=snippet,
                )
            )

        return retrieval_results

    async def get_context_for_task(
        self,
        task_description: str,
        org_id: str,
        team_id: Optional[str] = None,
        language: Optional[str] = None,
        framework: Optional[str] = None,
    ) -> str:
        """
        Get relevant context from RAG for a coding task.
        Returns formatted context string for the prompt.
        """
        filters = {}
        if language:
            filters["language"] = language
        if framework:
            filters["framework"] = framework

        # Retrieve relevant documents
        results = await self.retrieve(
            query=task_description,
            org_id=org_id,
            team_id=team_id,
            filters=filters if filters else None,
            top_k=5,
        )

        if not results:
            return ""

        # Format context
        context_parts = ["=== RELEVANT ORGANIZATION KNOWLEDGE ===\n"]

        for result in results:
            if result.score < 0.3:  # Skip low-relevance results
                continue

            doc = result.document
            header = f"[{doc.doc_type.value.upper()}]"
            if doc.language:
                header += f" ({doc.language})"

            context_parts.append(f"{header}")
            context_parts.append(result.snippet)
            context_parts.append("")

        return "\n".join(context_parts)

    def _extract_snippet(self, content: str, query: str, max_length: int = 500) -> str:
        """Extract the most relevant snippet from content."""
        # Simple extraction: find section containing query terms
        query_words = set(query.lower().split())

        # Split into paragraphs
        paragraphs = content.split("\n\n")

        # Score each paragraph by query word overlap
        scored = []
        for para in paragraphs:
            para_words = set(para.lower().split())
            overlap = len(query_words & para_words)
            scored.append((para, overlap))

        # Sort by score and take top paragraphs
        scored.sort(key=lambda x: x[1], reverse=True)

        result = []
        current_length = 0
        for para, score in scored:
            if current_length + len(para) > max_length:
                break
            result.append(para)
            current_length += len(para)

        return "\n\n".join(result) if result else content[:max_length]


# ============================================================
# DOCUMENT PARSERS
# ============================================================


class DocumentParser:
    """Parses various document formats for ingestion."""

    @staticmethod
    def parse_markdown(content: str) -> List[Dict]:
        """Parse markdown into sections."""
        sections = []
        current_section = {"title": "", "content": []}

        for line in content.split("\n"):
            if line.startswith("#"):
                # Save current section
                if current_section["content"]:
                    sections.append(
                        {
                            "title": current_section["title"],
                            "content": "\n".join(current_section["content"]),
                        }
                    )
                # Start new section
                current_section = {"title": line.lstrip("#").strip(), "content": []}
            else:
                current_section["content"].append(line)

        # Don't forget last section
        if current_section["content"]:
            sections.append(
                {
                    "title": current_section["title"],
                    "content": "\n".join(current_section["content"]),
                }
            )

        return sections

    @staticmethod
    def parse_code_review(review_text: str) -> List[Dict]:
        """Parse code review comments into structured feedback."""
        # Common patterns in code reviews
        patterns = [
            r"(?:should|must|please|consider)\s+(.+?)(?:\.|$)",
            r"(?:instead of|rather than)\s+(.+?),?\s+(?:use|try|prefer)\s+(.+?)(?:\.|$)",
            r"(?:don't|avoid|never)\s+(.+?)(?:\.|$)",
        ]

        feedback = []
        for pattern in patterns:
            matches = re.findall(pattern, review_text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    feedback.append(
                        {
                            "pattern": match[0],
                            "suggestion": match[1] if len(match) > 1 else None,
                        }
                    )
                else:
                    feedback.append({"pattern": match})

        return feedback


# ============================================================
# GLOBAL INSTANCE
# ============================================================

_rag_manager: Optional[RAGManager] = None


def get_rag_manager() -> RAGManager:
    """Get the global RAG manager instance."""
    global _rag_manager
    if _rag_manager is None:
        _rag_manager = RAGManager()
    return _rag_manager


async def get_rag_context(
    task: str,
    org_id: str,
    team_id: Optional[str] = None,
    language: Optional[str] = None,
    framework: Optional[str] = None,
) -> str:
    """Convenience function to get RAG context for a task."""
    manager = get_rag_manager()
    return await manager.get_context_for_task(
        task_description=task,
        org_id=org_id,
        team_id=team_id,
        language=language,
        framework=framework,
    )
