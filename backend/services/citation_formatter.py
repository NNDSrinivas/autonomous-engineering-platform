"""Citation Formatting for NAVI RAG System

Utilities for formatting search results as citations that NAVI
can include in chat responses.
"""

from typing import List, Dict, Any
import structlog

logger = structlog.get_logger(__name__)


def format_citation(memory: Dict[str, Any], index: int = 1) -> str:
    """
    Format a single memory as a citation for NAVI's response.

    Args:
        memory: Memory dictionary with keys: category, title, content, meta, similarity
        index: Citation number (e.g., [1], [2])

    Returns:
        Formatted citation string

    Example output:
        [1] **LAB-158: Specimen Collection Dual-Write** (Jira, similarity: 0.92)
            Status: In Progress | Priority: High
            Summary: Implement dual-write pattern for ALVA...
    """
    category = memory.get("category", "unknown")
    title = memory.get("title", "Untitled")
    content = memory.get("content", "")
    meta = memory.get("meta", {})
    similarity = memory.get("similarity", 0.0)

    # Truncate content for citation
    content_preview = content[:200] + "..." if len(content) > 200 else content

    # Build citation header
    citation = f"[{index}] **{title}**"

    # Add source info
    source_parts = []
    if category == "task":
        source_parts.append("Jira")
    elif category == "workspace":
        source_parts.append("Confluence")
        if "space" in meta:
            source_parts.append(f"Space: {meta['space']}")
    elif category == "interaction":
        source_parts.append("Chat History")
    elif category == "profile":
        source_parts.append("User Profile")

    source_parts.append(f"similarity: {similarity:.2f}")
    citation += f" ({', '.join(source_parts)})\n"

    # Add metadata if available
    if category == "task" and meta:
        metadata_line = "    "
        if "status" in meta:
            metadata_line += f"Status: {meta['status']}"
        if "priority" in meta:
            metadata_line += f" | Priority: {meta['priority']}"
        if metadata_line.strip():
            citation += metadata_line + "\n"

    # Add content preview
    citation += f"    {content_preview}\n"

    return citation


def format_citations_block(memories: List[Dict[str, Any]]) -> str:
    """
    Format multiple memories as a citations block.

    Args:
        memories: List of memory dictionaries

    Returns:
        Formatted citations block as markdown

    Example output:
        ### Relevant Knowledge

        [1] **LAB-158: Specimen Collection** (Jira, similarity: 0.92)
            Status: In Progress | Priority: High
            Summary: Implement dual-write pattern...

        [2] **Dual-Write Pattern Guide** (Confluence, Space: ENG, similarity: 0.89)
            Comprehensive guide for implementing...
    """
    if not memories:
        return ""

    citations = ["### Relevant Knowledge\n"]

    for idx, memory in enumerate(memories, 1):
        citation = format_citation(memory, index=idx)
        citations.append(citation)

    return "\n".join(citations)


def format_compact_citation(memory: Dict[str, Any]) -> str:
    """
    Format a memory as a compact one-line citation.

    Args:
        memory: Memory dictionary

    Returns:
        Compact citation string

    Example output:
        [Jira LAB-158] Implement dual-write pattern (similarity: 0.92)
    """
    category = memory.get("category", "unknown")
    title = memory.get("title", "Untitled")
    scope = memory.get("scope")
    similarity = memory.get("similarity", 0.0)

    # Build compact format
    parts = []

    if category == "task" and scope:
        parts.append(f"Jira {scope}")
    elif category == "workspace":
        meta = memory.get("meta", {})
        if "space" in meta:
            parts.append(f"Confluence:{meta['space']}")
        else:
            parts.append("Confluence")
    else:
        parts.append(category.title())

    parts.append(title)
    parts.append(f"similarity: {similarity:.2f}")

    return f"[{parts[0]}] {parts[1]} ({parts[2]})"


def format_citations_for_llm(memories: List[Dict[str, Any]]) -> str:
    """
    Format memories as context for LLM system prompt.

    This creates a structured block that can be injected into
    the system prompt to give NAVI grounded knowledge.

    Args:
        memories: List of memory dictionaries

    Returns:
        Formatted context block for LLM

    Example output:
        ## Retrieved Context

        **Source 1: Jira LAB-158**
        Title: Specimen Collection Dual-Write
        Content: Implement dual-write pattern for ALVA...
        Tags: {"source": "jira", "status": "In Progress"}

        **Source 2: Confluence Engineering Space**
        Title: Dual-Write Pattern Guide
        Content: Comprehensive guide...
        Tags: {"source": "confluence", "space": "ENG"}
    """
    if not memories:
        return ""

    context_blocks = ["## Retrieved Context\n"]

    for idx, memory in enumerate(memories, 1):
        category = memory.get("category", "unknown")
        scope = memory.get("scope")
        title = memory.get("title", "Untitled")
        content = memory.get("content", "")
        meta = memory.get("meta", {})

        # Build source label
        if category == "task" and scope:
            source_label = f"Jira {scope}"
        elif category == "workspace" and "space" in meta:
            source_label = f"Confluence {meta['space']} Space"
        else:
            source_label = category.title()

        block = f"**Source {idx}: {source_label}**\n"
        block += f"Title: {title}\n"
        block += f"Content: {content}\n"

        if meta:
            block += f"Tags: {meta}\n"

        context_blocks.append(block)

    return "\n".join(context_blocks)


def extract_source_urls(memories: List[Dict[str, Any]]) -> List[str]:
    """
    Extract URLs from memory metadata for citation links.

    Args:
        memories: List of memory dictionaries

    Returns:
        List of URLs found in metadata
    """
    urls = []

    for memory in memories:
        meta = memory.get("meta", {})

        # Check for URL in various metadata fields
        if "url" in meta:
            urls.append(meta["url"])
        elif "link" in meta:
            urls.append(meta["link"])
        elif "page_url" in meta:
            urls.append(meta["page_url"])

    return urls


def format_search_summary(query: str, result_count: int, categories: List[str]) -> str:
    """
    Format a summary of search results for NAVI to use.

    Args:
        query: Original search query
        result_count: Number of results found
        categories: Categories that were searched

    Returns:
        Summary string

    Example output:
        I searched for "dev environment URL" across Confluence and found 3 relevant results.
    """
    if result_count == 0:
        return f'I searched for "{query}" but didn\'t find any relevant memories.'

    category_names = {
        "task": "Jira",
        "workspace": "Confluence",
        "profile": "your profile",
        "interaction": "our chat history",
    }

    readable_cats = [category_names.get(cat, cat) for cat in categories]

    if len(readable_cats) == 1:
        location = readable_cats[0]
    elif len(readable_cats) == 2:
        location = f"{readable_cats[0]} and {readable_cats[1]}"
    else:
        location = ", ".join(readable_cats[:-1]) + f", and {readable_cats[-1]}"

    result_word = "result" if result_count == 1 else "results"

    return f'I searched for "{query}" across {location} and found {result_count} relevant {result_word}.'
