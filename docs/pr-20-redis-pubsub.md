# PR-20: Redis Pub/Sub for Live Plan Mode (DRAFT)

**Status:** 🚧 Draft - Tracking Issue  
**Depends On:** PR-19 must merge first  
**Priority:** Medium (needed before multi-server production deployment)

## Context

PR-19 implemented Live Plan Mode with in-memory SSE broadcasting. This works for:
- ✅ Single-server development
- ✅ Single-server staging  
- ✅ Testing environments

For production multi-server deployments, we need Redis Pub/Sub.

## Scope

### What This PR Will Add

1. **Broadcast Abstraction**
   - `Broadcast` interface
   - `InMemoryBroadcaster` (existing behavior)
   - `RedisBroadcaster` (new)

2. **Environment-Based Selection**
   - `REDIS_URL` not set → InMemory (dev/test)
   - `REDIS_URL` set → Redis (production)

3. **Testing**
   - Unit tests for both broadcasters
   - Playwright E2E for multi-client sync

4. **Documentation**
   - Deployment guide with Redis setup
   - Docker Compose example

### What This PR Won't Do

- Change Live Plan API contracts (backward compatible)
- Require Redis for development
- Block if Redis unavailable (graceful fallback)

## Implementation Plan

See attached implementation files in issue comments. Key files:
- `backend/infra/broadcast/base.py` - Interface
- `backend/infra/broadcast/memory.py` - Current behavior
- `backend/infra/broadcast/redis.py` - Production backend
- `backend/api/deps.py` - Auto-selection logic
- `tests/e2e/live-plan.spec.ts` - Multi-client E2E

## Prerequisites

- [x] PR-19 merged to main
- [ ] Redis available in staging environment
- [ ] Playwright added to CI pipeline
- [ ] Team decision on Redis hosting (AWS ElastiCache, self-hosted, etc.)

## Acceptance Criteria

- [ ] With `REDIS_URL` unset, behavior identical to PR-19
- [ ] With `REDIS_URL` set, events broadcast across server instances
- [ ] Unit tests pass for both broadcasters
- [ ] E2E test validates multi-client sync
- [ ] Documentation updated
- [ ] No performance regression for in-memory path

## Timeline

**Earliest Start:** After PR-19 merges  
**Estimated Effort:** 2-3 days  
**Target:** Before multi-server production deployment

## Questions for Team

1. **When do we need multi-server?** (determines priority)
2. **Redis hosting preference?** (AWS, self-hosted, etc.)
3. **Should we add Redis to CI?** (for testing, adds complexity)

## Notes

- Implementation is **ready to go** (see attached files)
- Waiting on PR-19 merge to avoid scope creep
- Can ship quickly once PR-19 is merged and prerequisites met

---

## Attached: Implementation Files

*(Implementation provided by user - ready to use once PR-19 merges)*

- Complete broadcast abstraction
- Redis + In-Memory implementations
- Environment-based auto-selection
- Unit tests and E2E suite
- Docker Compose setup

**Total estimated LOC:** ~800 lines (backend + tests + e2e)
