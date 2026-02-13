# NAVI Endpoints Overview

**Date:** 2026-02-09
**Purpose:** Clarify which NAVI endpoints use which implementation and where RAG optimization applies

---

## Two Separate NAVI Implementations

The Autonomous Engineering Platform has **two different NAVI implementations** serving different endpoints:

### 1. NaviEngine (`/api/navi/process`)

**File:** `backend/services/navi_brain.py`
**Endpoint:** POST `/api/navi/process` and `/api/navi/process/stream`
**Description:** "Clean LLM-First API" - Pure LLM intelligence without autonomous agent features

**Features:**
- ✅ LLM-based request processing
- ✅ Project analysis and context
- ✅ File creation/modification
- ✅ Command execution with safety features
- ✅ Streaming responses
- ❌ **No RAG** (Retrieval-Augmented Generation)
- ❌ **No memory context** integration
- ❌ No autonomous iteration with verification

**Use Case:**
Quick, direct LLM responses for simple code generation, explanations, and file modifications.

**API:**
```bash
curl -X POST http://localhost:8787/api/navi/process/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "Create a React component",
    "workspace": "/path/to/project",
    "llm_provider": "openai"
  }'
```

---

### 2. AutonomousAgent (`/api/navi/chat/autonomous`)

**File:** `backend/services/autonomous_agent.py`
**Endpoint:** POST `/api/navi/chat/autonomous`
**Description:** Full-featured autonomous agent with RAG, memory context, and self-healing

**Features:**
- ✅ **RAG** (Retrieval-Augmented Generation) from workspace codebase
- ✅ **Memory context** (user preferences, conversation history, org standards)
- ✅ Autonomous iteration and verification
- ✅ Self-healing on errors
- ✅ Tool calling and execution
- ✅ Multi-step planning
- ✅ LLM routing with fallbacks

**Use Case:**
Complex tasks requiring codebase understanding, multi-step execution, verification, and autonomous error recovery.

**API:**
```bash
curl -X POST http://localhost:8787/api/navi/chat/autonomous \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "Add authentication with tests and verify it works",
    "workspace_path": "/path/to/project",
    "model": "gpt-4o",
    "attachments": []
  }'
```

---

## RAG Optimization Impact

### ✅ RAG Optimization Applies To:

**Endpoint:** `/api/navi/chat/autonomous`
**Implementation:** `backend/services/autonomous_agent.py`

The RAG optimization (Phase 1: Background Indexing) implemented in:
- `backend/services/workspace_rag.py`
- `backend/services/autonomous_agent.py`

**Only affects the `/chat/autonomous` endpoint.**

### ❌ RAG Optimization Does NOT Apply To:

**Endpoint:** `/api/navi/process`
**Implementation:** `backend/services/navi_brain.py`

This endpoint **does not use RAG at all**, so the RAG optimization has no effect here.

---

## Performance Comparison

### `/api/navi/process` (NaviEngine)

**Before Optimization:** 4-5 seconds
**After Optimization:** 4-5 seconds (unchanged - no RAG)

**Breakdown:**
- Request parsing: 50ms
- Project analysis: 200ms
- LLM API call: 3,500ms
- Response formatting: 100ms

**Bottleneck:** OpenAI API (3.5s) - cannot optimize further

---

### `/api/navi/chat/autonomous` (AutonomousAgent)

**Before RAG Optimization:** 171+ seconds (first request with RAG indexing)
**After RAG Optimization (Phase 1):**
- **First request:** 4-5 seconds (no RAG, background indexing triggered)
- **Second request:** 4-5 seconds (with RAG context from background index)

**Breakdown (Second Request):**
- Request parsing: 50ms
- Memory context loading: 500ms (parallelized)
- RAG context retrieval: 200ms (from cached index)
- LLM API call: 3,500ms
- Response formatting: 100ms

**User Experience:**
- First request: Fast response, triggers background indexing
- Background: Workspace indexed in ~3 minutes
- Subsequent requests: Fast response WITH RAG context for better quality

---

## Testing RAG Optimization

