# AEP IntelliJ Adapter (PR-12)

## Overview

IntelliJ IDEA plugin that connects to the local AEP agent (`agent-core`) via JSON-RPC over WebSocket. Provides a tool window for:

- Session management with greeting and JIRA task triage
- Ticket selection and context pack retrieval
- LLM-powered plan generation
- Step-by-step execution with ask-before-do consent prompts
- Delivery actions (Draft PR creation, JIRA commenting)

All execution is local-first with deny-by-default security policy enforced by `agent-core`.

## Prerequisites

- **IntelliJ IDEA 2024.2+** (Ultimate or Community Edition)
- **JDK 17** or higher
- **Node.js 18+** (to run `aep-agentd` daemon if not already running)
- **Backend API** running at `http://localhost:8002` (from main repo)

## Build & Run

### Build the plugin

```bash
cd extensions/jetbrains
./gradlew build
```

### Run in IDE sandbox

```bash
./gradlew runIde
```

This launches a sandboxed IntelliJ instance with the plugin installed.

### Package for distribution

```bash
./gradlew buildPlugin
```

The plugin ZIP will be in `build/distributions/`.

## Setup

### 1. Start the backend API

From the repository root:

```bash
cd autonomous-engineering-platform
source .venv/bin/activate  # or your Python environment
PYTHONPATH=. python -m backend.api.main
```

Backend listens on `http://localhost:8002` by default.

### 2. Start the agent daemon (if needed)

The plugin attempts to auto-start `aep-agentd`, but you can start it manually:

```bash
cd agent-core
npm install
npm run build
npm run dev:agentd
```

Agent daemon listens on `ws://127.0.0.1:8765` by default.

### 3. Configure environment variables (optional)

- `AEP_AGENTD_URL`: WebSocket URL for agent daemon (default: `ws://127.0.0.1:8765`)
- `AEP_CORE_API`: Backend API URL (default: `http://localhost:8002`)

## Usage

### Open the tool window

1. In IntelliJ, go to **View → Tool Windows → AEP Agent**
2. Or use the action: **Tools → AEP: Open Agent**

### Workflow

#### 1. Open Session
- Click **Open Session** to initialize connection with agent
- Displays greeting and assigned JIRA tasks from backend

#### 2. Generate Plan (LLM)
- Click **Generate Plan (LLM)**
- Enter ticket key (e.g., `AEP-27`)
- Agent fetches context pack and proposes implementation plan using Model Router (PR-9)
- Plan is displayed in the output panel

#### 3. Approve & Run
- Click **Approve & Run**
- Paste the plan JSON items array (from previous step)
- For each step, a confirmation dialog appears
- Upon approval, step is executed via `plan.runStep` JSON-RPC call
- Results are displayed in real-time

#### 4. Draft PR
- Click **Draft PR**
- Enter:
  - Repository (e.g., `owner/repo`)
  - Base branch (e.g., `main`)
  - Head branch (e.g., `feat/sample`)
  - PR title
  - PR body (optional)
  - Ticket key (optional)
- Calls backend `/api/deliver/github/draft-pr` endpoint (PR-11)
- Creates draft pull request on GitHub

#### 5. JIRA Comment
- Click **JIRA Comment**
- Enter:
  - Issue key (e.g., `AEP-27`)
  - Comment text
  - Transition status (optional, e.g., `In Progress`)
- Calls backend `/api/deliver/jira/comment` endpoint (PR-11)
- Posts comment and optionally transitions issue

## Architecture

### Components

- **AgentService**: Manages WebSocket connection to `aep-agentd`, auto-starts daemon if needed
- **RpcClient**: JSON-RPC client over WebSocket for agent communication
- **AgentPanel**: Main UI with buttons for all agent operations
- **AepToolWindowFactory**: Registers tool window in IntelliJ
- **Actions**: Menu actions for quick access

### Data Flow

```
IntelliJ Plugin
    ↓
AgentService (WebSocket) → aep-agentd (agent-core)
    ↓
AgentPanel (HTTP) → Backend API (http://localhost:8002)
    ↓
GitHub/JIRA APIs (via backend integrations)
```

### Security

- **Deny-by-default**: All execution enforced by `agent-core` via `.aepolicy.json`
- **Ask-before-do**: Every step requires explicit user consent
- **Local-first**: No code or data leaves your machine
- **No credentials in plugin**: Uses backend connection tables from PR-4

## Development

### Hot reload

While running `./gradlew runIde`, you can make code changes and reload the plugin:

1. Make changes to Kotlin files
2. In the sandboxed IDE: **Help → Find Action → Reload All from Disk**
3. Or rebuild: `./gradlew build`

### Debugging

Add breakpoints in IntelliJ and run:

```bash
./gradlew runIde --debug-jvm
```

Attach debugger to port 5005.

### Testing

Currently manual testing via sandbox IDE. Future: add JUnit tests for RPC client and service logic.

## Troubleshooting

### Plugin won't load
- Ensure JDK 17 is configured in IntelliJ SDK settings
- Verify `build.gradle.kts` compatibility with your IntelliJ version

### Agent daemon connection fails
- Check `aep-agentd` is running: `curl ws://127.0.0.1:8765`
- Verify `AEP_AGENTD_URL` environment variable
- Check logs in IntelliJ: **Help → Show Log in Finder/Explorer**

### Backend API errors
- Ensure backend is running: `curl http://localhost:8002/health`
- Check backend logs for errors
- Verify `X-Org-Id` header is set (default: `default`)

### Build errors
- Clean and rebuild: `./gradlew clean build`
- Delete `.gradle` cache and retry
- Ensure Gradle 8.0+ is installed

## Next Steps

- Add status bar indicator for agent connection state
- Display plan telemetry (model, tokens, cost) in UI
- Support for batch operations and plan templates
- Integration tests with mock agent-core responses

## License

Same as main repository (see root LICENSE file).
