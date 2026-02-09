# NAVI Latency Optimization Plan

## Current Performance

**From [OPTIMIZED_TEST_RESULTS_FEB6.md](OPTIMIZED_TEST_RESULTS_FEB6.md):**

| Metric | Current | Target | Gap |
|--------|---------|--------|-----|
| **p50 Latency** | 5,847ms (5.8s) | <2,000ms (2s) | **+2.9x over target** |
| **p95 Latency** | 11,887ms (11.9s) | <5,000ms (5s) | +2.4x over target |
| **p99 Latency** | 12,511ms (12.5s) | <10,000ms (10s) | +1.3x over target |
| **Average Latency** | 6,038ms (6.0s) | - | - |
| **Success Rate** | **98%** ✅ | >95% | Exceeds target |

**Latency Distribution:**
- 37% of requests: 0-5s
- 52% of requests: 5-10s (**majority**)
- 9% of requests: 10-15s
- 2% of requests: >30s (timeout)

**Conclusion:** While latency exceeds targets, **98% success rate is excellent** and current 5-10s response time is acceptable for a complex AI agent system. Optimization should be done carefully to avoid regressing success rate.

---

## Root Cause Analysis

### Request Flow Bottlenecks

From analyzing [`backend/api/navi.py`](../backend/api/navi.py:5977-6126), the request flow is:

```
User Request
    ↓
1. Image Processing (if attachments) ────────────── ~500-2000ms
    ↓
2. Intent Detection ────────────────────────────── ~300-800ms
    ↓
3. Context Building (workspace, repo analysis) ─── ~1000-2000ms
    ↓
4. LLM API Call (OpenAI/Anthropic) ────────────── ~2000-4000ms
    ↓
5. Response Streaming (typing simulation) ────────  ~200-500ms
    ↓
Total Response Time ────────────────────────────── 5000-10000ms (5-10s)
```

### Identified Bottlenecks

#### 1. **Synchronous Image Processing** (High Impact)
**Location:** `backend/api/navi.py:6016-6064`

**Issue:**
```python
vision_response = await VisionClient.analyze_image(
    image_data=base64_data,
    prompt=analysis_prompt,
    provider=vision_provider,
)
```

**Impact:** Adds 500-2000ms per image attachment
**Opportunity:** Move image analysis to background task or stream results

#### 2. **Intent Detection Overhead** (Medium Impact)
**Location:** Multiple intent classifiers called sequentially

**Issue:**
- Intent detection happens on every request
- No caching of similar intents
- Sequential classification pipeline

**Impact:** ~300-800ms per request
**Opportunity:** Cache intent detection results for similar queries

#### 3. **Context Building Phase** (High Impact)
**Location:** Context pack building before LLM call

**Issue:**
- Workspace analysis happens before LLM call
- Repository scanning blocks response
- No progressive context building

**Impact:** ~1000-2000ms for large workspaces
**Opportunity:** Stream response while building context in background

#### 4. **Artificial Typing Delay** (Low Impact, Easy Fix)
**Location:** `backend/api/navi.py:6092-6098`

**Issue:**
```python
async for chunk in stream_text_with_typing(
    reply,
    chunk_size=3,
    delay_ms=12,  # Artificial 12ms delay per chunk
):
```

**Impact:** ~200-500ms artificial delay
**Opportunity:** Remove or reduce typing simulation delay

#### 5. **LLM API Latency** (Unavoidable)
**Location:** LLM API calls to OpenAI/Anthropic

**Issue:** Network latency to LLM provider (2-4 seconds)
**Impact:** ~2000-4000ms per request
**Opportunity:** Limited (external dependency), but could use:
  - Streaming responses (already implemented)
  - Model selection (use faster model for simple queries)

---

## Optimization Strategies

### 🟢 Phase 1: Quick Wins (1-2 hours, 15-20% improvement)

These optimizations are **low risk** and can be implemented immediately without affecting success rate.

#### 1.1 Remove Artificial Typing Delay
**File:** `backend/api/navi.py:6092-6098`
**Change:**
```python
# BEFORE
async for chunk in stream_text_with_typing(
    reply,
    chunk_size=3,
    delay_ms=12,  # Remove this
):

# AFTER
async for chunk in stream_text_with_typing(
    reply,
    chunk_size=10,  # Larger chunks
    delay_ms=0,     # No artificial delay
):
```

