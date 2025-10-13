from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
from backend.core.memory.vector_store import VectorStore

logger = logging.getLogger(__name__)


class TeamService:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        logger.info("TeamService initialized")

        # Initialize with some demo knowledge
        self._initialize_demo_knowledge()

    def _initialize_demo_knowledge(self):
        """Initialize the team knowledge base with demo content"""
        try:
            demo_knowledge = [
                {
                    "content": "API Design Best Practices: Use RESTful principles, proper HTTP status codes, consistent naming conventions, and comprehensive documentation. Always version your APIs and implement proper error handling.",
                    "metadata": {
                        "category": "api-design",
                        "project": "demo-project",
                        "author": "team-lead",
                    },
                },
                {
                    "content": "Code Review Guidelines: Focus on logic correctness, performance implications, security concerns, and maintainability. Always be constructive in feedback and suggest improvements.",
                    "metadata": {
                        "category": "code-review",
                        "project": "demo-project",
                        "author": "senior-dev",
                    },
                },
                {
                    "content": "Testing Strategy: Implement unit tests for individual components, integration tests for service interactions, and end-to-end tests for critical user journeys. Aim for 80%+ code coverage.",
                    "metadata": {
                        "category": "testing",
                        "project": "demo-project",
                        "author": "qa-lead",
                    },
                },
                {
                    "content": "Deployment Patterns: Use blue-green deployments for zero-downtime releases, implement proper health checks, and maintain rollback capabilities. Always test in staging before production.",
                    "metadata": {
                        "category": "deployment",
                        "project": "demo-project",
                        "author": "devops-engineer",
                    },
                },
                {
                    "content": "Performance Optimization: Profile before optimizing, focus on algorithmic improvements first, implement caching strategies, and monitor key metrics continuously.",
                    "metadata": {
                        "category": "performance",
                        "project": "demo-project",
                        "author": "performance-engineer",
                    },
                },
            ]

            for item in demo_knowledge:
                self.vector_store.add_document(
                    content=item["content"],
                    metadata=item["metadata"],
                    doc_id=f"demo-{item['metadata']['category']}",
                )

            logger.info("Demo knowledge base initialized")

        except Exception as e:
            logger.warning(f"Failed to initialize demo knowledge: {e}")

    async def search_team_context(
        self, query: str, project_id: Optional[str] = None, limit: int = 5
    ) -> Dict[str, Any]:
        """
        Search team knowledge and context
        """
        try:
            logger.info(f"Searching team context for: {query[:50]}...")

            # Search vector store
            results = self.vector_store.search(query, limit=limit)

            # Filter by project if specified
            if project_id:
                results = [
                    r
                    for r in results
                    if r.get("metadata", {}).get("project") == project_id
                ]

            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append(
                    {
                        "content": result.get("content", ""),
                        "score": result.get("score", 0.0),
                        "metadata": result.get("metadata", {}),
                        "relevant_sections": self._extract_relevant_sections(
                            result.get("content", ""), query
                        ),
                    }
                )

            # Generate summary
            summary = self._generate_context_summary(formatted_results, query)

            return {
                "query": query,
                "results": formatted_results,
                "summary": summary,
                "project_id": project_id,
                "total_results": len(formatted_results),
                "search_time": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error searching team context: {e}")
            return {
                "query": query,
                "results": [],
                "summary": "Error occurred while searching team context",
                "error": "internal_error",
                "project_id": project_id,
            }

    def _extract_relevant_sections(self, content: str, query: str) -> List[str]:
        """
        Extract sections of content most relevant to the query
        """
        try:
            # Simple keyword-based extraction
            query_words = query.lower().split()
            sentences = content.split(". ")

            relevant = []
            for sentence in sentences:
                score = sum(1 for word in query_words if word in sentence.lower())
                if score > 0:
                    relevant.append((sentence.strip() + ".", score))

            # Sort by relevance and return top 3
            relevant.sort(key=lambda x: x[1], reverse=True)
            return [r[0] for r in relevant[:3]]

        except Exception as e:
            logger.warning(f"Error extracting relevant sections: {e}")
            return [content[:200] + "..." if len(content) > 200 else content]

    def _generate_context_summary(self, results: List[Dict], query: str) -> str:
        """
        Generate a summary of the search results
        """
        try:
            if not results:
                return f"No relevant team context found for '{query}'. Consider adding documentation or knowledge base entries."

            categories = set()
            authors = set()

            for result in results:
                metadata = result.get("metadata", {})
                if "category" in metadata:
                    categories.add(metadata["category"])
                if "author" in metadata:
                    authors.add(metadata["author"])

            summary_parts = [
                f"Found {len(results)} relevant knowledge items for '{query}'."
            ]

            if categories:
                summary_parts.append(f"Categories covered: {', '.join(categories)}.")

            if authors:
                summary_parts.append(f"Contributors: {', '.join(authors)}.")

            # Add top recommendation
            if results:
                top_result = results[0]
                summary_parts.append(
                    f"Top recommendation: {top_result['content'][:100]}..."
                )

            return " ".join(summary_parts)

        except Exception as e:
            logger.warning(f"Error generating summary: {e}")
            return f"Found {len(results)} relevant items for '{query}'."

    async def add_team_knowledge(
        self, content: str, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add new knowledge to the team knowledge base
        """
        try:
            doc_id = f"team-{datetime.now().timestamp()}"

            # Add timestamp to metadata
            metadata["added_at"] = datetime.now().isoformat()

            self.vector_store.add_document(
                content=content, metadata=metadata, doc_id=doc_id
            )

            logger.info(f"Added team knowledge: {doc_id}")

            return {
                "success": True,
                "doc_id": doc_id,
                "message": "Knowledge successfully added to team database",
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(f"Error adding team knowledge: {e}")
            return {
                "success": False,
                "error": "internal_error",
                "message": "Failed to add knowledge to team database",
            }

    async def get_team_analytics(
        self, project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get analytics about team knowledge and usage
        """
        try:
            # This is a simplified version - in production you'd query actual usage data
            analytics = {
                "knowledge_base": {
                    "total_documents": 5,  # Would be actual count
                    "categories": [
                        "api-design",
                        "code-review",
                        "testing",
                        "deployment",
                        "performance",
                    ],
                    "top_contributors": [
                        "team-lead",
                        "senior-dev",
                        "qa-lead",
                        "devops-engineer",
                    ],
                    "recent_additions": 0,
                },
                "search_patterns": {
                    "popular_queries": ["API design", "testing", "deployment"],
                    "search_frequency": "moderate",
                    "avg_results_per_search": 3.2,
                },
                "project_coverage": {
                    "projects_documented": 1 if project_id else 1,
                    "documentation_completeness": "75%",
                },
                "recommendations": [
                    "Add more security-focused documentation",
                    "Include more code examples in knowledge base",
                    "Document common troubleshooting scenarios",
                ],
            }

            if project_id:
                analytics["project_id"] = project_id
                analytics["project_specific"] = {
                    "documented_areas": ["API", "Testing", "Deployment"],
                    "missing_areas": ["Security", "Monitoring", "Troubleshooting"],
                }

            return analytics

        except Exception as e:
            logger.error(f"Error generating team analytics: {e}")
            return {
                "error": "internal_error",
                "message": "Failed to generate team analytics",
            }
