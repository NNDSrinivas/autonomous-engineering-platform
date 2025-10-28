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
- Python 3.9+
- Node.js 16+
- PostgreSQL
- Redis (optional)

### Installation
\`\`\`bash
git clone <repository-url>
cd autonomous-engineering-platform

# Backend setup
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install

# Copy environment configuration
cp .env.template .env
\`\`\`

### Run Services
\`\`\`bash
# Start backend services
python -m backend.api.main        # Core API (port 8000)
python -m backend.api.realtime    # Realtime API (port 8001)

# Start frontend
cd frontend && npm start          # Web UI (port 3000)
\`\`\`

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

2. **Build VS Code Extension**
   ```bash
   cd ../extensions/vscode
   npm install
   npm run build
   ```

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

### Roadmap: PR-14B

**Coming next:** Connector integrations for:
- **Slack** - Index messages, threads, pins
- **Confluence** - Index wiki pages, attachments
- **Microsoft Teams** - Index chat, files
- **Zoom** - Index transcripts, recordings

Stay tuned for **PR-14B** to expand memory coverage!

---

## 🔌 PR-14B: Extended Connectors (Slack, Confluence, Wiki, Zoom/Teams)

### 🎯 **Expanded Memory Coverage**

PR-14B extends PR-14's memory search to cover your entire knowledge base:
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

### 🚧 **Future Enhancements (PR-15+)**

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

### ✅ PR-19: Live Plan Mode + Real-Time Collaboration (October 2025)

**Real-time collaborative planning for engineering teams**

Create plan sessions where multiple users can collaborate in real-time, see each other's contributions live, and archive completed plans to the memory graph for historical context.

#### Key Features
- **Real-time SSE Streaming** - See updates instantly as team members add steps
- **Collaborative Planning** - Multiple users working on the same plan session
- **Step-by-Step Tracking** - Chronological view of all plan steps with owner attribution
- **Memory Graph Integration** - Archive plans as `plan_session` nodes for context retrieval
- **React Dashboard** - Modern UI for browsing, creating, and collaborating
- **Telemetry** - Prometheus metrics for plan events, latency, and active sessions

#### Quick Start
```bash
# Apply database migration
make pr19-migrate

# Start backend (http://localhost:8000)
make pr19-dev

# Start frontend (http://localhost:5173)
make ui-plan-dev

# Open browser to: http://localhost:5173/plans

# Run smoke tests
make pr19-smoke

# Run full validation (migrate + tests + smoke)
make pr19-all
```

#### API Endpoints
- `POST /api/plan/start` - Create new plan session
- `GET /api/plan/{id}` - Get plan details
- `POST /api/plan/step` - Add step (broadcasts to all connected clients)
- `GET /api/plan/{id}/stream` - SSE stream for real-time updates
- `POST /api/plan/{id}/archive` - Archive plan to memory graph
- `GET /api/plan/list` - List plans with optional archive filter

#### Architecture
```
User → React UI → EventSource SSE → Backend API
                                    ↓
                        AsyncIO Queue Broadcast
                                    ↓
                        All Connected Clients
```

📚 **Full Documentation:** [docs/pr-19-plan-mode.md](docs/pr-19-plan-mode.md)

---

### ✅ PR-18: Memory Graph UI (October 2025)

**Interactive visualization of team memory and knowledge**

Explore your team's memory graph with an interactive network visualization, timeline view, and powerful query interface.

#### Key Features
- **Interactive Graph Visualization** - vis-network powered graph with 3D physics
- **Timeline View** - Chronological exploration of memories with filtering
- **Query Interface** - Test semantic/keyword/hybrid searches with live results
- **Node Details** - Inspect full memory content, metadata, and relationships
- **Telemetry** - Real-time connection status and performance metrics

📚 **Full Documentation:** [docs/pr-18-memory-graph.md](docs/pr-18-memory-graph.md)

---

**Next up:** PR-15 (Retrieval-Augmented Context Pack) will auto-attach top-k memory hits to coding tasks!

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

**Copyright © 2025 NavraLabs, Inc. All rights reserved.**