**Expected Impact:** -200-500ms (p50: 5.8s → 5.3s)

#### 1.2 Increase Stream Chunk Size
**File:** `backend/services/streaming_utils.py`
**Change:** Increase chunk size from 3 to 10-20 characters

**Expected Impact:** -50-100ms (reduce overhead from many small events)

#### 1.3 Optimize Intent Detection Caching
**File:** `backend/core/llm_intent_classifier.py`
**Change:** Add LRU cache for recent intent classifications

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def _cache_key(message: str) -> str:
    """Generate cache key from message."""
    return message.lower().strip()[:100]  # First 100 chars

# Before calling LLM for intent:
cache_key = _cache_key(message)
if cache_key in intent_cache:
    return intent_cache[cache_key]
```

**Expected Impact:** -200-500ms for cached intents (20-30% of requests)

### 🟡 Phase 2: Medium-Term Optimizations (1-2 days, 30-40% improvement)

These require more testing but have significant impact.

#### 2.1 Parallel Context Building
**File:** `backend/api/navi.py`
**Strategy:** Build context in parallel with LLM call

```python
# BEFORE (Sequential)
context = await build_context(workspace_root)  # 1-2s
response = await llm_call(message, context)    # 2-4s
# Total: 3-6s

# AFTER (Parallel)
async def stream_with_progressive_context():
    # Start LLM call immediately with basic context
    llm_task = asyncio.create_task(llm_call(message, basic_context))

    # Build full context in parallel
    context_task = asyncio.create_task(build_full_context(workspace_root))

    # Stream LLM response as it arrives
    async for chunk in llm_task:
        yield chunk

    # Use full context for follow-up if needed
    full_context = await context_task
```

**Expected Impact:** -500-1000ms (overlap context building with LLM call)

#### 2.2 Async Image Processing
**File:** `backend/api/navi.py:6016-6064`
**Strategy:** Process images in background, stream preliminary response

```python
# BEFORE (Synchronous)
if request.attachments:
    image_context = await analyze_images(attachments)  # 500-2000ms
    response = await llm_call(message + image_context)
# Total: 2500-6000ms

# AFTER (Async)
async def process_with_images():
    # Start image analysis in background
    image_task = asyncio.create_task(analyze_images(attachments))

    # Send immediate response
    yield "data: Analyzing your image...\n\n"

    # Get preliminary response without image context
    preliminary = await llm_call_quick(message)
    yield preliminary

    # Wait for image analysis
    image_context = await image_task

    # Send enhanced response with image context
    enhanced = await llm_call_with_context(message, image_context)
    yield enhanced
```

**Expected Impact:** -500-1500ms (stream response while processing images)

#### 2.3 Smart Model Selection
**File:** `backend/ai/llm_router.py`
**Strategy:** Use faster model (gpt-4o-mini) for simple queries

```python
def should_use_fast_model(message: str) -> bool:
    """Determine if query is simple enough for fast model."""
    simple_patterns = [
        r"^what is\b",
        r"^how do i\b",
        r"^explain\b",
        r"^list\b",
        r"^\d+\s*[\+\-\*\/]\s*\d+",  # Math
    ]
    return any(re.match(pattern, message.lower()) for pattern in simple_patterns)

# In request handler:
if should_use_fast_model(request.message):
    model = "gpt-4o-mini"  # 50% faster, 90% cheaper
else:
    model = "gpt-4o"  # Full capability
```

**Expected Impact:** -1000-2000ms for simple queries (30-40% of requests)

### 🔴 Phase 3: Advanced Optimizations (1 week, 50-60% improvement)

These require significant development and testing.

#### 3.1 Response Caching Layer
**File:** New `backend/services/response_cache.py`
**Strategy:** Cache common responses using Redis

```python
import redis
import hashlib

redis_client = redis.Redis(host='localhost', port=6379)

def cache_key(message: str, context_hash: str) -> str:
    """Generate cache key for request."""
    content = f"{message}:{context_hash}"
    return f"navi:response:{hashlib.sha256(content.encode()).hexdigest()}"

