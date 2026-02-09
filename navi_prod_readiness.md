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

### Analytics Endpoints - Multi-Tenant Scoping Tests

**Priority:** High (Security Critical)
**Location:** [backend/api/routers/analytics.py:172-209](backend/api/routers/analytics.py#L172-L209)

#### Issue
The analytics endpoints aggregate sensitive multi-tenant data with dialect-specific date truncation logic. While org_id validation has been added to prevent cross-tenant leakage, there are no tests verifying this critical security boundary.

#### Current Implementation
- `usage_dashboard()`: User-scoped analytics with org_id requirement (added in recent security fix)
- `org_dashboard()`: Org-scoped analytics for admins
- Dialect-specific date grouping: PostgreSQL (`date_trunc`) vs SQLite (`date`)
- Different return types: datetime objects vs strings

#### Required Test Cases
- [ ] Test org_id/user_id filtering prevents cross-tenant data leakage
- [ ] Verify 403 response when org context is missing (security boundary)
- [ ] Test daily grouping output for PostgreSQL (date_trunc returns datetime)
- [ ] Test daily grouping output for SQLite (date returns string)
- [ ] Validate date string parsing differs by dialect
- [ ] Test edge cases: empty data, single day, year boundary
- [ ] Verify aggregations (total_tokens, total_cost, avg_latency) compute correctly

#### Security Impact
Without tests, regressions could:
- Allow cross-tenant analytics leakage if user_id is not globally unique
- Expose sensitive usage metrics to unauthorized users
- Break org isolation guarantees

#### Acceptance Criteria
- API-level integration tests or unit tests for `_summarize_llm_metrics` helper
- Tests cover both PostgreSQL and SQLite dialects
- Security boundary tests confirm org_id requirement is enforced

---

### Audit Logs - CSV Export Memory Optimization

**Priority:** Medium
**Location:** [backend/api/routers/audit.py:224-289](backend/api/routers/audit.py#L224-L289)

#### Issue
CSV export buffers entire response in memory via `StringIO` before returning. With limit up to 10,000 rows and optional payload inclusion (including base64-encoded encrypted data), this can cause significant memory spikes.

#### Current Implementation
- Fetches all rows into memory
- Builds entire CSV in `StringIO` buffer
- Returns complete file via `PlainTextResponse`

#### Recommended Solution
Implement streaming CSV export using FastAPI `StreamingResponse`:
```python
def generate_csv_rows() -> Iterator[str]:
    yield header_row
    for row in fetch_rows_generator():
        yield csv_row

return StreamingResponse(
    generate_csv_rows(),
    media_type="text/csv",
    headers={"Content-Disposition": f'attachment; filename="{filename}"'}
)
```

#### Benefits
- Lower peak memory usage (O(1) vs O(n))
- Faster time-to-first-byte for large exports
- Better UX for exports approaching the 10,000 row limit
- Scales better with payload inclusion enabled

#### Acceptance Criteria
- Streaming implementation for CSV export
- Memory profiling shows reduced peak usage
- Maintains correct CSV formatting and encoding
- Proper handling of base64-encoded payloads

---

### Organization Onboarding - Remove Runtime DDL

**Priority:** Medium
**Location:** [backend/api/routers/org_onboarding.py:46-183](backend/api/routers/org_onboarding.py#L46-L183)

#### Issue
Runtime DDL (CREATE TABLE IF NOT EXISTS) creates divergence between dev/test and production environments, leading to schema drift, permission issues, and debugging complexity.

#### Current Behavior
- Development/test: Creates tables on-demand at request time
- Production/staging: Verifies tables exist, fails if missing
- Uses global flag and threading lock to prevent duplicate DDL

#### Problems
1. **Permissions:** Requires DDL rights that may differ across environments
2. **Concurrency:** Race conditions with multiple requests (even in dev with auto-reload)
3. **Performance:** Overhead on every request (mitigated by flag, but still wasteful)
4. **Operations:** Schema changes not tracked/versioned in dev, causing drift
5. **Debugging:** Different code paths for dev vs prod complicate troubleshooting

#### Recommended Solution
Create Alembic migration for org onboarding tables:
```python
# alembic/versions/XXXX_add_org_tables.py
def upgrade():
    op.create_table(
        'navi_orgs',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('slug', sa.String(length=80), nullable=False, unique=True),
        sa.Column('owner_user_id', sa.String(length=200), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    # ... similar for navi_org_members and navi_org_invites
```

Remove `_ensure_tables()` function entirely.

#### Benefits
- Consistent schema provisioning across all environments
- Version-controlled schema changes
- Eliminates request-path DDL overhead
- Clearer separation of deployment vs runtime concerns

#### Acceptance Criteria
- Alembic migration creates all three tables
- Runtime DDL code removed from org_onboarding.py
- All environments (dev, test, CI, staging, prod) use migrations
- Documentation updated to reflect migration-only approach

---

### MCP Server Secrets - Encryption Enforcement

**Priority:** High (Security Critical)
**Location:** [backend/models/mcp_server.py:24-49](backend/models/mcp_server.py#L24-L49)

#### Issue
The `secret_json` field stores sensitive credentials but has no enforcement preventing accidental plaintext writes. Current implementation relies on developers manually encrypting before writes and decrypting after reads.

#### Current State
- Field type: `LargeBinary` (accepts any bytes)
- No automatic encryption/decryption
- Comment warns to use `encrypt_token()` but no enforcement
- Risk: ORM updates, scripts, or migration errors could store plaintext

#### Recommended Solution
Implement SQLAlchemy `TypeDecorator` for automatic encryption:
```python
from backend.core.crypto import encrypt_token, decrypt_token

class EncryptedBinary(TypeDecorator):
    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Encrypt on write."""
        if value is None:
            return None
        if isinstance(value, str):
            value = value.encode('utf-8')
        return encrypt_token(value)

    def process_result_value(self, value, dialect):
        """Decrypt on read."""
        if value is None:
            return None
        return decrypt_token(value)

# Usage in model:
secret_json = Column(EncryptedBinary, nullable=True)
```

#### Alternative Approach
If TypeDecorator is not feasible:
1. Create repository/service layer as only allowed write path
2. Add runtime validation rejecting non-bytes at write time
3. Validate ciphertext format (Fernet signature)
4. Consider renaming field to `secret_ciphertext` for clarity
5. Enforce via linting rules and code review

#### Security Impact
Without enforcement:
- Accidental plaintext persistence via ORM or scripts
- Secrets exposed in database dumps
- Compliance violations (encryption at rest requirement)

#### Acceptance Criteria
- TypeDecorator implementation or service layer enforcement
- Tests verify automatic encryption/decryption
- Tests confirm plaintext rejection
- Migration to encrypt existing plaintext (if any)

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
