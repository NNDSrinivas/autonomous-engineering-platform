# NAVI Consolidation & RAG Enhancement Plan

**Date:** 2026-02-09
**Status:** 📋 **Planning Phase**

---

## Quick Analysis: Frontend Compatibility Issue

### Problem with Direct Switch to `/chat/autonomous`

The `/chat/autonomous` endpoint returns **streaming events** in this format:
```json
{"type": "status", "status": "planning"}
{"type": "text", "text": "..."}
{"type": "tool_call", "tool_call": {...}}
{"type": "complete", "summary": {...}}
```

But the frontend (`useNaviChat.ts`) expects this format from `/chat`:
```json
{
  "content": "...",      // NAVI's response text
  "actions": [...],      // Actions taken
  "agentRun": {...}      // Agent execution metadata
}
```

**Conclusion:** Directly switching to `/chat/autonomous` would **break the frontend**.

---

## Revised Quick Fix: Add RAG to Existing Endpoints

Instead of switching endpoints, **inject RAG into the existing implementations** that the frontend already uses.

### Option A: Add RAG to `agent_loop.py` (RECOMMENDED)

**File:** `backend/agent/agent_loop.py`
**Endpoint:** `/api/navi/chat` (primary endpoint)
**Status:** Used by frontend ✅

**Changes Needed:**
1. Import RAG functions from `workspace_rag.py`
2. Add RAG context retrieval before LLM call
3. Include RAG context in the prompt
4. Use background indexing (Phase 1 already done)

**Pros:**
- ✅ No frontend changes needed
- ✅ Keeps existing response format
- ✅ Enables RAG for all users immediately
- ✅ Minimal risk of breaking things

**Cons:**
- ⚠️ Duplicates RAG code (also in autonomous_agent)
- ⚠️ Temporary solution (consolidation still needed)

**Effort:** 2-3 hours

---

### Option B: Add RAG to `navi_brain.py`

**File:** `backend/services/navi_brain.py`
**Endpoints:** `/chat/stream`, `/process`, `/process/stream`
**Status:** Used by frontend for streaming ✅

**Changes Needed:**
1. Import RAG functions
2. Add RAG retrieval in `process_navi_request()`
3. Include in streaming version too

**Pros:**
- ✅ Covers both regular and streaming requests
- ✅ No frontend changes
- ✅ Simpler than agent_loop (fewer integrations)

**Cons:**
- ⚠️ Still duplicates RAG code
- ⚠️ navi_brain already 9,897 lines

**Effort:** 2-3 hours

---

### Option C: Create Adapter Endpoint

**New File:** `backend/api/routers/navi_enhanced.py`
**New Endpoint:** `/api/navi/chat/enhanced`

**Implementation:**
```python
@router.post("/chat/enhanced")
async def navi_chat_enhanced(request: ChatRequest):
    """
    Enhanced NAVI with RAG and memory context.
    Wraps autonomous_agent but returns same format as /chat.
    """
    # Use autonomous_agent internally
    agent = AutonomousAgent(...)

    # Collect streaming events
    events = []
    async for event in agent.execute_task(request.message):
        events.append(event)

    # Transform to /chat format
    return {
        "content": extract_content(events),
        "actions": extract_actions(events),
        "agentRun": extract_agent_run(events)
    }
```

**Pros:**
- ✅ Reuses autonomous_agent (no code duplication)
- ✅ Maintains frontend compatibility
- ✅ Can gradually migrate users

**Cons:**
- ⚠️ Collects all events before returning (not truly streaming)
- ⚠️ Need to transform event format

**Effort:** 3-4 hours

---

## Recommended Approach: **Option A + Long-term Consolidation**

### Phase 1: Quick Fix (Today - 2-3 hours)

**Add RAG to `agent_loop.py`**

```python
# backend/agent/agent_loop.py

async def run_agent_loop(...):
    # ... existing code ...

    # NEW: Add RAG context retrieval
    from backend.services.workspace_rag import search_codebase

    rag_context = ""
    if workspace and workspace.get("workspace_root"):
        workspace_path = workspace["workspace_root"]
        try:
            # Use Phase 1 background indexing (non-blocking)
            rag_results = await search_codebase(
                workspace_path=workspace_path,
                query=message,
                top_k=10,
                allow_background_indexing=True  # Won't block!
            )

            if rag_results:
                rag_context = "\n\n## Relevant Code Context:\n"
                for result in rag_results:
                    rag_context += f"\n### {result['file_path']}\n{result['content']}\n"
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
            # Continue without RAG

    # Include RAG context in prompt
    system_prompt = f"{base_system_prompt}\n{rag_context}"

    # ... rest of existing code ...
```

**Steps:**
1. [ ] Add RAG import to agent_loop.py
2. [ ] Add RAG retrieval before LLM call
3. [ ] Include RAG context in system prompt
4. [ ] Test with frontend
5. [ ] Commit changes

