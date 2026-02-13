# 🧠 Autonomous Engineering Intelligence Platform
> *The AI-Powered Digital Coworker for Software Engineering Teams*

⚖️ **Licensed under Business Source License 1.1 (BSL). Commercial use prohibited without agreement with NavraLabs.**

---

## 🚀 Vision

Transform how engineering teams work by providing an **autonomous AI assistant** that:
- **Understands** your entire codebase, tickets, and team context
- **Participates** in meetings and discussions like a team member
- **Codes autonomously** under supervision - plans, writes, tests, commits
- **Remembers everything** - decisions, patterns, and team knowledge
- **Integrates seamlessly** with your existing workflow (JIRA, GitHub, IDE)

---

## 💡 Key Capabilities

### 🤖 **Autonomous Coding**
- Plans implementation approaches based on requirements
- Writes code following team patterns and standards
- Runs tests and fixes issues automatically
- Creates PRs with detailed descriptions
- All under human supervision and approval

### 🧠 **Team Memory & Context**
- Persistent memory of all team decisions and discussions
- Understands codebase architecture and patterns
- Tracks project evolution and technical debt
- Provides context-aware suggestions and answers

### 🔗 **Workflow Integration**
- **JIRA**: Understands tickets, priorities, and sprint planning
- **GitHub**: Reviews PRs, understands code changes, manages issues
- **IDE**: Real-time assistance during development
- **Meetings**: Participates in standups, planning, and technical discussions

### 📊 **Intelligence & Analytics**
- Code quality insights and improvement suggestions
- Team productivity analytics and bottleneck identification
- Technical debt tracking and refactoring recommendations
- Knowledge gap analysis and documentation suggestions

---

## ⚙️ Quick Start