async def get_or_compute_response(message: str, context: Dict) -> str:
    """Get cached response or compute new one."""
    key = cache_key(message, hash_context(context))

    # Check cache
    cached = redis_client.get(key)
    if cached:
        logger.info("[CACHE-HIT] Returning cached response")
        return json.loads(cached)

    # Compute new response
    response = await llm_call(message, context)

    # Cache for 1 hour
    redis_client.setex(key, 3600, json.dumps(response))

    return response
```

**Expected Impact:** -4000-6000ms for cache hits (10-15% of requests)

#### 3.2 Streaming Context Updates
**File:** `backend/api/navi.py`
**Strategy:** Stream context as it's discovered

```python
async def stream_with_progressive_context():
    # Start with minimal context
    yield "data: Analyzing workspace...\n\n"

    # Stream context discoveries
    async for context_chunk in discover_context_streaming(workspace_root):
        # Update context in real-time
        yield f"data: Found {context_chunk.type}: {context_chunk.name}\n\n"

        # If we have enough context, start LLM call
        if context_chunk.sufficient:
            break

    # Stream LLM response
    async for response_chunk in llm_call_streaming(message, context):
        yield response_chunk
```

**Expected Impact:** -500-1000ms (start LLM call earlier)

#### 3.3 Predictive Prefetching
**File:** New `backend/services/prefetch_service.py`
**Strategy:** Predict next likely action and prefetch context

```python
async def prefetch_likely_contexts(user_id: str, session_history: List[str]):
    """Prefetch contexts user is likely to need next."""
    # Analyze session history
    predicted_actions = predict_next_actions(session_history)

    # Prefetch contexts in background
    for action in predicted_actions:
        asyncio.create_task(prefetch_context_for_action(action))

# Example predictions:
# - User asked about tests → Likely to ask about running tests next
# - User asked about file → Likely to ask about editing it next
```

**Expected Impact:** -500-1500ms for predicted requests (20-30% of requests)

---

## Implementation Roadmap

### Week 1: Quick Wins (Target: p50 5.8s → 4.5s)

**Priority:** HIGH
**Risk:** LOW
**Effort:** 1-2 hours

- [ ] Remove artificial typing delay (30 min)
- [ ] Increase stream chunk size (15 min)
- [ ] Add intent detection caching (1 hour)
- [ ] Test with real LLM suite (30 min)
- [ ] Validate 98% success rate maintained (30 min)

**Expected Result:**
- p50: 5.8s → 4.5s (-22%)
- p95: 11.9s → 9.5s (-20%)
- Success rate: 98% (no regression)

### Week 2: Medium-Term Optimizations (Target: p50 4.5s → 3.0s)

**Priority:** MEDIUM
**Risk:** MEDIUM
**Effort:** 2-3 days

- [ ] Implement parallel context building (1 day)
- [ ] Add async image processing (1 day)
- [ ] Implement smart model selection (4 hours)
- [ ] Comprehensive testing (1 day)
- [ ] A/B test in staging (2 days)

**Expected Result:**
- p50: 4.5s → 3.0s (-33%)
- p95: 9.5s → 6.0s (-37%)
- Success rate: 96-98% (acceptable range)

### Week 3-4: Advanced Optimizations (Target: p50 3.0s → 2.0s)

**Priority:** LOW (post-launch)
**Risk:** HIGH
**Effort:** 1 week

- [ ] Implement response caching layer (2 days)
- [ ] Add streaming context updates (2 days)
- [ ] Build predictive prefetching (2 days)
- [ ] Load testing with 100+ concurrent users (1 day)

**Expected Result:**
- p50: 3.0s → 2.0s (-33%) **→ MEETS TARGET! 🎯**
- p95: 6.0s → 4.0s (-33%)
- Success rate: 95-98%

---

## Risk Assessment

### Low-Risk Optimizations (Safe for v1)
✅ Remove typing delay
✅ Increase chunk size
✅ Intent caching
✅ Smart model selection

### Medium-Risk Optimizations (Staging test required)
⚠️ Parallel context building (could introduce race conditions)
⚠️ Async image processing (could affect image-based queries)

### High-Risk Optimizations (Post-launch only)
❌ Response caching (could serve stale data)
❌ Predictive prefetching (could waste resources on wrong predictions)
❌ Streaming context updates (complex state management)

---

## Testing Strategy

### Regression Testing
After each optimization, run the full real LLM test suite:

```bash
./run_tests_now.sh
```

**Success Criteria:**
- Success rate: ≥96% (allow 2% regression for significant latency gains)
- p50 latency: Reduced by ≥20%
- No new error patterns introduced

### A/B Testing
For medium/high-risk changes:

```python
# Feature flag in backend/core/config.py
ENABLE_PARALLEL_CONTEXT = os.getenv("ENABLE_PARALLEL_CONTEXT", "false").lower() == "true"

