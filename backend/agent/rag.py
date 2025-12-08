"""
RAG Fusion Engine - Intelligent Context Aggregation & Ranking (STEP C)

This is the HEART of NAVI's organizational intelligence.

Combines and ranks context from multiple sources:
- Memory (user profile, tasks, interactions)
- Jira (issues, comments, activity)
- Slack (messages, threads, discussions)
- Confluence (documentation, specs)
- GitHub (PRs, commits, code)
- Zoom (meeting notes, transcripts)
- Workspace (active files, code selection)

Then ranks, compresses, and produces a compact context for the LLM.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


async def retrieve_rag_context(
    user_id: str, user_message: str, db=None, max_chunks: int = 8
) -> List[Dict[str, Any]]:
    """
    Main RAG fusion function.

    Combines memory + org data + workspace signals,
    ranks them by relevance, and returns top N context chunks.

    Args:
        user_id: User identifier
        user_message: Current user message
        db: Database session
        max_chunks: Maximum context chunks to return

    Returns:
        List of ranked context chunks with source and summary
    """

    logger.info(f"[RAG] Starting context retrieval for user={user_id}")

    try:
        # ---------------------------------------------------------
        # STAGE 1: Retrieve from all sources
        # ---------------------------------------------------------
        from backend.agent.memory_retriever import retrieve_memories
        from backend.agent.org_retriever import retrieve_org_context
        from backend.agent.workspace_retriever import retrieve_workspace_context

        memories = await retrieve_memories(user_id, user_message, db=db, limit=5)
        org = await retrieve_org_context(user_id, user_message, db=db)
        workspace = await retrieve_workspace_context(
            user_id, workspace_root=None, include_files=True, attachments=None
        )

        logger.info(
            f"[RAG] Retrieved: {len(memories.get('tasks', []))} task memories, "
            f"{len(org.get('jira_issues', []))} Jira issues, "
            f"{len(workspace.get('recent_files', []))} workspace files"
        )

        # ---------------------------------------------------------
        # STAGE 2: Flatten all context into chunks
        # ---------------------------------------------------------
        all_chunks = []

        # Add memory chunks
        for category, mems in memories.items():
            for mem in mems:
                all_chunks.append(
                    {
                        "source": f"memory/{category}",
                        "content": mem.get("content", ""),
                        "title": mem.get("title", ""),
                        "meta": mem.get("meta_json", {}),
                        "score": mem.get("similarity", 0.5),  # From pgvector
                    }
                )

        # Add Jira issue chunks
        for issue in org.get("jira_issues", []):
            all_chunks.append(
                {
                    "source": "jira",
                    "content": issue.get("content", ""),
                    "title": f"{issue.get('key')}: {issue.get('summary', '')}",
                    "meta": issue.get("meta", {}),
                    "score": 0.8,  # High priority for Jira
                }
            )

        # Add Slack thread chunks
        for thread in org.get("slack_threads", []):
            all_chunks.append(
                {
                    "source": "slack",
                    "content": thread.get("content", ""),
                    "title": thread.get("channel", ""),
                    "meta": thread,
                    "score": 0.6,
                }
            )

        # Add Confluence page chunks
        for page in org.get("confluence_pages", []):
            all_chunks.append(
                {
                    "source": "confluence",
                    "content": page.get("content", "")[:500],  # Truncate long docs
                    "title": page.get("title", ""),
                    "meta": page,
                    "score": 0.7,
                }
            )

        # Add workspace file chunks (small files only)
        for file in workspace.get("recent_files", [])[:3]:  # Top 3 files
            all_chunks.append(
                {
                    "source": "workspace",
                    "content": file.get("content", "")[:300],  # Truncate
                    "title": file.get("path", ""),
                    "meta": {"path": file.get("path")},
                    "score": 0.5,
                }
            )

        logger.info(f"[RAG] Flattened {len(all_chunks)} total chunks")

        # ---------------------------------------------------------
        # STAGE 3: Rank by relevance
        # ---------------------------------------------------------
        ranked = await _rank_chunks_by_relevance(all_chunks, user_message)

        # ---------------------------------------------------------
        # STAGE 4: Take top N and compress/summarize
        # ---------------------------------------------------------
        top_chunks = ranked[:max_chunks]

        summarized = await _summarize_chunks(top_chunks)

        logger.info(f"[RAG] Returning {len(summarized)} ranked context chunks")
        return summarized

    except Exception as e:
        logger.error(f"[RAG] Error in RAG fusion: {e}", exc_info=True)
        return []


async def _rank_chunks_by_relevance(
    chunks: List[Dict[str, Any]], query: str
) -> List[Dict[str, Any]]:
    """
    Rank chunks by relevance to query.

    For now, uses simple scoring based on:
    1. Pre-assigned scores (e.g., Jira=0.8, Memory=0.5)
    2. Keyword matching
    3. Length (shorter is better for context window)

    In future, can use:
    - LLM-based reranking
    - Embedding similarity
    - User feedback
    """

    query_lower = query.lower()
    query_words = set(query_lower.split())

    for chunk in chunks:
        content = chunk.get("content", "").lower()
        title = chunk.get("title", "").lower()

        # Keyword overlap score
        content_words = set(content.split())
        title_words = set(title.split())

        keyword_overlap = len(query_words & (content_words | title_words))

        # Boost score based on keyword overlap
        chunk["score"] += keyword_overlap * 0.1

        # Penalize very long chunks (they take up context window)
        if len(content) > 1000:
            chunk["score"] -= 0.2

    # Sort by score descending
    chunks.sort(key=lambda x: x.get("score", 0), reverse=True)

    return chunks


async def _summarize_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Summarize/compress chunks for context injection.

    For now, just truncates long content.
    In future, can use:
    - LLM-based summarization
    - Extractive summarization
    - Key phrase extraction
    """

    summarized = []

    for chunk in chunks:
        content = chunk.get("content", "")

        # Truncate long content
        if len(content) > 500:
            summary = content[:500] + "..."
        else:
            summary = content

        summarized.append(
            {
                "source": chunk.get("source", "unknown"),
                "title": chunk.get("title", ""),
                "summary": summary,
                "meta": chunk.get("meta", {}),
                "score": chunk.get("score", 0),
            }
        )

    return summarized


def format_rag_context_for_llm(rag_results: List[Dict[str, Any]]) -> str:
    """
    Format RAG results into a human-readable text block for LLM injection.

    This gets added to the system prompt.
    """

    if not rag_results:
        return ""

    lines = ["# RELEVANT CONTEXT\n\n"]

    for i, chunk in enumerate(rag_results, 1):
        source = chunk.get("source", "unknown")
        title = chunk.get("title", "")
        summary = chunk.get("summary", "")
        score = chunk.get("score", 0)

        lines.append(f"## Context {i}: {source.upper()}")
        if title:
            lines.append(f"**{title}**\n")
        lines.append(f"{summary}\n")
        lines.append(f"*(relevance: {score:.2f})*\n\n")

    return "\n".join(lines)