### Prerequisites
- **Python 3.11.x** (recommended) or 3.9-3.12
  - ⚠️ Python 3.13+ not yet supported due to dependency compatibility
  - Install Python 3.11: `brew install python@3.11` (macOS) or download from [python.org](https://www.python.org)
- **Node.js 20+** (recommended for VSCode extension development)
  - Node.js 18+ supported for backend/frontend
  - Install Node 20: `brew install node@20` (macOS) or download from [nodejs.org](https://nodejs.org)
- **PostgreSQL**
- **Redis** (optional for development, required for production)

### Installation
```bash
git clone <repository-url>
cd autonomous-engineering-platform

# Backend setup
python3.11 -m venv aep-venv
source aep-venv/bin/activate
pip install -r requirements.txt

# Frontend setup
cd frontend
npm install

# Copy environment configuration
cp .env.template .env
# Edit .env with your configuration
```

### Run Services

#### Development Mode (Fast, No Auto-Reload)
```bash
# Start backend (recommended for development)
source aep-venv/bin/activate
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8787

# Start frontend
cd frontend && npm run dev          # Web UI (port 3000)
```

#### Development Mode (With Auto-Reload)
```bash
# ⚠️ Warning: Auto-reload can cause slow startup on large codebases
# Only use if you need automatic code reloading
source aep-venv/bin/activate
python -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8787
```

#### Production Mode
```bash
# Start with production settings
source aep-venv/bin/activate
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8787 --workers 4

# Frontend production build
cd frontend && npm run build && npm run preview
```

### Verify Installation
```bash
# Check backend health
curl http://localhost:8787/health
# Expected: {"status":"ok","service":"core"}

# Check frontend
open http://localhost:3000
```

---

## 🔧 Troubleshooting

### Backend Not Starting / Slow Performance

**Problem:** Backend takes 3-5 minutes to respond or doesn't start
```bash
ERROR: ModuleNotFoundError: No module named 'fastapi'
ERROR: [Errno 48] Address already in use
```

**Solution:**
```bash
# 1. Kill any hung processes
lsof -ti :8787 | xargs kill -9

# 2. Ensure you're using the correct virtual environment
source aep-venv/bin/activate
python --version  # Should show Python 3.11.x

# 3. Start WITHOUT --reload for better performance
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8787
```

### Python Version Compatibility

**Problem:** Using system Python 3.13+ instead of 3.11
```bash
# Check which Python you're using
python --version
which python
```

**Why Python 3.11?**
- Some dependencies (e.g., `chromadb`, `numpy`, `torch`) may not be compatible with Python 3.13 yet
- Python 3.11 is the stable, tested version for this project
- Python 3.9-3.12 are supported, 3.13+ not yet tested

**Solution:**
```bash
# Install Python 3.11
# macOS:
brew install python@3.11

# Ubuntu/Debian:
sudo apt install python3.11 python3.11-venv

# Create venv with specific Python version
python3.11 -m venv aep-venv
source aep-venv/bin/activate
pip install -r requirements.txt
```

### Auto-Reload Performance Issues

**Problem:** Backend startup is slow with `--reload` flag

**Cause:** WatchFiles monitors the entire codebase (2GB+), causing startup delays

**Solutions:**
```bash
# Option 1: Don't use --reload (recommended)
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8787

# Option 2: Exclude large directories from watching
# Add to .gitignore or create .watchignore
aep-venv/
node_modules/
*.pyc
__pycache__/

# Option 3: Clear Python cache before starting
find backend -name "*.pyc" -delete
find backend -name "__pycache__" -type d -delete
```

### Wrong Virtual Environment

**Problem:** Commands work in terminal but fail in IDE or scripts

**Solution:**
Always activate the correct virtual environment:
```bash
# Check current venv
which python
# Should show: /path/to/autonomous-engineering-platform/aep-venv/bin/python

# If not, activate:
source aep-venv/bin/activate

# Add to your shell profile for convenience (~/.bashrc or ~/.zshrc)
alias aep='cd /path/to/autonomous-engineering-platform && source aep-venv/bin/activate'
```

### Port Already in Use

**Problem:** `[Errno 48] Address already in use`

**Solution:**
```bash
# Find and kill process using port 8787
lsof -ti :8787 | xargs kill -9

# Or use a different port
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8788
```

---

### 🧩 Redis Broadcaster Mode (Production)

For **Live Plan Mode** real-time collaboration across multiple servers, configure Redis Pub/Sub:

#### **Local Development with Docker**
```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Or use docker-compose
docker-compose up -d redis
\`\`\`

#### **Environment Configuration**
```bash
# .env
REDIS_URL=redis://localhost:6379/0
PLAN_CHANNEL_PREFIX=plan:
\`\`\`

#### **Production Deployment**
- **AWS**: Use ElastiCache for Redis
- **Azure**: Use Azure Cache for Redis
- **GCP**: Use Memorystore for Redis
- **Self-hosted**: Configure Redis Cluster with TLS

**Note:** If `REDIS_URL` is not set, the platform falls back to in-memory broadcasting (single-server only).

#### **Docker Compose Example**
\`\`\`yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes

volumes:
  redis-data:
```

### 📦 Distributed Caching (PR-27)

**Why:** Reduce DB load and speed up reads for hot entities (plans, users, roles, orgs).  
**How:** Redis-backed JSON cache with singleflight (anti-stampede) and decorator helpers.

**Key pieces**
- `CacheService.cached_fetch(key, fetcher, ttl)` — central fetch-or-cache
- Decorators: `@cached(key_fn, ttl)` and `@invalidate(key_fn)`
- Keys: `plan:{id}`, `plan:{id}:steps`, `user:{org}:{sub}`, `role:{org}:{sub}`, `org:{key}`
- Middleware adds `X-Cache-*` headers (best-effort counters)

**Config**
```bash
CACHE_ENABLED=true
CACHE_DEFAULT_TTL_SEC=600     # 10 minutes
CACHE_MAX_VALUE_BYTES=262144  # 256 KB
```

**Usage**
```python
from backend.core.cache.decorators import cached, invalidate
from backend.core.cache.keys import plan_key

@cached(lambda plan_id: plan_key(plan_id), ttl_sec=300)
async def read_plan(plan_id: str): ...

@invalidate(lambda plan_id: plan_key(plan_id))
async def update_plan(plan_id: str, patch: dict): ...
```

---

## 🔒 Security & Policies

### **Role-Based Access Control (RBAC)**

The platform enforces role-based access on all Live Plan APIs:

| Role | Permissions |
|------|------------|
| **viewer** | Read-only access: list plans, view plans, subscribe to SSE streams |
| **planner** | All viewer permissions + create plans, add steps, publish changes, archive plans |
| **admin** | All planner permissions + manage users, settings, and configurations |

#### **Authentication Modes**

The platform supports two authentication modes:

**1. JWT Mode (Production)** - Token-based authentication with JWT verification

Set `JWT_ENABLED=true` in your `.env` file and configure JWT settings:

```bash
# .env
JWT_ENABLED=true
JWT_SECRET=your-secret-key-256-bits-minimum
JWT_ALGORITHM=HS256  # or RS256 for asymmetric
JWT_AUDIENCE=api.yourcompany.com  # optional
JWT_ISSUER=auth.yourcompany.com   # optional
```

All API requests must include a valid JWT token in the Authorization header:

```bash
curl -H "Authorization: Bearer eyJhbGc..." https://api.example.com/api/plan/p123
```

**Expected JWT Claims:**
- `sub` (required): user ID
- `org_id` (required): organization ID  
- `role` (defaults to viewer): `viewer`, `planner`, or `admin`
- `email` (optional): user's email address
- `name` (optional): display name
- `projects` (optional): array of accessible project IDs

**2. Development Mode (Local)** - Environment variable-based auth shim

Set `JWT_ENABLED=false` (default) and use DEV_* environment variables:

```bash
# .env
JWT_ENABLED=false  # Default for local development
DEV_USER_ID=u-123
DEV_USER_EMAIL=dev@navralabs.io
DEV_ORG_ID=org-1
DEV_USER_ROLE=planner  # Options: viewer, planner, admin (default: viewer)
DEV_PROJECTS=aep       # Comma-separated project IDs
```

> **Note**: Development mode is for local testing only. Always use JWT mode in production environments.

#### **Admin RBAC (PR-24): Database-Backed User & Role Management**

AEP now persists **Organizations**, **Users**, and **Roles** in the database, enabling centralized user management and flexible role assignments.

**Database Tables:**
- `organizations` - Multi-tenancy support with unique org keys
- `users` - User records linked to organizations via JWT `sub` claim
- `roles` - Standard roles: `viewer`, `planner`, `admin`
- `user_roles` - Role assignments (org-wide or project-scoped)

**Admin Endpoints** (require `admin` role):

```http
POST   /api/admin/rbac/orgs          # Create organization
GET    /api/admin/rbac/orgs          # List all organizations
POST   /api/admin/rbac/users         # Create/update user record
GET    /api/admin/rbac/users/{org_key}/{sub}  # Get user with roles
POST   /api/admin/rbac/roles/grant   # Grant role to user
DELETE /api/admin/rbac/roles/revoke  # Revoke role from user
```

**Example: Creating org and granting roles**
```bash
# 1. Create organization
curl -X POST http://localhost:8000/api/admin/rbac/orgs \
  -H "Authorization: Bearer $ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{"org_key": "navra", "name": "Navra Labs"}'

# 2. Create user (links JWT sub to org)
curl -X POST http://localhost:8000/api/admin/rbac/users \
  -H "Authorization: Bearer $ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "sub": "user-123",
    "email": "user@navra.io", 
    "display_name": "Jane Doe",
    "org_key": "navra"
  }'

# 3. Grant org-wide planner role
curl -X POST http://localhost:8000/api/admin/rbac/roles/grant \
  -H "Authorization: Bearer $ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "sub": "user-123",
    "org_key": "navra",
    "role": "planner"
  }'

# 4. Grant project-scoped admin role
curl -X POST http://localhost:8000/api/admin/rbac/roles/grant \
  -H "Authorization: Bearer $ADMIN_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "sub": "user-123",
    "org_key": "navra",
    "role": "admin",
    "project_key": "special-project"
  }'
```

**Effective Role Resolution:**
- Runtime role = **max(JWT role, DB roles)** where `admin > planner > viewer`
- Cached for 60 seconds (Redis if configured, else in-memory)
- Cache invalidated automatically on role changes

**Migration:**
```bash
# Apply RBAC schema
alembic upgrade head

# Verify tables created
sqlite3 data/engineering_platform.db ".tables"
# Should show: organizations, roles, users, user_roles
```

**Configuration:**
- Uses existing `DATABASE_URL` from your environment
- Optional `REDIS_URL` for role cache (fallback to in-process if not set)

### **Policy Guardrails**

Fine-grained authorization policies prevent dangerous operations. Policies are defined in `.aepolicy.json`:

```json
{
  "version": "1.0",
  "policies": [
    {
      "action": "plan.add_step",
      "deny_if": {
        "step_name_contains": [
          "rm\\s*-?\\s*rf",
          "sudo\\s*rm",
          "DROP\\s+TABLE"
        ]
      },
      "reason": "Dangerous commands not allowed in plan steps"
    }
  ]
}
```

**Note**: Patterns use regex with escape sequences (e.g., `\s*` matches optional whitespace). See `.aepolicy.json` for the full production configuration.

#### **How It Works**

1. **RBAC Check**: FastAPI dependencies (`require_role(Role.PLANNER)`) enforce minimum role requirements
2. **Policy Check**: PolicyEngine validates action against `.aepolicy.json` rules before execution
3. **Secure Defaults**: Missing roles default to `viewer` (read-only), blocked actions return HTTP 403

Example endpoint with RBAC + Policy:

```python
@router.post("/step")
async def add_step(
    user: User = Depends(require_role(Role.PLANNER)),
    policy_engine: PolicyEngine = Depends(get_policy_engine),
):
    # Policy check before executing
    check_policy_inline(
        "plan.add_step",
        {"step_name": step.text},
        policy_engine
    )
    # ... business logic
```

---

### 🚀 Presence & Cursor Sync (PR-22)

Real-time collaboration features for the Live Plan canvas.

**Channels:**
- `presence:plan:{id}` - User join/leave/heartbeat events
- `cursor:plan:{id}` - Cursor position updates

**Configuration:**
```env
PRESENCE_TTL_SEC=60                  # Idle timeout before user marked offline
HEARTBEAT_SEC=20                     # Client heartbeat interval
PRESENCE_CLEANUP_INTERVAL_SEC=60     # Cache cleanup interval (tune for traffic)
```

**Endpoints:**
- `POST /api/plan/{id}/presence/join` - User joins plan (viewer+)
- `POST /api/plan/{id}/presence/heartbeat` - Keep-alive ping (viewer+)
- `POST /api/plan/{id}/presence/leave` - User leaves plan (viewer+)
- `POST /api/plan/{id}/cursor` - Broadcast cursor position (viewer+)

**Frontend Integration:**
Subscribe to the unified `/api/plan/{id}/stream` endpoint which broadcasts both presence events and cursor updates. The frontend renders:
- Live presence list (avatars, online/away status)
- Ghost carets showing other users' cursor positions
- Automatic cleanup after TTL expiration

**Testing:**
```bash
# Unit tests
pytest -q tests/test_presence_ttl.py

# E2E tests
npx playwright install --with-deps
npm run e2e -- tests/e2e/presence-cursor.spec.ts
```

---

## 🧭 Development Roadmap

| Phase | Focus | Timeline |
|-------|-------|----------|
| **Phase 1** | Foundation - Core API, Memory Service, JIRA/GitHub Integration | Q1 2025 |
| **Phase 2** | AI Intelligence - Code Understanding, Context-Aware Q&A | Q2 2025 |
| **Phase 3** | Autonomous Coding - Code Generation, Testing, PR Creation | Q3 2025 |
| **Phase 4** | Team Intelligence - Analytics, Pattern Recognition | Q4 2025 |
| **Phase 5** | Enterprise - Multi-tenant, SSO, Global Deployment | 2026 |

---

## 📞 Contact

**Naga Durga Srinivas Nidamanuri**
- 📧 srinivasn7779@gmail.com
- 🔗 LinkedIn: [nnd-srinivas](https://www.linkedin.com/in/nnd-srinivas/)
- 💻 GitHub: [NNDSrinivas](https://github.com/NNDSrinivas)

---

## 🆕 PR-15: Retrieval-Augmented Context Pack (RACP)

### 🎯 **Intelligent Context for LLM Prompts**

The **Context Pack** feature provides automatic retrieval of relevant knowledge for every agent interaction. No more blind prompts—every LLM call gets enriched with semantic search, episodic memory, and consolidated notes.

#### **Key Features**
- **Hybrid Retrieval**: Combines semantic (55%), keyword (25%), recency (12%), and authority (8%) scoring
- **Episodic Memory**: Records short-term events (plans, decisions, errors, QA exchanges)
- **Agent Notes**: Consolidates sessions into long-term searchable knowledge
- **Policy Filtering**: Respects security policies (public_only, internal_only)
- **Telemetry**: Prometheus metrics for latency and hit counts

### 🏗️ **Architecture**

```
backend/
├── context/
│   ├── schemas.py       # Pydantic models (ContextPackRequest/Response)
│   ├── retriever.py     # Hybrid ranking algorithm
│   └── service.py       # Policy filtering & note fetching
├── api/
│   ├── context_pack.py  # POST /api/context/pack
│   └── memory.py        # POST /api/memory/event, /consolidate
└── telemetry/
    └── context_metrics.py # CTX_LAT_MS, CTX_HITS
```

### 🚀 **API Usage**

#### **1. Build Context Pack**
```bash
curl -X POST "http://localhost:8000/api/context/pack" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "authentication bug in user service",
    "k": 10,
    "sources": ["github", "jira", "slack"],
    "task_key": "ENG-42",
    "policy": "public_only"
  }'
```

**Response:**
```json
{
  "hits": [
    {
      "source": "github",
      "title": "Fix OAuth token refresh logic",
      "excerpt": "Fixed race condition in token refresh...",
      "score": 0.8523,
      "meta": {"pr_number": 123, "status": "Merged"}
    }
  ],
  "notes": [
    {
      "task_key": "ENG-42",
      "summary": "Implemented retry logic for auth failures",
      "importance": 8,
      "tags": ["auth", "reliability"]
    }
  ],
  "latency_ms": 45,
  "total": 10
}
```

#### **2. Record Episodic Event**
```bash
make mem-event
# Records decision, plan, error, qa, exec, or meeting event
```

#### **3. Consolidate into Agent Note**
```bash
make mem-consolidate
# Converts session events into searchable long-term memory
```

### 📊 **Metrics**
- `context_pack_latency_ms`: Retrieval latency histogram (p50, p95, p99)
- `context_pack_hits`: Number of results returned per query

### 🧪 **Testing**
```bash
# Run migration
alembic upgrade head

# Test context pack endpoint
make context-smoke

# Test memory recording
make mem-event
make mem-consolidate
```

#### Integration Tests (NAVI auth-protected)
Some integration tests hit protected NAVI endpoints and require a bearer token.

```bash
# 1) Start backend with dev device flow enabled (in-memory)
export OAUTH_DEVICE_USE_IN_MEMORY_STORE=true
export PUBLIC_BASE_URL=http://127.0.0.1:8787

# 2) Generate a dev token (script created in this repo)
source scripts/get_dev_token.sh

# 3) Run integration tests against the running backend
TEST_BASE_URL=http://127.0.0.1:8787 \
NAVI_TEST_URL=http://127.0.0.1:8787 \
NAVI_TEST_TOKEN="$NAVI_TEST_TOKEN" \
RUN_INTEGRATION_TESTS=1 \
pytest -q tests -m integration
```

Notes:
- `scripts/get_dev_token.sh` prints an `export NAVI_TEST_TOKEN=...` line and auto-exports when sourced.
- Tokens are stored in-memory in dev mode; restarting backend invalidates them.

### 🔗 **Integration with IDE**
The Context Pack is designed for IDE integration. When the agent needs context:
1. IDE sends query + task_key to `/api/context/pack`
2. Backend retrieves relevant chunks using hybrid search
3. Fetches consolidated notes for the task
4. Returns enriched context for LLM prompt

**Example IDE Flow:**
```typescript
const contextPack = await fetch('/api/context/pack', {
  method: 'POST',
  body: JSON.stringify({
    query: userQuery,
    task_key: currentJiraTicket,
    k: 10,
    active_path: editor.activeFile
  })
});
// Inject contextPack.hits into LLM prompt
```

---

## 🆕 PR-8: IDE Agent (VS Code)

### 🎯 **IDE-First Agent Architecture**

The **AEP Agent** provides intelligent coding assistance directly in VS Code with a **shared core** that enables future IDE extensions. Features include:

- **Contextual Greeting**: Time-aware greetings with assigned JIRA tasks
- **Task Selection**: Pick JIRA tickets and fetch comprehensive context packs
- **Smart Planning**: AI-generated implementation plans with file edits, tests, and git operations
- **Ask-Before-Do**: Explicit consent for every file modification and terminal command
- **Policy Enforcement**: Deny-by-default security with `.aepolicy.json` configuration

### 🏗️ **Architecture**

```
├── agent-core/          # Shared TypeScript core for all IDEs
│   ├── src/protocol.ts  # JSON-RPC message types
│   ├── src/runtime.ts   # Agent logic (greet, context, planning)
│   ├── src/tools.ts     # File/terminal operations
│   ├── src/policy.ts    # Security policy enforcement
│   └── src/agentd.ts    # Local WebSocket daemon for future IDEs
├── extensions/vscode/   # VS Code extension
│   ├── src/extension.ts # Main activation and webview
│   └── .vscode/launch.json # F5 debug configuration
└── .aepolicy.json       # Root security policies
```

### 🚀 **Getting Started**

#### **Prerequisites**
- Node.js 18+
- VS Code ^1.84.0  
- Backend services running (core on 8002, realtime on 8001)

#### **Build & Install**

1. **Build Shared Core**
   ```bash
   cd agent-core
   npm install
   npm run build
   ```

2. **Build AEP Professional Extension**
   ```bash
   cd ../extensions/aep-professional
   npm install
   npm run compile
   ```

> 📖 **For developers**: See [extensions/aep-professional/DEVELOPMENT.md](extensions/aep-professional/DEVELOPMENT.md) for detailed development workflow, conflict resolution, and troubleshooting.

#### **Launch Extension**

1. **Open VS Code** in the `extensions/vscode/` directory
2. **Press F5** to launch Extension Development Host
3. **Command Palette** → `AEP: Open Agent`

#### **Expected Workflow**

1. **Greeting** appears: "Good Morning/Afternoon/Evening... You have N tasks..."
2. **Pick a ticket** → Context Pack JSON renders → **Plan Proposed** with steps
3. **Approve & Run** → consent modal for each step → file edits and command execution
4. **Policy Protection**: Denied commands (e.g., `docker login`) are blocked

#### **Optional: Agent Daemon**

For future IDE integrations, start the local WebSocket daemon:

```bash
cd agent-core
npm run dev:agentd
# Listening on ws://127.0.0.1:8765
```

### 🛡️ **Security Policies**

Configure allowed operations in `.aepolicy.json`:

```json
{
  "allow": {
    "commands": ["pytest", "npm", "git"],
    "paths": ["src/**", "tests/**"]
  },
  "deny": { 
    "commands": ["docker login", "curl http://"] 
  }
}
```

### 📊 **Telemetry & Monitoring**

The platform includes comprehensive telemetry for LLM usage tracking and audit logging:

#### **Prometheus Metrics**

Metrics are exposed at `/metrics` endpoint:

- `aep_llm_calls_total{phase,model,status}` - Total LLM calls by phase, model, and status
- `aep_llm_tokens_total{phase,model}` - Total tokens used by LLM calls  
- `aep_llm_cost_usd_total{phase,model}` - Total USD cost of LLM calls
- `aep_llm_latency_ms_bucket{phase,model,le}` - LLM call latency histogram

Example metrics query:
```bash
curl http://localhost:8002/metrics | grep aep_llm
```

#### **Audit Database**

All LLM calls are logged to the `llm_call` table with:

- **Metadata**: phase, model, status, created_at
- **Performance**: tokens, cost_usd, latency_ms  
- **Security**: prompt_hash (no raw prompts stored)
- **Context**: org_id, user_id for multi-tenant support
- **Errors**: error_message for failed calls

#### **Privacy & Security**

- Only telemetry metadata is persisted
- Prompts and context are **hashed** (SHA256) for audit trails
- No raw code or sensitive data is stored
- Error messages are sanitized in user-facing responses

#### **Usage Monitoring**

Test telemetry with the smoke test:
```bash
./scripts/smoke.sh
```

This generates sample plans and verifies metrics are being recorded correctly.

### 🧪 **Testing**

1. **Start Backend Services**
   ```bash
   # Terminal 1: Core API
   python -m uvicorn backend.api.main:app --port 8002 --reload
   
   # Terminal 2: Realtime API  
   python -m uvicorn backend.realtime.main:app --port 8001 --reload
   ```

2. **Launch Extension** (F5 in VS Code)
3. **Test Flow**: Command Palette → "AEP: Open Agent" → Pick task → Approve plan
4. **Verify Policy**: Try denied command to confirm security enforcement

#### **VS Code Webview CORS (Dev Only)**

For local UI testing from the VS Code webview, allow CORS in dev:

```bash
# Dev only: allow all origins for local testing
export CORS_ORIGINS="*"
```

Restart the backend after changing envs. Do not use wildcard CORS in production. In prod, use a strict allowlist and require auth tokens.

#### **NAVI V2 Approval Flow (Onboarding)**

Use V2 plan + approval endpoints for the current approval UX and streaming execution events.

```bash
# 1) Propose plan (returns planId + actions)
curl -X POST http://localhost:8002/api/navi/v2/plan \
  -H "Content-Type: application/json" \
  -H "X-Org-Id: default" \
  -H "X-User-Id: dev1" \
  -d '{"message":"Add a /health endpoint","mode":"plan"}'

# 2) Approve + stream execution
curl -N -X POST http://localhost:8002/api/navi/v2/plan/{planId}/approve/stream \
  -H "Content-Type: application/json" \
  -H "X-Org-Id: default" \
  -H "X-User-Id: dev1"
```

Notes:
- Use `/api/navi/v2/plan/{planId}/approve` for non-stream execution.
- Use `/api/navi/apply` to apply file edits + run commands when actions are ready.

#### **Extension Compile Check**

```bash
./scripts/check_extension_compile.sh
```

#### **VSCode Extension Build Process**

The VSCode extension (`extensions/vscode-aep`) includes an automated webview build process.

**Prerequisites:**
- Node.js 20+ required (Vite 6.x build tooling requires Node 18.19+ or 20+)

**Setup (One-Time):**
```bash
# IMPORTANT: Run from repository root to install all workspace dependencies
cd /path/to/autonomous-engineering-platform
npm install  # Installs all workspaces: navi-contracts, frontend, extension, webview
```

**Build Commands:**
```bash
cd extensions/vscode-aep

# Full build (webview + TypeScript extension)
npm run compile

# Development workflow (faster, TypeScript-only)
npm run watch  # Use this for extension development - no webview rebuild

# Webview development (hot reload)
cd webview && npm run dev  # Live preview at http://localhost:5173

# Publishing
npm run vscode:prepublish  # Builds everything for production
```

**How It Works:**
1. `npm install` at repo root installs all npm workspaces (including webview dependencies)
2. `npm run compile` builds webview (Vite 6.x) → compiles TypeScript extension
3. `npm run watch` watches TypeScript only (no webview rebuild - faster for development)

**Note**: This repository uses npm workspaces. Always run `npm install` from the **repository root** to ensure all workspace dependencies (including `@aep/navi-contracts` local workspace) are correctly resolved. Running `npm install` in subdirectories may break local workspace dependency resolution. For development, use `npm run watch` for fast incremental TypeScript builds.

#### **Enterprise Ops Readiness**

For production-oriented security and ops guidance (audit retention, encryption, JWT rotation),
see `docs/NAVI_PROD_READINESS.md`.

### 🔮 **Future Roadmap**

- **PR-9**: Model Router & LLM-powered Planning with cost controls
- **PR-10**: Confluence/Slack integration for enriched context
- **PR-11**: Automated PR creation with JIRA comments  
- **PR-12**: JetBrains adapter using `agent-core` WebSocket protocol
- **PR-13**: Org Policy & Change Review (RBAC, Guardrails, Approvals) ✅
- **PR-14**: Context Intelligence Dashboard + Memory Search ✅

---

## 🔐 **PR-13 — Organization Policy & Change Review (RBAC + Guardrails)**

Enterprise-grade access control, policy enforcement, and approval workflows for autonomous coding operations.

### **Overview**

PR-13 adds organization-level RBAC (Role-Based Access Control), a policy engine for guardrails, and mandatory review workflows that gate risky actions before execution. This provides enterprise teams with fine-grained control over:

- **Who** can perform which actions (RBAC roles)
- **What** models, commands, paths, repos, and branches are allowed (Policy Engine)
- **When** human approval is required before execution (Change Review Workflow)

### **Architecture**

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐
│   IDE/UI    │────▶│ Policy Check │────▶│ Change Request │
│  Extension  │     │    Engine    │     │   (if needed)  │
└─────────────┘     └──────────────┘     └────────────────┘
                            │                      │
                            ▼                      ▼
                    ┌───────────────┐     ┌──────────────┐
                    │  Org Policy   │     │   Reviewers  │
                    │   Database    │     │ (approve/rej)│
                    └───────────────┘     └──────────────┘
```

### **RBAC Roles**

Four hierarchical roles with distinct permissions:

| Role | Permissions | Use Case |
|------|-------------|----------|
| **admin** | Full control: manage policy, users, approve changes | Platform administrators |
| **maintainer** | Review and approve changes, manage some policy | Tech leads, senior engineers |
| **developer** | Submit changes, execute approved plans | Team developers |
| **viewer** | Read-only access to plans and changes | Stakeholders, auditors |

### **Policy Engine**

Central `org_policy` table controls:

#### **Model Controls**
```json
{
  "models_allow": ["gpt-4o", "claude-3-5-sonnet", "gpt-4-turbo"],
  "phase_budgets": {
    "plan": {"tokens": 150000, "usd_per_day": 5.00},
    "code": {"tokens": 200000, "usd_per_day": 8.00},
    "review": {"tokens": 80000, "usd_per_day": 2.00}
  }
}
```

#### **Command Controls**
```json
{
  "commands_allow": ["pytest", "npm", "git", "grep", "find"],
  "commands_deny": ["docker login", "curl http://", "rm -rf", "sudo"]
}
```

#### **Path & Repository Controls**
```json
{
  "paths_allow": ["backend/**", "frontend/**", "src/**", "tests/**"],
  "repos_allow": ["myorg/myrepo", "myorg/another-repo"],
  "branches_protected": ["main", "master", "release/*"]
}
```

#### **Review Requirements**
```json
{
  "required_reviewers": 1,
  "require_review_for": ["git", "pr", "jira"]
}
```

### **Change Review Workflow**

1. **Plan Generation**: Agent generates execution plan with proposed steps
2. **Policy Check**: Each step validated against org policy
3. **Submit for Review**: If review required, creates `change_request` with status `pending`
4. **Approval Process**: Maintainers/admins review and approve/reject
5. **Execution**: Once approved (`required_reviewers` met), agent executes with ask-before-do flow

```mermaid
sequenceDiagram
    User->>Backend: Generate Plan
    Backend->>Policy Engine: Check each step
    Policy Engine-->>Backend: Violations or Review Required
    Backend->>DB: Create Change Request (pending)
    Reviewer->>Backend: POST /api/change/{id}/review
    Backend->>DB: Record approval
    Backend->>DB: Update status → approved
    User->>Backend: Execute approved plan
```

### **API Endpoints**

#### **Policy Management**

```bash
# Get current org policy
GET /api/policy
Headers: X-Org-Id: default

# Update org policy (admin/maintainer only)
POST /api/policy
Headers: X-Org-Id: default, X-User-Id: admin1
Body: {
  "models_allow": ["gpt-4o"],
  "commands_deny": ["sudo", "docker login"],
  "required_reviewers": 2
}

# Check if action is allowed
GET /api/policy/check?kind=cmd&command=pytest
Headers: X-Org-Id: default
```

#### **Change Requests**

```bash
# Submit change request
POST /api/change/request
Headers: X-Org-Id: default, X-User-Id: dev1
Body: {
  "title": "Implement user authentication",
  "ticket_key": "PROJ-123",
  "plan": {
    "items": [
      {"kind": "edit", "files": ["auth.py"]},
      {"kind": "cmd", "command": "pytest tests/"},
      {"kind": "git", "branch": "main"}
    ]
  }
}

# Response:
{
  "accepted": true,
  "change_id": 42,
  "status": "pending",  # or "approved" if no review needed
  "needs_review": true
}

# Get change request details
GET /api/change/42
Headers: X-Org-Id: default

# Review change request (maintainer/admin only)
POST /api/change/42/review
Headers: X-Org-Id: default, X-User-Id: lead1
Body: {
  "decision": "approve",  # or "reject"
  "comment": "LGTM, proceed with implementation"
}

# List change requests
GET /api/change?status=pending&limit=50
Headers: X-Org-Id: default
```

### **Database Schema**

```sql
-- Organizations
CREATE TABLE org (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(128) NOT NULL
);

-- User-Organization membership with roles
CREATE TABLE org_user (
    id SERIAL PRIMARY KEY,
    org_id VARCHAR(64) REFERENCES org(id),
    user_id VARCHAR(64) NOT NULL,
    role VARCHAR(16) NOT NULL  -- admin|maintainer|developer|viewer
);

-- Organization policies
CREATE TABLE org_policy (
    org_id VARCHAR(64) PRIMARY KEY REFERENCES org(id),
    models_allow TEXT,           -- JSON array
    phase_budgets TEXT,          -- JSON object
    commands_allow TEXT,         -- JSON array
    commands_deny TEXT,          -- JSON array
    paths_allow TEXT,            -- JSON array (globs)
    repos_allow TEXT,            -- JSON array
    branches_protected TEXT,     -- JSON array
    required_reviewers INTEGER DEFAULT 1,
    require_review_for TEXT      -- JSON array
);

-- Change requests submitted for approval
CREATE TABLE change_request (
    id SERIAL PRIMARY KEY,
    org_id VARCHAR(64) REFERENCES org(id),
    user_id VARCHAR(64) NOT NULL,
    ticket_key VARCHAR(64),
    title VARCHAR(256),
    plan_json TEXT NOT NULL,
    patch_summary TEXT,
    status VARCHAR(16) DEFAULT 'pending',  -- pending|approved|rejected
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Reviews for change requests
CREATE TABLE change_review (
    id SERIAL PRIMARY KEY,
    change_id INTEGER REFERENCES change_request(id) ON DELETE CASCADE,
    reviewer_id VARCHAR(64) NOT NULL,
    decision VARCHAR(16) NOT NULL,  -- approve|reject
    comment TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### **Telemetry & Metrics**

New Prometheus metrics for policy enforcement:

```python
# Policy checks
aep_policy_checks_total{result="allow|deny", kind="edit|cmd|git|pr|jira", org_id}

# Change requests
aep_change_requests_total{status="pending|approved|rejected", org_id}

# Change reviews  
aep_change_reviews_total{decision="approve|reject", org_id}

# Budget violations
aep_budget_violations_total{phase="plan|code|review", limit_type="tokens|usd", org_id}
```

### **Setup & Configuration**

1. **Run Migration**
   ```bash
   make migrate  # Applies 0008_org_policy_rbac_approvals
   ```

2. **Seed Default Policy**
   ```bash
   make seed-policy  # Creates 'default' org with sample users and policy
   ```

3. **Verify Setup**
   ```bash
   # Check policy loaded
   curl http://localhost:8002/api/policy \
     -H "X-Org-Id: default"
   
   # Test policy check
   curl "http://localhost:8002/api/policy/check?kind=cmd&command=sudo" \
     -H "X-Org-Id: default"
   # Should return: {"allowed": false, "reasons": ["command denied: sudo"]}
   ```

### **IDE Integration**

Extensions (VS Code, JetBrains) now surface:

1. **Submit for Review** button after plan generation
2. **Policy Violations** displayed inline if action denied
3. **Approval Status** tracking for pending change requests
4. **Execute Approved Plan** button appears when CR approved

Users still retain **ask-before-do** confirmation dialogs during execution, but the policy layer adds organization-wide guardrails and approval gates before reaching that point.

### **Security Best Practices**

✅ **Least Privilege**: Start developers with minimal permissions, expand as needed  
✅ **Protected Branches**: Always include `main`, `master`, `production` in `branches_protected`  
✅ **Command Deny List**: Block `sudo`, `docker login`, `curl http://`, `wget`, `rm -rf`  
✅ **Budget Limits**: Set daily token and cost caps per phase to prevent runaway usage  
✅ **Audit Trail**: All policy checks and reviews logged to `audit_log` table  
✅ **Required Reviews**: Mandate approval for sensitive actions (`git`, `pr`, `jira`)

### **Token Security**

🔒 **Encryption at Rest**: All API tokens (GitHub, JIRA, Slack, Confluence) are encrypted using AWS KMS envelope encryption with AES-256-GCM before database storage.

✅ **Environment Variables**: Set `TOKEN_ENCRYPTION_KEY_ID` to your AWS KMS key ARN  
✅ **KMS Permissions**: Application IAM role needs `kms:GenerateDataKey` and `kms:Decrypt`  
✅ **Key Rotation**: Enable automatic yearly rotation in AWS KMS console  
✅ **Audit Monitoring**: Monitor KMS CloudTrail events for encryption/decryption operations  
✅ **Incident Response**: See `docs/security.md` for token compromise procedures

**Required Environment Setup:**
```bash
# AWS KMS key for token encryption (required for production)
TOKEN_ENCRYPTION_KEY_ID=arn:aws:kms:us-east-1:123456789012:key/your-key-id

# AWS credentials (via IAM role or environment)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key  
AWS_DEFAULT_REGION=us-east-1
```

**Security Validation:**
```bash
# Verify tokens are encrypted in database (should return no plaintext patterns)
psql -c "SELECT access_token LIKE 'github_pat_%' AS plaintext_detected FROM gh_connection;"
psql -c "SELECT access_token LIKE 'xoxb-%' AS plaintext_detected FROM slack_connection;"
```

### **Testing**

```bash
# 1. Seed policy
make seed-policy

# 2. Test policy endpoint
curl http://localhost:8002/api/policy -H "X-Org-Id: default"

# 3. Submit test change request
curl -X POST http://localhost:8002/api/change/request \
  -H "Content-Type: application/json" \
  -H "X-Org-Id: default" \
  -H "X-User-Id: dev1" \
  -d '{
    "title": "Test change",
    "plan": {
      "items": [
        {"kind": "git", "branch": "main", "repo": "myorg/myrepo"}
      ]
    }
  }'

# 4. Review as maintainer
curl -X POST http://localhost:8002/api/change/1/review \
  -H "Content-Type: application/json" \
  -H "X-Org-Id: default" \
  -H "X-User-Id: lead1" \
  -d '{"decision": "approve", "comment": "Approved for testing"}'

# 5. Verify metrics
curl http://localhost:8002/metrics | grep aep_policy
curl http://localhost:8002/metrics | grep aep_change
```

### **Acceptance Criteria**

✅ Migration creates all tables with proper indexes and foreign keys  
✅ `GET /api/policy` returns current org policy configuration  
✅ `POST /api/policy` requires admin/maintainer role  
✅ Policy violations block change requests with detailed reasons  
✅ Change requests requiring review start in `pending` status  
✅ Maintainers/admins can approve/reject changes  
✅ Approval count threshold triggers status → `approved`  
✅ All operations logged to `audit_log` table  
✅ Prometheus metrics increment correctly  
✅ Seed script creates default org, users, and sensible policy


---

## 🧠 **PR-14 — Context Intelligence Dashboard + Memory Search**

**Status:** ✅ Complete  
**Branch:** `feat/pr-14-memory-search`

### Overview

PR-14 adds a **semantic memory search system** that indexes and retrieves content from:
- **JIRA issues** (summaries, descriptions, status)
- **Meeting summaries** (action items, decisions, transcripts)
- **GitHub code** (file content from indexed repositories)

A lightweight **Next.js dashboard** provides a unified search interface with citations, scores, and direct links to source content.

### Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ JIRA Issues  │────▶│              │     │              │
│ Meeting Data │────▶│   Indexer    │────▶│ memory_chunk │
│ GitHub Files │────▶│              │     │  (embeddings)│
└──────────────┘     └──────────────┘     └──────────────┘
                              │
                              ▼
                     ┌──────────────┐
                     │   Retriever  │
                     │  (cosine sim)│
                     └──────────────┘
                              │
                              ▼
                     ┌──────────────┐
                     │ /api/search  │◀──── Next.js UI
                     └──────────────┘
```

### Database Schema

**Tables:**
- `memory_object` - Source content metadata (JIRA key, meeting ID, file path)
- `memory_chunk` - Text chunks with embeddings for semantic search

**Migration:** `alembic/versions/0009_memory_search.py`

### API Endpoints

#### `POST /api/search/`
Semantic search across all indexed content.

**Request:**
```json
{
  "q": "jwt token expiry handling",
  "k": 8
}
```

**Response:**
```json
{
  "hits": [
    {
      "score": 0.8234,
      "source": "jira",
      "title": "Fix JWT refresh token rotation",
      "foreign_id": "PROJ-123",
      "url": "https://your-jira.atlassian.net/browse/PROJ-123",
      "meta": {"status": "In Progress"},
      "chunk_seq": 0,
      "excerpt": "Implement JWT token refresh rotation to prevent..."
    },
    {
      "score": 0.7891,
      "source": "code",
      "title": "auth/jwt.py",
      "foreign_id": "org/repo::auth/jwt.py",
      "url": "https://github.com/org/repo/blob/HEAD/auth/jwt.py",
      "meta": {"repo": "org/repo", "path": "auth/jwt.py"},
      "chunk_seq": 2,
      "excerpt": "def refresh_token(token: str) -> str:\\n    ..."
    }
  ]
}
```

#### `POST /api/search/reindex/jira`
Reindex all JIRA issues (limit: 2000 most recent).

#### `POST /api/search/reindex/meetings`
Reindex meetings and summaries (limit: 1000 most recent).

#### `POST /api/search/reindex/code`
Reindex GitHub code files (limit: 5000 most recent).

### Embeddings Configuration

Set via environment variables:

```bash
# Embedding provider (default: openai)
EMBED_PROVIDER=openai

# OpenAI embedding model (default: text-embedding-3-small)
OPENAI_EMBED_MODEL=text-embedding-3-small

# Vector dimensions (default: 1536 for OpenAI)
EMBED_DIM=1536

# OpenAI API key (required for openai provider)
OPENAI_API_KEY=sk-...
```

**Dev Fallback:** If `OPENAI_API_KEY` is not set, a simple fallback embedder is used (returns sparse vectors based on text length).

### Web Dashboard

**Tech Stack:** Next.js 14, TypeScript, React 18

**Features:**
- **Overview** page (`/`) - Introduction and stats
- **Memory Search** page (`/search`) - Query interface with live results
- Citation cards showing source, score, excerpt, and links

**Run Locally:**
```bash
# Install dependencies and start dev server
make web-dev

# Open http://localhost:3030
```

**Configuration:**
Copy `web/.env.local.example` to `web/.env.local`:
```
NEXT_PUBLIC_AEP_CORE=http://localhost:8002
```

### Setup & Usage

1. **Run Migration**
   ```bash
   make migrate  # Applies 0009_memory_search
   ```

2. **Start Core API**
   ```bash
   make dev  # Backend runs at :8002
   ```

3. **Reindex Content**
   ```bash
   make reindex  # Populates memory from JIRA/Meetings/GitHub
   ```
   
   Or manually:
   ```bash
   curl -X POST "http://localhost:8002/api/search/reindex/jira" \
     -H "X-Org-Id: default"
   
   curl -X POST "http://localhost:8002/api/search/reindex/meetings" \
     -H "X-Org-Id: default"
   
   curl -X POST "http://localhost:8002/api/search/reindex/code" \
     -H "X-Org-Id: default"
   ```

4. **Start Dashboard**
   ```bash
   make web-dev  # Next.js runs at :3030
   ```

5. **Search**
   - Open http://localhost:3030/search
   - Enter query: "authentication bugs", "meeting decisions on API rate limits", etc.
   - View results with scores, sources, and links

### Smoke Test

```bash
# 1. Index sample content
make reindex

# 2. Test semantic search API
curl -X POST "http://localhost:8002/api/search/" \
  -H "Content-Type: application/json" \
  -H "X-Org-Id: default" \
  -d '{"q": "jwt expiry", "k": 5}'

# 3. Open dashboard
make web-dev
# Visit http://localhost:3030/search
```

### Performance & Limits

- **Chunk size:** 1200 chars with 150 char overlap
- **Max chunks scanned:** 6000 per query (adjust in `retriever.py` if needed)
- **Reindex limits:**
  - JIRA: 2000 most recent issues
  - Meetings: 1000 most recent
  - Code: 5000 most recent files
  
For production deployments:
- Use a vector database (Pinecone, Weaviate, pgvector) for >10k chunks
- Implement incremental indexing on JIRA/GitHub webhooks
- Add background workers for async reindexing

### Acceptance Criteria

✅ `memory_object` and `memory_chunk` tables created  
✅ `/api/search` returns top-k results with citations  
✅ Reindex endpoints populate embeddings from JIRA/Meetings/Code  
✅ Next.js dashboard runs locally at :3030  
✅ Search interface displays source, title, excerpt, and Open link  
✅ Works with SQLite and PostgreSQL  
✅ Embeddings provider configurable via env vars  
✅ All API calls audited and rate-limited (existing middleware)

### Roadmap: Extended Connectors

**Coming next:** Connector integrations for:
- **Slack** - Index messages, threads, pins
- **Confluence** - Index wiki pages, attachments
- **Microsoft Teams** - Index chat, files
- **Zoom** - Index transcripts, recordings

---

## 🔌 Extended Connectors (Slack, Confluence, Wiki, Zoom/Teams)

### 🎯 **Expanded Memory Coverage**

Extended connectors expand memory search to cover your entire knowledge base:
- **Slack**: Messages, threads, channels (incremental sync with cursor)
- **Confluence**: Wiki pages, documentation spaces
- **Local Wiki**: Markdown files from `docs/` directory
- **Zoom/Teams**: Meeting transcripts and summaries

All content is **read-only**, **org-scoped**, and **indexed into memory** for unified semantic search.

### 🏗️ **Architecture**

```
backend/
├── integrations_ext/          # Read-only connectors
│   ├── slack_read.py          # Slack Web API client
│   ├── confluence_read.py     # Confluence REST API
│   └── wiki_read.py           # Local markdown scanner
├── api/integrations_ext.py    # Connection management endpoints
├── search/router.py           # Extended reindex endpoints
└── telemetry/ingest_metrics.py # Prometheus counters

alembic/versions/
└── 0010_ext_connectors.py     # slack_connection, confluence_connection, sync_cursor, wiki_page
```

### 🚀 **Getting Started**

#### **1. Apply Migration**
```bash
make migrate  # applies 0010_ext_connectors
```

#### **2. Connect Integrations**

**Slack:**
```bash
curl -X POST http://localhost:8002/api/integrations-ext/slack/connect \
  -H 'Content-Type: application/json' \
  -H 'X-Org-Id: default' \
  -d '{"bot_token":"xoxb-your-token","team_id":"T12345"}'
```

**Confluence:**
```bash
curl -X POST http://localhost:8002/api/integrations-ext/confluence/connect \
  -H 'Content-Type: application/json' \
  -H 'X-Org-Id: default' \
  -d '{
    "base_url":"https://your.atlassian.net/wiki",
    "access_token":"your-token",
    "email":"you@org.com"
  }'
```

#### **3. Reindex Content**

```bash
# Reindex all extended sources
make reindex-ext

# Or individually:
curl -X POST http://localhost:8002/api/search/reindex/slack -H 'X-Org-Id: default'
curl -X POST http://localhost:8002/api/search/reindex/confluence \
  -H 'X-Org-Id: default' \
  -H 'Content-Type: application/json' \
  -d '{"space_key":"ENG"}'
curl -X POST http://localhost:8002/api/search/reindex/wiki -H 'X-Org-Id: default'
curl -X POST http://localhost:8002/api/search/reindex/zoom_teams -H 'X-Org-Id: default'
```

#### **4. Search Across Sources**

```bash
curl -X POST http://localhost:8002/api/search/ \
  -H 'Content-Type: application/json' \
  -H 'X-Org-Id: default' \
  -d '{"q":"authentication flow","k":10}'
```

**Response includes results from all sources:**
```json
{
  "hits": [
    {"source":"slack","score":0.89,"title":"#eng-auth 1698765432.123","excerpt":"We decided to use OAuth2..."},
    {"source":"confluence","score":0.86,"title":"Auth Architecture","url":"https://...","excerpt":"..."},
    {"source":"wiki","score":0.82,"title":"security","excerpt":"Authentication patterns..."},
    {"source":"meeting","score":0.78,"title":"Meeting 42","excerpt":"Discussed MFA implementation..."}
  ]
}
```

### 📊 **API Endpoints**

#### **Connection Management**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/integrations-ext/slack/connect` | POST | Connect Slack workspace |
| `/api/integrations-ext/confluence/connect` | POST | Connect Confluence instance |

**Request Headers:**
- `X-Org-Id`: Organization identifier (required)
- `Content-Type: application/json`

**Slack Connect Body:**
```json
{
  "bot_token": "xoxb-...",  // required: Slack Bot User OAuth Token
  "team_id": "T12345"       // optional: Team ID
}
```

**Confluence Connect Body:**
```json
{
  "base_url": "https://your.atlassian.net/wiki",  // required
  "access_token": "...",                          // required: API token or OAuth
  "email": "you@org.com"                          // optional
}
```

#### **Reindex Endpoints**

| Endpoint | Method | Description | Body |
|----------|--------|-------------|------|
| `/api/search/reindex/slack` | POST | Index Slack messages (incremental) | None |
| `/api/search/reindex/confluence` | POST | Index Confluence pages | `{"space_key":"KEY"}` |
| `/api/search/reindex/wiki` | POST | Index local markdown docs | None |
| `/api/search/reindex/zoom_teams` | POST | Index Zoom/Teams transcripts | None |

**All reindex endpoints:**
- Return: `{"ok": true, "count": <num_docs>}`
- Headers: `X-Org-Id` required
- Rate-limited and audited (existing middleware)

### 🔒 **Security Features**

- **Read-only access**: No writes to Slack/Confluence/etc.
- **Org isolation**: `X-Org-Id` header enforced on all endpoints
- **Token storage**: ⚠️ Currently stored in plaintext (encryption planned - see [Issue #18](https://github.com/NNDSrinivas/autonomous-engineering-platform/issues/18))
- **Incremental sync**: Slack uses cursor-based pagination
- **Rate limiting**: Inherited from existing API middleware
- **Audit logs**: All API calls logged with request IDs

> **⚠️ SECURITY NOTE**: Token encryption at rest is not yet implemented. This is acceptable for development/testing environments but **must be addressed before production deployment**. See `backend/api/integrations_ext.py` for TODO comments with implementation options.

### 📈 **Metrics (Prometheus)**

```python
# backend/telemetry/ingest_metrics.py
INGEST_DOCS = Counter('aep_ingest_docs_total', 'Docs ingested into memory', ['source'])
INGEST_ERRORS = Counter('aep_ingest_errors_total', 'Ingestion errors', ['source'])
```

**Usage in endpoints:**
```python
from backend.telemetry.ingest_metrics import INGEST_DOCS, INGEST_ERRORS

INGEST_DOCS.labels(source="slack").inc(count)
INGEST_ERRORS.labels(source="confluence").inc()
```

### 🗄️ **Database Schema**

**slack_connection** - Slack workspace credentials
```sql
CREATE TABLE slack_connection (
  id INTEGER PRIMARY KEY,
  org_id VARCHAR(64) NOT NULL,
  bot_token TEXT NOT NULL,
  team_id VARCHAR(64),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**confluence_connection** - Confluence instance credentials
```sql
CREATE TABLE confluence_connection (
  id INTEGER PRIMARY KEY,
  org_id VARCHAR(64) NOT NULL,
  base_url TEXT NOT NULL,
  access_token TEXT NOT NULL,
  email TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**sync_cursor** - Incremental sync state (e.g., Slack message timestamps)
```sql
CREATE TABLE sync_cursor (
  id INTEGER PRIMARY KEY,
  org_id VARCHAR(64) NOT NULL,
  source VARCHAR(32) NOT NULL,  -- slack|confluence|wiki|zoom|teams
  cursor TEXT,                  -- timestamp/etag/id
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_sync_cursor_org_src ON sync_cursor(org_id, source);
```

**wiki_page** - Local wiki/docs content cache (optional)
```sql
CREATE TABLE wiki_page (
  id INTEGER PRIMARY KEY,
  org_id VARCHAR(64) NOT NULL,
  title TEXT NOT NULL,
  url TEXT,
  content TEXT,
  updated TIMESTAMP
);
```

### 🎯 **Acceptance Criteria**

✅ Connections persisted and audited  
✅ Reindex endpoints populate `memory_object`/`memory_chunk`  
✅ Slack incremental sync with cursor (no duplicates)  
✅ Confluence pages indexed with HTML→text cleaning  
✅ Local wiki markdown files scanned from `docs/`  
✅ Zoom/Teams meeting transcripts reused from PR-3 tables  
✅ `/api/search` returns unified results across all sources  
✅ Source badges, titles, excerpts, URLs displayed correctly  
✅ Prometheus metrics track ingestion counts and errors  
✅ All endpoints enforce `X-Org-Id` header requirement  

### 🚧 **Future Enhancements**

**Planned improvements:**
- **OAuth flows** for Slack/Confluence (vs. token-based)
- **Webhook-based sync** for real-time updates
- **Attachment indexing** (PDFs, images with OCR)
- **Vector database upgrade** (pgvector/FAISS for >10k chunks)
- **Hybrid search** (BM25 + semantic for better recall)
- **Data residency controls** (PII filtering, field-level policies)
- **Retrieval-Augmented Context** (auto-attach relevant docs to coding tasks)

### 🛠️ **Development Tips**

**Testing locally:**
```bash
# 1. Connect test workspace (get tokens from Slack/Confluence admin)
curl -X POST http://localhost:8002/api/integrations-ext/slack/connect \
  -H 'Content-Type: application/json' \
  -H 'X-Org-Id: test-org' \
  -d '{"bot_token":"xoxb-test"}'

# 2. Reindex (will use cursor for incremental updates)
make reindex-ext

# 3. Search
curl -X POST http://localhost:8002/api/search/ \
  -H 'Content-Type: application/json' \
  -H 'X-Org-Id: test-org' \
  -d '{"q":"your search query","k":5}' | jq .
```

**Monitoring:**
```bash
# Check Prometheus metrics
curl http://localhost:8002/metrics | grep aep_ingest

# View recent ingestion logs
docker logs aep_core | grep "reindex"
```

**Debugging sync issues:**
```sql
-- Check current sync cursor
SELECT * FROM sync_cursor WHERE org_id='default' AND source='slack';

-- Reset cursor (force full reindex)
DELETE FROM sync_cursor WHERE org_id='default' AND source='slack';
```

---

## 🎉 Recent Features & Updates

- **Live Plan Mode**: Real-time collaborative planning with SSE updates, step tracking, and memory graph archiving.
- **Memory Graph UI**: Interactive graph and timeline views with rich node inspection and search tooling.

---

## ⚖️ License & Usage

### Business Source License 1.1 (BSL)

This project is licensed under the **Business Source License 1.1**. 

**What You CAN Do:**
- ✅ **Study & Learn** - Read and understand the code
- ✅ **Fork for Learning** - Create private forks for educational purposes
- ✅ **Internal Testing** - Test within your organization (non-production)
- ✅ **Research** - Use for academic or personal research
- ✅ **Contribute** - Submit PRs (requires signing CLA)

**What You CANNOT Do:**
- ❌ **Deploy Publicly** - No hosting or publishing as a public app/service
- ❌ **Commercial Use** - No SaaS, hosting, or commercial deployment
- ❌ **Sell or License** - Cannot resell or sublicense the software
- ❌ **Rebrand** - Cannot white-label or use "NavraLabs" trademarks
- ❌ **Production Use** - Cannot use to serve external customers

### Change Date: 2029-01-01

On **2029-01-01**, this license automatically converts to **Apache License 2.0**, making it fully permissive and open-source.

### Commercial Licensing

Need to deploy AEP in production or offer it as a service?

**Contact:** legal@navralabs.ai  
**Founder:** NagaDurga S. Nidamanuri

We offer flexible commercial licenses for:
- Enterprise deployments
- White-label solutions
- SaaS hosting rights
- Custom support and features

### Enforcement

Unauthorized deployments are actively monitored and will be subject to:
- DMCA takedown requests
- Cease and desist notices
- Legal action for trademark infringement
- Reporting to hosting providers (AWS, GCP, Azure, etc.)

See [ENFORCEMENT_PLAYBOOK.md](ENFORCEMENT_PLAYBOOK.md) for details.

---

## 📄 Additional Legal Documents

- [LICENSE](LICENSE) - Full BSL 1.1 license text
- [TRADEMARK.md](TRADEMARK.md) - NavraLabs trademark policy
- [SECURITY.md](SECURITY.md) - Security vulnerability disclosure
- [CLA.md](CLA.md) - Contributor License Agreement
- [NOTICE](NOTICE) - Copyright and ownership notice

---

### Observability & Tracing (PR-28)

**Structured Logs**
- JSON logs with `ts, level, msg, request_id, org_id, user_sub, route, method, status`
- Config: `LOG_LEVEL=INFO|DEBUG`, `APP_NAME=aep`

**Metrics (Prometheus)**
- `/metrics` endpoint (when `PROMETHEUS_ENABLED=true`)
- `http_requests_total{service,method,path,status}`
- `http_request_latency_seconds{service,method,path,status}`
- `sse_stream_drops_total{plan_id}`
- `plan_publish_e2e_seconds{plan_id}`

**Tracing (OpenTelemetry OTLP)**
- Env: `OTEL_ENABLED=true`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318`
- Auto-instrumented FastAPI spans with service name from `APP_NAME`

**Headers**
- `X-Request-Id` is attached to every response for correlation
- `Server-Timing` includes a basic app timing segment

### Health Checks & Circuit Breakers (PR-29)

**Endpoints**
- `GET /health/live` — liveness (always simple/fast)
- `GET /health/ready` — readiness: checks DB/Redis with latency per check
- `GET /health/startup` — mirrors readiness for platforms that require a separate probe

**Circuit Breakers**
- Lightweight async breaker utility with states: **closed → open → half-open → closed**
- Open after N failures within a window; half-open after `open_sec`; close on M successes
- Middleware returns **503** with `X-Circuit: open` when upstream is unavailable

**K8s Probes (example)**
```yaml
livenessProbe:
  httpGet: { path: /health/live, port: 8000 }
  initialDelaySeconds: 5
  periodSeconds: 10
readinessProbe:
  httpGet: { path: /health/ready, port: 8000 }
  initialDelaySeconds: 10
  periodSeconds: 10
```

### UI/UX Resilience & Offline Resume (PR-30)

**Bulletproof frontend experience with auto-recovery and offline support**

Enhanced frontend resilience ensures uninterrupted collaboration even with poor network conditions, browser refreshes, or temporary backend outages.

#### Key Features
- **SSE Auto-Resume** - Automatic reconnection with Last-Event-ID backfill
- **Offline Outbox** - Queue mutations locally when offline, flush when back online
- **Connection UI** - Visual indicators and notifications for connection state
- **Presence Idle Detection** - Smart away/idle state management
- **Toast Notifications** - User-friendly feedback for network events

#### Architecture
```
User Action → Offline Outbox → Network Available? → Backend API
     ↓              ↓                    ↓             ↓
SSE Client ← Connection State ← Browser Events → UI Updates
```

#### Frontend Components

**SSE Client** (`frontend/src/lib/sse/SSEClient.ts`)
- Resilient SSE client with auto-reconnect and exponential backoff
- Last-Event-ID tracking for seamless event resume
- Demultiplexed subscriptions (multiple callbacks per connection)
- Smart reconnection logic with circuit breaker patterns

**Offline Outbox** (`frontend/src/lib/offline/Outbox.ts`)
- localStorage-based mutation queueing for offline scenarios
- Automatic flush when connection restored
- Persistent across page refreshes and browser restarts
- FIFO queue with retry logic and error handling

**Connection Management** (`frontend/src/state/connection/useConnection.ts`)
- Real-time tracking of browser online/offline state
- SSE connection health monitoring
- React hooks for component integration
- Event-driven state updates

**UI Components**
- `ConnectionChip.tsx` - Visual connection status indicator
- `Toast.tsx` - Notification system for network events
- Integrated into `PlanView.tsx` with offline-aware interactions

#### Backend Enhancements

**Enhanced SSE Streaming** (`backend/api/routers/plan.py`)
```python
# Last-Event-ID support for resume
if last_event_id := request.headers.get("Last-Event-ID"):
    since = int(last_event_id)
    # Backfill missed events from eventstore
    backfill_events = eventstore.replay(plan_id, since)
    for event in backfill_events:
        yield f"id: {event.seq}\ndata: {json.dumps(event.data)}\n\n"

# Continue with live stream
async for event in broadcaster.stream(plan_id):
    yield f"id: {event.seq}\ndata: {json.dumps(event.data)}\n\n"
```

**Event Sequence Tracking**
- Every SSE event includes sequence ID for ordered replay
- Eventstore maintains chronological event history
- Gap detection and backfill for missed events

#### Usage Example

**Resilient Plan Updates**
```typescript
// Auto-reconnecting SSE client
const sseClient = new SSEClient('/api/plan/stream');

// Subscribe to plan updates with auto-resume
sseClient.subscribe('plan:123', (event) => {
  updatePlanUI(event.data);
});

// Offline-aware mutations
const handleAddStep = async (step: PlanStep) => {
  if (!isOnline) {
    // Queue for later when back online
    outbox.push({
      method: 'POST',
      url: `/api/plan/${planId}/step`,
      body: step
    });
    showToast('Step queued (offline)', 'info');
    return;
  }
  
  try {
    await api.addPlanStep(planId, step);
  } catch (error) {
    // Fallback to outbox on failure
    outbox.push({ method: 'POST', url: `/api/plan/${planId}/step`, body: step });
    showToast('Step queued for retry', 'warning');
  }
};
```

#### Configuration

**Environment Variables**
```bash
# SSE reconnection settings
SSE_RECONNECT_DELAY_MS=1000
SSE_MAX_RECONNECT_DELAY_MS=30000
SSE_RECONNECT_BACKOFF_FACTOR=1.5

# Offline outbox settings  
OUTBOX_MAX_ITEMS=100
OUTBOX_RETRY_ATTEMPTS=3
OUTBOX_FLUSH_INTERVAL_MS=5000

# Presence idle detection
IDLE_TIMEOUT_MS=300000  # 5 minutes
AWAY_TIMEOUT_MS=600000  # 10 minutes
```

#### E2E Testing

**Playwright Test Coverage** (`frontend/tests/plan-resume.spec.ts`)
- Offline/online transition scenarios
- Connection status UI validation
- Outbox persistence across page refreshes
- SSE reconnection and backfill verification
- Toast notification behavior
- Error handling and recovery flows

```bash
# Run resilience tests
npm run test:e2e -- plan-resume.spec.ts
```

#### Monitoring & Metrics

**Browser Metrics** (via `performance.mark()`)
- `sse.reconnect.duration` - Time to restore SSE connection
- `outbox.flush.duration` - Time to sync offline actions
- `connection.offline.duration` - Total offline time

**Backend Metrics** (Prometheus)
- `sse_reconnections_total{plan_id}` - SSE reconnection events
- `sse_backfill_events_total{plan_id}` - Events replayed on resume
- `plan_offline_mutations_total{plan_id}` - Queued offline actions

#### Benefits

✅ **Uninterrupted UX** - Seamless experience during network hiccups  
✅ **Data Consistency** - No lost mutations with offline queueing  
✅ **Real-time Sync** - Automatic catch-up when connection restored  
✅ **User Awareness** - Clear visual feedback on connection state  
✅ **Mobile Friendly** - Handles mobile network switching gracefully  
✅ **Enterprise Ready** - Robust for corporate networks with proxies

---

**Copyright © 2025 NavraLabs, Inc. All rights reserved.**