---

### Phase 2: Full Consolidation (Next Week - 4-5 days)

**Merge all implementations into ONE unified NAVI**

**Target Architecture:**
```
backend/services/navi_unified.py  (New unified implementation)
├─ RAG support (from autonomous_agent)
├─ Memory context (from autonomous_agent)
├─ Agent loop pipeline (from agent_loop)
├─ Streaming support (from navi_brain)
└─ Tool execution (unified)

backend/api/routers/navi.py (Simplified routing)
├─ POST /api/navi/chat → navi_unified
├─ POST /api/navi/chat/stream → navi_unified (streaming mode)
└─ Deprecated: /chat/autonomous, /process, etc.
```

**Steps:**
1. [ ] Create `navi_unified.py` with all features
2. [ ] Update `/chat` endpoint to use unified implementation
3. [ ] Add comprehensive tests
4. [ ] Update frontend (if needed)
5. [ ] Deprecate old implementations
6. [ ] Remove deprecated code after confirmation

---

## RAG Enhancement Phases

### ✅ Phase 1: Background Indexing (Completed)

- Implemented non-blocking indexing
- First request triggers background indexing
- Subsequent requests use cached index
- Performance: 171s → 9s (95% faster)

---

### 📋 Phase 2: Smart Indexing (Next - 2-3 days)

**Goal:** Make indexing 4-5x faster (167s → 30-40s)

#### 2.1 Incremental Indexing
```python
# backend/services/workspace_rag.py

async def index_workspace_incremental(
    workspace_path: str,
    previous_index: Optional[WorkspaceIndex] = None
) -> WorkspaceIndex:
    """
    Only index changed files since last index.
    """
    if not previous_index:
        return await index_workspace(workspace_path)  # Full index

    # Get file hashes
    current_files = await scan_workspace_files(workspace_path)
    previous_files = previous_index.file_hashes

    # Identify changes
    changed_files = []
    for file_path, current_hash in current_files.items():
        if file_path not in previous_files or previous_files[file_path] != current_hash:
            changed_files.append(file_path)

    # Only index changed files
    logger.info(f"[RAG] Incremental: {len(changed_files)} changed files")
    new_chunks = await index_files(changed_files)

    # Update index delta
    return previous_index.merge(new_chunks)
```

#### 2.2 Selective Indexing
```python
# Priority-based indexing

PRIORITY_PATTERNS = [
    ("high", ["package.json", "README.md", "*.config.js"]),
    ("high", ["src/**/*.ts", "backend/**/*.py"]),  # Source code
    ("medium", ["docs/**/*.md"]),
    ("low", ["tests/**/*"]),
    ("skip", ["node_modules/**", "dist/**", ".git/**"]),  # Never index
]

async def index_workspace_selective(workspace_path: str):
    """Index high-priority files first."""
    files_by_priority = categorize_files(workspace_path, PRIORITY_PATTERNS)

    # Index high-priority files first
    for file in files_by_priority["high"]:
        await index_file(file)

    # Then medium priority (can be interrupted)
    for file in files_by_priority["medium"]:
        await index_file(file)
```

