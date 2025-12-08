"""
Organizational Brain Query Engine

Provides natural language query capabilities across the entire organizational memory graph.
Combines semantic search with LLM reasoning to answer complex questions about:
- Jira issues and their relationships
- Slack discussions and decisions
- GitHub PRs and code changes
- Confluence documentation
- Team activities and expertise
- Cross-platform connections (e.g., "What PRs implement JIRA-123?")

The query engine:
1. Performs semantic search to find relevant nodes
2. Traverses edges to gather related context
3. Uses LLM to synthesize a comprehensive answer
"""

import logging
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI
import os
from backend.services.memory_graph_service import MemoryGraphService

logger = logging.getLogger(__name__)


class OrgBrainQuery:
    """
    Unified query engine for organizational intelligence.

    Enables natural language queries like:
    - "Show everything related to SCRUM-1"
    - "Summarize the auth redesign discussion"
    - "Find discussions about deployment failure yesterday"
    - "What PRs did Alice work on last week?"
    - "What decisions were made in the standup meeting?"
    """

    def __init__(self, memory_service: MemoryGraphService):
        self.mg = memory_service
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4"

    async def query(
        self,
        question: str,
        limit: int = 12,
        node_types: Optional[List[str]] = None,
        include_edges: bool = True,
    ) -> Dict[str, Any]:
        """
        Answer a natural language question about the organization.

        Args:
            question: Natural language question
            limit: Maximum number of nodes to retrieve
            node_types: Optional filter by node types
            include_edges: Whether to include edge information

        Returns:
            Dict with answer, nodes, edges, and metadata
        """
        try:
            logger.info(f"Processing org brain query: {question}")

            # Step 1: Semantic search to find relevant nodes
            search_results = await self.mg.search(
                query=question, limit=limit, node_types=node_types
            )

            if not search_results:
                return {
                    "question": question,
                    "answer": "I couldn't find any relevant information in the organizational memory.",
                    "nodes": [],
                    "edges": [],
                    "total_nodes": 0,
                }

            logger.info(f"Found {len(search_results)} relevant nodes")

            # Step 2: Gather related edges if requested
            edges_data = []
            if include_edges:
                for node in search_results[:5]:  # Get edges for top 5 nodes
                    related_nodes, edges = self.mg.get_related_nodes(node["id"])
                    for edge in edges:
                        edges_data.append(
                            {
                                "from_id": edge.from_id,
                                "to_id": edge.to_id,
                                "edge_type": edge.edge_type,
                                "weight": edge.weight,
                            }
                        )

            logger.info(f"Gathered {len(edges_data)} related edges")

            # Step 3: Build context for LLM
            context_text = self._build_context(search_results, edges_data)

            # Step 4: Use LLM to synthesize answer
            system_prompt = """You are NAVI, an intelligent assistant with access to your organization's complete memory graph.

You have access to information from:
- Jira issues and tickets
- Slack conversations
- GitHub pull requests and issues
- Confluence documentation
- Team meetings and decisions
- Code repositories

Your task is to provide accurate, concise answers based on the organizational context provided.
If the information is insufficient, say so clearly. Always cite specific sources when possible."""

            user_prompt = f"""Question: {question}

Organizational Context:
{context_text}

Please provide a comprehensive answer based on the context above."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
            )

            answer = response.choices[0].message.content
            if answer is None:
                answer = "I couldn't generate an answer. Please try rephrasing your question."

            logger.info(f"Generated answer: {len(answer)} chars")

            return {
                "question": question,
                "answer": answer,
                "nodes": search_results,
                "edges": edges_data if include_edges else None,
                "total_nodes": len(search_results),
                "model_used": self.model,
            }

        except Exception as e:
            logger.error(f"Query failed: {e}", exc_info=True)
            raise

    def _build_context(
        self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]
    ) -> str:
        """
        Build a formatted context string for the LLM.

        Args:
            nodes: List of node dicts with text and metadata
            edges: List of edge dicts

        Returns:
            Formatted context string
        """
        context_parts = []

        # Add nodes
        context_parts.append("## Relevant Information:\n")
        for i, node in enumerate(nodes, 1):
            node_type = node.get("node_type", "unknown")
            title = node.get("title", "Untitled")
            text = node.get("text", "")
            score = node.get("score", 0.0)

            # Truncate long text
            if len(text) > 500:
                text = text[:500] + "..."

            context_parts.append(
                f"{i}. [{node_type.upper()}] {title} (relevance: {score:.2f})\n{text}\n"
            )

        # Add relationships
        if edges:
            context_parts.append("\n## Relationships:\n")
            edge_summaries = {}
            for edge in edges:
                edge_type = edge.get("edge_type", "relates_to")
                key = edge_type
                edge_summaries[key] = edge_summaries.get(key, 0) + 1

            for edge_type, count in edge_summaries.items():
                context_parts.append(f"- {count} {edge_type} relationships\n")

        return "\n".join(context_parts)

    async def summarize_node(self, node_id: int) -> str:
        """
        Generate a summary of a specific node and its relationships.

        Args:
            node_id: Node ID to summarize

        Returns:
            Summary text
        """
        try:
            # Get the node
            node = self.mg.get_node(node_id)
            if not node:
                return "Node not found."

            # Get related nodes and edges
            related_nodes, edges = self.mg.get_related_nodes(node_id)

            # Build prompt
            prompt = f"""Summarize the following organizational entity and its relationships:

Title: {node.title}
Type: {node.node_type}
Content: {node.text[:1000]}

Related entities: {len(related_nodes)}
Relationships: {len(edges)}

Provide a concise 2-3 sentence summary."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a concise summarization assistant.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=200,
            )

            summary = response.choices[0].message.content
            return summary if summary else "Could not generate summary."

        except Exception as e:
            logger.error(f"Failed to summarize node: {e}", exc_info=True)
            raise

    async def find_connections(self, node_id_a: int, node_id_b: int) -> Dict[str, Any]:
        """
        Find all paths connecting two nodes in the graph.

        Args:
            node_id_a: First node ID
            node_id_b: Second node ID

        Returns:
            Dict with connection paths and analysis
        """
        try:
            # Get nodes
            node_a = self.mg.get_node(node_id_a)
            node_b = self.mg.get_node(node_id_b)

            if not node_a or not node_b:
                return {"error": "One or both nodes not found"}

            # Get related nodes for both (depth 2)
            related_a, edges_a = self.mg.get_related_nodes(node_id_a, depth=2)
            related_b, edges_b = self.mg.get_related_nodes(node_id_b, depth=2)

            # Find common nodes
            ids_a = {n.id for n in related_a}
            ids_b = {n.id for n in related_b}
            common_ids = ids_a.intersection(ids_b)

            return {
                "node_a": {
                    "id": node_a.id,
                    "title": node_a.title,
                    "type": node_a.node_type,
                },
                "node_b": {
                    "id": node_b.id,
                    "title": node_b.title,
                    "type": node_b.node_type,
                },
                "common_nodes": len(common_ids),
                "connection_strength": (
                    len(common_ids) / max(len(ids_a), len(ids_b))
                    if ids_a or ids_b
                    else 0
                ),
            }

        except Exception as e:
            logger.error(f"Failed to find connections: {e}", exc_info=True)
            raise
