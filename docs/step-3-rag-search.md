# Step 3: Unified RAG Search System

## Overview

The Unified RAG (Retrieval-Augmented Generation) Search System enables NAVI to access long-term memory from organizational systems (Jira, Confluence, Slack) and conversational context to provide intelligent, context-aware responses.

## Architecture

```
┌─────────────────────┐
│   VS Code NAVI      │
│   Extension         │
└──────────┬──────────┘
           │
           │ /api/navi/chat
           ▼
┌─────────────────────┐
│  NAVI Chat          │
│  (navi.py)          │
└──────────┬──────────┘
           │
           │ search_memory()
           ▼
┌─────────────────────┐
│  Memory Service     │
│  (Step 2)           │
└──────────┬──────────┘
           │
           │ pgvector similarity
           ▼
┌─────────────────────┐
│  navi_memory table  │
│  (PostgreSQL)       │
└─────────────────────┘
```

## Components

### 1. Search API (`backend/api/navi_search.py`)

**Endpoints:**

- `POST /api/navi/search` - Unified semantic search
- `GET /api/navi/search/stats` - Memory statistics
- `GET /api/navi/search/health` - Service health check

**Request Example:**
```json
{
  "query": "What's the dev environment URL?",
  "user_id": "user-123",
  "categories": ["workspace", "task"],
  "limit": 8,
  "min_importance": 0.3
}
```

**Response Example:**
```json
{
  "results": [
    {
      "id": "uuid",
      "category": "workspace",
      "scope": "global",
      "title": "Development Environment",
      "content": "The dev environment URL is https://dev.example.com...",
      "similarity": 0.87,
      "importance": 0.8,
      "metadata": {
        "source": "confluence",
        "page_id": "123"
      }
    }
  ],
  "total": 1
}
```

### 2. Citation Formatter (`backend/services/citation_formatter.py`)

Formats search results into LLM-ready context with citations.

**Functions:**
- `format_context_for_llm()` - Creates token-optimized context
- `format_citations()` - Pretty-print citations for display
- `format_inline_citation()` - Generates `[1]`, `[2]` style references

### 3. NAVI Integration (`backend/api/navi.py`)

Enhanced chat endpoint that:
1. Retrieves relevant memory via `search_memory()`
2. Formats context via `format_context_for_llm()`
3. Injects context into LLM prompt
4. Returns response with source citations

## Usage Examples

### Example 1: Environment Configuration

**User:** "What's the dev environment URL?"

**NAVI Process:**
1. Search memory: `query="dev environment URL", categories=["workspace"]`
2. Find Confluence page: "Development Environment Setup"
3. Extract URL: `https://dev.example.com`
4. Respond with citation: "The dev environment is at https://dev.example.com [1]"

### Example 2: Issue Context

**User:** "Any useful Confluence pages for LAB-158?"

**NAVI Process:**
1. Search memory: `query="LAB-158 confluence", scope="LAB-158"`
2. Find related pages from Jira sync
3. Return formatted list with links

### Example 3: Historical Discussions

**User:** "Where did we discuss barcode overrides?"

**NAVI Process:**
1. Search memory: `query="barcode override discussion"`
2. Find interaction/task memories
3. Return context: "We discussed this in Slack on [date]..."

## Memory Categories

| Category | Scope | Content Type | Example |
|----------|-------|--------------|---------|
| `profile` | `{user_id}` | User preferences, settings | "Prefers TypeScript over JavaScript" |
| `workspace` | `global` or `{workspace_id}` | Repos, environments, tools | "Dev URL: https://dev.example.com" |
| `task` | `{issue_key}` | Jira issues, discussions | "LAB-158: Barcode override feature" |
| `interaction` | `{user_id}` or `global` | Past conversations | "Previously asked about API auth" |

## Ranking Algorithm

Results ranked by:
```
score = (similarity * 0.7) + (importance * 0.3)
```

Where:
- **similarity**: Cosine similarity from pgvector (0.0 to 1.0)
- **importance**: User-defined weight (0.0 to 1.0)

Higher scores appear first.

## Integration with Step 2

Step 3 builds on Step 2's memory infrastructure:

**Step 2 (Memory Foundation):**
- `navi_memory` table with pgvector
- Jira/Confluence clients
- Org ingestor with LLM summarization
- Sync endpoints

**Step 3 (Search & RAG):**
- Semantic search API
- Citation formatting
- NAVI chat integration
- Context injection

## Configuration

Required environment variables:

```bash
# OpenAI (for embeddings)
OPENAI_API_KEY=sk-...

# Jira/Confluence (from Step 2)
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@example.com
JIRA_API_TOKEN=your-token

CONFLUENCE_BASE_URL=https://your-domain.atlassian.net/wiki
CONFLUENCE_EMAIL=your-email@example.com
CONFLUENCE_API_TOKEN=your-token
```

## Testing

### 1. Test Search Endpoint

```bash
python scripts/test_step3_rag.py
```

### 2. Manual Testing

```bash
# Search for memories
curl -X POST http://localhost:8787/api/navi/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "dev environment",
    "user_id": "test-user",
    "limit": 5
  }'

# Get stats
curl http://localhost:8787/api/navi/search/stats?user_id=test-user

# Health check
curl http://localhost:8787/api/navi/search/health
```

### 3. Test NAVI Integration

Use VS Code extension to chat with NAVI:
- "What's the dev environment URL?"
- "Any pages about LAB-158?"
- "Where did we discuss X?"

## Performance Considerations

### Query Optimization

- Use category filters to reduce search space
- Set appropriate `min_importance` threshold
- Limit results (8-10 is optimal for LLM context)

### Embedding Caching

- Embeddings cached in `navi_memory.embedding` column
- No re-computation on search
- Only computed once during ingestion

### Token Management

- `format_context_for_llm()` truncates long content
- Prioritizes high-similarity results
- Keeps context under 3000 tokens

## Troubleshooting

### Search returns no results

1. Check if memory exists: `GET /api/navi/search/stats`
2. Verify OpenAI API key configured
3. Run org sync: `POST /api/org/sync/jira`
4. Lower `min_importance` threshold

### Memory context not in NAVI responses

1. Check logs for memory search errors
2. Verify `search_memory()` returns results
3. Test search endpoint directly
4. Check OpenAI API usage limits

### Relevance issues

1. Adjust similarity/importance weights
2. Improve memory titles and summaries
3. Use more specific search queries
4. Filter by category/scope

## Future Enhancements

- [ ] User feedback loop (thumbs up/down on results)
- [ ] Automatic memory pruning (remove stale items)
- [ ] Multi-hop reasoning (combine multiple memories)
- [ ] Context window optimization (dynamic token allocation)
- [ ] Slack integration (Step 4?)

## Related Documentation

- [Step 2: Jira + Confluence Integration](../alembic/versions/0018_navi_memory.py)
- [NAVI Memory Service](../backend/services/navi_memory_service.py)
- [Citation Formatter](../backend/services/citation_formatter.py)

## API Reference

See [navi_search.py](../backend/api/navi_search.py) for complete API documentation with examples.
