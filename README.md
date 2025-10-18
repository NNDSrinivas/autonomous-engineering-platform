# 🧠 Autonomous Engineering Intelligence Platform
> *The AI-Powered Digital Coworker for Software Engineering Teams*

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
