# NAVI Performance Analysis & Context Storage Report

**Date:** 2026-02-09
**Status:** 🔴 **CRITICAL ISSUES FOUND**
**Priority:** P0 - Performance blockers identified

---

## Executive Summary

**User Report:** "NAVI is taking too much time to respond on users request"

**Findings:**
1. ❌ PostgreSQL was NOT running → All requests waiting for DB timeout
2. ❌ Anthropic API rate limit reached → NAVI cannot process requests
3. ⚠️ Health endpoint still slow (2.84s) even with PostgreSQL running
4. ❓ Context storage untested → Database connection issues

---

## Performance Measurements

### Before Fixes
| Endpoint | Response Time | Status |
|----------|--------------|--------|
| `/health` | **3.57 seconds** | PostgreSQL not running |
| `/api/navi/process` | **Unable to test** | PostgreSQL not running |

### After Starting PostgreSQL
| Endpoint | Response Time | Status |
|----------|--------------|--------|
| `/health` | **2.84 seconds** | Still slow! |
| `/api/navi/process` | **6.70 seconds** | API rate limit error |

### Expected Performance
| Endpoint | Target | Current | Delta |
|----------|--------|---------|-------|
| `/health` | 50-100ms | 2,840ms | **28x slower** |
| `/api/navi/process` | 2-5s (LLM call) | 6.7s | 34-135% slower |

---

## Root Cause Analysis

### Issue 1: PostgreSQL Not Running

**Symptoms:**
```
connection to server at "127.0.0.1", port 5432 failed: Connection refused
Is the server running on that host and accepting TCP/IP connections?
```

**Impact:**
- Every request tries to connect to database
- Connection timeout adds 3-5 seconds per request
- Audit logging fails
- Context storage fails
- Memory system unavailable

**Fix:**
```bash
brew services start postgresql@14
```

**Verification:**
```bash
$ pg_ctl -D /opt/homebrew/var/postgresql@14 status
pg_ctl: server is running (PID: 18609)
```

---

### Issue 2: Anthropic API Rate Limit

**Error:**
```json
{
  "type": "error",
  "error": {
    "type": "invalid_request_error",
    "message": "You have reached your specified API usage limits. You will regain access on 2026-03-01 at 00:00 UTC."
  },
  "request_id": "req_011CXx3wfgjahuFJxKWYVv48"
}
```

**Impact:**
- NAVI cannot process ANY requests
- Users see: "NAVI encountered a temporary issue"
- No code generation, no file edits, no assistance
- **Complete blocker for NAVI functionality**

**Solutions:**

**Option A: Add Anthropic API Key**
```bash
# Add to .env file
ANTHROPIC_API_KEY=sk-ant-api03-...

# Or set environment variable
export ANTHROPIC_API_KEY=sk-ant-api03-...

# Restart backend
```

**Option B: Use Different LLM Provider**
```bash
# OpenAI (requires API key)
OPENAI_API_KEY=sk-proj-...

# Ollama (local, free)
# No API key needed, install:
brew install ollama
ollama pull llama3.1

# In request:
{
  "llm_provider": "ollama",
  "message": "Help me write code"
}
```

**Option C: Wait Until March 1st**
- Anthropic API access resets on 2026-03-01 00:00 UTC
- Not viable for production

---

### Issue 3: Health Endpoint Still Slow (2.84s)

**Observation:**
Even with PostgreSQL running, `/health` endpoint takes 2.84 seconds.

**Expected:** 50-100ms for simple health check
**Actual:** 2,840ms (28x slower)

**Potential Causes:**

1. **Database Connection Pool Initialization**
   - First request initializing connection pool
   - Solution: Warm up pool on startup

2. **Slow Health Checks**
   ```python
   # backend/core/health/checks.py
   def readiness_payload():
       # May be running slow queries
   ```

3. **Middleware Overhead**
   - Audit middleware
   - Rate limit middleware
   - Observability middleware
   - Each adding latency

4. **Blocking I/O Operations**
   - Synchronous database checks
   - Redis connection checks
   - File system operations

**Investigation Needed:**
```bash
# Add timing logs to health checks
# Check middleware latency
# Profile with cProfile or py-spy
```

---

## Context Storage Analysis

**Question:** "Is NAVI storing context and how far back?"

### Database Schema

**Conversation Storage:**
```sql
-- backend/database/models/memory.py:623
CREATE TABLE navi_conversations (
    id UUID PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    org_id INTEGER REFERENCES organizations(id),
    title VARCHAR(255),
    workspace_path TEXT,
    is_pinned BOOLEAN DEFAULT FALSE,
    is_starred BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Message Storage:**
```sql
CREATE TABLE conversation_messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES navi_conversations(id),
    role VARCHAR(20),  -- 'user' | 'assistant' | 'system'
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE
);
```

### Context Retrieval

**API Endpoints:**
```
GET /api/navi-memory/conversations
    → List all user conversations