#### 2.3 Parallel Processing
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def index_files_parallel(files: List[str], max_workers: int = 4):
    """Index multiple files in parallel."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(executor, index_single_file, file)
            for file in files
        ]
        results = await asyncio.gather(*tasks)
    return results
```

**Expected Result:** 167s → 30-40s (4-5x faster)

---

### 📋 Phase 3: Persistent Indexes (Following Week - 3-5 days)

**Goal:** Store indexes in database for instant RAG on first request

#### 3.1 Database Schema
```sql
-- Store workspace indexes persistently
CREATE TABLE workspace_indexes (
    id UUID PRIMARY KEY,
    workspace_path TEXT NOT NULL,
    git_commit_hash TEXT,
    indexed_at TIMESTAMP DEFAULT NOW(),
    file_count INTEGER,
    chunk_count INTEGER,
    UNIQUE(workspace_path, git_commit_hash)
);

CREATE TABLE workspace_chunks (
    id UUID PRIMARY KEY,
    index_id UUID REFERENCES workspace_indexes(id),
    file_path TEXT NOT NULL,
    chunk_number INTEGER,
    content TEXT,
    embedding VECTOR(1536),  -- Using pgvector
    metadata JSONB,
    INDEX idx_embedding USING ivfflat (embedding vector_cosine_ops)
);
```

#### 3.2 Implementation
```python
# backend/services/workspace_rag.py

async def get_or_create_index(workspace_path: str) -> WorkspaceIndex:
    """
    Check database for existing index, create if not found.
    """
    # Get current git commit
    commit_hash = get_git_commit_hash(workspace_path)

    # Check database
    existing_index = await db.query(WorkspaceIndex).filter_by(
        workspace_path=workspace_path,
        git_commit_hash=commit_hash
    ).first()

    if existing_index:
        logger.info(f"[RAG] Using cached index from database")
        return existing_index

    # No cached index - trigger background indexing
    logger.info(f"[RAG] No cached index - scheduling background indexing")
    asyncio.create_task(_background_index_and_store(workspace_path, commit_hash))

    return None  # Will be available for next request
```

#### 3.3 Redis Caching Layer
```python
import redis
import pickle

redis_client = redis.Redis(host='localhost', port=6379)

async def search_codebase_with_cache(workspace_path: str, query: str):
    """Search with Redis cache for hot paths."""
    cache_key = f"rag:{workspace_path}:{hash(query)}"

    # Check cache
    cached = redis_client.get(cache_key)
    if cached:
        logger.info("[RAG] Cache hit!")
        return pickle.loads(cached)

    # Not cached - do search
    results = await search_codebase(workspace_path, query)

    # Cache for 1 hour
    redis_client.setex(cache_key, 3600, pickle.dumps(results))

    return results
```

**Expected Result:** First request has index ready = instant RAG (0s indexing time)

---

### 📋 Phase 4: Advanced Optimizations (Future - 1-2 weeks)

**Goal:** Sub-second RAG retrieval (<500ms)

#### 4.1 Vector Database
- Use Pinecone, Weaviate, or Qdrant
- Distributed indexing
- Optimized similarity search

#### 4.2 Smaller Embeddings
- Use more efficient models (e.g., `all-MiniLM-L6-v2` instead of `ada-002`)
- Quantize embeddings to reduce storage/memory
- Approximate nearest neighbor search (HNSW)

#### 4.3 Smart Query Optimization
```python
async def optimize_query(query: str) -> str:
    """
    Optimize query for better RAG results.
    """
    # Extract key terms
    keywords = extract_keywords(query)

    # Expand with synonyms
    expanded = expand_synonyms(keywords)

    # Rerank by relevance
    optimized = f"{query} {' '.join(expanded)}"

    return optimized
```

**Expected Result:** <500ms RAG retrieval consistently

---

## Implementation Timeline

| Phase | Duration | Start | Complete |
|-------|----------|-------|----------|
| **Quick Fix: Add RAG to agent_loop** | 2-3 hours | Today | Today |
| **Testing & Verification** | 1 hour | Today | Today |
| **Phase 2: Smart Indexing** | 2-3 days | Tomorrow | This Week |
| **Phase 3: Persistent Indexes** | 3-5 days | Next Week | Next Week |
| **Full Consolidation** | 4-5 days | Next Week | Next Week |
| **Phase 4: Advanced Optimizations** | 1-2 weeks | Later | Later |

---

## Success Metrics

### Quick Fix (Today)
- [ ] RAG enabled for all `/chat` requests
- [ ] No performance regression (<5s response time)
- [ ] No frontend breakage
- [ ] Background indexing working

### Phase 2 (This Week)
- [ ] Indexing time: 167s → <40s (4x faster)
- [ ] Support for incremental updates
- [ ] Priority-based indexing working

### Phase 3 (Next Week)
- [ ] Database storage working
- [ ] First request uses cached index (0s wait)
- [ ] Cache hit rate >95% after warmup

### Full Consolidation (Next Week)
- [ ] Single NAVI implementation
- [ ] All features unified (RAG, memory, streaming)
- [ ] Code reduction: 17,500 LOC → ~8,000 LOC
- [ ] Frontend working perfectly

---

## Next Steps

### Immediate (Now)
1. **Implement Quick Fix:** Add RAG to agent_loop.py
2. **Test thoroughly:** Verify no breakage
3. **Commit changes**

### Short-term (This Week)
4. **Implement Phase 2:** Smart indexing
5. **Begin consolidation planning**

### Medium-term (Next Week)
6. **Implement Phase 3:** Persistent indexes
7. **Execute full consolidation**
8. **Comprehensive testing**

---

## Risk Mitigation

### Risk 1: Quick fix breaks frontend
**Mitigation:**
- Test locally first
- Add feature flag to enable/disable RAG
- Keep fallback to existing behavior

### Risk 2: Consolidation too complex
**Mitigation:**
- Break into smaller PRs
- Gradual migration with dual-mode support
- Comprehensive test coverage

### Risk 3: Performance regression
**Mitigation:**
- Monitor metrics continuously
- Keep background indexing non-blocking
- Add timeout guards everywhere

---

## Conclusion

**Today:** Quick fix adds RAG to existing implementation (2-3 hours)
**This Week:** Smart indexing Phase 2 (2-3 days)
**Next Week:** Persistent indexes Phase 3 + Full consolidation (3-5 days)
**Future:** Advanced optimizations Phase 4 (1-2 weeks)

**Total effort:** ~2 weeks for complete solution with all phases