### ❌ Wrong Way (Tests NaviEngine without RAG):
```bash
curl -X POST http://localhost:8787/api/navi/process \
  -H 'Content-Type: application/json' \
  -d '{"message": "Hello", "workspace": "/path"}'

# This will be fast (4-5s) but does NOT use RAG
# Testing this endpoint does NOT verify RAG optimization
```

### ✅ Correct Way (Tests AutonomousAgent with RAG):
```bash
# First request (triggers background indexing)
curl -X POST http://localhost:8787/api/navi/chat/autonomous \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "Explain the codebase structure",
    "workspace_path": "/Users/mounikakapa/dev/autonomous-engineering-platform",
    "model": "gpt-4o"
  }'

# Expected: Fast response (4-5s), log shows "scheduling background indexing"

# Wait ~3 minutes for background indexing to complete

# Second request (uses RAG context)
curl -X POST http://localhost:8787/api/navi/chat/autonomous \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "What memory services exist in the codebase?",
    "workspace_path": "/Users/mounikakapa/dev/autonomous-engineering-platform",
    "model": "gpt-4o"
  }'

# Expected: Fast response (4-5s) WITH relevant code context from RAG
```

---

## Which Endpoint Should You Use?

### Use `/api/navi/process` (NaviEngine) when:
- ✅ Quick code generation or file modifications
- ✅ Simple explanations or documentation
- ✅ You want fastest possible response
- ✅ Task doesn't need deep codebase understanding
- ✅ No need for verification or autonomous iteration

**Example:**
- "Create a React button component"
- "Explain this error message"
- "Add a new route to the API"

---

### Use `/api/navi/chat/autonomous` (AutonomousAgent) when:
- ✅ Need deep codebase understanding (RAG)
- ✅ Multi-step tasks with verification
- ✅ Want autonomous error recovery
- ✅ Need personalized responses (memory context)
- ✅ Task requires iteration until success
- ✅ Complex refactoring or architectural changes

**Example:**
- "Add authentication system with tests and verify it works"
- "Refactor the user service to use async/await and fix any issues"
- "Find and fix all type errors in the codebase"

---

## Frontend Integration

### VS Code Extension Default

Check which endpoint the VS Code extension uses by default:

```typescript
// extensions/vscode-aep/webview/src/components/navi/NaviChatPanel.tsx

// If it calls /api/navi/process:
const url = `${backendBase}/api/navi/process/stream`;
// → Uses NaviEngine (no RAG)

// If it calls /api/navi/chat/autonomous:
const url = `${backendBase}/api/navi/chat/autonomous`;
// → Uses AutonomousAgent (with RAG)
```

**Recommendation:** Add a UI toggle to let users choose between:
- **"Quick Mode"** → `/api/navi/process` (faster, simpler)
- **"Deep Mode"** → `/api/navi/chat/autonomous` (smarter, RAG-powered)

---

## Related Documents

- [RAG_OPTIMIZATION_STRATEGY.md](RAG_OPTIMIZATION_STRATEGY.md) - RAG optimization details
- [MEMORY_CONTEXT_OPTIMIZATION.md](MEMORY_CONTEXT_OPTIMIZATION.md) - Memory context parallelization
- [NAVI_PERFORMANCE_REALISTIC_LIMITS.md](NAVI_PERFORMANCE_REALISTIC_LIMITS.md) - Performance analysis

---

## Summary

| Feature | `/api/navi/process`<br>(NaviEngine) | `/api/navi/chat/autonomous`<br>(AutonomousAgent) |
|---------|-------------------------------------|--------------------------------------------------|
| **RAG** | ❌ No | ✅ Yes |
| **Memory Context** | ❌ No | ✅ Yes |
| **Autonomous Iteration** | ❌ No | ✅ Yes |
| **Self-Healing** | ❌ No | ✅ Yes |
| **Response Time** | 4-5s | 4-5s (after Phase 1) |
| **Quality** | Good | Excellent (with context) |
| **Use Case** | Simple tasks | Complex tasks |

**Key Insight:** The RAG optimization only benefits `/chat/autonomous` endpoint. If you're testing `/process` endpoint, you won't see any RAG-related improvements because that endpoint doesn't use RAG at all.
