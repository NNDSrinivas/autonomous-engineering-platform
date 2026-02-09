# NAVI Features Documentation
**Autonomous Intelligence for Enterprise Development**

Last Updated: February 7, 2026

---

## Table of Contents
1. [Autonomous Multi-Step Execution](#1-autonomous-multi-step-execution)
2. [Human Checkpoint Gates](#2-human-checkpoint-gates)
3. [Multi-Agent Parallel Execution](#3-multi-agent-parallel-execution)
4. [Enterprise Compliance Scanning](#4-enterprise-compliance-scanning)
5. [Audit Encryption & Security](#5-audit-encryption--security)
6. [Learning System](#6-learning-system)
7. [RAG Context Integration](#7-rag-context-integration)
8. [Memory Persistence](#8-memory-persistence)
9. [Real Command Execution](#9-real-command-execution)
10. [MCP External Servers](#10-mcp-external-servers)
11. [Self-Hosted Deployment](#11-self-hosted-deployment)
12. [Observability & Database Persistence](#12-observability--database-persistence)

---

## 1. Autonomous Multi-Step Execution

### What Makes NAVI Unique
Unlike assistants that provide suggestions or single-step completions, NAVI **autonomously executes complex, multi-step tasks** from start to finish. It can:
- Break down complex requests into 25+ sequential steps
- Execute each step independently with tool usage
- Verify outcomes and adapt based on results
- Iterate until task completion (up to 999,999 steps for enterprise tasks)

**Example:** "Deploy a microservice to Kubernetes" becomes 30+ automated steps: building Docker images, creating manifests, applying configurations, verifying health checks, and monitoring deployment status.

### Assurance by NAVI
- **Adaptive Complexity**: Automatically adjusts iteration limits based on task complexity (8 for simple, 15 for medium, 25 for complex, unlimited for enterprise)
- **Smart Exit on Errors**: Immediately exits on non-retryable errors (rate limits, quota exceeded, auth failures) instead of wasting iterations
- **Result Verification**: Every step's output is verified before proceeding
- **Rollback Capability**: Can undo changes if verification fails

### Benefits for End Users & Organizations
- **Time Savings**: Tasks that take hours manually complete in minutes
- **Consistency**: Same task executed the same way every time - no human error
- **Scalability**: Handle 100+ tasks in parallel without fatigue
- **24/7 Operation**: Works around the clock without downtime

### Data Protection & Safety
- All execution logs are encrypted at rest using AES-GCM envelope encryption
- Sensitive command outputs (API keys, credentials) are automatically redacted
- Execution history is auditable with tamper-proof audit logs
- Commands are sandboxed in isolated environments (configurable)

### How to Use & Maximize Benefits
```bash
# Simple task (completes in ~8 iterations)
"Fix the typo in README.md"

# Medium task (up to 15 iterations)
"Add unit tests for the UserService class"

# Complex task (up to 25 iterations)
"Refactor the authentication system to use JWT"

# Enterprise task (unlimited iterations with checkpoints)
"Build and deploy a complete CI/CD pipeline with GitHub Actions, Docker, and Kubernetes"
```

**Pro Tips:**
- Start with clear, specific goals: "Deploy to staging" > "Do deployment stuff"
- Provide context: Attach relevant files or specify workspace path
- Use enterprise mode for tasks requiring human approval at critical steps

---

## 2. Human Checkpoint Gates

### What Makes NAVI Unique
NAVI is the **only autonomous agent with built-in human approval workflows**. Before executing critical operations, NAVI pauses and requests explicit human approval through:
- **Architecture Gates**: Approve database schema changes, API design choices
- **Security Gates**: Approve credential changes, permission modifications
- **Cost Gates**: Approve infrastructure changes that incur costs (cloud resources, paid APIs)
- **Deployment Gates**: Approve production deployments, database migrations

### Assurance by NAVI
- **Automatic Gate Detection**: NAVI automatically detects when a checkpoint is needed based on:
  - Files being modified (e.g., `schema.sql`, `.env`, `terraform/*.tf`)
  - Commands being run (e.g., `kubectl apply`, `terraform apply`, `npm publish`)
  - Cost implications (e.g., provisioning EC2 instances, upgrading databases)
- **Clear Explanation**: Each gate shows exactly what NAVI plans to do and why
- **Override Protection**: Gates cannot be bypassed without explicit approval
- **Audit Trail**: All gate decisions (approve/reject) are logged with timestamps and user IDs

### Benefits for End Users & Organizations
- **Risk Mitigation**: Prevent accidental production outages or data loss
- **Compliance**: Meet SOC2/ISO 27001 requirements for change approval
- **Learning Opportunity**: Review NAVI's approach before execution to learn best practices
- **Cost Control**: Prevent runaway cloud spend by approving resource provisioning

### Data Protection & Safety
- Gate approvals are cryptographically signed with user identity
- Approval audit logs are encrypted and tamper-proof
- Rejected actions are never executed, even partially
- Gate state is persisted to database for disaster recovery

### How to Use & Maximize Benefits
```bash
# Enable enterprise mode for automatic gates
POST /api/navi/chat/autonomous
{
  "message": "Deploy the new API version to production",
  "mode": "enterprise",  # <-- Enables automatic checkpoint gates
  "workspace_root": "/path/to/project"
}

# Gates will trigger at critical points:
# 1. Architecture Gate: "About to modify database schema in migrations/002_add_users_table.sql"
#    → Approve to continue, or modify the migration first
# 2. Deployment Gate: "About to run 'kubectl apply -f production/deployment.yaml'"
#    → Approve after reviewing the deployment manifest
# 3. Verification: NAVI confirms deployment health checks pass
```

**Pro Tips:**
- Always use enterprise mode for production workflows
- Review the full plan before approving the first gate
- Use "reject with feedback" to guide NAVI toward a better approach
- Set up Slack/email notifications for gate approvals in team environments

---

## 3. Multi-Agent Parallel Execution

### What Makes NAVI Unique
NAVI can spawn **multiple autonomous agents in parallel**, each working on independent subtasks simultaneously. This is the **distributed agent fleet** architecture:
- Decompose complex tasks into parallel-safe subtasks
- Execute up to 10 agents concurrently (configurable)
- Automatic conflict detection and resolution for file/resource conflicts
- Aggregate results when all agents complete

**Example:** "Refactor entire codebase to use TypeScript"
- Agent 1: Convert `/src/api` files
- Agent 2: Convert `/src/ui` files
- Agent 3: Convert `/src/utils` files
- Agent 4: Update configuration files
- All agents work simultaneously, completing in 25% of the time

### Assurance by NAVI
- **Conflict Detection**: Agents cannot modify the same file simultaneously
- **Resource Locking**: Database/file resources are locked during modification
- **Atomic Commits**: Each agent's work is committed as a single transaction
- **Failure Isolation**: If one agent fails, others continue; failed subtask is retried

### Benefits for End Users & Organizations
- **10x Faster**: Parallel execution reduces total time by up to 90%
- **Better Resource Utilization**: Fully utilize multi-core systems
- **Scalable**: Handle enterprise-scale codebases (millions of lines)
- **Fault Tolerant**: Partial failures don't block entire workflow

### Data Protection & Safety
- Each agent has isolated execution environment (separate working directory)
- Agent-to-agent communication is encrypted
- Shared resources (git repo, database) use distributed locking with Redis
- All agents log to centralized audit system with correlation IDs

### How to Use & Maximize Benefits
```bash
# Automatic parallel decomposition
"Migrate all API endpoints from REST to GraphQL"
# NAVI will automatically:
# 1. Analyze codebase to identify all endpoints
# 2. Decompose into parallel-safe subtasks (one agent per module)
# 3. Execute agents concurrently
# 4. Merge results with conflict resolution

# Manual parallel task specification
"Run these tasks in parallel:
 - Task 1: Run all unit tests
 - Task 2: Run integration tests
 - Task 3: Build Docker images
 - Task 4: Generate API documentation"
```

**Pro Tips:**
- Use parallel execution for tasks with independent subtasks (tests, builds, migrations)
- Avoid for tasks with sequential dependencies (database migrations)
- Monitor resource usage (CPU, memory) when running many agents
- Set `max_parallel_agents` in configuration based on your system's capabilities

---

## 4. Enterprise Compliance Scanning

### What Makes NAVI Unique
NAVI has **built-in compliance scanners for PCI-DSS, HIPAA, and SOC2** that automatically:
- Scan code for compliance violations before committing
- Check infrastructure configurations (Kubernetes, Terraform) for security issues
- Validate API endpoints for encryption requirements
- Detect sensitive data exposure (PII, PHI, credit card numbers)

**Compliance Frameworks Supported:**
- **PCI-DSS**: Payment Card Industry Data Security Standard
- **HIPAA**: Health Insurance Portability and Accountability Act
- **SOC2**: Service Organization Control 2 (Security, Availability, Confidentiality)

### Assurance by NAVI
- **Pre-Commit Scanning**: Violations are detected before code is committed
- **Automated Remediation**: NAVI can automatically fix common violations
- **Compliance Reports**: Generate audit-ready compliance reports
- **Continuous Monitoring**: Scan on every code change, not just once

### Benefits for End Users & Organizations
- **Faster Compliance**: Achieve certification in months instead of years
- **Cost Savings**: Reduce expensive compliance consultant fees by 80%
- **Audit Readiness**: Always have up-to-date compliance reports
- **Developer Productivity**: Fix issues immediately instead of discovering them during audits

### Data Protection & Safety
- Compliance scan results are encrypted and access-controlled
- PII/PHI detected during scans is immediately redacted and never stored
- Compliance reports include only metadata, not sensitive code
- Scan history is retained for audit purposes (configurable retention period)

### How to Use & Maximize Benefits
```bash
# Enable compliance scanning for a project
"Scan this codebase for PCI-DSS compliance violations"
# NAVI will:
# 1. Scan all source code, configs, and infrastructure files
# 2. Generate a report with violations and severity
# 3. Offer to auto-fix common issues
# 4. Create a compliance roadmap for remaining issues

# Continuous compliance monitoring
"Enable continuous HIPAA compliance scanning for this repository"
# NAVI will:
# 1. Set up pre-commit hooks to scan on every commit
# 2. Configure CI/CD pipeline to fail on new violations
# 3. Send alerts to Slack/email when violations are detected
# 4. Generate monthly compliance reports

# Remediation
"Fix all SOC2 compliance violations in the authentication module"
# NAVI will:
# 1. Identify violations (weak passwords, missing MFA, etc.)
# 2. Automatically implement fixes (password policies, MFA enforcement)
# 3. Run tests to verify fixes don't break functionality
# 4. Generate a remediation report for audit trail
```

**Pro Tips:**
- Run compliance scans in CI/CD to catch violations early
- Use auto-remediation for common issues (encryption, password policies)
- Generate reports before audits to identify gaps
- Integrate with security tools (SonarQube, Snyk) for comprehensive coverage

---

## 5. Audit Encryption & Security

### What Makes NAVI Unique
NAVI is the **only AI coding assistant with mandatory audit encryption in production**. Every action NAVI takes is:
- **Logged**: Every command, file change, API call, and decision
- **Encrypted**: Audit logs are encrypted at rest using AES-256-GCM
- **Tamper-Proof**: Cryptographic signatures prevent log modification
- **Searchable**: Encrypted logs can be decrypted and searched by authorized admins

**Encryption Architecture:**
- **At Rest**: AES-256-GCM envelope encryption with AWS KMS key management
- **In Transit**: TLS 1.3 for all network communication
- **Key Rotation**: Automatic encryption key rotation every 90 days
- **Access Control**: Role-based access to decrypt audit logs (admin-only)

### Assurance by NAVI
- **Mandatory in Production**: Application refuses to start if `AUDIT_ENCRYPTION_KEY` is missing in production/staging
- **Fail-Safe**: If encryption fails, operation is aborted (no unencrypted logs written)
- **Audit Trail**: All encryption key usage is logged separately
- **Retention Policies**: Automatic log purging after configurable retention period (default 90 days)

### Benefits for End Users & Organizations
- **Compliance**: Meet SOC2, ISO 27001, GDPR requirements for audit logging
- **Incident Response**: Full audit trail for forensic analysis after security incidents
- **Accountability**: Know exactly what NAVI did, when, and why
- **Trust**: Prove to customers/auditors that all AI actions are tracked

### Data Protection & Safety
- **Encryption Keys**: Stored in AWS KMS, never in plain text
- **Key Access**: Requires AWS IAM permissions (principle of least privilege)
- **Key Rotation**: Old logs are re-encrypted with new keys automatically
- **Data Minimization**: Only essential data is logged (no PII/PHI unless necessary)
- **Geographic Control**: Logs stored in your region (GDPR compliance)

### How to Use & Maximize Benefits
```bash
# Enable audit encryption (required for production)
export AUDIT_ENCRYPTION_KEY=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
export AUDIT_ENCRYPTION_KEY_ID="production-key-v1"
export APP_ENV="production"

# Start backend - will validate encryption is configured
python -m uvicorn backend.api.main:app

# Query encrypted audit logs (admin-only)
POST /api/audit/{audit_id}/decrypt
{
  "reason": "Investigating incident #1234",
  "user_id": "admin@company.com"
}
# Response: Decrypted audit log payload

# Purge old audit logs (retention compliance)
make audit-purge
# Removes logs older than AUDIT_RETENTION_DAYS (default 90)
```

**Pro Tips:**
- Store encryption keys in AWS Secrets Manager or HashiCorp Vault, not in .env files
- Set up automated key rotation every 90 days
- Configure audit log retention to match your compliance requirements
- Use audit logs for incident response, not just compliance
- Set up alerts for suspicious activity (unauthorized decryption attempts)

---

## 6. Learning System

### What Makes NAVI Unique
NAVI **learns from feedback and improves over time**. Every interaction is used to:
- Improve suggestion quality based on user acceptance/rejection
- Learn user preferences (code style, testing approach, deployment method)
- Identify patterns in successful vs. failed tasks
- Optimize tool usage (which tools work best for which tasks)

**Learning Architecture:**
- **Feedback Collection**: Thumbs up/down, ratings (1-5 stars), and written feedback
- **Pattern Detection**: Machine learning models identify what works
- **Thompson Sampling**: Multi-armed bandit algorithm optimizes tool selection
- **Continuous Improvement**: Learning runs every 15 minutes in background

### Assurance by NAVI
- **Privacy-Preserving**: Learning happens on aggregate patterns, not individual data
- **Reversible**: Can reset learning state if bad patterns are learned
- **Auditable**: All learning decisions are logged with reasoning
- **Opt-Out**: Organizations can disable learning (uses defaults only)

### Benefits for End Users & Organizations
- **Personalization**: NAVI adapts to your team's coding style and preferences
- **Quality Improvement**: Suggestions get better over time
- **Efficiency**: Learns which approaches work best for your codebase
- **Team Knowledge**: Captures institutional knowledge in the learning system

### Data Protection & Safety
- Learning data is stored in encrypted database
- Feedback is anonymized before learning (user IDs stripped)
- Learning models cannot reverse-engineer original feedback
- Organizations can export/import learning state for backups

### How to Use & Maximize Benefits
```bash
# Provide feedback on NAVI responses
# In UI: Click thumbs up/down or rate 1-5 stars
# With reason codes:
{
  "feedback": "like",
  "reason": "too_verbose",  # or "too_concise", "incorrect", "perfect"
  "generation_id": "gen-abc123"
}

# View learning insights (admin-only)
GET /api/learning/insights?user_id=team@company.com
# Response: Patterns learned, success rates, preferences

# Reset learning state (if bad patterns learned)
POST /api/learning/reset?confirmation=yes

# Export learning state for backup
GET /api/learning/export
# Response: JSON file with learning patterns

# Import learning state (new environment)
POST /api/learning/import
{ "learning_state": {...} }
```

**Pro Tips:**
- Encourage team to provide feedback consistently (use Slack reminders)
- Review learning insights monthly to identify improvement opportunities
- Export learning state before major system changes
- Use reason codes consistently for better pattern detection
- Give specific feedback in text comments (helps learning more than just thumbs up/down)

---

## 7. RAG Context Integration

### What Makes NAVI Unique
NAVI uses **Retrieval-Augmented Generation (RAG)** to inject relevant codebase context into every request:
- Automatically indexes your entire codebase (files, functions, classes, comments)
- Retrieves top-K most relevant code snippets for each task
- Injects context into LLM prompts (up to 4000 tokens)
- Updates index in real-time as code changes

**RAG Architecture:**
- **Vector Database**: FAISS, pgvector, or ChromaDB for semantic search
- **4-Stage Pipeline**: Retrieval → Flattening → Ranking → Compression
- **Semantic Search**: Uses embedding models to find conceptually similar code
- **Fusion**: Combines results from multiple search strategies

### Assurance by NAVI
- **Graceful Degradation**: If RAG fails, NAVI continues without context (not blocked)
- **Relevance Scoring**: Only injects context above relevance threshold (filters noise)
- **First Iteration Only**: RAG context injected once to avoid repetition
- **Privacy**: Index stays local (never sent to third-party services)

### Benefits for End Users & Organizations
- **Better Responses**: NAVI understands your codebase architecture and conventions
- **Faster Development**: No need to explain context repeatedly
- **Consistency**: NAVI follows existing patterns in your codebase
- **Reduced Hallucination**: Grounded in actual code, not generic examples

### Data Protection & Safety
- Vector database is encrypted at rest
- Code embeddings do not expose full code (only semantic similarity)
- RAG index can be regenerated anytime from source code
- No external services required (fully self-hosted)

### How to Use & Maximize Benefits
```bash
# Automatic RAG indexing on first use
"Add error handling to the UserService class"
# NAVI will:
# 1. Index the codebase if not already indexed
# 2. Retrieve UserService.java and related files
# 3. Inject context: "Here's the existing UserService implementation..."
# 4. Generate error handling that matches existing patterns

# Manual index refresh (after major code changes)
POST /api/rag/reindex?workspace=/path/to/project

# Query RAG index directly (debugging)
POST /api/rag/search
{
  "query": "authentication flow",
  "top_k": 5
}
# Response: Top 5 most relevant code snippets
```

**Pro Tips:**
- Reindex after major refactorings or dependency updates
- Use specific queries to get better RAG results ("JWT authentication" > "auth")
- Increase `top_k` for complex tasks requiring more context
- Exclude large files (e.g., `node_modules`, `*.min.js`) from indexing

---

## 8. Memory Persistence

### What Makes NAVI Unique
NAVI has **graph-based memory** that persists across sessions:
- **Remembers**: Past tasks, user preferences, project context, team conventions
- **Relates**: Builds a knowledge graph connecting tasks, files, and concepts
- **Recalls**: Automatically retrieves relevant memories for new tasks
- **Consolidates**: Merges similar memories to reduce noise

**Memory Types:**
- **Task Memory**: What NAVI has done before (e.g., "Last time you asked to deploy, I used method X")
- **User Memory**: Preferences (e.g., "You prefer Jest over Mocha for testing")
- **Project Memory**: Architecture (e.g., "This is a microservices architecture with 5 services")
- **Team Memory**: Conventions (e.g., "This team uses feature branches and squash merges")

### Assurance by NAVI
- **Decay**: Old, unused memories fade over time (configurable half-life)
- **Conflict Resolution**: Contradictory memories are flagged and reconciled
- **Privacy Controls**: Memories can be deleted or scoped to specific users
- **Semantic Search**: Memories retrieved based on meaning, not just keywords

### Benefits for End Users & Organizations
- **Continuity**: NAVI remembers project context across sessions
- **Onboarding**: New team members benefit from institutional memory
- **Efficiency**: No need to re-explain project structure every time
- **Team Alignment**: NAVI enforces consistent patterns learned from team

### Data Protection & Safety
- Memory database is encrypted at rest (same encryption as audit logs)
- Memories are scoped by organization (no cross-contamination)
- Can export/import memories for disaster recovery
- Automatic memory consolidation prevents unbounded growth

### How to Use & Maximize Benefits
```bash
# NAVI automatically builds memories as you work
"Deploy the API to staging"
# NAVI remembers:
# - Memory: "User prefers deploying to staging before production"
# - Memory: "This project uses GitHub Actions for CI/CD"
# - Memory: "Staging environment is at staging.example.com"

# Next time:
"Deploy the latest changes"
# NAVI recalls memories and knows:
# - To deploy to staging first (user preference)
# - How to trigger GitHub Actions (project memory)
# - Where staging is hosted (project memory)

# Query memories (debugging)
GET /api/memory/recent?user_id=user123&limit=50

# Delete specific memory
DELETE /api/memory/{memory_id}

# Export memories (backup)
GET /api/memory/export?org_id=org123
```

**Pro Tips:**
- Correct NAVI when it misremembers (creates new memory overriding old one)
- Use consistent terminology so NAVI builds coherent memories
- Review recent memories periodically to ensure accuracy
- Export memories before major system changes

---

## 9. Real Command Execution

### What Makes NAVI Unique
Unlike assistants that generate code snippets, NAVI **executes real commands** in your environment:
- Run bash commands (`npm install`, `pytest`, `kubectl apply`)
- Start/stop servers and services
- Interact with git, Docker, Kubernetes, databases
- Handle long-running operations (up to 30 minutes with auto-extension)

**Execution Safety:**
- **Sandboxed**: Commands run in isolated environments (Docker, VM, or container)
- **Timeout Protection**: Commands auto-terminate after timeout (default 5 minutes)
- **Output Streaming**: Real-time output streaming with heartbeat keep-alive
- **Error Recovery**: Automatic retry with exponential backoff for transient failures

### Assurance by NAVI
- **Command Validation**: Dangerous commands require confirmation (e.g., `rm -rf`)
- **Dry-Run Mode**: Preview commands before execution
- **Rollback**: Snapshot environment before destructive operations
- **Audit Logging**: Every command logged with input/output/exit code

### Benefits for End Users & Organizations
- **End-to-End Automation**: From code generation to deployment in one workflow
- **Real Validation**: NAVI knows if commands succeeded (not just guessing)
- **Faster Debugging**: NAVI can run tests, inspect logs, and fix issues iteratively
- **CI/CD Integration**: NAVI can trigger pipelines, monitor deployments, rollback if needed

### Data Protection & Safety
- Command outputs are sanitized to redact credentials (API keys, passwords)
- Execution logs are encrypted at rest
- Sandboxed execution prevents access to host system
- Resource limits prevent runaway processes (CPU, memory, disk)

### How to Use & Maximize Benefits
```bash
# Simple command execution
"Run the unit tests"
# NAVI executes: pytest tests/ --verbose

# Long-running operations
"Install all dependencies and build the project"
# NAVI executes:
# 1. npm install (auto-extended timeout to 20 minutes)
# 2. npm run build
# 3. Streams output in real-time
# 4. Reports success/failure

# Complex multi-step workflows
"Deploy to production and verify health checks"
# NAVI executes:
# 1. docker build -t myapp:latest .
# 2. docker push myapp:latest
# 3. kubectl set image deployment/myapp myapp=myapp:latest
# 4. kubectl rollout status deployment/myapp
# 5. curl https://prod.example.com/health
# 6. If health check fails: kubectl rollout undo deployment/myapp
```

**Pro Tips:**
- Use enterprise mode for production commands (requires approval gates)
- Configure command timeouts based on your environment
- Enable verbose output for debugging (`--verbose`, `-vv`)
- Use dry-run flags when available (`kubectl apply --dry-run=client`)

---

## 10. MCP External Servers

### What Makes NAVI Unique
NAVI supports **Model Context Protocol (MCP)** to integrate with external tools and services:
- Connect to third-party MCP servers (Slack, GitHub, Jira, custom APIs)
- Execute tools from external servers alongside built-in NAVI tools
- Manage credentials securely (encrypted token storage)
- Test connectivity and list available tools before use

**Supported Features:**
- **Server Management**: Add, edit, disable, delete custom MCP servers
- **Tool Discovery**: Auto-discover tools provided by MCP servers
- **Tool Execution**: Execute external tools with parameter validation
- **Enterprise Mode**: Org-managed servers (admin-only, scoped to organization)
- **Policy Controls**: Enforce HTTPS, block private networks, whitelist hosts

### Assurance by NAVI
- **Connection Testing**: Verify server is reachable before adding
- **Tool Validation**: Validate tool schemas match MCP specification
- **Credential Security**: Tokens encrypted with same system as audit logs
- **Rate Limiting**: Prevent abuse of external services
- **Egress Filtering**: Block calls to internal/private networks (configurable)

### Benefits for End Users & Organizations
- **Extensibility**: Add custom tools without modifying NAVI codebase
- **Integration**: Connect to company-specific services and APIs
- **Flexibility**: Use different tool providers for different projects
- **Governance**: Org admins control which servers are available

### Data Protection & Safety
- MCP server credentials are encrypted at rest
- Tokens can be cleared/rotated without deleting server configuration
- All MCP tool calls are logged in audit trail
- Policy controls prevent data exfiltration (e.g., block calls to unknown domains)

### How to Use & Maximize Benefits

**Where to Access:**
- **Command Center → MCP Tools**
- **Sidebar → MCP Tools**

**What You Can Do:**
- Add external MCP servers
- Test connectivity and list tools
- Enable/disable servers
- Edit server configuration and credentials
- Execute tools with parameters
- Delete servers

**Add an MCP Server (Real Usage):**

**Enterprise:** This is **admin-only** and scoped to your organization. Non-admins can use tools but cannot change servers.

1. Open **MCP Tools**.
2. Click **Add Custom MCP Server**.
3. Enter:
   - **Server Name**
   - **Server URL** (must include protocol, e.g. `https://mcp.example.com`)
   - **Auth Type**: `none`, `bearer`, `header`, or `basic`
4. Save, then click **Test connection**.

**Execute a Tool:**
1. Select a tool from the left panel (built-in or external).
2. Fill parameters.
3. Click **Execute Tool**.

**Edit or Clear Credentials:**
1. Click the **Edit** icon on a server card.
2. Update URL/auth as needed.
3. To remove stored secrets, check **Clear stored credentials**.
4. Click **Save Changes**.

**Disable or Delete:**
- **Disable** hides the server's tools without deleting the record.
- **Delete** removes the server from the DB.

**API Examples:**
```bash
# Add custom MCP server
POST /api/mcp/servers
{
  "name": "Company JIRA",
  "url": "https://mcp.company.com",
  "auth_type": "bearer",
  "auth_token": "secret-token-123"
}

# Test connection
POST /api/mcp/servers/{server_id}/test
# Response: { "status": "success", "tools_available": 15 }

# List available tools
GET /api/mcp/servers/{server_id}/tools
# Response: List of tools with descriptions and parameters

# Execute external tool
POST /api/mcp/tools/execute
{
  "tool_name": "create_jira_ticket",
  "server_id": "server-abc123",
  "parameters": {
    "project": "ENG",
    "summary": "Fix authentication bug",
    "description": "Users cannot log in with SSO"
  }
}

# Disable server (temporarily)
PATCH /api/mcp/servers/{server_id}
{ "enabled": false }

# Clear credentials (token rotation)
POST /api/mcp/servers/{server_id}/clear_credentials
```

**Notes:**
- External servers use **Streamable HTTP** transport.
- Server credentials are stored encrypted in the database.
- Servers are **org-scoped** when an org is present (enterprise-safe).
- Optional policy controls: `MCP_REQUIRE_HTTPS`, `MCP_BLOCK_PRIVATE_NETWORKS`, `MCP_ALLOWED_HOSTS`.
- For local dev, you can relax policies: `MCP_REQUIRE_HTTPS=false` and `MCP_BLOCK_PRIVATE_NETWORKS=false`.

**Pro Tips:**
- Use enterprise mode for organization-wide MCP server management
- Enable `MCP_REQUIRE_HTTPS` in production (block HTTP servers)
- Set `MCP_BLOCK_PRIVATE_NETWORKS=true` to prevent internal network access
- Use `MCP_ALLOWED_HOSTS` whitelist for strict control
- Test new servers in development before adding to production

---

## 11. Self-Hosted Deployment

### What Makes NAVI Unique
NAVI is **fully self-hosted** - no data leaves your infrastructure:
- Deploy on-premises or in your cloud account (AWS, GCP, Azure)
- No third-party services required (except LLM APIs)
- Complete data sovereignty and control
- Airgapped deployment option for maximum security

**Deployment Options:**
- **Docker Compose**: Single-server deployment (dev/staging)
- **Kubernetes**: Production deployment with auto-scaling (2-10 replicas)
- **AWS ECS/Fargate**: Managed container service
- **VM/Bare Metal**: Traditional deployment

### Assurance by NAVI
- **No Phone Home**: NAVI never sends telemetry to external services
- **Offline Mode**: Can run without internet access (with local LLM)
- **Update Control**: You control when to update (no forced updates)
- **Backup & Recovery**: Full disaster recovery procedures documented

### Benefits for End Users & Organizations
- **Compliance**: Meet requirements for data residency (GDPR, HIPAA, etc.)
- **Security**: No attack surface through third-party services
- **Cost Control**: No per-user pricing or usage limits
- **Customization**: Modify source code for specific requirements

### Data Protection & Safety
- All data stored in your database (PostgreSQL in your account)
- No data sent to NAVI Labs or third parties
- LLM API calls go directly to Anthropic/OpenAI (no proxy)
- Encryption keys stored in your AWS KMS, not ours

### How to Use & Maximize Benefits
```bash
# Docker Compose (single-server, development)
docker-compose up -d
# Services: backend, frontend, PostgreSQL, Redis

# Kubernetes (production, multi-server)
kubectl apply -f kubernetes/deployments/backend-staging.yaml
kubectl apply -f kubernetes/secrets/database-staging.yaml
# Auto-scaling: 2-10 replicas based on CPU usage

# AWS ECS/Fargate (managed containers)
terraform apply -var-file=production.tfvars
# Provisions: ECS cluster, RDS PostgreSQL, ElastiCache Redis, ALB

# Airgapped deployment (no internet)
# 1. Deploy with local LLM (Ollama, vLLM)
# 2. Disable all external integrations
# 3. Use local vector database (FAISS, pgvector)
export LLM_PROVIDER=local
export LLM_ENDPOINT=http://localhost:11434
```

**Pro Tips:**
- Start with Docker Compose for development, migrate to Kubernetes for production
- Use managed databases (RDS, Cloud SQL) instead of self-managed PostgreSQL
- Enable auto-scaling (HPA) to handle variable load
- Set up monitoring (Prometheus, Grafana) before going to production
- Use infrastructure-as-code (Terraform) for reproducible deployments

---

## 12. Observability & Database Persistence

### What Makes NAVI Unique
NAVI has **production-grade observability** built-in from day one:
- All metrics, logs, and traces stored in PostgreSQL (not just in-memory)
- Prometheus metrics endpoint for LLM costs, latency, token usage
- Structured JSON logging with request correlation
- Historical data for trend analysis and optimization

**Data Stored:**
- **LLM Metrics**: Token usage, costs, latency per call (with model/phase labels)
- **RAG Metrics**: Retrieval performance, chunk counts, relevance scores
- **Task Metrics**: Iteration counts, completion rates, success/failure reasons
- **Learning Data**: User feedback, suggestions, patterns, insights
- **Telemetry Events**: Frontend/backend event tracking
- **Performance Metrics**: Response times, error rates, throughput
- **Error Events**: Structured error tracking with resolution status

### Assurance by NAVI
- **Data Retention**: Configurable retention policies (default: 90 days for logs, unlimited for metrics)
- **Privacy**: PII/PHI automatically redacted before storage
- **Performance**: Indexed queries for fast analytics (23 performance indexes)
- **Migrations**: Alembic database migrations ensure schema consistency

### Benefits for End Users & Organizations
- **Cost Optimization**: Identify expensive LLM calls and optimize prompts
- **Performance Tuning**: Find bottlenecks and optimize response times
- **Trend Analysis**: Track improvement over time (task success rates, user satisfaction)
- **Capacity Planning**: Predict infrastructure needs based on historical usage

### Data Protection & Safety
- Metrics database encrypted at rest
- Access-controlled queries (role-based permissions)
- Data anonymization for analytics (user IDs hashed)
- Automatic data purging after retention period

### How to Use & Maximize Benefits
```bash
# Prometheus metrics endpoint
GET /metrics
# Metrics exposed:
# - aep_llm_calls_total{model, phase, status}
# - aep_llm_latency_ms{model, phase}
# - aep_llm_tokens_total{model, phase, type}
# - aep_llm_cost_usd_total{model, phase}
# - aep_task_iterations{complexity}
# - aep_task_success_rate{complexity}

# Query LLM cost trends (SQL)
SELECT
  DATE(created_at) as date,
  model_name,
  SUM(cost_usd) as total_cost
FROM llm_metrics
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at), model_name
ORDER BY date DESC;

# Identify slow tasks
SELECT
  task_type,
  AVG(execution_time_ms) as avg_time,
  COUNT(*) as count
FROM task_metrics
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY task_type
HAVING AVG(execution_time_ms) > 5000
ORDER BY avg_time DESC;

# User feedback analysis
SELECT
  feedback_type,
  COUNT(*) as count,
  AVG(rating) as avg_rating
FROM learning_suggestions
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY feedback_type;

# Error resolution tracking
SELECT
  error_type,
  COUNT(*) as count,
  SUM(CASE WHEN resolution_status = 'resolved' THEN 1 ELSE 0 END) as resolved
FROM error_events
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY error_type;
```

**Pro Tips:**
- Set up Grafana dashboards for real-time monitoring
- Create alerts for anomalies (cost spikes, error rate increases)
- Run weekly reports to identify optimization opportunities
- Use historical data for capacity planning before scaling
- Export metrics to data warehouse for long-term analysis

---

## Summary: Why Choose NAVI?

### Unique Value Propositions
1. **Truly Autonomous**: Not just suggestions - full execution from start to finish
2. **Enterprise-Ready**: Human checkpoints, compliance scanning, audit encryption
3. **Self-Hosted**: Complete data sovereignty and control
4. **Learns & Adapts**: Gets better over time based on your team's feedback
5. **Production-Grade**: Built-in observability, security, and scalability

### Best For
- **Enterprises**: Needing compliance (PCI-DSS, HIPAA, SOC2) and data sovereignty
- **Regulated Industries**: Healthcare, finance, government (self-hosted requirement)
- **High-Velocity Teams**: Want to automate repetitive tasks and focus on innovation
- **Security-Conscious Orgs**: Require audit encryption and human approval workflows

### Not Best For
- **Hobbyists**: Overkill for small personal projects (use GitHub Copilot instead)
- **Non-Technical Users**: Requires understanding of git, CI/CD, infrastructure
- **Cloud-Only Shops**: If you're not comfortable self-hosting (wait for SaaS version)

---

## Getting Started

### Quick Start (5 minutes)
```bash
# 1. Clone repository
git clone https://github.com/your-org/autonomous-engineering-platform
cd autonomous-engineering-platform

# 2. Set up environment
cp .env.example .env
# Edit .env to add API keys (ANTHROPIC_API_KEY or OPENAI_API_KEY)

# 3. Start with Docker Compose
docker-compose up -d

# 4. Open UI
open http://localhost:3000

# 5. Start chatting with NAVI
"Hello NAVI! Can you help me deploy this project to staging?"
```

### Production Deployment (1-2 days)
See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for full instructions.

---

## Recent Enhancements (February 2026)

### Connection Stability
- **Extended Uvicorn Timeout**: Increased from 120s to 3600s (1 hour) for long-running operations
- **Improved Heartbeat**: Reduced interval from 15s to 10s for better connection reliability
- **Smart Timeout Extension**: Auto-extends timeout for known long-running commands (npm install, pip install, etc.)

### Error Handling
- **Smart Error Detection**: Automatically detects non-retryable errors (rate limits, quota exceeded, auth failures)
- **Early Exit**: Stops immediately on non-retryable errors instead of wasting 15 iterations
- **Clear Error Messages**: Provides actionable guidance when errors occur

### Security
- **Mandatory Audit Encryption**: Production deployment requires AUDIT_ENCRYPTION_KEY
- **Startup Validation**: Double-checks security configuration on application startup
- **Fail-Fast**: Application refuses to start if critical security settings are missing

---

## Support & Resources

- **Documentation**: [docs/](../docs/)
- **GitHub Issues**: https://github.com/your-org/autonomous-engineering-platform/issues
- **Production Readiness**: [NAVI_PROD_READINESS.md](NAVI_PROD_READINESS.md)
- **Deployment Guide**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

---

**Last Updated**: February 7, 2026
**Document Version**: 2.0
**NAVI Version**: 2.0
