"""
Memory Graph Service - Core Brain Module

This service provides the foundational intelligence layer for NAVI's organizational brain:
- Creates nodes for any organizational entity (Jira, Slack, PRs, code, etc)
- Creates edges to link related entities
- Embeds text content using OpenAI embeddings
- Performs semantic search across all organizational knowledge
- Supports graph traversal and relationship discovery

The memory graph enables NAVI to understand connections across:
- Jira issues → PRs → Code changes
- Slack discussions → Decisions → Documentation
- Meetings → Action items → Implementation
- Team members → Expertise → Projects
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
import tiktoken
from openai import AsyncOpenAI
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.models.memory_graph import MemoryNode, MemoryChunk, MemoryEdge

logger = logging.getLogger(__name__)


class MemoryGraphService:
    """
    Core service for managing the organizational memory graph.
    
    Handles node creation, edge linking, embedding generation, and semantic search.
    """
    
    def __init__(self, db: Session, org_id: str, user_id: str):
        """
        Initialize the memory graph service.
        
        Args:
            db: SQLAlchemy database session
            org_id: Organization identifier
            user_id: User identifier (for audit/tracking)
        """
        self.db = db
        self.org_id = org_id
        self.user_id = user_id
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.encoder = tiktoken.get_encoding("cl100k_base")
        
        # Configuration
        self.chunk_size = 200  # tokens per chunk
        self.embedding_model = "text-embedding-3-large"
        self.embedding_dimensions = 1536
    
    async def embed(self, text: str) -> List[float]:
        """
        Generate dense vector embedding for text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = await self.client.embeddings.create(
                model=self.embedding_model,
                input=text,
                dimensions=self.embedding_dimensions
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise
    
    async def add_node(
        self,
        node_type: str,
        text: str,
        title: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Add a new node to the memory graph with automatic chunking and embedding.
        
        Args:
            node_type: Type of node (jira_issue, slack_msg, pr, code, etc)
            text: Full text content of the node
            title: Optional title/heading
            meta: Optional metadata dictionary
            
        Returns:
            Node ID of the created node
        """
        try:
            # Create the memory node
            node = MemoryNode(
                org_id=self.org_id,
                node_type=node_type,
                title=title,
                text=text,
                meta_json=meta or {}
            )
            self.db.add(node)
            self.db.flush()  # Get node.id without committing
            
            logger.info(f"Created memory node: id={node.id}, type={node_type}, title={title}")
            
            # Chunk the text and create embeddings
            tokens = self.encoder.encode(text)
            chunks = [
                tokens[i:i + self.chunk_size] 
                for i in range(0, len(tokens), self.chunk_size)
            ]
            
            logger.info(f"Chunking text into {len(chunks)} chunks for node {node.id}")
            
            for idx, token_block in enumerate(chunks):
                block_text = self.encoder.decode(token_block)
                embedding = await self.embed(block_text)
                
                # Convert embedding to PostgreSQL array format
                embedding_str = f"[{','.join(map(str, embedding))}]"
                
                chunk = MemoryChunk(
                    node_id=node.id,
                    chunk_index=idx,
                    chunk_text=block_text,
                    embedding=embedding_str
                )
                self.db.add(chunk)
            
            self.db.commit()
            logger.info(f"Successfully created node {node.id} with {len(chunks)} chunks")
            
            return node.id  # type: ignore
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add node: {e}", exc_info=True)
            raise
    
    def add_edge(
        self,
        from_id: int,
        to_id: int,
        edge_type: str,
        weight: float = 1.0,
        meta: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Add an edge between two nodes in the memory graph.
        
        Args:
            from_id: Source node ID
            to_id: Target node ID
            edge_type: Type of relationship (mentions, documents, implements, etc)
            weight: Edge weight (0-10), default 1.0
            meta: Optional metadata dictionary
            
        Returns:
            Edge ID of the created edge
        """
        try:
            edge = MemoryEdge(
                org_id=self.org_id,
                from_id=from_id,
                to_id=to_id,
                edge_type=edge_type,
                weight=weight,
                meta_json=meta or {}
            )
            self.db.add(edge)
            self.db.commit()
            
            logger.info(f"Created edge: {from_id} --{edge_type}--> {to_id}")
            
            return edge.id  # type: ignore
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add edge: {e}", exc_info=True)
            raise
    
    async def search(
        self,
        query: str,
        limit: int = 10,
        node_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Semantic search across the memory graph using vector similarity.
        
        Args:
            query: Natural language search query
            limit: Maximum number of results to return
            node_types: Optional filter by node types
            
        Returns:
            List of dicts with node info and similarity scores
        """
        try:
            # Generate embedding for the query
            query_embed = await self.embed(query)
            query_embed_str = f"[{','.join(map(str, query_embed))}]"
            
            # Build the SQL query
            sql = """
            SELECT DISTINCT ON (mc.node_id)
                mc.node_id,
                mn.node_type,
                mn.title,
                mn.text,
                mn.meta_json,
                1 - (mc.embedding <=> :embedding::vector) AS score
            FROM memory_chunk mc
            JOIN memory_node mn ON mc.node_id = mn.id
            WHERE mn.org_id = :org_id
            """
            
            params = {
                "embedding": query_embed_str,
                "org_id": self.org_id,
                "limit": limit
            }
            
            # Add node type filter if specified
            if node_types:
                sql += " AND mn.node_type = ANY(:node_types)"
                params["node_types"] = node_types
            
            sql += """
            ORDER BY mc.node_id, mc.embedding <=> :embedding::vector
            LIMIT :limit
            """
            
            # Execute the query
            result = self.db.execute(text(sql), params)
            rows = result.fetchall()
            
            # Format results
            results = [
                {
                    "id": row.node_id,
                    "node_type": row.node_type,
                    "title": row.title,
                    "text": row.text,
                    "meta_json": row.meta_json,
                    "score": float(row.score)
                }
                for row in rows
            ]
            
            logger.info(f"Search query '{query}' returned {len(results)} results")
            
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            raise
    
    def get_node(self, node_id: int) -> Optional[MemoryNode]:
        """Get a node by ID."""
        return self.db.query(MemoryNode).filter(
            MemoryNode.id == node_id,
            MemoryNode.org_id == self.org_id
        ).first()
    
    def get_related_nodes(
        self,
        node_id: int,
        edge_types: Optional[List[str]] = None,
        depth: int = 1
    ) -> Tuple[List[MemoryNode], List[MemoryEdge]]:
        """
        Get nodes related to a given node via edges.
        
        Args:
            node_id: Starting node ID
            edge_types: Optional filter by edge types
            depth: How many hops to traverse (1-3)
            
        Returns:
            Tuple of (related_nodes, edges)
        """
        try:
            # Get outgoing edges
            query = self.db.query(MemoryEdge).filter(
                MemoryEdge.from_id == node_id,
                MemoryEdge.org_id == self.org_id
            )
            
            if edge_types:
                query = query.filter(MemoryEdge.edge_type.in_(edge_types))
            
            edges = query.all()
            
            # Get related node IDs
            related_ids = [e.to_id for e in edges]
            
            # Get the nodes
            nodes = self.db.query(MemoryNode).filter(
                MemoryNode.id.in_(related_ids)
            ).all() if related_ids else []
            
            logger.info(f"Found {len(nodes)} related nodes for node {node_id}")
            
            return nodes, edges
            
        except Exception as e:
            logger.error(f"Failed to get related nodes: {e}", exc_info=True)
            raise
    
    def delete_node(self, node_id: int) -> bool:
        """
        Delete a node and all its chunks and edges.
        
        Args:
            node_id: Node ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        try:
            node = self.get_node(node_id)
            if not node:
                return False
            
            self.db.delete(node)
            self.db.commit()
            
            logger.info(f"Deleted node {node_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete node: {e}", exc_info=True)
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the memory graph."""
        try:
            node_count = self.db.query(MemoryNode).filter(
                MemoryNode.org_id == self.org_id
            ).count()
            
            edge_count = self.db.query(MemoryEdge).filter(
                MemoryEdge.org_id == self.org_id
            ).count()
            
            # Get node type distribution
            type_dist = self.db.execute(
                text("""
                    SELECT node_type, COUNT(*) as count
                    FROM memory_node
                    WHERE org_id = :org_id
                    GROUP BY node_type
                """),
                {"org_id": self.org_id}
            ).fetchall()
            
            return {
                "total_nodes": node_count,
                "total_edges": edge_count,
                "node_types": {row.node_type: row.count for row in type_dist},
                "org_id": self.org_id
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}", exc_info=True)
            raise