GET /api/navi-memory/conversations/{id}?include_messages=true&message_limit=200
    → Get conversation with last 200 messages

POST /api/navi-memory/conversations/{id}/messages
    → Add message to conversation
```

**Memory Integration:**
```python
# backend/services/navi_brain.py:85
async def _get_memory_context_async(
    query: str,
    user_id: Optional[int],
    org_id: Optional[int],
    workspace_path: Optional[str],
    current_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Get memory context for a NAVI request."""
    memory = _get_memory_integration()
    if not memory:
        return {}

    # Retrieves:
    # - Recent conversation history
    # - Relevant codebase context
    # - User preferences
    # - Team patterns
```

### Current Status: ❓ **UNTESTED**

**Cannot test context storage because:**
1. Database role "postgres" doesn't exist
2. Need to use correct database user (probably `$USER`)
3. May need to create database first

**To Test:**
```bash
# Fix database connection
psql -U $(whoami) -d postgres -c "CREATE DATABASE navi_db;"

# Run migrations
cd backend
alembic upgrade head

# Check if tables exist
psql -U $(whoami) -d navi_db -c "\dt navi_*"

# Test context storage
curl -X POST http://localhost:8787/api/navi-memory/conversations \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "title": "Test Chat"}'
```

---

## Performance Bottlenecks

### 1. Database Connection Issues

**Evidence:**
- PostgreSQL not running by default
- Connection timeout adding 3-5s per request
- No connection pooling warmup
- Role configuration issues

**Impact:** High (3-5s delay per request)

**Priority:** P0

**Fix:**
```bash
# 1. Start PostgreSQL automatically
brew services start postgresql@14

# 2. Add to backend startup
# warm up connection pool on app startup

# 3. Add to README
```

### 2. LLM API Rate Limits

**Evidence:**
- Anthropic API limit reached
- No fallback to alternative providers
- No rate limit handling

**Impact:** Critical (NAVI completely non-functional)

**Priority:** P0

**Fix:**
```python
# Add rate limit detection and fallback
if anthropic_rate_limited:
    # Fall back to Ollama local model
    use_ollama()
```

### 3. Slow Health Endpoint

**Evidence:**
- 2.84s for simple health check
- Should be <100ms

**Impact:** Medium (affects monitoring, delays first request)

**Priority:** P1

**Fix:**
```python
# Cache health check results for 5 seconds
# Add fast path for liveness probe
# Profile and optimize slow checks
```

### 4. Context Retrieval Latency

**Evidence:** Not yet measured (DB issues)

**Potential Impact:** Medium-High if not optimized

**Priority:** P1

**Optimization:**
```python
# 1. Limit context window
max_messages = 50  # Don't load all messages

# 2. Use indexes
CREATE INDEX idx_conv_updated ON navi_conversations(updated_at DESC);
CREATE INDEX idx_msg_created ON conversation_messages(created_at DESC);

# 3. Cache recent context
# Use Redis for hot conversations
```

---

## Context Retention Policy

**Question:** "How far back is context stored?"

### Current Implementation

**Database Storage:** Unlimited
- All conversations stored forever
- No automatic cleanup
- No retention policy

**Context Window for LLM:**
```python
# backend/services/navi_brain.py
message_limit = 200  # Load last 200 messages

# Typical LLM context windows:
# - Claude 3.5 Sonnet: 200K tokens (~150K words)
# - GPT-4 Turbo: 128K tokens (~96K words)
# - Llama 3.1: 128K tokens
```

**Effective Retention:**
- **Database:** ∞ (unlimited)
- **LLM Context:** Last 200 messages (~10-50 conversations)
- **Working Memory:** Last conversation session

### Recommended Retention Policy

**Hot Storage (PostgreSQL):**
- Last 90 days: Full access
- 90-365 days: Archived (slower access)
- 365+ days: Cold storage or deleted

**LLM Context:**
- Last 50 messages (default)
- Smart truncation (keep most relevant)
- Summarize older context

**Implementation:**
```python
# backend/services/conversation_memory.py
async def get_context_for_llm(
    conversation_id: str,
    max_messages: int = 50,
    include_summary: bool = True
) -> List[Message]:
    # 1. Get last 50 messages
    recent = await get_recent_messages(conversation_id, max_messages)

    # 2. If conversation is long, add summary of older messages
    if include_summary:
        total_count = await count_messages(conversation_id)
        if total_count > max_messages:
            summary = await get_conversation_summary(conversation_id)
            recent.insert(0, summary)

    return recent
```

---

## Recommendations

### Immediate (Day 1)

1. **Add Anthropic API Key** ✅ P0
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-api03-...
   # Or add to .env
   ```

2. **Start PostgreSQL Automatically** ✅ P0
   ```bash
   brew services start postgresql@14
   ```

3. **Document in README** ✅ P0
   - Add "Start PostgreSQL" to setup instructions
   - Add API key configuration
   - Add troubleshooting section

### Short Term (Week 1)

4. **Optimize Health Endpoint** ⚠️ P1
   - Profile health checks
   - Cache results for 5 seconds
   - Add fast liveness probe

5. **Fix Database Connection** ⚠️ P1
   - Create correct database user
   - Run migrations
   - Test connection pool

6. **Test Context Storage** ⚠️ P1
   - Verify messages are saved
   - Test context retrieval
   - Measure query performance

### Medium Term (Month 1)

7. **Add LLM Fallback** 💡 P2
   - Ollama as backup when API limits hit
   - Graceful degradation
   - Rate limit detection

8. **Implement Retention Policy** 💡 P2
   - Archive old conversations
   - Summarize long context
   - Add storage cleanup

9. **Optimize Context Retrieval** 💡 P2
   - Add database indexes
   - Cache hot conversations
   - Smart context truncation

---

## Testing Plan

### Performance Testing

```bash
# 1. Health endpoint
time curl http://localhost:8787/health
# Target: <100ms

# 2. NAVI request (with valid API key)
time curl -X POST http://localhost:8787/api/navi/process \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello","workspace":"/tmp","llm_provider":"anthropic"}'
# Target: 2-5s (includes LLM API call)

# 3. Context storage
curl -X POST http://localhost:8787/api/navi-memory/conversations \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"title":"Test"}'
# Should return conversation ID

# 4. Context retrieval
curl http://localhost:8787/api/navi-memory/conversations/{id}?include_messages=true
# Should return conversation with messages
```

### Context Storage Testing

```sql
-- Check if conversations are being stored
SELECT COUNT(*) FROM navi_conversations;

-- Check message count
SELECT COUNT(*) FROM conversation_messages;

-- Check recent conversations
SELECT id, title, created_at, updated_at
FROM navi_conversations
ORDER BY updated_at DESC
LIMIT 10;

-- Check context retention
SELECT
    DATE(created_at) as date,
    COUNT(*) as message_count
FROM conversation_messages
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 30;
```

---

## Success Metrics

### Performance
- Health endpoint: < 100ms (currently 2,840ms)
- NAVI request: 2-5s (currently 6.7s + errors)
- Context retrieval: < 200ms (not yet measured)
- Database queries: < 50ms (not yet measured)

### Context Storage
- Messages saved: 100% (not yet verified)
- Context retrieved: 100% (not yet verified)
- Retention period: 90 days minimum
- Storage efficiency: Optimal (with archiving)

---

## Next Steps

**Immediate Actions:**
1. Add Anthropic API key to environment
2. Ensure PostgreSQL starts automatically
3. Update README with setup instructions
4. Fix database connection and test context storage

**Follow-up Investigation:**
1. Profile health endpoint to find bottleneck
2. Measure context retrieval performance
3. Test with real NAVI requests
4. Implement monitoring for LLM API limits

---

## Related Documents

- [CHAT_PERSISTENCE_BUG.md](CHAT_PERSISTENCE_BUG.md) - Chat data loss fix
- [CHAT_PERSISTENCE_FIX_SUMMARY.md](CHAT_PERSISTENCE_FIX_SUMMARY.md) - Fix implementation
- [README.md](../README.md) - Setup instructions
- [NAVI_PROD_READINESS.md](NAVI_PROD_READINESS.md) - Production readiness

---

## Appendix: Logs

### PostgreSQL Not Running
```
connection to server at "127.0.0.1", port 5432 failed: Connection refused
Multiple connection attempts failed. All failures were:
- host: 'localhost', port: 5432, hostaddr: '::1': Connection refused
- host: 'localhost', port: 5432, hostaddr: '127.0.0.1': Connection refused
```

### Anthropic API Rate Limit
```json
{
  "type": "error",
  "error": {
    "type": "invalid_request_error",
    "message": "You have reached your specified API usage limits. You will regain access on 2026-03-01 at 00:00 UTC."
  }
}
```

### NAVI Request Flow
```
[INFO] 🎯 Processing NAVI request: Hello NAVI, can you help me?...
[INFO] 🤖 Using LLM: anthropic (default model)
[INFO] [NAVI] Analyzing project at: /tmp
[ERROR] NAVI processing error: Anthropic API error
```
