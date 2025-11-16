# Step 2: Jira + Confluence Integration

**🎯 Goal**: Give NAVI long-term memory of your Jira tasks and Confluence documentation.

**✅ Status**: Complete

---

## What Was Built

### 1. Database Schema
- **Table**: `navi_memory` with pgvector support
- **Migration**: `alembic/versions/0018_navi_memory.py`
- **Indexes**: User, category, scope, importance, and HNSW vector index

### 2. Integration Clients
- **Jira**: Async client with email + API token auth
- **Confluence**: Async client with page fetching and HTML parsing

### 3. Memory Service
- Store memories with automatic embedding generation
- Semantic search using pgvector cosine similarity
- Category-based retrieval (profile, workspace, task, interaction)

### 4. Organization Ingestor
- Fetch Jira issues and summarize with LLM
- Fetch Confluence pages and convert HTML to text
- Store compressed summaries in memory

### 5. API Endpoints
- `POST /api/org/sync/jira` - Sync Jira issues
- `POST /api/org/sync/confluence` - Sync Confluence pages
- `GET /api/org/sync/status` - Check service health

---

## Quick Start

### 1. Configure Credentials

Add to your `.env` file:

```bash
# Jira
AEP_JIRA_BASE_URL=https://your-domain.atlassian.net
AEP_JIRA_EMAIL=service-account@yourcompany.com
AEP_JIRA_API_TOKEN=your_jira_api_token

# Confluence
AEP_CONFLUENCE_BASE_URL=https://your-domain.atlassian.net/wiki
AEP_CONFLUENCE_EMAIL=service-account@yourcompany.com
AEP_CONFLUENCE_API_TOKEN=your_confluence_api_token
```

### 2. Run Migration

```bash
alembic upgrade head
```

### 3. Start Backend

```bash
uvicorn backend.api.main:app --reload --port 8787 --env-file .env
```

### 4. Sync Your Data

```bash
# Sync Jira issues
curl -X POST http://localhost:8787/api/org/sync/jira \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-email@example.com",
    "max_issues": 10
  }'

# Sync Confluence pages
curl -X POST http://localhost:8787/api/org/sync/confluence \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-email@example.com",
    "space_key": "ENG",
    "limit": 20
  }'
```

---

## Architecture

### Two Memory Systems

1. **Memory Graph** (existing):
   - Organization-level artifact relationships
   - Tables: `memory_node`, `memory_edge`
   - Use case: Timeline reconstruction, causality

2. **NAVI Memory** (new):
   - User-level conversational context
   - Table: `navi_memory`
   - Use case: Task-aware conversations

### Data Flow

```
Jira/Confluence → Ingestor (LLM) → navi_memory (pgvector) → NAVI Chat
```

---

## Files Created

```
alembic/versions/
  └── 0018_navi_memory.py              # Database migration

backend/integrations/
  ├── jira_client.py                   # Jira API client
  └── confluence_client.py             # Confluence API client

backend/services/
  ├── navi_memory_service.py           # Memory CRUD operations
  └── org_ingestor.py                  # Ingestion + summarization

backend/api/
  └── org_sync.py                      # REST API endpoints

scripts/
  └── test_step2_setup.py              # Setup verification script

docs/
  └── step-2-org-integrations.md       # Full documentation

.env.example                           # Updated with Jira/Confluence vars
```

---

## Testing

Run the setup verification script:

```bash
python scripts/test_step2_setup.py
```

Expected output:
```
✓ PASS: Imports
✓ PASS: Migration
✓ PASS: .env.example
✓ PASS: Router Registration

🎉 All tests passed!
```

---

## What NAVI Can Do Now

### Before Integration
```
User: What's my current task?
NAVI: I don't have access to your tasks yet.
```

### After Integration
```
User: What's my current task?
NAVI: You're working on ENG-102: Implement dual-write pattern.
      Status: In Progress
      Priority: High
      
      Key requirements:
      - Use Postgres + Redis dual-write
      - Maintain consistency with CDC
      
      Related docs: Found "Dual-Write Pattern Guide" in Confluence...
```

---

## Next Steps

### Step 3: RAG Search API
Build unified search across all memory:
- `/api/navi/search?q=dev environment URL`
- Ranking by similarity + importance
- Citation formatting

### Step 4: Slack/Teams Integration
- Meeting transcripts → memories
- Sprint discussions → workspace context

### Step 5: Startup Greeting
- "Good morning Srinivas!"
- Daily task summary
- Meeting reminders

---

## Troubleshooting

### "JiraClient is not configured"
Check `.env` has `AEP_JIRA_BASE_URL`, `AEP_JIRA_EMAIL`, `AEP_JIRA_API_TOKEN`

### "Failed to generate embedding"
Verify `OPENAI_API_KEY` is set in `.env`

### "Confluence GET failed: 401"
- Verify API token is valid
- Check email matches Atlassian account
- Ensure read access to space

---

## Documentation

Full documentation: [`docs/step-2-org-integrations.md`](./docs/step-2-org-integrations.md)

---

**Built by**: GitHub Copilot + Claude Sonnet 4.5  
**Date**: November 16, 2025  
**Status**: ✅ Complete and tested
