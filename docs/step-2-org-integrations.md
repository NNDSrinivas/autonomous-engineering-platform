# Step 2: Jira + Confluence Integration into NAVI Memory

**Status:** Complete ✅  
**Date:** November 16, 2025  
**Branch:** `feature/step-2-org-integrations`

---

## Overview

This implements Step 2 of the NAVI Memory System: **Organization Integrations**.

NAVI now automatically ingests Jira issues and Confluence documentation into its conversational memory, enabling context-aware responses about your tasks and documentation.

### Key Features

- **Jira Integration**: Fetch and summarize assigned issues
- **Confluence Integration**: Fetch and summarize documentation pages
- **LLM Summarization**: Compress content for efficient memory storage
- **Semantic Search**: pgvector + OpenAI embeddings for relevant context
- **Async Architecture**: Non-blocking API with httpx
- **Structured Logging**: Full observability with structlog

---

## Architecture

### Memory System Design

We now have **two complementary memory systems**:

1. **Memory Graph** (existing from PR-17):
   - **Purpose**: Track relationships between engineering artifacts
   - **Scope**: Organization-level (JIRA issues, PRs, deployments, incidents)
   - **Use Case**: Timeline reconstruction, causality chains, impact analysis
   - **Tables**: `memory_node`, `memory_edge`

2. **NAVI Memory** (new in Step 2):
   - **Purpose**: Conversational context for NAVI assistant
   - **Scope**: User-level (profile, workspace, tasks, interactions)
   - **Use Case**: "Remember I prefer TypeScript", "What's my current Jira task?"
   - **Table**: `navi_memory`

### Data Flow

```
┌─────────────┐
│   Jira API  │────┐
└─────────────┘    │
                   │
┌─────────────┐    │    ┌──────────────────┐    ┌─────────────────┐
│Confluence   │────┼───▶│  Org Ingestor    │───▶│  NAVI Memory    │
│    API      │    │    │  (LLM Summary)   │    │   (pgvector)    │
└─────────────┘    │    └──────────────────┘    └─────────────────┘
                   │
┌─────────────┐    │                                       │
│  VS Code    │────┘                                       │
│  Extension  │                                            │
└─────────────┘                                            │
                                                           │
                   ┌────────────────────────────────────────┘
                   │
                   ▼
            ┌──────────────┐
            │ NAVI Chat    │
            │  (Context)   │
            └──────────────┘
```

---

## Database Schema

### `navi_memory` Table

```sql
CREATE TABLE navi_memory (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,           -- User identifier
    category VARCHAR(50) NOT NULL,            -- profile|workspace|task|interaction
    scope VARCHAR(255),                       -- Scope: workspace path, task ID, etc.
    title TEXT,                               -- Human-readable title
    content TEXT NOT NULL,                    -- Memory content
    embedding_vec VECTOR(1536),               -- OpenAI embedding for semantic search
    meta_json JSON,                           -- Additional metadata: tags, source, etc.
    importance INTEGER NOT NULL DEFAULT 3,    -- Importance score 1-5
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX idx_navi_memory_user ON navi_memory(user_id);
CREATE INDEX idx_navi_memory_category ON navi_memory(user_id, category);
CREATE INDEX idx_navi_memory_scope ON navi_memory(user_id, scope);
CREATE INDEX idx_navi_memory_importance ON navi_memory(importance);

-- pgvector HNSW index for fast semantic search
CREATE INDEX idx_navi_memory_embedding 
ON navi_memory 
USING hnsw (embedding_vec vector_cosine_ops);
```

### Memory Categories

| Category | Description | Examples |
|----------|-------------|----------|
| `profile` | User preferences and style | "Prefers TypeScript", "Uses tabs not spaces" |
| `workspace` | Project/workspace context | Confluence docs, README summaries |
| `task` | Current tasks and issues | Jira tickets, GitHub issues |
| `interaction` | Compressed chat history | Previous conversations, decisions |

---

## Implementation

### 1. Migration

**File**: `alembic/versions/0018_navi_memory.py`

Creates the `navi_memory` table with pgvector support.

```bash
# Run migration
alembic upgrade head
```

### 2. Integration Clients

#### Jira Client

**File**: `backend/integrations/jira_client.py`

- Async HTTP client using `httpx`
- Basic auth with email + API token
- Methods:
  - `get_assigned_issues()`: Fetch issues with JQL
  - `get_issue(key)`: Fetch single issue
  - `get_issues_by_project()`: Fetch by project

