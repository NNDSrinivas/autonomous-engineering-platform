# NAVI Tools Implementation Status

> Last Updated: January 25, 2025

This document tracks the implementation status of all NAVI agent tools, including what's fully integrated, what has backend support but needs NAVI_TOOLS definitions, and what's planned for future development.

---

## Table of Contents

1. [Overview](#overview)
2. [Fully Implemented Tools](#fully-implemented-tools)
3. [Command Execution System](#command-execution-system)
4. [Dangerous Commands Permission System](#dangerous-commands-permission-system)
5. [Integration Tools](#integration-tools)
6. [Tools with Backend Support (Pending NAVI_TOOLS)](#tools-with-backend-support-pending-navi_tools)
7. [Implementation Priorities](#implementation-priorities)
8. [Architecture](#architecture)

---

## Overview

### Current Statistics

| Category | Count | Status |
|----------|-------|--------|
| Tools in NAVI_TOOLS | 79 | ✅ Active |
| Dangerous Commands | 20 | ✅ Permission System |
| Safe Commands Whitelist | 422 | ✅ Auto-allowed |
| Dispatch Handlers | 30+ | ✅ Ready |
| Tool Files (Backend) | 46 | ✅ Fully Integrated |

### Key Files

| File | Purpose |
|------|---------|
| `backend/services/streaming_agent.py` | NAVI_TOOLS definitions (LLM tool schemas) |
| `backend/agent/tool_executor.py` | Tool dispatch and execution |
| `backend/agent/tools/__init__.py` | Tool exports |
| `backend/agent/tools/dangerous_commands.py` | Permission system |
| `backend/agent/tools/run_command.py` | Command execution with safety |

---

## Fully Implemented Tools

### 1. Core File Operations (5 tools)

| Tool Name | Description | File |
|-----------|-------------|------|
| `read_file` | Read file contents with optional line range | `read_file.py` |
| `write_file` | Create or overwrite files | `create_file.py` |
| `edit_file` | Targeted text replacement | `edit_file.py` |
| `search_files` | Glob pattern and content search | `search_repo.py` |
| `list_directory` | List directory contents | Built-in |

### 2. Server & Web Tools (5 tools)

| Tool Name | Description | File |
|-----------|-------------|------|
| `start_server` | Start dev servers in background with health checks | `run_command.py` |
| `check_endpoint` | HTTP health checks | `run_command.py` |
| `stop_server` | Stop servers by port | `run_command.py` |
| `fetch_url` | Fetch and parse web content | `web_tools.py` |
| `web_search` | Web search via Tavily API | `web_tools.py` |

### 3. Infrastructure Tools (6 tools in NAVI_TOOLS, 11 in backend)

| Tool Name | Description | Status |
|-----------|-------------|--------|
| `infra.generate_terraform` | Generate Terraform IaC config | ✅ In NAVI_TOOLS |
| `infra.generate_k8s` | Generate Kubernetes manifests | ✅ In NAVI_TOOLS |
| `infra.generate_docker_compose` | Generate docker-compose.yml | ✅ In NAVI_TOOLS |
| `infra.generate_helm` | Generate Helm charts | ✅ In NAVI_TOOLS |
| `infra.terraform_plan` | Run terraform plan | ✅ In NAVI_TOOLS |
| `infra.kubectl_apply` | Apply K8s manifests | ✅ In NAVI_TOOLS |
| `infra.terraform_apply` | Apply Terraform changes | Backend only |
| `infra.terraform_destroy` | Destroy Terraform resources | Backend only |
| `infra.helm_install` | Install Helm charts | Backend only |
| `infra.docker_build` | Build Docker images | Backend only |
| `infra.docker_push` | Push Docker images | Backend only |

**File:** `infrastructure_tools.py` (65KB, 2255 lines)

### 4. Database Tools (6 tools in NAVI_TOOLS, 11 in backend)

| Tool Name | Description | Status |
|-----------|-------------|--------|
| `db.design_schema` | Design DB schema from natural language | ✅ In NAVI_TOOLS |
| `db.generate_migration` | Generate migration files | ✅ In NAVI_TOOLS |
| `db.run_migration` | Execute migrations | ✅ In NAVI_TOOLS |
| `db.generate_seed` | Generate seed data | ✅ In NAVI_TOOLS |
| `db.analyze_schema` | Analyze schema improvements | ✅ In NAVI_TOOLS |
| `db.generate_erd` | Generate ERD diagrams | ✅ In NAVI_TOOLS |
| `db.connect` | Connect to database | Backend only |
| `db.query` | Execute queries | Backend only |
| `db.backup` | Backup database | Backend only |
| `db.restore` | Restore database | Backend only |
| `db.optimize` | Optimize performance | Backend only |

**File:** `database_tools.py` (55KB, 1657 lines)

### 5. Test Generation Tools (4 tools in NAVI_TOOLS, 5 in backend)

| Tool Name | Description | Status |
|-----------|-------------|--------|
| `test.generate_for_file` | Generate tests for file | ✅ In NAVI_TOOLS |
| `test.generate_for_function` | Generate tests for function | ✅ In NAVI_TOOLS |
| `test.generate_suite` | Generate full test suite | ✅ In NAVI_TOOLS |
| `test.detect_framework` | Detect test framework | ✅ In NAVI_TOOLS |
| `test.run` | Run tests | Backend only |

**File:** `test_generation_tools.py` (37KB, 1136 lines)

### 6. CI/CD Tools (2 tools in NAVI_TOOLS)

| Tool Name | Description | Status |
|-----------|-------------|--------|
| `gitlab_ci.generate` | Generate .gitlab-ci.yml | ✅ In NAVI_TOOLS |
| `github_actions.generate` | Generate GitHub Actions workflows | ✅ In NAVI_TOOLS |

**Files:** `gitlab_ci_tools.py` (39KB), `github_actions_tools.py` (22KB)

### 7. Documentation Tools (5 tools in NAVI_TOOLS)

| Tool Name | Description | Status |
|-----------|-------------|--------|
| `docs.generate_readme` | Generate comprehensive README.md | ✅ In NAVI_TOOLS |
| `docs.generate_api` | Generate API documentation (OpenAPI, Markdown) | ✅ In NAVI_TOOLS |
| `docs.generate_component` | Generate component documentation | ✅ In NAVI_TOOLS |
| `docs.generate_architecture` | Generate architecture documentation | ✅ In NAVI_TOOLS |
| `docs.generate_comments` | Generate inline code comments | ✅ In NAVI_TOOLS |

**File:** `documentation_tools.py` (44KB)

### 8. Scaffolding Tools (4 tools in NAVI_TOOLS)

| Tool Name | Description | Status |
|-----------|-------------|--------|
| `scaffold.project` | Create new project from template | ✅ In NAVI_TOOLS |
| `scaffold.detect_requirements` | Analyze requirements and suggest structure | ✅ In NAVI_TOOLS |
| `scaffold.add_feature` | Add feature to existing project | ✅ In NAVI_TOOLS |
| `scaffold.list_templates` | List available templates | ✅ In NAVI_TOOLS |

**File:** `scaffolding_tools.py` (37KB)

### 9. Monitoring Tools (5 tools in NAVI_TOOLS)

| Tool Name | Description | Status |
|-----------|-------------|--------|
| `monitor.setup_errors` | Set up error tracking (Sentry, Rollbar) | ✅ In NAVI_TOOLS |
| `monitor.setup_apm` | Set up APM (Datadog, New Relic) | ✅ In NAVI_TOOLS |
| `monitor.setup_logging` | Configure structured logging | ✅ In NAVI_TOOLS |
| `monitor.generate_health_checks` | Generate health check endpoints | ✅ In NAVI_TOOLS |
| `monitor.setup_alerting` | Configure alerting rules | ✅ In NAVI_TOOLS |

**File:** `monitoring_tools.py` (27KB)

### 10. Secrets Management Tools (5 tools in NAVI_TOOLS)

| Tool Name | Description | Status |
|-----------|-------------|--------|
| `secrets.generate_env` | Generate .env.example template | ✅ In NAVI_TOOLS |
| `secrets.setup_provider` | Set up secrets provider (Vault, AWS) | ✅ In NAVI_TOOLS |
| `secrets.sync_to_platform` | Sync secrets to deployment platform | ✅ In NAVI_TOOLS |
| `secrets.audit` | Audit for exposed secrets | ✅ In NAVI_TOOLS |
| `secrets.rotate` | Generate secret rotation commands | ✅ In NAVI_TOOLS |

**File:** `secrets_tools.py` (28KB)

### 11. Architecture Tools (5 tools in NAVI_TOOLS)

| Tool Name | Description | Status |
|-----------|-------------|--------|
| `arch.recommend_stack` | Get technology stack recommendations | ✅ In NAVI_TOOLS |
| `arch.design_system` | Design system architecture | ✅ In NAVI_TOOLS |
| `arch.generate_diagram` | Generate architecture diagrams | ✅ In NAVI_TOOLS |
| `arch.decompose_microservices` | Suggest microservices boundaries | ✅ In NAVI_TOOLS |
| `arch.generate_adr` | Generate Architecture Decision Records | ✅ In NAVI_TOOLS |

**File:** `architecture_tools.py` (41KB)

### 12. Deployment Tools (4 tools in NAVI_TOOLS)

| Tool Name | Description | Status |
|-----------|-------------|--------|
| `deploy.detect_project` | Detect project type and suggest platforms | ✅ In NAVI_TOOLS |
| `deploy.check_cli` | Check deployment CLI authentication | ✅ In NAVI_TOOLS |
| `deploy.get_info` | Get deployment status | ✅ In NAVI_TOOLS |
| `deploy.list_platforms` | List supported platforms | ✅ In NAVI_TOOLS |

**File:** `deployment_tools.py` (48KB)

---

## Command Execution System

### Safe Commands (run_command)

The `run_command` tool automatically allows 422 safe commands including:

**Development:**
- `git`, `npm`, `yarn`, `pnpm`, `bun`, `node`, `npx`
- `python`, `python3`, `pip`, `pip3`, `poetry`, `pipenv`
- `go`, `cargo`, `rustc`, `ruby`, `gem`

**Build & Test:**
- `make`, `cmake`, `gradle`, `mvn`, `ant`
- `jest`, `pytest`, `mocha`, `vitest`
- `webpack`, `vite`, `esbuild`, `rollup`

**Cloud & Infrastructure:**
- `docker`, `docker-compose`, `podman`
- `kubectl`, `helm`, `minikube`, `kind`
- `terraform`, `pulumi`, `ansible`
- `aws`, `gcloud`, `az`, `doctl`

**Utilities:**
- `curl`, `wget`, `jq`, `yq`
- `cat`, `grep`, `find`, `ls`, `pwd`
- `ssh`, `scp`, `rsync`

### Command Variants

| Tool | Description | Use Case |
|------|-------------|----------|
| `run_command` | Standard execution | Normal commands |
| `run_dangerous_command` | With user approval | rm, kill, chmod, etc. |
| `run_interactive_command` | Auto-answers prompts | npm install, apt-get |
| `run_parallel_commands` | Concurrent execution | Build + test in parallel |
| `run_command_with_retry` | Auto-retry on failure | Flaky network operations |

---

## Dangerous Commands Permission System

### Risk Levels

| Level | Color | Icon | Description |
|-------|-------|------|-------------|
| CRITICAL | Red | 🔴 | Can destroy system/data |
| HIGH | Orange | 🟠 | Significant risk |
| MEDIUM | Yellow | 🟡 | Moderate risk |
| LOW | Green | 🟢 | Minor risk |

### Dangerous Commands by Category

#### Disk Operations (CRITICAL)

| Command | Description | Rollback |
|---------|-------------|----------|
| `format` | Format disk/partition | ❌ No |
| `mkfs` | Create filesystem | ❌ No |
| `dd` | Low-level data copy | ❌ No |

#### System Control (CRITICAL)

| Command | Description | Rollback |
|---------|-------------|----------|
| `shutdown` | Shutdown system | ❌ No |
| `reboot` | Restart system | ❌ No |
| `init` | Change runlevel | ❌ No |

#### Privilege Escalation (CRITICAL)

| Command | Description | Rollback |
|---------|-------------|----------|
| `sudo` | Execute as root | ❌ No |
| `su` | Switch user | ❌ No |
| `visudo` | Edit sudoers | ✅ Yes |

#### File/Process Operations (HIGH)

| Command | Description | Rollback |
|---------|-------------|----------|
| `rm` | Delete files/directories | ✅ Backup |
| `rmdir` | Remove directories | ✅ Backup |
| `kill` | Terminate process | ❌ No |
| `killall` | Kill by name | ❌ No |
| `pkill` | Kill by pattern | ❌ No |
| `chmod` | Change permissions | ✅ Record |
| `chown` | Change ownership | ✅ Record |

#### User Management (HIGH/MEDIUM)

| Command | Risk | Description |
|---------|------|-------------|
| `passwd` | HIGH | Change password |
| `useradd` | HIGH | Create user |
| `userdel` | HIGH | Delete user |
| `groupadd` | MEDIUM | Create group |

### Blocked Commands (No Bypass)

| Command | Reason |
|---------|--------|
| `>` | Shell redirect (overwrite) |
| `>>` | Shell redirect (append) |

---

## Integration Tools

### Jira (3 tools in NAVI_TOOLS)

| Tool | Description | Write |
|------|-------------|-------|
| `create_jira_issue` | Create issues | ✅ Approval |
| `search_jira_issues` | Search with JQL | Read |
| `add_jira_comment` | Add comments | ✅ Approval |

**Additional in Backend:** `list_assigned`, `update_issue`

### GitHub (6 tools in NAVI_TOOLS)

| Tool | Description | Write |
|------|-------------|-------|
| `github_create_issue` | Create issues | ✅ |
| `github_list_issues` | List issues | Read |
| `github_add_issue_comment` | Comment on issues | ✅ |
| `github_add_pr_review` | Review PRs | ✅ |
| `github_list_prs` | List PRs | Read |
| `github_merge_pr` | Merge PRs | ✅ |

**Additional in Backend:** `create_branch`, `create_pr`

### Slack (3 tools in NAVI_TOOLS)

| Tool | Description | Write |
|------|-------------|-------|
| `slack.search_messages` | Search messages across channels | Read |
| `slack.list_channel_messages` | List recent channel messages | Read |
| `slack.send_message` | Send message to channel | ✅ Approval |

### GitLab (4 tools in NAVI_TOOLS)

| Tool | Description | Write |
|------|-------------|-------|
| `gitlab.list_my_merge_requests` | List your merge requests | Read |
| `gitlab.list_my_issues` | List your assigned issues | Read |
| `gitlab.get_pipeline_status` | Get CI/CD pipeline status | Read |
| `gitlab.search` | Search projects, issues, MRs | Read |

---

## Tools with Backend Support (Pending NAVI_TOOLS)

These tools have full backend implementations and dispatch handlers, but are not yet exposed in NAVI_TOOLS.

### High Priority (Future)

| Prefix | File | Description |
|--------|------|-------------|
| `linear.` | linear_tools.py | Modern issue tracking |
| `notion.` | notion_tools.py | Knowledge base |
| `confluence.` | confluence_tools.py | Wiki documentation |
| `cloud.` | multicloud_tools.py | Multi-cloud operations (67KB) |

### Medium Priority (Project Management)

| Prefix | File | Category |
|--------|------|----------|
| `asana.` | asana_tools.py | Project Management |
| `trello.` | trello_tools.py | Project Management |
| `clickup.` | clickup_tools.py | Project Management |
| `monday.` | monday_tools.py | Project Management |

### Lower Priority (Specialized Integrations)

| Prefix | File | Category |
|--------|------|----------|
| `bitbucket.` | bitbucket_tools.py | Git Platform |
| `sentry.` | sentry_tools.py | Error Tracking |
| `datadog.` | datadog_tools.py | Monitoring |
| `pagerduty.` | pagerduty_tools.py | Incident Management |
| `snyk.` | snyk_tools.py | Security Scanning |
| `sonarqube.` | sonarqube_tools.py | Code Quality |
| `figma.` | figma_tools.py | Design |
| `loom.` | loom_tools.py | Video |
| `discord.` | discord_tools.py | Communication |
| `zoom.` | zoom_tools.py | Meetings |
| `gcalendar.` | google_calendar_tools.py | Calendar |
| `gdrive.` | google_drive_tools.py | File Storage |
| `vercel.` | vercel_tools.py | Deployment |
| `circleci.` | circleci_tools.py | CI/CD |

---

## Implementation Priorities

### Phase 1: Core Development Tools ✅ COMPLETE

- [x] File operations (read, write, edit, search)
- [x] Command execution with safety
- [x] Dangerous command permission system
- [x] Server management (start, stop, health check)
- [x] Web tools (fetch, search)

### Phase 2: DevOps & Infrastructure ✅ COMPLETE

- [x] Infrastructure tools (Terraform, K8s, Docker, Helm)
- [x] Database tools (schema, migrations, ERD)
- [x] Test generation tools
- [x] CI/CD tools (GitLab CI, GitHub Actions)

### Phase 3: Integrations ✅ COMPLETE

- [x] Jira integration (3 tools)
- [x] GitHub integration (6 tools)
- [x] Slack integration (3 tools)
- [x] GitLab integration (4 tools)
- [ ] Linear/Notion/Confluence (backend ready)

### Phase 4: Advanced Tools ✅ COMPLETE

- [x] Documentation generation (`docs.` - 5 tools)
- [x] Project scaffolding (`scaffold.` - 4 tools)
- [x] Monitoring setup (`monitor.` - 5 tools)
- [x] Secrets management (`secrets.` - 5 tools)
- [x] Architecture tools (`arch.` - 5 tools)
- [x] Deployment tools (`deploy.` - 4 tools)

### Phase 5: Extended Integrations (Future)

- [ ] Linear integration
- [ ] Notion integration
- [ ] Confluence integration
- [ ] Multi-cloud tools (`cloud.`)
- [ ] Additional project management (Asana, Trello, ClickUp, Monday)

---

## Architecture

### Tool Execution Flow

```
User Request
    │
    ▼
┌─────────────────┐
│ Streaming Agent │  ← NAVI_TOOLS definitions
│ (streaming_agent.py)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Tool Executor  │  ← Dispatch handlers
│ (tool_executor.py)
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐  ┌───────────────┐
│ Safe  │  │   Dangerous   │
│Command│  │   Command     │
└───┬───┘  └───────┬───────┘
    │              │
    │       ┌──────┴──────┐
    │       │ Permission  │
    │       │   Check     │
    │       └──────┬──────┘
    │              │
    │       ┌──────┴──────┐
    │       │   Backup    │
    │       │  (if needed)│
    │       └──────┬──────┘
    │              │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   Execute    │
    │   Command    │
    └──────────────┘
```

### Adding New Tools

1. **Create tool file** in `backend/agent/tools/`
2. **Define TOOL_REGISTRY** dict with tool functions
3. **Add dispatch handler** in `tool_executor.py`
4. **Add to NAVI_TOOLS** in `streaming_agent.py`
5. **Export in `__init__.py`**

### Tool Schema Format

```python
{
    "name": "tool.action",
    "description": "What the tool does",
    "input_schema": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
            "param2": {"type": "boolean", "description": "..."},
        },
        "required": ["param1"],
    },
}
```

---

## Changelog

### 2025-01-25 (Update 2)
- **Added 35 new tools to NAVI_TOOLS** (total now: 79 tools)
- Documentation tools: `docs.generate_readme`, `docs.generate_api`, `docs.generate_component`, `docs.generate_architecture`, `docs.generate_comments`
- Scaffolding tools: `scaffold.project`, `scaffold.detect_requirements`, `scaffold.add_feature`, `scaffold.list_templates`
- Monitoring tools: `monitor.setup_errors`, `monitor.setup_apm`, `monitor.setup_logging`, `monitor.generate_health_checks`, `monitor.setup_alerting`
- Secrets tools: `secrets.generate_env`, `secrets.setup_provider`, `secrets.sync_to_platform`, `secrets.audit`, `secrets.rotate`
- Architecture tools: `arch.recommend_stack`, `arch.design_system`, `arch.generate_diagram`, `arch.decompose_microservices`, `arch.generate_adr`
- Deployment tools: `deploy.detect_project`, `deploy.check_cli`, `deploy.get_info`, `deploy.list_platforms`
- Slack tools: `slack.search_messages`, `slack.list_channel_messages`, `slack.send_message`
- GitLab tools: `gitlab.list_my_merge_requests`, `gitlab.list_my_issues`, `gitlab.get_pipeline_status`, `gitlab.search`
- Updated `__init__.py` to export all new tool registries
- Phases 3 and 4 now complete

### 2025-01-25 (Update 1)
- Added 12 system-level commands to dangerous commands (format, mkfs, dd, shutdown, reboot, init, su, passwd, useradd, userdel, groupadd, visudo)
- Moved system commands from BLOCKED to DANGEROUS (permission-based)
- Added `github_actions.generate` function
- Updated `__init__.py` exports for all tool registries
- Total dangerous commands: 20
- Total safe commands: 422

---

## Contributing

When adding new tools:

1. Follow the existing naming conventions (`category.action`)
2. Include proper error handling
3. Add approval requirements for write operations
4. Document in this file
5. Add tests if possible
