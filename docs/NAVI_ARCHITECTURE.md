# NAVI Architecture Documentation

## Overview

NAVI (Navigation Assistant for Visual Intelligence) is the autonomous engineering agent for the AEP platform. This document explains its architecture, capabilities, and limitations.

---

## Architecture: Hybrid Intent-First + LLM-Enhanced

NAVI uses a **hybrid architecture** that prioritizes fast, deterministic intent classification with optional LLM enhancement:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER MESSAGE                                     │
│               "show my jira tickets assigned to me"                      │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 1: Intent Classification                        │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Rule-Based Classifier (backend/agent/intent_classifier.py)     │    │
│  │  • Keyword detection for 30 providers                           │    │
│  │  • Pattern matching for intent families & kinds                 │    │
│  │  • Zero-latency, deterministic                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │ confidence < threshold                    │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  LLM Classifier (backend/ai/intent_llm_classifier.py)           │    │
│  │  • Optional enhancement for ambiguous intents                   │    │
│  │  • Uses GPT-4o-mini or Claude for classification                │    │
│  │  • Structured JSON output                                       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ NaviIntent
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 2: Planning (PlannerV3)                         │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Fast-Path Shortcuts                                            │    │
│  │  • Jira: "my issues" → jira.list_assigned_issues_for_user       │    │
│  │  • Slack: "#channel summary" → slack.fetch_recent_channel       │    │
│  │  • GitHub: "my PRs" → github.list_my_prs                        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │ no shortcut match                         │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Provider-Based Routing                                         │    │
│  │  • Maps Provider + IntentKind → specific tool                   │    │
│  │  • 27 connectors × 127 tools                                    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │ no direct mapping                         │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Family-Based Fallback                                          │    │
│  │  • Generic plans per IntentFamily (PROJECT_MANAGEMENT, CODE)    │    │
│  │  • Never fails - always produces a plan                         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ PlanResult
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 3: Approval Check                               │
│  • Write operations require user approval                               │
│  • Read operations execute immediately                                  │
│  • VS Code extension shows approval UI                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 4: Tool Execution                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  ToolExecutor (backend/agent/tool_executor.py)                  │    │
│  │  • 127 registered tools across 27 connectors                    │    │
│  │  • Returns ToolResult(output, sources)                          │    │
│  │  • Sources enable clickable links in VS Code                    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    STAGE 5: Response Generation                          │
│  • Format tool output for display                                       │
│  • Include clickable sources                                            │
│  • Stream response to VS Code extension                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. Intent Classifier (`backend/agent/intent_classifier.py`)

**Type**: Rule-based heuristic classifier

**How it works**:
- Keyword matching for 30 providers (Jira, GitHub, Slack, etc.)
- Pattern detection for intent families and kinds
- Priority inference from urgency keywords
- Zero external dependencies, sub-millisecond execution

**Example**:
```python
# Input: "show my jira tickets"
# Output:
NaviIntent(
    family=IntentFamily.PROJECT_MANAGEMENT,
    kind=IntentKind.LIST_MY_ITEMS,
    provider=Provider.JIRA,
    priority=IntentPriority.NORMAL,
    confidence=0.85
)
```

### 2. LLM Intent Classifier (`backend/ai/intent_llm_classifier.py`)

**Type**: Optional LLM-powered enhancement

**When used**:
- Rule-based confidence is low
- Ambiguous user messages
- Complex multi-intent queries

**Models supported**:
- OpenAI: gpt-4o-mini, gpt-4o
- Anthropic: claude-3-5-sonnet
- Google: gemini-1.5-flash

### 3. Planner V3 (`backend/agent/planner_v3.py`)

**Type**: Deterministic plan generator

**Planning strategies** (in order):
1. **Fast-path shortcuts**: Direct tool mapping for common queries
2. **Provider routing**: Provider + Kind → Tool
3. **Family fallback**: Generic plans per intent family

### 4. Tool Executor (`backend/agent/tool_executor.py`)

**Type**: Tool dispatch and execution engine

**Features**:
- 127 tools across 27 connectors
- Async execution with error handling
- ToolResult with clickable sources
- Write operation protection (requires approval)

---

## Response Validation

NAVI validates responses at multiple levels:

### 1. Intent Validation
- Schema validation via Pydantic models
- Enum constraints for providers, families, kinds
- Confidence scoring

### 2. Tool Result Validation
- ToolResult dataclass ensures consistent output structure
- Sources are validated for required fields (name, type, url)
- Empty results are handled gracefully

### 3. Execution Validation
- Write operations require explicit user approval
- Destructive operations are flagged
- Tool failures are caught and reported

---

## Current Capabilities

### What NAVI Can Do Today

#### 1. Connector Queries (27 connectors, 127 tools)

