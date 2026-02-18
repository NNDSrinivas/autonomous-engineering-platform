# 🧠 Autonomous Engineering Intelligence Platform
> *The AI-Powered Digital Coworker for Software Engineering Teams*

⚖️ **Licensed under Business Source License 1.1 (BSL). Commercial use prohibited without agreement with NavraLabs.**

---

## 👨‍💻 New Developer? Start Here!

**📘 Complete Setup Guide:** [DEVELOPER_SETUP.md](./DEVELOPER_SETUP.md)

New to the project? The [Developer Setup Guide](./DEVELOPER_SETUP.md) provides a step-by-step walkthrough from cloning to running tests. Perfect for onboarding!

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

| Tool | Version | Install (macOS) | Install (Linux) |
|------|---------|-----------------|-----------------|
| **Python** | 3.11.x recommended (3.13+ not supported) | `brew install python@3.11` | `sudo apt install python3.11` |
| **Node.js** | 20+ LTS (18.19+ minimum) | `brew install node@20` | [nodejs.org](https://nodejs.org) |
| **Docker Desktop** | Latest | [docker.com](https://www.docker.com/products/docker-desktop/) | [docs.docker.com](https://docs.docker.com/engine/install/) |
| **Git** | 2.0+ | `brew install git` | `sudo apt install git` |

**API keys** — you need at least one LLM provider key:
- OpenAI: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- Anthropic: [console.anthropic.com](https://console.anthropic.com)

---

### Step 1 — Clone and install dependencies

```bash
git clone <repository-url>
cd autonomous-engineering-platform

# Python backend
python3.11 -m venv aep-venv
source aep-venv/bin/activate
pip install -r requirements.txt

# Node.js (frontend + all workspaces) — run from repo root
npm install
```

### Step 2 — Configure environment

```bash
cp .env.template .env
```

Open the **root `.env`** file (not `backend/.env`) and fill in your values. This is the only file `start_backend_dev.sh` reads.

#### Required keys (at minimum one LLM provider)

```
# Infrastructure
REDIS_URL=redis://localhost:6379/0
APP_ENV=dev
JWT_ENABLED=false
ALLOW_DEV_AUTH_BYPASS=true

# LLM provider — set at least ONE of these
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

**Database** — the template already contains individual `DB_*` components; the backend constructs the connection URL from them automatically. No extra action needed for local dev. If you prefer a single URL (e.g. for a remote DB), you can set `DATABASE_URL` instead — it takes precedence:

```
# Default (already in .env.template — no changes needed):
DB_HOST=localhost
DB_PORT=5432
DB_USER=mentor
DB_PASSWORD=mentor
DB_NAME=mentor

# Alternative — overrides the components above when set:
# DATABASE_URL=postgresql+psycopg://mentor:mentor@localhost:5432/mentor
```

#### All supported LLM provider keys

| Provider | Env variable | Where to get the key | Required? |
|----------|-------------|----------------------|-----------|
| **OpenAI** (GPT-4o, GPT-4, etc.) | `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | Yes — default provider |
| **Anthropic** (Claude 3.5/3.7) | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) | If using Claude models |
| **Google / Gemini** | `GOOGLE_API_KEY` | [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey) | If using Gemini models |
| **Groq** (fast inference) | `GROQ_API_KEY` | [console.groq.com/keys](https://console.groq.com/keys) | If using Groq models |
| **xAI / Grok** | `XAI_API_KEY` | [console.x.ai](https://console.x.ai) | If using Grok models |
| **OpenRouter** (multi-provider) | `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) | If using OpenRouter |
| **Mistral** | `MISTRAL_API_KEY` | [console.mistral.ai](https://console.mistral.ai) | If using Mistral models |
| **Cohere** | `COHERE_API_KEY` | [dashboard.cohere.com/api-keys](https://dashboard.cohere.com/api-keys) | If using Cohere models |
| **Ollama** (local/self-hosted) | `OLLAMA_BASE_URL` | Set to `http://localhost:11434` | If running Ollama locally |

> **One key is enough to get started.** `OPENAI_API_KEY` is the default. All other provider keys are only needed when you route requests to those providers.

> **Security:** `.env` is git-ignored. Never commit real API keys. For production/staging, use environment secrets (AWS Secrets Manager, Vault, Kubernetes Secrets — see `kubernetes/secrets/`).

### Step 3 — Start infrastructure (PostgreSQL + Redis)

```bash
docker compose up -d
```

Starts `aep_postgres` on port **5432** and `aep_redis` on port **6379**.

Verify:
```bash
docker compose ps    # both should show "healthy"
```

### Step 4 — Run database migrations

```bash
source aep-venv/bin/activate
alembic upgrade head
```

### Step 5 — Start observability stack (Prometheus + Grafana)

```bash
./scripts/run_grafana_local.sh
```

This starts:
- **Prometheus** → http://localhost:9090
- **Grafana** → http://localhost:3001 (login: `admin` / `admin`)

All 4 dashboards (LLM metrics, task metrics, errors, learning) are provisioned automatically.

### Step 6 — Start backend

```bash
./start_backend_dev.sh
```

This activates the venv, loads `.env`, and starts the API on **http://localhost:8787**.

Verify: `curl http://localhost:8787/health`

### Step 7 — Start frontend

```bash
cd frontend && npm run dev
```

Vite starts on **http://localhost:3007** (configured in `frontend/vite.config.ts`; auto-increments to 3008/3009/etc. if 3007 is taken — the terminal output shows the actual URL).

---

### Step 8 — VS Code Extension (optional, for extension development)

The NAVI VS Code extension lives in `extensions/vscode-aep/`. You only need this step if you're developing or debugging the extension itself.

#### One-time setup

```bash
# Install extension dependencies
cd extensions/vscode-aep
npm install

# Compile the extension + webview (must do this before launching)
npm run compile
```

#### Launch the extension host

1. Open the repo root in VS Code
2. Press **F5** — this reads `.vscode/launch.json` and opens a new **Extension Development Host** window with the extension loaded

The `launch.json` configuration:
```json
{
  "name": "Launch Extension",
  "type": "extensionHost",
  "request": "launch",
  "args": ["--extensionDevelopmentPath=${workspaceFolder}/extensions/vscode-aep"]
}
```

#### VS Code settings required

Your `.vscode/settings.json` already contains these — verify they match your setup:

```json
{
  "aep.navi.backendUrl": "http://127.0.0.1:8787",
  "aep.development.useReactDevServer": true
}
```

> `useReactDevServer: true` tells the extension to load the UI from the Vite dev server (Step 7) instead of the compiled bundle — so hot-reload works.

#### Tasks available (Ctrl+Shift+P → "Tasks: Run Task")

| Task | What it does |
|------|-------------|
| `npm: compile - extensions/vscode-aep` | One-time build before F5 |
| `npm: watch` | Incremental TypeScript compile on save |
| `webview: watch` | Hot-reload the webview React app |
| `dev: start all (backend + frontend + watch)` | Starts backend + frontend + both watchers in parallel |
| `backend: restart` | Kill + restart backend on port 8787 |

---

### All services at a glance

| Service | URL | Started by |
|---------|-----|------------|
| Backend API | http://localhost:8787 | `./start_backend_dev.sh` |
| Frontend | http://localhost:3007 | `cd frontend && npm run dev` |
| Prometheus | http://localhost:9090 | `./scripts/run_grafana_local.sh` |
| Grafana | http://localhost:3001 | `./scripts/run_grafana_local.sh` |
| PostgreSQL | localhost:5432 | `docker compose up -d` |
| Redis | localhost:6379 | `docker compose up -d` |

---

### Stop everything

```bash
# Stop backend and frontend: Ctrl+C in their terminals

# Stop Docker services (keeps data)
docker compose down

# Stop Prometheus + Grafana (keeps data)
docker stop navi-prometheus grafana

# Stop Prometheus + Grafana AND remove containers (fresh start next time)
./scripts/stop_grafana_local.sh
```

---

### Production mode

```bash
# Backend
source aep-venv/bin/activate
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8787 --workers 4

# Frontend
cd frontend && npm run build && npm run preview
```

---

### Common gotchas

These are the most frequent issues new developers run into:

**1. Wrong `.env` file — keys not picked up**
`start_backend_dev.sh` reads the **root `.env`**, not `backend/.env`. Always edit the root one. If you added keys to `backend/.env` only, the backend won't see them.

**2. Docker Desktop not running**
`docker compose up -d` silently fails or errors if Docker Desktop isn't started first. Open Docker Desktop, wait for it to be ready, then retry.

**3. Migrations fail with "connection refused"**
`alembic upgrade head` needs postgres running first. Run `docker compose up -d` and wait for healthy status before migrating.

**4. Virtual environment mismatch**
The repo has `aep-venv/` (what `start_backend_dev.sh` uses). If VSCode shows import errors, point it at the right interpreter:
`Ctrl+Shift+P` → **Python: Select Interpreter** → choose `./aep-venv/bin/python`

**5. Frontend shows a different port than 3007**
Vite is configured to start on **3007** (`frontend/vite.config.ts`) and auto-increments to 3008/3009/etc. if that port is taken. Always read the **actual URL from the terminal output** after `npm run dev`. If the VS Code extension can't connect, verify `aep.navi.backendUrl` in `.vscode/settings.json` is pointing at the right port.

**6. Extension blank panel after F5**
The backend and the Vite dev server (Step 6 + 7) must both be running before launching the extension host. Also ensure you ran `npm run compile` in `extensions/vscode-aep/` first.

**7. `npm install` run from the wrong directory**
Always run the root `npm install` from the **repo root**, not from `frontend/` or `extensions/vscode-aep/`. The root `package.json` is a workspace config that installs all sub-packages at once.

**8. Grafana port conflict**
`run_grafana_local.sh` defaults to port **3001** for Grafana and **9090** for Prometheus. If either port is taken, override before running:
```bash
GRAFANA_PORT=3002 ./scripts/run_grafana_local.sh
```

**9. Budget policy validation fails at startup**
If the backend logs `budget policy invalid`, run:
```bash
npm run validate:budget-policy
```
and check `shared/budget-policy-dev.json` against the schema in `shared/budget-policy.schema.json`.

**10. `alembic` not found**
Make sure the venv is activated: `source aep-venv/bin/activate`. Alembic is a Python package installed into the venv, not globally.

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

## 📚 Documentation

| Document | Description |
|---|---|
| [DEVELOPER_SETUP.md](./DEVELOPER_SETUP.md) | Local setup, dependencies, running tests |
| [docs/STAGING.md](./docs/STAGING.md) | Staging environment, deploy commands, VS Code workspaces |
| [docs/NAVI_PROD_READINESS.md](./docs/NAVI_PROD_READINESS.md) | Production readiness checklist and hardening plan |
| [docs/NAVI_ARCHITECTURE.md](./docs/NAVI_ARCHITECTURE.md) | System architecture and component overview |
| [docs/DEPLOYMENT_GUIDE.md](./docs/DEPLOYMENT_GUIDE.md) | Deployment runbook |
| [docs/ONCALL_PLAYBOOK.md](./docs/ONCALL_PLAYBOOK.md) | On-call and incident response |
| [docs/NAVI_VISION.md](./docs/NAVI_VISION.md) | Feature deep-dives: RACP, IDE Agent, RBAC, Context Intelligence, Connectors |
| [docs/THREAT_MODEL.md](./docs/THREAT_MODEL.md) | Security threat model |
| [SECURITY.md](./SECURITY.md) | Vulnerability disclosure policy |

---

## 🚀 Staging Environment

The live staging environment is deployed on AWS ECS Fargate at **https://staging.navralabs.com**.

For full deploy commands, VS Code workspace setup, and AWS infrastructure reference see **[docs/STAGING.md](./docs/STAGING.md)**.

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
