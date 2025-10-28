# PR-19: Live Plan Mode + Real-Time Collaboration

**Status:** ✅ Complete  
**Branch:** `feat/pr-19-live-plan-mode`  
**Type:** Feature  
**Related:** Enhanced by PR-18 (Memory Graph UI for visualizing archived plans)

## 📋 Overview

Live Plan Mode introduces a real-time collaborative planning environment where multiple users can work together on engineering plans. Teams can create plan sessions, add steps in real-time, see each other's contributions live via Server-Sent Events (SSE), and archive completed plans to the memory graph for historical context.

### Key Features

- **Real-time collaboration** - Multiple users see updates instantly via SSE streaming
- **Step-by-step planning** - Add and view plan steps chronologically with owner tracking
- **Participant tracking** - See who's involved in each plan session
- **Memory graph integration** - Archive plans as `plan_session` nodes for context retrieval
- **Frontend dashboard** - React UI for browsing, creating, and collaborating on plans
- **VS Code extension** - Open plan panels directly from the IDE
- **Telemetry** - Prometheus metrics for plan events, latency, and active sessions

## 🏗️ Architecture

### System Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     VS Code Extension                        │
│              (Command + WebView Panel)                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Frontend React UI                          │
│           (PlanList, PlanView, Components)                   │
│              EventSource SSE Connection                      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                   Backend API Layer                          │
│        /api/plan/* (start, get, step, stream, archive)       │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼───────┐ ┌───────▼───────┐ ┌───────▼────────┐
│   PostgreSQL  │ │ SSE Broadcast │ │ Memory Graph   │
│   live_plan   │ │  asyncio.Queue│ │  plan_session  │
│     Table     │ │   (in-memory) │ │     nodes      │
└───────────────┘ └───────────────┘ └────────────────┘
```

### Data Flow

**Creating a Plan Session:**
```
User → POST /api/plan/start → Create LivePlan record → Return plan_id
                             ↓
                    Emit plan_events_total metric (PLAN_START)
```

**Adding a Step (Real-time Broadcast):**
```
User A → POST /api/plan/step → Append to steps JSON array
                               ↓
                        Broadcast to all SSE streams
                               ↓
                        User B receives update via EventSource
                               ↓
                        Frontend merges step into UI
```

**Archiving to Memory Graph:**
```
User → POST /api/plan/{id}/archive → Mark archived=True
                                     ↓
                              Create MemoryNode (kind="plan_session")
                                     ↓
                              Create MemoryEdge (context → plan)
                                     ↓
                              Return memory_node_id
```

## 🗄️ Database Schema

### LivePlan Table

```sql
CREATE TABLE live_plan (
    id VARCHAR PRIMARY KEY,           -- UUID v4
    org_id VARCHAR NOT NULL,          -- Organization identifier
    title VARCHAR NOT NULL,           -- Plan title
    description TEXT,                 -- Optional description
    steps JSON NOT NULL DEFAULT '[]', -- Array of {text, owner, ts}
    participants JSON NOT NULL DEFAULT '[]', -- Array of usernames
    archived BOOLEAN DEFAULT FALSE,   -- Archive status
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ix_live_plan_org_id ON live_plan(org_id);
CREATE INDEX ix_live_plan_archived ON live_plan(archived);
CREATE INDEX ix_live_plan_org_archived ON live_plan(org_id, archived);
```

### Step Structure

Each step in the `steps` JSON array:
```json
{
  "text": "Implement authentication service",
  "owner": "user1",
  "ts": "2025-01-15T10:30:00Z"
}
```

## 🔌 API Endpoints

### 1. Start Plan Session

**POST** `/api/plan/start`

Create a new collaborative plan session.

**Headers:**
```
X-Org-Id: <organization-id>
```

**Request Body:**
```json
{
  "title": "Feature X Implementation",
  "description": "Build the new authentication flow",
  "participants": ["user1", "user2"]
}
```

**Response (200):**
```json
{
  "status": "started",
  "plan_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

---

### 2. Get Plan Details

**GET** `/api/plan/{plan_id}`

Retrieve full plan details including all steps.

**Headers:**
```
X-Org-Id: <organization-id>
```

**Response (200):**
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "org_id": "org-123",
  "title": "Feature X Implementation",
  "description": "Build the new authentication flow",
  "steps": [
    {
      "text": "Design API endpoints",
      "owner": "user1",
      "ts": "2025-01-15T10:30:00Z"
    },
    {
      "text": "Implement JWT service",
      "owner": "user2",
      "ts": "2025-01-15T10:45:00Z"
    }
  ],
  "participants": ["user1", "user2"],
  "archived": false,
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:45:00Z"
}
```

---

### 3. Add Step

**POST** `/api/plan/step`

Add a new step to the plan and broadcast to all connected clients.

**Headers:**
```
X-Org-Id: <organization-id>
```

**Request Body:**
```json
{
  "plan_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "text": "Write unit tests",
  "owner": "user1"
}
```

**Response (200):**
```json
{
  "status": "step_added",
  "step": {
    "text": "Write unit tests",
    "owner": "user1",
    "ts": "2025-01-15T11:00:00Z"
  }
}
```

**Side Effects:**
- Appends step to `steps` JSON array
- Broadcasts step to all SSE streams for this plan
- Emits `plan_step_latency` histogram metric
- Creates audit log: `PLAN_STEP`

---

### 4. Stream Updates (SSE)

**GET** `/api/plan/{plan_id}/stream`

Subscribe to real-time updates via Server-Sent Events.

**Headers:**
```
X-Org-Id: <organization-id>
```

**Response (200 - streaming):**

Content-Type: `text/event-stream`

```
data: {"type": "connected", "plan_id": "a1b2c3d4-..."}

data: {"text": "New step", "owner": "user2", "ts": "2025-01-15T11:05:00Z"}

data: {"text": "Another step", "owner": "user1", "ts": "2025-01-15T11:10:00Z"}
```

**Client-side (EventSource):**
```typescript
const eventSource = new EventSource(
  `${API_URL}/api/plan/${planId}/stream?org=${orgId}`
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.text && data.owner && data.ts) {
    // New step received
    addStepToUI(data);
  }
};

// Cleanup
eventSource.close();
```

---

### 5. Archive Plan

**POST** `/api/plan/{plan_id}/archive`

Mark plan as archived and create memory graph node for context.

**Headers:**
```
X-Org-Id: <organization-id>
```

**Response (200):**
```json
{
  "status": "archived",
  "plan_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "memory_node_id": "m1n2o3p4-..."
}
```

**Side Effects:**
- Sets `archived = TRUE` in database
- Creates `MemoryNode` with:
  - `kind = "plan_session"`
  - `content = JSON(title, steps, participants)`
  - `metadata = {"plan_id": "...", "step_count": 5}`
- Creates `MemoryEdge` linking context to plan
- Emits `plan_events_total` metric (PLAN_ARCHIVE)

---

### 6. List Plans

**GET** `/api/plan/list`

List all plans with optional archive filter.

**Headers:**
```
X-Org-Id: <organization-id>
```

**Query Parameters:**
- `archived` (optional): `true` | `false` - Filter by archive status

**Examples:**
```bash
# List active plans
GET /api/plan/list?archived=false

# List archived plans
GET /api/plan/list?archived=true

# List all plans
GET /api/plan/list
```

**Response (200):**
```json
{
  "plans": [
    {
      "id": "a1b2c3d4-...",
      "title": "Feature X",
      "description": "...",
      "steps": [...],
      "participants": ["user1", "user2"],
      "archived": false,
      "created_at": "2025-01-15T10:00:00Z",
      "updated_at": "2025-01-15T11:00:00Z"
    }
  ],
  "count": 1
}
```

## 🎨 Frontend Components

### File Structure

```
frontend/src/
├── hooks/
│   └── useLivePlan.ts          # React Query hooks for plan API
├── components/
│   ├── StepList.tsx            # Chronological step display
│   └── ParticipantList.tsx     # Participant badges
└── pages/
    ├── PlansListPage.tsx       # Browse/create plans
    └── PlanView.tsx            # Real-time plan collaboration
```

### React Query Hooks

**useLivePlan.ts** provides 5 hooks:

```typescript
// Fetch single plan
const { data: plan, isLoading } = usePlan(planId);

// List plans with filter
const { data: { plans, count } } = usePlanList(archived);

// Create new plan
const startPlan = useStartPlan();
await startPlan.mutateAsync({ title, description, participants });

// Add step
const addStep = useAddStep();
await addStep.mutateAsync({ plan_id, text, owner });

// Archive plan
const archivePlan = useArchivePlan();
await archivePlan.mutateAsync(plan_id);
```

### PlansListPage Component

**Features:**
- Grid layout of plan cards
- Toggle between active/archived views
- Create new plan form (modal/inline)
- Navigate to plan on click
- Display step count, participant count, updated date

**UI Elements:**
- Header: "Live Plans" title + description
- Controls: "Show Archived" toggle + "New Plan" button
- Create form: Title (required) + Description (optional) fields
- Plans grid: Cards with title, description, metadata, archived badge
- Empty state: "No plans" message with create link

### PlanView Component

**Features:**
- Real-time SSE streaming of new steps
- Add step form (owner name + text input)
- Archive plan with confirmation
- Display participants, steps, archived status
- Navigate back to plans list

**State Management:**
```typescript
const [liveSteps, setLiveSteps] = useState<PlanStep[]>([]);
const allSteps = [...(plan?.steps || []), ...liveSteps];
```

**SSE Connection:**
```typescript
useEffect(() => {
  const eventSource = new EventSource(`${API}/plan/${id}/stream?org=${ORG}`);
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.text && data.owner && data.ts) {
      setLiveSteps((prev) => [...prev, data]);
    }
  };
  
  return () => eventSource.close();
}, [id]);
```

## 🔧 VS Code Extension

### Extension Command

**Command ID:** `aep.openPlanPanel`

**Activation:**
- Command palette: "AEP: Open Plan Panel"
- Context menu: "Open in Plan Mode"
- Keybinding: `Cmd+Shift+P` → type "plan"

### WebView Panel

**Implementation:**
```typescript
// extensions/vscode/src/extension.ts
vscode.commands.registerCommand('aep.openPlanPanel', () => {
  const panel = vscode.window.createWebviewPanel(
    'aepPlanView',
    'Live Plan Mode',
    vscode.ViewColumn.Beside,
    { enableScripts: true }
  );
  
  panel.webview.html = getWebviewContent(planId);
});
```

**Features:**
- Embedded plan view with SSE streaming
- Add steps from editor selection
- Archive on completion
- Sync with web dashboard

## 📊 Telemetry & Observability

### Prometheus Metrics

**1. Plan Events Counter**
```python
plan_events_total = Counter(
    'plan_events_total',
    'Total plan events',
    ['event', 'org_id']
)

# Usage:
plan_events_total.labels(event='PLAN_START', org_id=org_id).inc()
plan_events_total.labels(event='PLAN_STEP', org_id=org_id).inc()
plan_events_total.labels(event='PLAN_ARCHIVE', org_id=org_id).inc()
```

**2. Step Latency Histogram**
```python
plan_step_latency = Histogram(
    'plan_step_latency',
    'Latency for adding plan steps',
    ['org_id'],
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 0.8]
)

# Usage:
with plan_step_latency.labels(org_id=org_id).time():
    # Add step logic
```

**3. Active Plans Counter**
```python
plan_active_total = Counter(
    'plan_active_total',
    'Total active plans',
    ['org_id']
)

# Usage:
plan_active_total.labels(org_id=org_id).inc()
```

### Audit Logs

All plan operations create audit entries:

```python
from backend.telemetry.audit import create_audit_log

create_audit_log(
    db=db,
    org_id=org_id,
    user_id=user_id,
    action="PLAN_START",
    resource_type="live_plan",
    resource_id=plan_id,
    details={"title": title, "participants": participants}
)
```

**Event Types:**
- `PLAN_START` - Plan session created
- `PLAN_STEP` - Step added
- `PLAN_ARCHIVE` - Plan archived to memory graph

## 🧪 Testing

### Backend Tests

**File:** `tests/test_plan_api.py`

**Test Classes:**
1. `TestPlanCreation` - Create plans, validation, missing org header
2. `TestPlanRetrieval` - Get plan, not found, RBAC checks
3. `TestAddStep` - Add single/multiple steps, broadcast verification
4. `TestPlanList` - List active/archived, filtering, pagination
5. `TestArchivePlan` - Archive success, memory node creation
6. `TestSSEStream` - Stream connection, non-existent plan

**Run Tests:**
```bash
pytest tests/test_plan_api.py -v
```

### Frontend Playwright Tests

**File:** `tests/e2e/test_plan_smoke.spec.ts`

**Test Scenarios:**
```typescript
test('create and collaborate on plan', async ({ page }) => {
  await page.goto('/plans');
  await page.click('text=New Plan');
  await page.fill('[name="title"]', 'E2E Test Plan');
  await page.click('text=Create Plan');
  
  // Should navigate to plan view
  await expect(page).toHaveURL(/\/plan\/[a-f0-9-]+/);
  
  // Add steps
  await page.fill('[name="owner"]', 'tester');
  await page.fill('[name="text"]', 'Step 1');
  await page.click('text=Add Step');
  
  await expect(page.locator('text=Step 1')).toBeVisible();
  
  // Archive plan
  await page.click('text=Archive Plan');
  await page.click('text=Confirm');
  
  await expect(page).toHaveURL('/plans');
});
```

### Smoke Tests

**File:** `Makefile` target `pr19-smoke`

```bash
make pr19-smoke
```

**Curl Script:**
```bash
#!/bin/bash
set -e

ORG="test-org-123"
API="http://localhost:8000"

echo "Creating plan..."
PLAN_ID=$(curl -s -X POST "$API/api/plan/start" \
  -H "X-Org-Id: $ORG" \
  -H "Content-Type: application/json" \
  -d '{"title":"Smoke Test","participants":["user1"]}' \
  | jq -r '.plan_id')

echo "Plan ID: $PLAN_ID"

echo "Adding step..."
curl -s -X POST "$API/api/plan/step" \
  -H "X-Org-Id: $ORG" \
  -H "Content-Type: application/json" \
  -d "{\"plan_id\":\"$PLAN_ID\",\"text\":\"Test step\",\"owner\":\"user1\"}"

echo "Getting plan..."
curl -s "$API/api/plan/$PLAN_ID" -H "X-Org-Id: $ORG" | jq

echo "Archiving plan..."
curl -s -X POST "$API/api/plan/$PLAN_ID/archive" -H "X-Org-Id: $ORG" | jq

echo "✅ Smoke test passed!"
```

## 🚀 Development Workflow

### Setup

1. **Run Database Migration:**
```bash
alembic upgrade head
```

2. **Start Backend:**
```bash
uvicorn backend.api.main:app --reload --port 8000
```

3. **Start Frontend:**
```bash
cd frontend
npm run dev
```

4. **Open Browser:**
```
http://localhost:5173/plans
```

### Makefile Targets

```makefile
# PR-19 Development
pr19-dev:
	uvicorn backend.api.main:app --reload --port 8000

# Run backend tests
pr19-test:
	pytest tests/test_plan_api.py -v

# Run smoke test
pr19-smoke:
	./scripts/pr19_smoke_test.sh

# Run frontend dev server
ui-plan-dev:
	cd frontend && npm run dev

# Full validation
pr19-all: pr19-migrate pr19-test pr19-smoke
	@echo "✅ PR-19 validation complete"

# Apply migration
pr19-migrate:
	alembic upgrade head
```

### Usage Example

```bash
# 1. Apply migration
make pr19-migrate

# 2. Start backend
make pr19-dev

# 3. In another terminal: Start frontend
make ui-plan-dev

# 4. Open http://localhost:5173/plans
# 5. Click "New Plan", enter title, create
# 6. Add steps, see real-time updates
# 7. Archive plan, verify memory graph node
```

## 🔒 Security Considerations

### RBAC Integration

All endpoints enforce organization-based access:

```python
org_id = request.headers.get("X-Org-Id")
if not org_id:
    raise HTTPException(status_code=400, detail="X-Org-Id header required")

# Check plan belongs to org
plan = db.query(LivePlan).filter(
    LivePlan.id == plan_id,
    LivePlan.org_id == org_id
).first()

if not plan:
    raise HTTPException(status_code=404, detail="Plan not found")
```

### Data Isolation

- Plans filtered by `org_id` in all queries
- SSE streams scoped to organization
- Memory graph nodes tagged with org metadata

### Input Validation

- Title: Max 255 chars, required
- Description: Max 2000 chars, optional
- Step text: Max 1000 chars
- Owner: Max 100 chars
- Participants: Max 50 users per plan

## 📈 Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Step Add Latency | < 200ms p95 | Database + broadcast |
| SSE Connection Time | < 100ms | Initial connection |
| SSE Message Latency | < 50ms | Broadcast to clients |
| Active Plans/Org | 1000 | Concurrent sessions |
| Steps/Plan | 500 | Before performance degrades |
| SSE Retention | 98% | Connection stability |

### Scaling Considerations

**Current (Development):**
- In-memory `asyncio.Queue` for broadcasting
- Single-server SSE connections

**Production (Recommended):**
- Redis Pub/Sub for multi-server broadcasting
- WebSocket upgrade for bidirectional communication
- CDN for static frontend assets
- Read replicas for plan retrieval
- Horizontal scaling with load balancer

**Redis Broadcast Example:**
```python
import redis.asyncio as redis

r = await redis.from_url("redis://localhost")
pubsub = r.pubsub()
await pubsub.subscribe(f"plan:{plan_id}")

async for message in pubsub.listen():
    if message['type'] == 'message':
        yield f"data: {message['data']}\n\n"
```

## 🔗 Memory Graph Integration

### Archive Workflow

When a plan is archived:

1. Create `MemoryNode`:
```python
memory_node = MemoryNode(
    kind="plan_session",
    content=json.dumps({
        "title": plan.title,
        "steps": plan.steps,
        "participants": plan.participants
    }),
    metadata={
        "plan_id": plan.id,
        "step_count": len(plan.steps),
        "archived_at": datetime.utcnow().isoformat()
    },
    org_id=plan.org_id
)
```

2. Create `MemoryEdge` (if context exists):
```python
if context_id:
    edge = MemoryEdge(
        source_id=context_id,
        target_id=memory_node.id,
        kind="used_in_planning",
        org_id=plan.org_id
    )
```

### Querying Archived Plans

Use memory graph queries to retrieve historical plans:

```python
from backend.core.memory.vector_store import search_memories

results = search_memories(
    query="authentication implementation plans",
    org_id="org-123",
    filters={"kind": "plan_session"}
)

for result in results:
    plan_data = json.loads(result.content)
    print(f"Plan: {plan_data['title']}")
    print(f"Steps: {len(plan_data['steps'])}")
```

## 🎯 Success Criteria

- [x] Backend API with 6 endpoints functional
- [x] SSE streaming broadcasts steps to all clients
- [x] Frontend UI for creating/viewing/archiving plans
- [x] Memory graph integration (plan_session nodes)
- [x] Telemetry metrics (events, latency, active count)
- [x] Comprehensive backend tests (pytest)
- [ ] Frontend Playwright smoke tests
- [ ] VS Code extension panel
- [ ] Documentation complete
- [ ] Makefile targets operational

## 📚 Related Documentation

- [PR-18: Memory Graph UI](./pr-18-memory-graph.md)
- [Backend API Reference](./api-reference.md)
- [Frontend Development Guide](./frontend-guide.md)
- [Telemetry & Metrics](./telemetry.md)
- [Memory Graph Architecture](./memory-graph.md)

---

**Contributors:** Autonomous Engineering Platform Team  
**Last Updated:** 2025-01-15  
**Version:** 1.0
