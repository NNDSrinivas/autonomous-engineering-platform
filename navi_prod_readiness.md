# Navi Production Readiness Checklist

This document tracks production readiness items that need to be addressed before deployment or in subsequent PRs.

## Test Coverage

### Redis Cache - getdel_json() Method

**Priority:** High
**Location:** [backend/infra/cache/redis_cache.py:97-151](backend/infra/cache/redis_cache.py#L97-L151)

#### Issue
The `getdel_json()` method introduces critical correctness behavior (atomic get+delete) with multiple fallback paths but lacks targeted test coverage. This method is essential for auth/SSO flows that depend on single-consumer semantics to prevent TOCTOU (Time-of-check to Time-of-use) vulnerabilities.

#### Current Implementation
The method has three execution paths:
1. **Redis GETDEL command** (Redis 6.2+, redis-py with getdel support)
2. **Lua script fallback** (older Redis versions or redis-py without getdel method)
3. **In-memory locked get-then-delete** (when Redis is unavailable)

#### Required Test Cases
- [ ] Test GETDEL command when supported by both server and client
- [ ] Test fallback to Lua script when Redis server returns "unknown command" for GETDEL
- [ ] Test fallback to Lua script when redis-py client lacks getdel method (AttributeError/TypeError)
- [ ] Test in-memory mode with proper locking semantics
- [ ] Test atomicity guarantees in concurrent scenarios
- [ ] Test expiration handling in all code paths

#### Security Impact
Without comprehensive test coverage, regressions in the atomic get+delete behavior could:
- Allow OAuth state reuse (authentication bypass)
- Enable CSRF attacks through state token replay
- Compromise SSO flows that depend on single-use tokens

#### Acceptance Criteria
- Unit tests covering all three execution paths
- Integration tests verifying atomicity under concurrent access
- Tests confirming proper error propagation (e.g., non-"unknown command" ResponseError should raise)

---

## Future Items

### Performance Monitoring
- [ ] Add metrics for cache hit rates in production
- [ ] Monitor LLM API latency and cost per request
- [ ] Track feedback submission rates and patterns

### Security Hardening
- [ ] Implement rate limiting for public endpoints
- [ ] Add API key rotation mechanism
- [ ] Enable audit log encryption at rest

### Operational Excellence
- [ ] Set up alerting for cache eviction rates
- [ ] Create runbook for Redis failover scenarios
- [ ] Document disaster recovery procedures