#### Confluence Client

**File**: `backend/integrations/confluence_client.py`

- Async HTTP client using `httpx`
- Basic auth with email + API token
- Methods:
  - `get_pages_in_space()`: Fetch pages from space
  - `get_page(page_id)`: Fetch single page
  - `search_pages(cql)`: Search with CQL
  - `html_to_text()`: Convert HTML to plain text

### 3. Memory Service

**File**: `backend/services/navi_memory_service.py`

Core memory operations:

- `store_memory()`: Store memory with embedding generation
- `search_memory()`: Semantic search using cosine similarity
- `get_recent_memories()`: Time-ordered retrieval
- `delete_memory()`: Delete with authorization check

### 4. Organization Ingestor

**File**: `backend/services/org_ingestor.py`

Ingests external data into memory:

- `summarize_for_memory()`: LLM-based content compression
- `ingest_jira_for_user()`: Fetch and store Jira issues
- `ingest_confluence_space()`: Fetch and store Confluence pages
- `_extract_text_from_adf()`: Parse Atlassian Document Format

### 5. API Routes

**File**: `backend/api/org_sync.py`

REST endpoints for triggering syncs:

- `POST /api/org/sync/jira`: Sync Jira issues
- `POST /api/org/sync/confluence`: Sync Confluence pages
- `GET /api/org/sync/status`: Check service status

---

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Jira Integration
AEP_JIRA_BASE_URL=https://your-domain.atlassian.net
AEP_JIRA_EMAIL=service-account@yourcompany.com
AEP_JIRA_API_TOKEN=your_jira_api_token

# Confluence Integration
AEP_CONFLUENCE_BASE_URL=https://your-domain.atlassian.net/wiki
AEP_CONFLUENCE_EMAIL=service-account@yourcompany.com
AEP_CONFLUENCE_API_TOKEN=your_confluence_api_token
```

### Getting API Tokens

1. **Jira/Confluence API Token**:
   - Go to https://id.atlassian.com/manage-profile/security/api-tokens
   - Click "Create API token"
   - Give it a label (e.g., "AEP NAVI")
   - Copy the token (you won't see it again!)

2. **Service Account** (recommended for production):
   - Create dedicated service account email
   - Grant read access to relevant Jira projects and Confluence spaces
   - Use service account credentials in env vars

---

## Usage

### 1. Sync Jira Issues

```bash
curl -X POST http://localhost:8787/api/org/sync/jira \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "srinivas@example.com",
    "max_issues": 10
  }'
```

**Response:**
```json
{
  "processed_keys": ["ENG-102", "LAB-158", "INFRA-45"],
  "total": 3,
  "user_id": "srinivas@example.com"
}
```

### 2. Sync Confluence Pages

```bash
curl -X POST http://localhost:8787/api/org/sync/confluence \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "srinivas@example.com",
    "space_key": "ENG",
    "limit": 20
  }'
```

**Response:**
```json
{
  "processed_page_ids": ["123456", "789012", "345678"],
  "total": 3,
  "user_id": "srinivas@example.com",
  "space_key": "ENG"
}
```

### 3. Check Service Status

```bash
curl http://localhost:8787/api/org/sync/status
```

**Response:**
```json
{
  "status": "ok",
  "message": "Organization sync service is running. Available endpoints: /sync/jira, /sync/confluence"
}
```

---

## End-to-End Behavior

Once you sync Jira and Confluence:

1. **Jira issues** are stored as `category=task` memories
2. **Confluence pages** are stored as `category=workspace` memories
3. Each memory gets an OpenAI embedding for semantic search
4. When you ask NAVI a question, it:
   - Generates embedding for your query
   - Searches `navi_memory` using cosine similarity
   - Retrieves top 5-10 most relevant memories
   - Includes them in the LLM context
   - Provides task-aware, documentation-aware responses

### Example Conversations

**Before Sync:**
```
User: What's my current task?
NAVI: I don't have access to your current tasks yet.
```

**After Sync:**
```
User: What's my current task?
NAVI: You're working on ENG-102: Implement dual-write pattern for specimen collection.
      Status: In Progress
      Priority: High
      
      Key requirements:
      - Use Postgres + Redis dual-write
      - Maintain consistency with CDC
      - Add comprehensive error handling
      
      Related documentation: I found the "Dual-Write Pattern Guide" in Confluence...
