# PR-17: Memory Graph & Temporal Reasoning Engine

**Status:** Complete  
**Version:** 1.0.0  
**Last Updated:** October 27, 2025

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Database Schema](#database-schema)
4. [Graph Builder Heuristics](#graph-builder-heuristics)
5. [Temporal Reasoner](#temporal-reasoner)
6. [API Endpoints](#api-endpoints)
7. [Performance Budgets](#performance-budgets)
8. [Observability](#observability)
9. [Testing](#testing)
10. [Deployment](#deployment)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The Memory Graph & Temporal Reasoning Engine provides automatic relationship discovery and timeline construction across engineering artifacts (JIRA issues, PRs, deployments, incidents, meetings).

### Key Features

- **Automatic Edge Detection:** 6 heuristics discover relationships without manual linking
- **Temporal Reasoning:** Construct timelines and explain causality chains
- **Natural Language Queries:** Ask questions, get narratives with citations
- **Multi-Org Isolation:** Complete RBAC with org-level data separation
- **Real-time Updates:** Incremental graph building as artifacts are created

### Use Cases

1. **Incident Investigation:** "What caused INC-789 and how was it fixed?"
2. **Timeline Reconstruction:** Show all events related to ENG-102
3. **Impact Analysis:** What deployments and incidents are linked to this PR?
4. **Knowledge Transfer:** Generate narratives explaining technical decisions

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer                        │
├──────────────────┬────────────────────┬──────────────────────┤
│  VS Code Panel   │   React Dashboard  │   CLI/Make Targets   │
└──────────────────┴────────────────────┴──────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                      │
├──────────────────┬────────────────────┬──────────────────────┤
│  /graph/rebuild  │  /graph/node/{id}  │    /graph/query      │
│                  │    /timeline       │                       │
└──────────────────┴────────────────────┴──────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                      Core Services                            │
├──────────────────┬────────────────────┬──────────────────────┤
│  GraphBuilder    │  TemporalReasoner  │     AIService        │
│  (6 heuristics)  │  (BFS/Dijkstra)    │  (LLM narratives)    │
└──────────────────┴────────────────────┴──────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              Database (PostgreSQL + pgvector)                 │
├──────────────────┬────────────────────┬──────────────────────┤
│  memory_node     │   memory_edge      │   audit_log          │
│  (entities)      │  (relationships)   │  (RBAC tracking)     │
└──────────────────┴────────────────────┴──────────────────────┘
```

### Data Flow

1. **Ingest:** Artifacts arrive via webhooks (JIRA, GitHub, Slack) or API
2. **Extract:** GraphBuilder applies 6 heuristics to detect relationships
3. **Store:** Nodes and edges written to PostgreSQL with org_id scoping
4. **Query:** TemporalReasoner builds subgraphs and generates narratives
5. **Present:** API returns JSON; UI renders graph/timeline

---

## Database Schema

### memory_node Table

Represents entities: JIRA issues, PRs, meetings, deployments, incidents, etc.

```sql
CREATE TABLE memory_node (
    id SERIAL PRIMARY KEY,
    org_id VARCHAR(255) NOT NULL,
    kind VARCHAR(50) NOT NULL,  -- jira_issue|pr|meeting|run|incident|doc|wiki|slack_thread
    foreign_id VARCHAR(255) NOT NULL,  -- External ID (ENG-102, PR#456, etc.)
    title TEXT,
    summary TEXT,  -- AI-generated summary
    meta_json JSON,  -- Metadata (status, assignee, url, etc.)
    embedding_vec VECTOR(1536),  -- pgvector for semantic search
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_memory_node_org ON memory_node(org_id);
CREATE INDEX idx_memory_node_foreign ON memory_node(org_id, foreign_id);
CREATE INDEX idx_memory_node_kind ON memory_node(org_id, kind);
CREATE INDEX idx_memory_node_embedding ON memory_node USING hnsw (embedding_vec vector_cosine_ops);
```

### memory_edge Table

Represents relationships between nodes with confidence and weight.

```sql
CREATE TABLE memory_edge (
    id SERIAL PRIMARY KEY,
    org_id VARCHAR(255) NOT NULL,
    src_id INTEGER NOT NULL REFERENCES memory_node(id) ON DELETE CASCADE,
    dst_id INTEGER NOT NULL REFERENCES memory_node(id) ON DELETE CASCADE,
    relation VARCHAR(50) NOT NULL,  -- discusses|references|implements|fixes|duplicates|derived_from|caused_by|next|previous
    weight FLOAT NOT NULL DEFAULT 1.0,  -- Edge importance [0, 1]
    confidence FLOAT NOT NULL DEFAULT 1.0,  -- Confidence in relationship [0, 1]
    meta_json JSON,  -- Heuristic source, timestamp_diff, etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_memory_edge_org_rel ON memory_edge(org_id, relation);
CREATE INDEX idx_memory_edge_src ON memory_edge(src_id);
CREATE INDEX idx_memory_edge_dst ON memory_edge(dst_id);
```

### Relation Types

| Relation | Description | Example |
|----------|-------------|---------|
| `discusses` | Meeting or thread mentions entity | Meeting → Issue |
| `references` | One entity mentions another | Issue → PR |
| `implements` | PR implements feature/fix | Issue ← PR |
| `fixes` | PR or action resolves issue | PR → Issue |
| `duplicates` | Two entities are duplicates | Issue → Issue |
| `derived_from` | Entity spawned from another | Meeting → Issue |
| `caused_by` | Incident caused by deployment/change | Incident → Deploy |
| `next` | Temporal successor | PR → Deploy |
| `previous` | Temporal predecessor | Deploy → PR |

---

## Graph Builder Heuristics

The `GraphBuilder` applies 6 heuristics to detect relationships automatically.

### 1. FIXES Pattern Extraction

**Pattern:** `(?:fixes?|closes?|resolves?)\s*(?:#(\d+)|([A-Z]{2,10}-\d+))`

**Logic:**
- Scan PR descriptions, commit messages, and comments
- Extract PR numbers (#123) or JIRA keys (ENG-102)
- Create `fixes` edges: `PR → Issue` and `Issue → PR` (bidirectional)

**Confidence:** 1.0 (explicit reference)

**Example:**
```
PR #456 description: "Implements caching layer. Fixes ENG-102."
→ Creates edges: PR#456 --[fixes]--> ENG-102
                  ENG-102 --[implements]--> PR#456
```

### 2. Meeting Minutes → JIRA Extraction

**Pattern:** JIRA keys in meeting transcripts

**Logic:**
- Extract JIRA keys from meeting summaries/notes
- Create `derived_from` edges: `Meeting → Issue`
- Timestamp proximity boosts confidence

**Confidence:** 0.85-0.95 (depending on context)

**Example:**
```
Meeting notes: "Created ENG-102 to track caching work"
→ Creates edge: Meeting --[derived_from]--> ENG-102
```

### 3. Deployment → PR Linkage

**Pattern:** PR number in deployment metadata

**Logic:**
- Match PR numbers to deployment records
- Create `next/previous` edges
- Track deployment timestamp

**Confidence:** 1.0 (explicit linkage)

**Example:**
```
Deployment DEPLOY-456-prod has pr_number: 456
→ Creates edges: PR#456 --[next]--> DEPLOY-456-prod
                  DEPLOY-456-prod --[previous]--> PR#456
```

### 4. Temporal Proximity (Incident Detection)

**Pattern:** Incident within 24h of deployment

**Logic:**
- Find incidents occurring within 24h after deployments
- Calculate confidence based on time delta (closer = higher)
- Create `caused_by` edges

**Confidence:** 0.7-0.9 (time-based heuristic)

**Example:**
```
DEPLOY-456-prod at 15:30 UTC
INC-789 detected at 09:00 UTC next day (17.5h later)
→ Creates edge: INC-789 --[caused_by]--> DEPLOY-456-prod (confidence: 0.85)
```

### 5. JIRA Key Co-occurrence

**Pattern:** Multiple JIRA keys in same artifact

**Logic:**
- Find JIRA keys mentioned together in descriptions, comments
- Create `references` edges
- Weight by mention frequency

**Confidence:** 0.6-0.8 (contextual)

**Example:**
```
Comment: "This relates to ENG-102 and ENG-98"
→ Creates edge: ENG-102 --[references]--> ENG-98
```

### 6. GitHub Entity Type Detection

**Pattern:** Pull request, issue, discussion mentions

**Logic:**
- Detect GitHub URLs and references
- Extract entity type (PR, issue, discussion)
- Create appropriate edges based on context

**Confidence:** 0.9 (explicit reference)

**Example:**
```
Issue body: "Related to PR #456 and discussion #789"
→ Creates edges: Issue --[references]--> PR#456
                  Issue --[references]--> Discussion#789
```

---

## Temporal Reasoner

The `TemporalReasoner` provides timeline construction and causality path finding.

### timeline_for()

Constructs chronologically ordered event sequences around a root entity.

**Signature:**
```python
def timeline_for(
    org_id: str,
    root_foreign_id: str,
    window: str = "30d"
) -> Dict[str, Any]
```

**Algorithm:**
1. Find root node by `foreign_id`
2. Build subgraph within time window (BFS traversal)
3. Follow `next/previous` edges for temporal sequence
4. Sort by `created_at` timestamp
5. Return nodes + edges + timeline array

**Returns:**
```json
{
  "nodes": [...],
  "edges": [...],
  "timeline": [
    {"ts": "2025-10-01T10:00:00Z", "title": "Sprint Grooming", "kind": "meeting", ...},
    {"ts": "2025-10-01T11:00:00Z", "title": "ENG-102 Created", "kind": "jira_issue", ...},
    ...
  ]
}
```

### explain()

Finds causality paths and generates natural language narratives.

**Signature:**
```python
def explain(
    query: str,
    depth: int = 3,
    k: int = 12
) -> Dict[str, Any]
```

**Algorithm:**
1. Semantic search for relevant nodes (query embedding)
2. Build subgraph up to `depth` hops (BFS or Dijkstra)
3. Limit to top `k` nodes by relevance
4. Find causality chains (`caused_by`, `fixes` edges)
5. Generate narrative via LLM with node citations

**Path Finding:**
- **Weighted BFS:** Fast, used when all edges have similar weights
- **Dijkstra:** Used when weight × confidence varies significantly

**Returns:**
```json
{
  "nodes": [...],
  "edges": [...],
  "narrative": "ENG-102 was implemented in PR #456, which was deployed to production...",
  "citations": ["ENG-102", "PR#456", "DEPLOY-456-prod", "INC-789"]
}
```

---

## API Endpoints

All endpoints require `X-Org-Id` header for multi-tenancy.

### POST /api/memory/graph/rebuild

Enqueue batch graph rebuild for an organization.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/memory/graph/rebuild" \
  -H "Content-Type: application/json" \
  -H "X-Org-Id: default" \
  -d '{
    "org_id": "default",
    "since": "30d"
  }'
```

**Response:**
```json
{
  "status": "enqueued",
  "org_id": "default",
  "job_id": "rebuild_default_2025-10-27",
  "estimated_duration": "2-5 minutes"
}
```

### GET /api/memory/graph/node/{foreign_id}

Get node and 1-hop neighborhood.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/memory/graph/node/ENG-102" \
  -H "X-Org-Id: default"
```

**Response:**
```json
{
  "nodes": [
    {
      "id": 123,
      "org_id": "default",
      "kind": "jira_issue",
      "foreign_id": "ENG-102",
      "title": "Implement caching layer",
      "summary": "Add Redis-based caching...",
      "created_at": "2025-10-01T11:00:00Z"
    },
    ...
  ],
  "edges": [
    {
      "id": 456,
      "src_id": 123,
      "dst_id": 789,
      "relation": "implements",
      "weight": 1.0,
      "confidence": 1.0
    },
    ...
  ]
}
```

### POST /api/memory/graph/query

Natural language graph query with narrative.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/memory/graph/query" \
  -H "Content-Type: application/json" \
  -H "X-Org-Id: default" \
  -d '{
    "query": "Why was ENG-102 reopened and what was the fix?",
    "depth": 3,
    "k": 12
  }'
```

**Response:**
```json
{
  "nodes": [...],
  "edges": [...],
  "narrative": "ENG-102 was initially implemented in PR #456, which introduced a caching layer. After deployment (DEPLOY-456-prod), an incident (INC-789) was detected due to incomplete cache invalidation. The issue was fixed in hotfix PR #478, which added comprehensive invalidation logic.",
  "citations": ["ENG-102", "PR#456", "DEPLOY-456-prod", "INC-789", "PR#478"]
}
```

### GET /api/memory/timeline

Get timeline for an entity.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/memory/timeline?issue=ENG-102&window=30d" \
  -H "X-Org-Id: default"
```

**Response:**
```json
[
  {
    "ts": "2025-10-01T10:00:00Z",
    "id": 100,
    "kind": "meeting",
    "foreign_id": "MEET-2025-10-01",
    "title": "Sprint Grooming"
  },
  {
    "ts": "2025-10-01T11:00:00Z",
    "id": 123,
    "kind": "jira_issue",
    "foreign_id": "ENG-102",
    "title": "Implement caching layer"
  },
  ...
]
```

---

## Performance Budgets

### Target Latencies (P95)

| Operation | Target (P95) | Actual | Status |
|-----------|-------------|--------|--------|
| `timeline_for(depth≤3, k≤12)` | <600ms | TBD | ⏳ Pending |
| `explain(depth≤3, k≤12)` | <600ms | TBD | ⏳ Pending |
| `/graph/node/{id}` | <200ms | TBD | ⏳ Pending |
| `/timeline` | <300ms | TBD | ⏳ Pending |
| `/graph/query` | <800ms | TBD | ⏳ Pending |

### Optimization Strategies

1. **Indexing:**
   - `(org_id, foreign_id)` composite index
   - `(org_id, kind)` for filtering by type
   - HNSW index on `embedding_vec` for semantic search

2. **Caching (Future PR-19):**
   - LRU cache for subgraphs (60s TTL)
   - Redis for hot nodes
   - Precomputed next/previous edges

3. **Query Optimization:**
   - Limit depth to 3 hops maximum
   - Cap node count (k≤12 for narrative generation)
   - Use `joinedload()` to avoid N+1 queries

4. **Background Processing:**
   - Async graph rebuild via task queue
   - Incremental edge attachment on artifact updates
   - Debounce high-frequency events

---

## Observability

### Prometheus Metrics

```python
# Gauges (current state)
aep_graph_nodes_total{org_id="default"}
aep_graph_edges_total{org_id="default"}

# Counters (cumulative)
aep_graph_builds_total{org_id="default", status="success"}
aep_graph_queries_total{org_id="default", endpoint="/graph/query"}

# Histograms (distribution)
aep_graph_build_latency_ms{org_id="default"}
aep_graph_query_latency_ms{org_id="default"}
```

### Audit Logging

All operations logged to `audit_log` table:

```json
{
  "event_type": "GRAPH_READ",
  "org_id": "default",
  "user_id": "alice@example.com",
  "req_id": "uuid-123",
  "endpoint": "/graph/node/ENG-102",
  "params": {"foreign_id": "ENG-102"},
  "duration_ms": 45,
  "node_count": 6,
  "edge_count": 12,
  "timestamp": "2025-10-27T22:00:00Z"
}
```

### Grafana Dashboards

- **Graph Size:** Nodes/edges over time
- **Query Performance:** P50/P95/P99 latencies
- **Build Success Rate:** % successful rebuilds
- **RBAC Violations:** Cross-org access attempts

---

## Testing

### Test Fixture

6-node chain in `data/seed/pr17_fixture.json`:
```
Meeting → ENG-102 → PR#456 → DEPLOY-456 → INC-789 → PR#478 (hotfix)
```

12 edges covering all relation types.

### Running Tests

```bash
# Seed fixture
make pr17-seed

# Run smoke tests
make pr17-smoke

# Run full test suite
pytest tests/test_graph_*.py -v

# Or all at once
make pr17-all
```

### Test Coverage

- **27 test cases** across 4 modules
- **Edge accuracy:** ≥80% threshold validation
- **Timeline ordering:** Strictly increasing timestamps
- **Narrative generation:** Citations and causality chains
- **RBAC isolation:** Cross-org blocking verified

---

## Deployment

### Prerequisites

- PostgreSQL 14+ with pgvector extension
- Python 3.11+
- Redis (for future caching)

### Database Migration

```bash
# Run migration
alembic upgrade head

# Verify tables
psql -d your_db -c "\dt memory_*"
```

### Environment Variables

```bash
# Required
DATABASE_URL=postgresql://user:pass@localhost/dbname
EMBED_DIM=1536

# Optional
GRAPH_CACHE_TTL=60  # seconds
MAX_GRAPH_DEPTH=3
MAX_GRAPH_NODES=12
```

### Initial Seed

```bash
# Load test fixture
python scripts/seed_graph_fixture.py data/seed/pr17_fixture.json

# Or trigger rebuild via API
make graph-rebuild
```

---

## Troubleshooting

### No Edges Created

**Symptoms:** Graph rebuild completes but edge count is 0.

**Causes:**
1. Heuristics not matching artifact format
2. Foreign IDs not normalized
3. Org ID mismatch

**Solutions:**
```bash
# Check node count
psql -c "SELECT org_id, kind, COUNT(*) FROM memory_node GROUP BY org_id, kind;"

# Verify JIRA/PR patterns
psql -c "SELECT foreign_id FROM memory_node WHERE kind IN ('jira_issue', 'pr') LIMIT 10;"

# Review logs
grep "Created edge" logs/graph_builder.log
```

### High Latency on Timeline Queries

**Symptoms:** `/timeline` endpoint >1s response time.

**Causes:**
1. Missing indexes
2. Large time windows
3. Deep subgraph traversal

**Solutions:**
```sql
-- Verify indexes
SELECT tablename, indexname FROM pg_indexes WHERE tablename = 'memory_node';

-- Check query plan
EXPLAIN ANALYZE SELECT * FROM memory_node WHERE org_id='default' AND created_at > NOW() - INTERVAL '30 days';
```

```bash
# Reduce window size
curl "/timeline?issue=ENG-102&window=7d"  # Instead of 30d
```

### Cross-Org Data Leakage

**Symptoms:** Users seeing data from other orgs.

**Causes:**
1. Missing org_id in WHERE clause
2. JOIN without org_id filter
3. Cache key collision

**Solutions:**
```python
# Always filter by org_id
nodes = session.query(MemoryNode).filter(MemoryNode.org_id == org_id).all()

# Verify edges don't cross orgs
SELECT e.id FROM memory_edge e
JOIN memory_node n1 ON e.src_id = n1.id
JOIN memory_node n2 ON e.dst_id = n2.id
WHERE n1.org_id != n2.org_id;  -- Should return 0 rows
```

### Narrative Contains No Citations

**Symptoms:** `explain()` returns narrative without node references.

**Causes:**
1. LLM prompt doesn't emphasize citations
2. Node IDs not included in context
3. Response parsing issue

**Solutions:**
```python
# Verify nodes in context
print(f"Nodes sent to LLM: {[n.foreign_id for n in nodes]}")

# Check LLM response
print(f"Raw narrative: {narrative}")

# Update prompt template
context += "IMPORTANT: Cite entities using their IDs (e.g., ENG-102, PR#456)\n"
```

### Graph Rebuild Stuck

**Symptoms:** Rebuild job never completes.

**Causes:**
1. Circular edge detection loop
2. Database deadlock
3. Task queue failure

**Solutions:**
```bash
# Check task queue
dramatiq workers list

# Check database locks
psql -c "SELECT * FROM pg_stat_activity WHERE state = 'active';"

# Kill stuck job
psql -c "SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE query LIKE '%memory_%';"
```

---

## Future Enhancements

### PR-18: React Dashboard
- Interactive graph visualization
- Timeline filtering and search
- Node detail panels

### PR-19: Performance & Caching
- LRU cache for hot subgraphs
- Precomputed next/previous edges
- Redis-backed cache layer

### PR-20: Streaming Edge Builder
- Real-time edge attachment via webhooks
- Debounced batch processing
- Incremental graph updates

---

## References

- [SQLAlchemy ORM Documentation](https://docs.sqlalchemy.org/)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Graph Algorithms (BFS/Dijkstra)](https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm)

---

**Document Version:** 1.0.0  
**Last Updated:** October 27, 2025  
**Maintained By:** Autonomous Engineering Platform Team
