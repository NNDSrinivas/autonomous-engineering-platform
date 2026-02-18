# 🚀 Developer Setup Guide

> **Quick start guide for developers new to the Autonomous Engineering Platform**

This guide will get you from `git clone` to a fully running development environment in under 15 minutes.

---

## 📋 Table of Contents

1. [Prerequisites](#-prerequisites)
2. [Quick Start (TL;DR)](#-quick-start-tldr)
3. [Detailed Setup](#-detailed-setup)
4. [Running Tests](#-running-tests)
5. [Development Workflows](#-development-workflows)
6. [Troubleshooting](#-troubleshooting)
7. [Next Steps](#-next-steps)

---

## ✅ Prerequisites

### Required Software

| Tool | Required Version | Check Command | Install |
|------|-----------------|---------------|---------|
| **Python** | 3.11.x recommended (3.13+ not supported) | `python3 --version` | macOS: `brew install python@3.11`<br>Linux: `sudo apt install python3.11` |
| **Node.js** | 20+ LTS (18.19+ minimum) | `node --version` | macOS: `brew install node@20`<br>Linux: [nodejs.org](https://nodejs.org) |
| **Docker Desktop** | Latest | `docker --version` | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| **Git** | 2.0+ | `git --version` | macOS: `brew install git`<br>Linux: `sudo apt install git` |

> **PostgreSQL and Redis run inside Docker** via `docker compose up -d` — no local install needed.

### Quick Version Check

Run this command to check all prerequisites:

```bash
echo "Python: $(python3 --version)"
echo "Node:   $(node --version)"
echo "Docker: $(docker --version)"
echo "Git:    $(git --version)"
```

### Environment Setup

You'll need API keys for LLM providers (at least one):

- **OpenAI API Key**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Anthropic API Key**: [console.anthropic.com](https://console.anthropic.com)
- **Google AI API Key** (optional): [makersuite.google.com](https://makersuite.google.com)

---

## 🎯 Quick Start (TL;DR)

**For experienced developers who want the fastest path:**

```bash
# 1. Clone
git clone <repository-url>
cd autonomous-engineering-platform

# 2. Python backend
python3.11 -m venv aep-venv
source aep-venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-test.txt  # for running tests

# 3. Node.js workspaces (frontend + all packages) — run from repo root
npm install

# 4. Environment — copy template and set your API key(s)
cp .env.template .env
# Minimum required in .env:
#   OPENAI_API_KEY=sk-...  (or ANTHROPIC_API_KEY)
#   DATABASE_URL=postgresql+psycopg://mentor:mentor@localhost:5432/mentor
#   REDIS_URL=redis://localhost:6379/0
#   APP_ENV=dev
#   JWT_ENABLED=false
#   ALLOW_DEV_AUTH_BYPASS=true

# 5. Start PostgreSQL + Redis via Docker
docker compose up -d
# Verify: docker compose ps  (both should show "healthy")

# 6. Run database migrations
alembic upgrade head

# 7. Start Prometheus + Grafana (observability stack)
./scripts/run_grafana_local.sh
# Prometheus → http://localhost:9090
# Grafana    → http://localhost:3001  (admin / admin)

# 8. Start backend (Terminal 1) — loads .env and activates venv automatically
./start_backend_dev.sh
# API → http://localhost:8787

# 9. Start frontend (Terminal 2)
cd frontend && npm run dev
# UI → http://localhost:3007  (Vite default; auto-increments to 3008/3009 if taken)
```

**Done!** ✅ Skip to [Development Workflows](#-development-workflows)

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8787 |
| Frontend | http://localhost:3007 (check terminal for actual port) |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

## 📚 Detailed Setup

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd autonomous-engineering-platform
```

### Step 2: Set Up Python Backend

#### Create Virtual Environment

**Why?** Isolates Python dependencies from your system Python.

```bash
# Create virtual environment with Python 3.11
python3.11 -m venv aep-venv

# Activate it
source aep-venv/bin/activate

# Verify correct Python version
python --version  # Should show Python 3.11.x
which python      # Should show /path/to/aep-venv/bin/python
```

**Windows users:**
```powershell
python -m venv aep-venv
.\aep-venv\Scripts\activate
```

#### Install Python Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# Install development/test dependencies
pip install -r requirements-test.txt
```

**What gets installed?**
- `requirements.txt`: FastAPI, SQLAlchemy, Redis, LLM clients, etc.
- `requirements-test.txt`: pytest, fakeredis, linters (ruff, black)

### Step 3: Set Up Node.js Workspaces

**Important:** Run this from the **repository root**, not from subdirectories!

```bash
# Install all npm workspaces (frontend, extension, webview, packages)
npm install
```

**What gets installed?**
- Frontend dependencies (React, Vite, TypeScript)
- VS Code extension dependencies
- Shared packages (`@aep/navi-contracts`)
- Development tools

### Step 4: Configure Environment Variables

```bash
# Copy template
cp .env.template .env

# Edit with your favorite editor
nano .env  # or vim, code, etc.
```

**Minimum required configuration:**

```bash
# Database (SQLite for development)
DATABASE_URL=sqlite:///./data/engineering_platform.db

# LLM Provider API Keys (add at least one)
OPENAI_API_KEY=sk-your-openai-api-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Security
SECRET_KEY=your-random-secret-key-change-this-in-production
JWT_SECRET=another-random-secret-for-jwt

# Authentication (development mode)
JWT_ENABLED=false
DEV_USER_ID=dev-user-123
DEV_USER_EMAIL=developer@example.com
DEV_ORG_ID=default
DEV_USER_ROLE=developer
```

**Optional but recommended:**

```bash
# Redis (for circuit breakers, caching, pub/sub)
REDIS_URL=redis://localhost:6379/0

# Observability
LOG_LEVEL=INFO
PROMETHEUS_ENABLED=true
```

### Step 5: Set Up Database

```bash
# Ensure virtual environment is activated
source aep-venv/bin/activate

# Run all migrations to create database schema
alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001_init, initial baseline
INFO  [alembic.runtime.migration] Running upgrade 0001_init -> 0002_audit_log, audit log table
...
INFO  [alembic.runtime.migration] Running upgrade ... -> HEAD
```

**Verify database created:**
```bash
# SQLite
ls -lh data/engineering_platform.db

# PostgreSQL
psql -c "\dt" postgresql://localhost/aep_dev
```

### Step 6: Start Development Servers

You'll need **multiple terminal windows** or use a terminal multiplexer (tmux/screen).

#### Terminal 1: Backend API

```bash
# Activate virtual environment
source aep-venv/bin/activate

# Start backend server (WITHOUT --reload for faster startup)
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8787

# Server should start in ~2-3 seconds
# ✅ Application startup complete
# ℹ️  Uvicorn running on http://127.0.0.1:8787
```

**Verify backend is running:**
```bash
curl http://localhost:8787/health
# Expected: {"status":"ok","service":"core"}
```

#### Terminal 2: Frontend Dev Server

```bash
# Navigate to frontend directory
cd frontend

# Start development server with hot reload
npm run dev

# Server should start at http://localhost:3007  (configured in frontend/vite.config.ts)
# VITE v6.x ready in 500ms
```

**Verify frontend is running:**

Open http://localhost:3007 in your browser

#### Terminal 3: Redis (Optional)

Only needed if you're testing circuit breakers, caching, or real-time features.

```bash
# Start Redis server
redis-server

# Or with Docker
docker run -d -p 6379:6379 redis:7-alpine
```

### Step 7: Verify Installation

**Backend Health Check:**
```bash
curl http://localhost:8787/health
# {"status":"ok","service":"core"}

curl http://localhost:8787/metrics  # Prometheus metrics
```

**Frontend Access:**
- Open http://localhost:3007
- You should see the AEP dashboard/UI

**Database Check:**
```bash
# Activate venv first
source aep-venv/bin/activate

# Check if tables exist
alembic current
# Should show current migration revision
```

---

## 🧪 Running Tests

### Python Tests

```bash
# Activate virtual environment
source aep-venv/bin/activate

# Run all tests
pytest

# Run specific test file
pytest backend/tests/test_provider_health.py

# Run with coverage
pytest --cov=backend --cov-report=html

# Run only unit tests (skip integration)
pytest -m "not integration"

# Run with verbose output
pytest -xvs backend/tests/
```

**Common test commands:**

```bash
# Circuit breaker tests
pytest backend/tests/test_redis_circuit_breaker.py -xvs

# Provider health tests
pytest backend/tests/test_provider_health.py -xvs

# Integration tests (requires Redis)
pytest backend/tests/test_router_circuit_breaker_integration.py -xvs
```

### Frontend Tests

```bash
cd frontend

# Run unit tests
npm run test

# Run E2E tests (requires backend running)
npm run test:e2e

# Run specific E2E test
npm run test:e2e -- tests/plan-resume.spec.ts
```

### Code Quality Checks

```bash
# Python linting with ruff
ruff check backend/

# Python formatting with black
black --check backend/

# TypeScript type checking
cd frontend && npm run type-check

# Run all quality checks
make lint  # If Makefile exists
```

---

## 💻 Development Workflows

### Common Development Tasks

#### 1. Making Code Changes

**Backend (Python):**
- Edit files in `backend/`
- Changes require server restart (no --reload in development)
- Run tests: `pytest backend/tests/`

**Frontend (React):**
- Edit files in `frontend/src/`
- Hot reload works automatically
- Check browser console for errors

#### 2. Adding New Dependencies

**Python:**
```bash
# Activate venv
source aep-venv/bin/activate

# Install package
pip install package-name

# Update requirements
pip freeze > requirements.txt

# Or add manually to requirements.txt and reinstall
pip install -r requirements.txt
```

**Node.js:**
```bash
# Always run from repository root!
npm install package-name

# Or add to specific workspace
cd frontend && npm install package-name
```

#### 3. Database Migrations

**Create new migration:**
```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "Add new table"

# Review generated migration in alembic/versions/
# Edit if needed, then apply
alembic upgrade head
```

**Rollback migration:**
```bash
# Downgrade one revision
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade abc123
```

#### 4. Running Backend Without Auto-Reload

**Why?** Much faster startup, but requires manual restart on changes.

```bash
# Fast startup (recommended for development)
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8787

# With auto-reload (slow startup, 3-5 minutes)
python -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8787
```

#### 5. Debugging

**Backend debugging:**
```bash
# Add breakpoints with pdb
import pdb; pdb.set_trace()

# Or use ipdb for better experience
pip install ipdb
import ipdb; ipdb.set_trace()
```

**Frontend debugging:**
- Use browser DevTools (F12)
- React DevTools extension recommended
- Check console for errors and warnings

### VS Code Extension Development

```bash
# Build agent core
cd agent-core
npm install
npm run build

# Build VS Code extension
cd ../extensions/aep-professional
npm install
npm run compile

# Launch extension (F5 in VS Code)
# Open extensions/aep-professional/ in VS Code
# Press F5 to launch Extension Development Host
```

---

## 🔧 Troubleshooting

### Backend Won't Start

**Problem:** `ModuleNotFoundError: No module named 'fastapi'`

**Solution:**
```bash
# Verify virtual environment is activated
which python
# Should show: /path/to/aep-venv/bin/python

# If not, activate it
source aep-venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

---

**Problem:** Port 8787 already in use

**Solution:**
```bash
# Find and kill process using port
lsof -ti :8787 | xargs kill -9

# Or use a different port
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8788
```

---

**Problem:** Backend startup takes 3-5 minutes

**Solution:**
```bash
# DON'T use --reload flag for development
python -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8787

# Only use --reload if you need auto-restart (slow!)
```

### Frontend Issues

**Problem:** `npm install` fails with workspace errors

**Solution:**
```bash
# MUST run from repository root, not subdirectories!
cd /path/to/autonomous-engineering-platform
npm install

# Clear cache if issues persist
rm -rf node_modules package-lock.json
npm install
```

---

**Problem:** Vite dev server won't start

**Solution:**
```bash
cd frontend

# Check Node version (needs 18.19+ or 20+)
node --version

# Clear cache and reinstall
rm -rf node_modules .vite
npm install
npm run dev
```

### Database Issues

**Problem:** `alembic upgrade head` fails

**Solution:**
```bash
# Check database file permissions
ls -la data/

# Create data directory if missing
mkdir -p data

# Try again
alembic upgrade head

# If PostgreSQL connection fails
createdb aep_dev
```

---

**Problem:** Migration conflicts

**Solution:**
```bash
# Check current revision
alembic current

# Downgrade to base
alembic downgrade base

# Reapply migrations
alembic upgrade head
```

### Python Version Issues

**Problem:** Using system Python 3.13+ instead of 3.11

**Solution:**
```bash
# Check which Python you're using
python --version
which python

# Install Python 3.11
# macOS
brew install python@3.11

# Ubuntu/Debian
sudo apt install python3.11 python3.11-venv

# Create venv with specific version
python3.11 -m venv aep-venv
source aep-venv/bin/activate

# Verify
python --version  # Should show 3.11.x
```

### Redis Not Available

**Problem:** Circuit breaker tests fail without Redis

**Solution:**
```bash
# Option 1: Start Redis locally
redis-server

# Option 2: Use Docker
docker run -d -p 6379:6379 redis:7-alpine

# Option 3: Use fakeredis for tests (already in requirements-test.txt)
# Tests will automatically use fakeredis if Redis not available
pytest backend/tests/test_redis_circuit_breaker.py
```

### Tests Failing

**Problem:** Tests pass locally but fail in CI

**Common causes:**
- Missing test dependencies: `pip install -r requirements-test.txt`
- Different Python version: Use Python 3.11.x
- Missing environment variables: Check `.env` file
- Redis not available: Tests should use fakeredis automatically

**Debug:**
```bash
# Run tests with verbose output
pytest -xvs backend/tests/

# Run specific failing test
pytest -xvs backend/tests/test_file.py::test_name

# Check test environment
pytest --collect-only
```

---

## 🎓 Next Steps

### Learning Resources

1. **Architecture Documentation**
   - Read `README.md` for feature overview
   - Check `docs/` directory for detailed guides
   - Review PR descriptions in GitHub for recent changes

2. **Code Structure**
   ```
   backend/
   ├── api/          # FastAPI routes and endpoints
   ├── services/     # Business logic (LLM clients, router, health tracking)
   ├── database/     # SQLAlchemy models and DB access
   ├── tests/        # pytest test suite
   └── core/         # Core utilities (config, cache, auth)

   frontend/
   ├── src/
   │   ├── components/  # React components
   │   ├── lib/         # Utilities and hooks
   │   └── pages/       # Page components
   └── tests/           # E2E tests (Playwright)
   ```

3. **Key Concepts**
   - **Circuit Breakers**: `backend/services/redis_circuit_breaker.py`
   - **Provider Health**: `backend/services/provider_health.py`
   - **Model Router**: `backend/services/model_router.py`
   - **LLM Clients**: `backend/services/llm_client.py`

### Contributing

1. **Create a branch for your changes**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes and test**
   ```bash
   # Run tests
   pytest backend/tests/

   # Check code quality
   ruff check backend/
   black --check backend/
   ```

3. **Commit and push**
   ```bash
   git add .
   git commit -m "Add feature: your description"
   git push origin feature/your-feature-name
   ```

4. **Create Pull Request**
   - Use GitHub UI or `gh pr create`
   - Follow the PR template
   - Wait for CI checks to pass

### Common Development Patterns

**Adding a new API endpoint:**
1. Create route in `backend/api/routers/`
2. Add business logic in `backend/services/`
3. Write tests in `backend/tests/`
4. Update frontend to call new endpoint

**Adding a new LLM provider:**
1. Create adapter in `backend/services/llm_client.py`
2. Add to `LLMProvider` enum
3. Update `get_adapter()` function
4. Add health tracking integration
5. Write tests

**Adding a new database table:**
1. Create model in `backend/database/models/`
2. Generate migration: `alembic revision --autogenerate -m "Add table"`
3. Review and apply: `alembic upgrade head`
4. Write tests for new model

---

## 📞 Getting Help

### Resources

- **Documentation**: Check `README.md` and `docs/` directory
- **Issues**: Search GitHub issues for similar problems
- **Tests**: Look at test files for usage examples
- **Code**: Read the implementation - it's well-commented!

### Asking for Help

When asking for help, include:

1. **What you're trying to do**
2. **What you expected to happen**
3. **What actually happened**
4. **Error messages** (full stack trace)
5. **Environment info**:
   ```bash
   python --version
   node --version
   cat .env | grep -v API_KEY  # Don't share API keys!
   ```

---

## 🌐 Connecting to Staging

You don't need to run the backend locally to test against the live staging environment. This section covers how to point your local tooling at `https://staging.navralabs.com`.

### VS Code extension — open the staging workspace

The repo ships three workspace files. Open the right one based on what you're doing:

| Workspace file | Backend URL | When to use |
|---|---|---|
| `aep.dev.code-workspace` | `http://127.0.0.1:8787` | Local development |
| `aep.staging.code-workspace` | `https://staging.navralabs.com` | Testing against staging |
| `aep.prod.code-workspace` | `https://app.navralabs.com` | Production access (future) |

```
File → Open Workspace from File → aep.staging.code-workspace
```

The NAVI extension will immediately connect to staging — no settings change needed.

> **No repo access?** Ask the team for the `navi-assistant-staging-<version>.vsix` file and install it with:
> ```bash
> code --install-extension navi-assistant-staging-<version>.vsix
> ```

### Web app

Open https://staging.navralabs.com in any browser. No login required currently (JWT disabled in staging).

### Checking staging health

```bash
# Backend liveness
curl https://staging.navralabs.com/health/live

# Backend via API path
curl https://staging.navralabs.com/api/health/ready
```

### Deploying to staging

See **[docs/STAGING.md](./docs/STAGING.md)** for full deploy commands, migration one-liners, and AWS infrastructure reference.

---

## ✅ Setup Checklist

Use this to verify your setup is complete:

- [ ] Python 3.11 installed and virtual environment created
- [ ] All Python dependencies installed (`requirements.txt` + `requirements-test.txt`)
- [ ] Node.js 20+ installed
- [ ] All npm workspaces installed (ran `npm install` from root)
- [ ] `.env` file created and configured with API keys
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] Backend starts successfully on port 8787
- [ ] Frontend starts successfully on port 3000
- [ ] Health check endpoint responds: `curl http://localhost:8787/health`
- [ ] Tests pass: `pytest backend/tests/`
- [ ] Redis running (optional, for circuit breaker features)

**If all checkboxes are checked, you're ready to develop!** 🎉

---

**Welcome to the Autonomous Engineering Platform development team!**

For questions or issues, create a GitHub issue or reach out to the maintainers.
