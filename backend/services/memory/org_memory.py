"""
Organization Memory Service for NAVI.

Manages organization-level knowledge, coding standards, and shared context
to enable consistent AI responses across the entire organization.

Features:
- Organization knowledge base with semantic search
- Coding standards management and enforcement
- Hierarchical context with inheritance
- Cross-team knowledge sharing
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from backend.database.models.memory import (
    OrgContext,
    OrgKnowledge,
    OrgStandard,
)
from backend.services.memory.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class OrgMemoryService:
    """
    Service for managing organization-level memory and context.

    Provides methods to store and retrieve organizational knowledge,
    manage coding standards, and maintain shared context hierarchies.
    """

    def __init__(self, db: Session):
        """
        Initialize the organization memory service.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.embedding_service = get_embedding_service()

    # =========================================================================
    # Organization Knowledge Base
    # =========================================================================

    async def add_knowledge(
        self,
        org_id: int,
        knowledge_type: str,
        title: str,
        content: str,
        source: Optional[str] = None,
        created_by: Optional[int] = None,
        confidence: float = 1.0,
    ) -> OrgKnowledge:
        """
        Add knowledge to the organization knowledge base.

        Args:
            org_id: Organization ID
            knowledge_type: Type of knowledge (pattern, convention, architecture, etc.)
            title: Knowledge title
            content: Knowledge content
            source: Source of knowledge (manual, inferred, documentation)
            created_by: User ID who added this knowledge
            confidence: Confidence level [0.0, 1.0]

        Returns:
            Created OrgKnowledge
        """
        # Generate embedding for semantic search
        embedding = await self.embedding_service.embed_text(f"{title}\n\n{content}")

        knowledge = OrgKnowledge(
            org_id=org_id,
            knowledge_type=knowledge_type,
            title=title,
            content=content,
            embedding_text=embedding,  # pgvector handles the vector type natively
            source=source or "manual",
            created_by=created_by,
            confidence=confidence,
        )
        self.db.add(knowledge)
        self.db.commit()
        self.db.refresh(knowledge)

        logger.info(f"Added knowledge '{title}' for org {org_id}")
        return knowledge

    def get_knowledge(
        self,
        org_id: int,
        knowledge_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[OrgKnowledge]:
        """
        Get organization knowledge entries.

        Args:
            org_id: Organization ID
            knowledge_type: Optional filter by type
            limit: Maximum entries to return

        Returns:
            List of OrgKnowledge objects
        """
        query = self.db.query(OrgKnowledge).filter(OrgKnowledge.org_id == org_id)

        if knowledge_type:
            query = query.filter(OrgKnowledge.knowledge_type == knowledge_type)

        return query.order_by(desc(OrgKnowledge.updated_at)).limit(limit).all()

    async def search_knowledge(
        self,
        org_id: int,
        query: str,
        knowledge_type: Optional[str] = None,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search in organization knowledge base.

        Args:
            org_id: Organization ID
            query: Search query
            knowledge_type: Optional filter by type
            limit: Maximum results to return
            min_similarity: Minimum similarity threshold

        Returns:
            List of knowledge entries with similarity scores
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.embed_text(query)

        # Get all relevant knowledge entries
        db_query = self.db.query(OrgKnowledge).filter(
            and_(
                OrgKnowledge.org_id == org_id,
                OrgKnowledge.embedding_text.isnot(None),
            )
        )

        if knowledge_type:
            db_query = db_query.filter(OrgKnowledge.knowledge_type == knowledge_type)

        entries = db_query.all()

        # Calculate similarities
        results = []
        for entry in entries:
            if entry.embedding_text is None:
                continue

            # pgvector returns the embedding directly as a numpy array
            entry_embedding = list(entry.embedding_text)
            similarity = self.embedding_service.cosine_similarity(query_embedding, entry_embedding)

            if similarity >= min_similarity:
                results.append({
                    "id": str(entry.id),
                    "title": entry.title,
                    "content": entry.content,
                    "knowledge_type": entry.knowledge_type,
                    "confidence": entry.confidence,
                    "similarity": similarity,
                })

        # Sort by similarity and return top results
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    def update_knowledge(
        self,
        knowledge_id: UUID,
        **kwargs: Any,
    ) -> Optional[OrgKnowledge]:
        """
        Update a knowledge entry.

        Args:
            knowledge_id: Knowledge ID
            **kwargs: Fields to update

        Returns:
            Updated OrgKnowledge or None if not found
        """
        knowledge = (
            self.db.query(OrgKnowledge)
            .filter(OrgKnowledge.id == knowledge_id)
            .first()
        )

        if not knowledge:
            return None

        allowed_fields = {"title", "content", "confidence", "source"}
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(knowledge, key, value)

        self.db.commit()
        self.db.refresh(knowledge)
        return knowledge

    def delete_knowledge(self, knowledge_id: UUID) -> bool:
        """
        Delete a knowledge entry.

        Args:
            knowledge_id: Knowledge ID

        Returns:
            True if deleted, False if not found
        """
        result = (
            self.db.query(OrgKnowledge)
            .filter(OrgKnowledge.id == knowledge_id)
            .delete()
        )
        self.db.commit()
        return result > 0

    # =========================================================================
    # Coding Standards
    # =========================================================================

    def add_standard(
        self,
        org_id: int,
        standard_type: str,
        standard_name: str,
        rules: Dict[str, Any],
        good_examples: Optional[List[Dict[str, Any]]] = None,
        bad_examples: Optional[List[Dict[str, Any]]] = None,
        enforced: bool = False,
    ) -> OrgStandard:
        """
        Add a coding standard.

        Args:
            org_id: Organization ID
            standard_type: Type (naming, structure, testing, security, etc.)
            standard_name: Name of the standard
            rules: Machine-readable rules
            good_examples: Examples following the standard
            bad_examples: Examples violating the standard
            enforced: Whether to enforce this standard

        Returns:
            Created OrgStandard
        """
        standard = OrgStandard(
            org_id=org_id,
            standard_type=standard_type,
            standard_name=standard_name,
            rules=rules,
            good_examples=good_examples or [],
            bad_examples=bad_examples or [],
            enforced=enforced,
        )
        self.db.add(standard)
        self.db.commit()
        self.db.refresh(standard)

        logger.info(f"Added standard '{standard_name}' for org {org_id}")
        return standard

    def get_standards(
        self,
        org_id: int,
        standard_type: Optional[str] = None,
        enforced_only: bool = False,
    ) -> List[OrgStandard]:
        """
        Get organization coding standards.

        Args:
            org_id: Organization ID
            standard_type: Optional filter by type
            enforced_only: Only return enforced standards

        Returns:
            List of OrgStandard objects
        """
        query = self.db.query(OrgStandard).filter(OrgStandard.org_id == org_id)

        if standard_type:
            query = query.filter(OrgStandard.standard_type == standard_type)

        if enforced_only:
            query = query.filter(OrgStandard.enforced)

        return query.order_by(OrgStandard.standard_type, OrgStandard.standard_name).all()

    def get_standard_by_name(
        self,
        org_id: int,
        standard_type: str,
        standard_name: str,
    ) -> Optional[OrgStandard]:
        """
        Get a specific standard by type and name.

        Args:
            org_id: Organization ID
            standard_type: Standard type
            standard_name: Standard name

        Returns:
            OrgStandard or None if not found
        """
        return (
            self.db.query(OrgStandard)
            .filter(
                and_(
                    OrgStandard.org_id == org_id,
                    OrgStandard.standard_type == standard_type,
                    OrgStandard.standard_name == standard_name,
                )
            )
            .first()
        )

    def update_standard(
        self,
        standard_id: UUID,
        **kwargs: Any,
    ) -> Optional[OrgStandard]:
        """
        Update a coding standard.

        Args:
            standard_id: Standard ID
            **kwargs: Fields to update

        Returns:
            Updated OrgStandard or None if not found
        """
        standard = (
            self.db.query(OrgStandard)
            .filter(OrgStandard.id == standard_id)
            .first()
        )

        if not standard:
            return None

        allowed_fields = {
            "rules", "good_examples", "bad_examples",
            "enforced",
        }
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(standard, key, value)

        self.db.commit()
        self.db.refresh(standard)
        return standard

    def delete_standard(self, standard_id: UUID) -> bool:
        """
        Delete a coding standard.

        Args:
            standard_id: Standard ID

        Returns:
            True if deleted, False if not found
        """
        result = (
            self.db.query(OrgStandard)
            .filter(OrgStandard.id == standard_id)
            .delete()
        )
        self.db.commit()
        return result > 0

    # =========================================================================
    # Shared Context
    # =========================================================================

    def set_context(
        self,
        org_id: int,
        context_type: str,
        context_key: str,
        context_value: Dict[str, Any],
        parent_id: Optional[UUID] = None,
    ) -> OrgContext:
        """
        Set or update organization context.

        Args:
            org_id: Organization ID
            context_type: Context type (global, project, team, domain)
            context_key: Unique key within type
            context_value: Context data
            parent_id: Optional parent context for inheritance

        Returns:
            Created or updated OrgContext
        """
        # Check for existing context
        existing = (
            self.db.query(OrgContext)
            .filter(
                and_(
                    OrgContext.org_id == org_id,
                    OrgContext.context_type == context_type,
                    OrgContext.context_key == context_key,
                )
            )
            .first()
        )

        if existing:
            existing.context_value = context_value
            existing.parent_id = parent_id
            self.db.commit()
            self.db.refresh(existing)
            return existing

        context = OrgContext(
            org_id=org_id,
            context_type=context_type,
            context_key=context_key,
            context_value=context_value,
            parent_id=parent_id,
        )
        self.db.add(context)
        self.db.commit()
        self.db.refresh(context)
        return context

    def get_context(
        self,
        org_id: int,
        context_type: str,
        context_key: str,
        include_inherited: bool = True,
    ) -> Dict[str, Any]:
        """
        Get organization context with optional inheritance.

        Args:
            org_id: Organization ID
            context_type: Context type
            context_key: Context key
            include_inherited: Whether to include inherited context

        Returns:
            Merged context dictionary
        """
        context = (
            self.db.query(OrgContext)
            .filter(
                and_(
                    OrgContext.org_id == org_id,
                    OrgContext.context_type == context_type,
                    OrgContext.context_key == context_key,
                )
            )
            .first()
        )

        if not context:
            return {}

        if not include_inherited or not context.parent_id:
            return dict(context.context_value)

        # Build inherited context chain
        result = {}
        current = context

        # Collect context chain (from parent to child)
        chain = []
        while current:
            chain.append(current.context_value)
            if current.parent_id:
                current = (
                    self.db.query(OrgContext)
                    .filter(OrgContext.id == current.parent_id)
                    .first()
                )
            else:
                current = None

        # Merge from parent to child (child overrides parent)
        for ctx in reversed(chain):
            result.update(ctx)

        return result

    def get_all_context(
        self,
        org_id: int,
        context_type: Optional[str] = None,
    ) -> List[OrgContext]:
        """
        Get all organization contexts.

        Args:
            org_id: Organization ID
            context_type: Optional filter by type

        Returns:
            List of OrgContext objects
        """
        query = self.db.query(OrgContext).filter(OrgContext.org_id == org_id)

        if context_type:
            query = query.filter(OrgContext.context_type == context_type)

        return query.order_by(OrgContext.context_type, OrgContext.context_key).all()

    def delete_context(
        self,
        org_id: int,
        context_type: str,
        context_key: str,
    ) -> bool:
        """
        Delete organization context.

        Args:
            org_id: Organization ID
            context_type: Context type
            context_key: Context key

        Returns:
            True if deleted, False if not found
        """
        result = (
            self.db.query(OrgContext)
            .filter(
                and_(
                    OrgContext.org_id == org_id,
                    OrgContext.context_type == context_type,
                    OrgContext.context_key == context_key,
                )
            )
            .delete()
        )
        self.db.commit()
        return result > 0

    # =========================================================================
    # Context Building
    # =========================================================================

    def build_org_context(
        self,
        org_id: int,
        project: Optional[str] = None,
        team: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build comprehensive organization context for NAVI responses.

        Aggregates knowledge, standards, and context hierarchies.

        Args:
            org_id: Organization ID
            project: Optional project context key
            team: Optional team context key

        Returns:
            Dictionary with organization context
        """
        context = {
            "standards": {},
            "knowledge_summary": {},
            "context": {},
        }

        # Get enforced standards
        standards = self.get_standards(org_id, enforced_only=True)
        for std in standards:
            if std.standard_type not in context["standards"]:
                context["standards"][std.standard_type] = []
            context["standards"][std.standard_type].append({
                "name": std.standard_name,
                "rules": std.rules,
            })

        # Get knowledge summary by type
        all_knowledge = self.get_knowledge(org_id, limit=100)
        for k in all_knowledge:
            if k.knowledge_type not in context["knowledge_summary"]:
                context["knowledge_summary"][k.knowledge_type] = 0
            context["knowledge_summary"][k.knowledge_type] += 1

        # Get global context
        global_ctx = self.get_context(org_id, "global", "default")
        if global_ctx:
            context["context"]["global"] = global_ctx

        # Get project context if specified
        if project:
            project_ctx = self.get_context(org_id, "project", project, include_inherited=True)
            if project_ctx:
                context["context"]["project"] = project_ctx

        # Get team context if specified
        if team:
            team_ctx = self.get_context(org_id, "team", team, include_inherited=True)
            if team_ctx:
                context["context"]["team"] = team_ctx

        return context


def get_org_memory_service(db: Session) -> OrgMemoryService:
    """Factory function to create OrgMemoryService."""
    return OrgMemoryService(db)