# In request handler:
if ENABLE_PARALLEL_CONTEXT:
    result = await parallel_context_builder(...)
else:
    result = await sequential_context_builder(...)
```

**Metrics to Track:**
- Latency (p50, p95, p99)
- Success rate
- Error rate by error type
- User satisfaction (if available)

### Load Testing
Before production deployment:

```bash
# Test with 100 concurrent users
./scripts/load_test.sh --users=100 --duration=5m

# Monitor:
# - p99 latency under load
# - Error rate under load
# - Memory/CPU usage
# - Database connection pool
```

---

## Monitoring & Rollback

### Monitoring
Add latency tracking to all optimization points:

```python
import time
from backend.telemetry.metrics import record_metric

async def optimized_function():
    start = time.time()
    try:
        result = await original_function()
        record_metric("optimization.success", 1, {"function": "optimized_function"})
        return result
    finally:
        duration = time.time() - start
        record_metric("optimization.latency_ms", duration * 1000, {"function": "optimized_function"})
```

### Rollback Plan
If optimization causes issues:

```bash
# 1. Disable feature flag
kubectl set env deployment/navi-backend ENABLE_OPTIMIZATION=false -n navi-staging

# 2. Monitor for recovery
kubectl logs -f deployment/navi-backend -n navi-staging | grep "latency\|error"

# 3. If not recovered, rollback deployment
kubectl rollout undo deployment/navi-backend -n navi-staging

# 4. Verify rollback
./scripts/verify_k8s.sh staging
```

---

## Recommendation

### For Production v1 Launch (This Week)

**Ship with current performance:**
- ✅ 98% success rate (excellent)
- ⚠️ 5.8s p50 latency (acceptable for complex AI)
- ✅ All critical bugs fixed
- ✅ Audit encryption enforced

**Rationale:**
- Users expect AI agents to take a few seconds
- 5-10s is reasonable for complex operations
- Premature optimization could break the 98% success rate
- Better to launch stable than fast-but-broken

### Post-Launch Optimization (Week 2-3)

**Implement Phase 1 (Quick Wins):**
- Low risk, easy to implement
- 20-30% latency improvement
- No expected success rate regression

**Timeline:**
- Week 1: Launch v1 with current performance
- Week 2: Monitor production for 1 week
- Week 3: Implement Phase 1 optimizations
- Week 4: A/B test in production, rollout gradually

### Long-Term Optimization (Month 2-3)

**Implement Phase 2 & 3:**
- After production stabilization
- With comprehensive A/B testing
- Gradual rollout with feature flags

**Target Timeline:**
- Month 2: Phase 2 optimizations (p50: 3-4s)
- Month 3: Phase 3 optimizations (p50: 2-3s)
- Quarterly: Continuous optimization based on production data

---

## Conclusion

**Current Status:** ✅ **Production-Ready (with acceptable latency)**

**Optimization Path:**
1. **Launch v1 now** with 98% success rate and 5.8s p50 latency
2. **Week 2-3:** Implement low-risk optimizations (→ 4.5s p50)
3. **Month 2:** Medium-risk optimizations (→ 3.0s p50)
4. **Month 3:** Advanced optimizations (→ 2.0s p50, meets target!)

**Key Insight:**
> Don't let perfect be the enemy of good. Ship a stable, reliable system now. Optimize gradually based on real production usage patterns.

---

*Last Updated: February 6, 2026*
*Author: Claude Sonnet 4.5*
*Status: Ready for Review*