| Category | Connectors | Example Queries |
|----------|------------|-----------------|
| **Issue Tracking** | Jira, Linear, Asana, Trello, Monday, ClickUp | "show my jira tickets", "create a linear issue" |
| **Code/VCS** | GitHub, GitLab, Bitbucket | "show my PRs", "list recent commits" |
| **CI/CD** | GitHub Actions, CircleCI, Vercel | "show pipeline status", "trigger build" |
| **Documentation** | Confluence, Notion, Google Drive, Google Docs | "search confluence for deployment docs" |
| **Communication** | Slack, Teams, Discord | "summarize #standup channel" |
| **Monitoring** | Datadog, Sentry, PagerDuty, Snyk, SonarQube | "show sentry errors", "who's on-call?" |
| **Meetings** | Zoom, Google Calendar, Loom | "list my meetings today" |
| **Design** | Figma | "show recent figma files" |

#### 2. Code Operations

| Operation | Tool | Description |
|-----------|------|-------------|
| Read files | `code.read_file` | Read file contents |
| Search code | `code.search`, `repo.search` | Search across codebase |
| Inspect repo | `repo.inspect` | Get project structure overview |
| Create files | `code.create_file` | Create new files (requires approval) |
| Edit files | `code.apply_diff`, `code.edit_file` | Modify existing files (requires approval) |
| Run commands | `code.run_command` | Execute shell commands (requires approval) |

#### 3. Multi-Turn Conversations
- Context preservation across turns
- State management per user/session
- Memory retrieval for relevant context

---

## Current Limitations

### What NAVI Cannot Do (Yet)

#### 1. End-to-End Feature Implementation
**Status**: Not fully autonomous

NAVI can:
- Understand the feature request
- Create a plan with steps
- Execute individual tool calls

NAVI cannot:
- Autonomously iterate on code until tests pass
- Handle complex multi-file refactoring without human guidance
- Make architectural decisions independently

**Why**: The current agent loop executes single plans. True end-to-end development requires:
- Iterative planning (plan → execute → evaluate → replan)
- Test-driven verification
- Rollback capabilities

#### 2. Image Processing
**Status**: Infrastructure exists, not wired

- `vision_service.py` exists but is not integrated into the main agent loop
- VS Code extension can send attachments, but NAVI doesn't process images yet

**To enable**:
1. Wire VisionService into agent_loop.py
2. Add image analysis tool
3. Update intent classifier to detect image queries

#### 3. Complex Debugging
**Status**: Basic support only

NAVI can:
- Read error messages from Problems tab
- Search for related code
- Suggest fixes

NAVI cannot:
- Step through code execution
- Analyze stack traces dynamically
- Correlate logs with code paths

**Why**: No debugger integration or runtime inspection capabilities.

#### 4. Plan Mode (Senior Engineer Workflow)
**Status**: Partial support

The described workflow:
```
1. User: "implement X"
2. NAVI: Asks clarifying questions
3. NAVI: Reads codebase, understands patterns
4. NAVI: Proposes plan for approval
5. NAVI: Implements step by step
6. NAVI: Runs tests, fixes errors
7. NAVI: Iterates until complete
```

**Current state**:
- Steps 1-5: Supported via PlannerV3 + approval flow
- Step 6: Manual - user must run tests and provide feedback
- Step 7: No automatic iteration

**To enable full plan mode**:
1. Add test execution tool with result parsing
2. Implement iterative planning loop
3. Add success criteria evaluation

---

## Architecture Decision: Why Intent-First?

### Benefits of Current Approach

1. **Speed**: Sub-millisecond classification for common queries
2. **Reliability**: No LLM call failures for simple operations
3. **Cost**: Most queries never hit LLM
4. **Debugging**: Deterministic behavior is easier to trace

### Trade-offs

1. **Flexibility**: New intent patterns require code changes
2. **Nuance**: Complex queries may need LLM enhancement
3. **Maintenance**: Keyword lists grow with connectors

### Future Direction

The architecture is designed to evolve:
- Rule-based classification handles 80%+ of queries
- LLM enhancement available for complex cases
- Path to full LLM-first mode if needed

---

## File Reference

| File | Purpose |
|------|---------|
| [backend/agent/agent_loop.py](../backend/agent/agent_loop.py) | Main 7-stage reasoning pipeline |
| [backend/agent/intent_classifier.py](../backend/agent/intent_classifier.py) | Rule-based intent classification |
| [backend/agent/intent_schema.py](../backend/agent/intent_schema.py) | NaviIntent, Provider, IntentKind enums |
| [backend/agent/planner_v3.py](../backend/agent/planner_v3.py) | Plan generation with shortcuts |
| [backend/agent/tool_executor.py](../backend/agent/tool_executor.py) | 127 tools execution engine |
| [backend/ai/intent_llm_classifier.py](../backend/ai/intent_llm_classifier.py) | Optional LLM classification |
| [backend/api/navi.py](../backend/api/navi.py) | Main chat endpoint |

---

## Summary

| Aspect | Current State | Future State |
|--------|---------------|--------------|
| **Classification** | Intent-first + optional LLM | LLM-first with intent shortcuts |
| **Planning** | Single-pass deterministic | Iterative with evaluation |
| **Execution** | Single tool or plan | Multi-step with verification |
| **Validation** | Schema + approval | Schema + tests + rollback |
| **Autonomy** | Low (human-in-loop) | Medium (test-driven iteration) |

NAVI is designed as a **reliable assistant** that excels at connector queries and basic code operations. Full autonomous development is architecturally possible but requires additional iteration and verification infrastructure.
