# Step 3: Unified RAG Search - Quick Start

## What's New

Step 3 adds **Retrieval-Augmented Generation (RAG)** to NAVI, enabling intelligent context retrieval from organizational memory.

**NAVI can now answer questions like:**
- "What's the dev environment URL?"
- "Any Confluence pages for LAB-158?"
- "Where did we discuss barcode overrides?"

## Files Changed/Added

### New Files
- `backend/api/navi_search.py` - Search API endpoint (220 lines)
- `backend/services/citation_formatter.py` - Citation formatting utility
- `docs/step-3-rag-search.md` - Complete documentation
- `scripts/test_step3_rag.py` - Test suite

### Modified Files
- `backend/api/navi.py` - Integrated memory search into chat
- `backend/api/main.py` - Registered navi_search router

## Quick Test

### 1. Start Backend

```bash
python main.py
```

### 2. Run Test Suite

```bash
python scripts/test_step3_rag.py
```

### 3. Create Test Memory (via org sync from Step 2)

```bash
# Sync Jira issues
curl -X POST http://localhost:8787/api/org/sync/jira \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "project_key": "LAB",
    "max_issues": 10
  }'

# Sync Confluence pages
curl -X POST http://localhost:8787/api/org/sync/confluence \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "space_key": "DEV",
    "max_pages": 5
  }'
```

### 4. Test Search

```bash
# Direct search
curl -X POST http://localhost:8787/api/navi/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "environment URL",
    "user_id": "test-user",
    "limit": 5
  }'

# Via NAVI chat (use VS Code extension or curl)
curl -X POST http://localhost:8787/api/navi/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What'\''s the dev environment URL?",
    "model": "gpt-4"
  }'
```

## How It Works

1. **User asks question** → NAVI receives message
2. **Memory search** → Query embedded, pgvector finds similar memories
3. **Context injection** → Top results formatted and added to LLM prompt
4. **Enhanced response** → NAVI answers with citations

## Architecture

```
User Question
    ↓
NAVI Chat (/api/navi/chat)
    ↓
search_memory() ← pgvector similarity search
    ↓
format_context_for_llm() ← citation formatting
    ↓
OpenAI LLM (with injected context)
    ↓
Response with citations
```

## Memory Categories

- **profile**: User preferences, settings
- **workspace**: Repos, environments, tools
- **task**: Jira issues, discussions
- **interaction**: Past conversations

## Configuration

Ensure these are set in `.env`:

```bash
OPENAI_API_KEY=sk-...              # For embeddings and LLM
JIRA_BASE_URL=https://...
JIRA_EMAIL=...
JIRA_API_TOKEN=...
CONFLUENCE_BASE_URL=https://...
CONFLUENCE_EMAIL=...
CONFLUENCE_API_TOKEN=...
```

## Verification Checklist

- [ ] Backend starts without errors
- [ ] Test suite runs successfully
- [ ] Search endpoint returns results (`/api/navi/search`)
- [ ] Stats endpoint shows memory counts (`/api/navi/search/stats`)
- [ ] Health check passes (`/api/navi/search/health`)
- [ ] NAVI chat includes memory context
- [ ] Citations appear in responses

## Troubleshooting

**No search results?**
- Run org sync to create memory first
- Check `GET /api/navi/search/stats` for memory counts
- Lower `min_importance` threshold

**NAVI not using context?**
- Check logs for "Retrieved N memory items"
- Test search endpoint directly
- Verify OpenAI API key

**Import errors?**
- Ensure Step 2 completed (navi_memory_service exists)
- Check citation_formatter.py exists
- Run migration: `alembic upgrade head`

## Next Steps

After Step 3 is working:
1. Populate memory via org sync (Step 2 endpoints)
2. Test real-world queries in VS Code extension
3. Monitor search quality and adjust ranking
4. Consider Slack integration (Step 4?)

## Complete Documentation

See [docs/step-3-rag-search.md](docs/step-3-rag-search.md) for:
- Detailed architecture
- API reference with examples
- Performance optimization tips
- Troubleshooting guide
- Future enhancements

## Status

**Step 3: COMPLETE ✅**

- [x] Search API endpoint (`navi_search.py`)
- [x] Citation formatter utility
- [x] NAVI chat integration
- [x] Router registration
- [x] Test suite
- [x] Documentation

Ready to commit and push!
