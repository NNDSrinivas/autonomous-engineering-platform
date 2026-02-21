# Redis Phase 2 Migration Strategy (Centralized Client)

Last updated: 2026-02-20
Status: Phase 1 complete (health check uses centralized lifecycle client; readiness is green).

## 1) Background

Current state (pre-migration):
- Redis client instantiation occurs in multiple modules (≈16 points).
- At least one pattern is broken:
  - module-level singleton created at import time using `aioredis.Redis.from_url(...)`
  - connections can close and be reused → "transport closed" errors

Phase 1 fixed readiness by introducing:
- `backend/services/redis_client.py` with init/shutdown lifecycle
- Health check uses centralized client + optional reset

Phase 2 goal:
- Migrate all Redis usage to the centralized client with minimal disruption and controlled rollout.

## 2) Target End State

All Redis usage flows through one interface:
- `get_redis()` for runtime usage
- `init_redis()` on app startup
- `close_redis()` on shutdown

No module should call:
- `aioredis.Redis.from_url`
- `redis.from_url`
- `Redis.from_url`
- `ConnectionPool.from_url`
outside `redis_client.py`.

## 3) Migration Approach

### Option A (Recommended): Adapter + Gradual Replacement
1. Keep existing abstractions (e.g., `RedisCache`) but change their internals to use `get_redis()`.
2. Remove module-level singletons; instantiate caches/services in startup or dependency injection.
3. Migrate call sites per module, verifying with tests + staging deploy after each batch.

### Option B: Big Bang
Replace all instantiations in one PR.
Not recommended—risk of regressions across features.

We will do Option A.

## 4) Step-by-Step Plan

### Step 4.1 — Inventory
Run ripgrep and create a checklist:

- `Redis.from_url`
- `redis.from_url`
- `aioredis.Redis.from_url`
- `ConnectionPool.from_url`

Record:
- file path
- purpose (cache, rate limit, session, job queue, etc.)
- sync vs async usage

### Step 4.2 — Standardize on a single Redis library
Pick one and standardize:
- Preferred: `redis.asyncio` (redis-py)
- Avoid mixing legacy `aioredis` if possible.

If parts of the app still use `aioredis`, plan a conversion per module.

### Step 4.3 — Create a compatibility layer (if needed)
If existing code expects an `aioredis`-style API, consider a thin wrapper around `redis.asyncio` to reduce code churn.

Example: keep method names consistent (`get`, `set`, `expire`, `pipeline`, etc.).

### Step 4.4 — Migrate module-level singleton caches
Example broken pattern:
- `Cache()` instantiated at import
- holds its own Redis client

Migration:
- Remove module-level instance.
- Provide either:
  - `get_cache()` dependency that uses `get_redis()`, or
  - a cache class that does **not** own the Redis client and instead calls `get_redis()`.

### Step 4.5 — Migrate in safe batches
Batch order (lowest risk first):
1. Health checks (done)
2. Read-only caches (simple GET)
3. Write caches (SET/DEL)
4. Pipelines/transactions
5. PubSub/streams/queues (if any)
6. Rate limiting / distributed locks (highest sensitivity)

After each batch:
- unit tests
- deploy to staging
- verify:
  - no increase in Redis errors
  - readiness stays green
  - key functionality works

## 5) Guidelines & Gotchas

### Avoid creating Redis clients in request handlers
- Use `get_redis()` to reuse the pool.
- Creating clients per request can cause connection churn.

### Avoid module import side-effects
- No `Cache()` singletons created at import.
- No network connections initiated at import.

### Timeouts and resilience
Use explicit timeouts in centralized pool:
- `socket_connect_timeout`
- `socket_timeout`
- `health_check_interval`
- `retry_on_timeout`

### Closing behavior
Only `close_redis()` should close the pool/client.
No other module should call `close()` on the shared client.

## 6) Testing Strategy

- Unit tests with mocked redis client
- Integration test (optional but strong):
  - spin up redis (docker compose) in CI
  - run key cache operations
  - verify no event-loop issues
- Runtime check:
  - staging load test for basic endpoints
  - ensure `/health/ready` stable

## 7) Rollout Checklist

Per PR:
- ✅ Remove one or more Redis instantiation points
- ✅ Replace with `get_redis()` usage
- ✅ Confirm no other module closes shared client
- ✅ Deploy to staging
- ✅ Check:
  - backend logs: no "transport closed"
  - redis ping OK
  - key feature works

## 8) Completion Criteria

Phase 2 is complete when:
- Search for instantiation patterns returns zero results outside `redis_client.py`
- No module-level caches create their own redis clients
- Redis errors are stable near-zero in staging
- Readiness remains green across deploys