```

---

## Testing

### Manual Testing

1. **Configure credentials**:
   ```bash
   cp .env.example .env
   # Edit .env with your Jira/Confluence credentials
   ```

2. **Run migration**:
   ```bash
   alembic upgrade head
   ```

3. **Start backend**:
   ```bash
   uvicorn backend.api.main:app --reload --port 8787 --env-file .env
   ```

4. **Sync Jira**:
   ```bash
   curl -X POST http://localhost:8787/api/org/sync/jira \
     -H "Content-Type: application/json" \
     -d '{"user_id": "your-email@example.com", "max_issues": 5}'
   ```

5. **Check memories**:
   ```sql
   SELECT id, user_id, category, title, importance
   FROM navi_memory
   WHERE user_id = 'your-email@example.com'
   ORDER BY created_at DESC;
   ```

### Automated Testing

Create `backend/tests/test_org_sync.py`:

```python
import pytest
from backend.services.org_ingestor import ingest_jira_for_user

@pytest.mark.asyncio
async def test_jira_sync(db_session):
    """Test Jira issue ingestion"""
    # Requires test Jira instance or mocks
    keys = await ingest_jira_for_user(
        db=db_session,
        user_id="test@example.com",
        max_issues=5
    )
    assert len(keys) > 0
```

---

## Observability

### Logging

All operations emit structured logs:

```json
{
  "event": "Jira ingestion complete",
  "user_id": "srinivas@example.com",
  "processed": 3,
  "total": 3,
  "timestamp": "2025-11-16T12:34:56Z",
  "level": "info"
}
```

### Monitoring

Key metrics to track:

- **Sync duration**: Time to fetch and process issues/pages
- **Memory count**: Number of memories per user/category
- **Search performance**: Semantic search latency
- **Embedding cost**: OpenAI API usage for embeddings

---

## Next Steps

### Step 3: RAG Search API

Build unified search across all memory types:

- `GET /api/navi/search?q=dev%20environment%20URL`
- Rank results by similarity + importance
- Format citations for LLM context
- Support filters (category, date, importance)

### Step 4: Slack/Teams Integration

- Meeting transcripts → `category=interaction` memories
- Sprint discussions → `category=workspace` memories
- DM context → `category=profile` memories

### Step 5: Startup Greeting

- "Good morning Srinivas!"
- "Here are your 3 tasks for today..."
- "Quick reminder: Sprint planning at 2pm"

---

## Troubleshooting

### "JiraClient is not configured"

**Problem**: Missing environment variables

**Solution**:
```bash
# Check .env file has:
AEP_JIRA_BASE_URL=https://your-domain.atlassian.net
AEP_JIRA_EMAIL=your-email@example.com
AEP_JIRA_API_TOKEN=your_token_here
```

### "Failed to generate embedding"

**Problem**: OpenAI API key not configured or invalid

**Solution**:
```bash
# Check OPENAI_API_KEY in .env
export OPENAI_API_KEY=sk-...
```

### "Confluence GET failed: 401"

**Problem**: Invalid credentials or token

**Solution**:
1. Verify API token is valid
2. Check email matches Atlassian account
3. Ensure service account has read access to space

### Slow semantic search

**Problem**: Missing or inefficient vector index

**Solution**:
```sql
-- Check index exists
SELECT indexname FROM pg_indexes 
WHERE tablename = 'navi_memory' 
AND indexname = 'idx_navi_memory_embedding';

-- If missing, create it:
CREATE INDEX idx_navi_memory_embedding 
ON navi_memory 
USING hnsw (embedding_vec vector_cosine_ops);
```

---

## Files Created

### Core Implementation
- `alembic/versions/0018_navi_memory.py` - Database migration
- `backend/integrations/jira_client.py` - Jira API client
- `backend/integrations/confluence_client.py` - Confluence API client
- `backend/services/navi_memory_service.py` - Memory CRUD operations
- `backend/services/org_ingestor.py` - Ingestion + summarization
- `backend/api/org_sync.py` - REST API endpoints

### Configuration
- `.env.example` - Updated with Jira/Confluence vars
- `backend/api/main.py` - Registered org_sync router

### Documentation
- `docs/step-2-org-integrations.md` - This file

---

## Summary

Step 2 is **complete** ✅. NAVI now has:

- ✅ Jira integration with automatic issue ingestion
- ✅ Confluence integration with page summarization
- ✅ Semantic memory storage with pgvector
- ✅ REST API for triggering syncs
- ✅ LLM-based content compression
- ✅ Full observability with structured logging

**Next**: Step 3 - Build unified RAG search API for "What's the dev environment URL?" queries.
