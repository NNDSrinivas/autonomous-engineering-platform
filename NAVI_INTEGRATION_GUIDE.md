# NAVI Integration Guide

## What is NAVI?

NAVI is an **aggressive, action-taking AI coding assistant** that competes with GitHub Copilot, Claude Code, and Cline. Unlike cautious assistants that ask permission for everything, NAVI **DOES things immediately** based on natural language commands.

### Key Features

- 🚀 **Instant Action**: Executes commands without asking permission
- 🎯 **Intent Detection**: Understands natural language with typo tolerance
- 🛠️ **Multi-Framework**: Supports React, Next.js, Vue, Angular, FastAPI, Django, Flask, Express, NestJS, Go, Rust, Java
- 📦 **Auto-Install**: Detects and installs required dependencies
- 🔄 **Git Integration**: Commits, pushes, and creates PRs automatically
- 🧠 **Context-Aware**: Analyzes project structure and generates appropriate code
- ⚡ **Fast**: Sub-second response time for most operations

### Comparison with Other Tools

| Feature | NAVI | GitHub Copilot | Claude Code | Cline |
|---------|------|---------------|-------------|-------|
| Instant Actions | ✅ | ❌ | ❌ | ⚠️ |
| Typo Tolerance | ✅ | ❌ | ⚠️ | ⚠️ |
| Multi-Framework | ✅ | ✅ | ✅ | ❌ |
| Auto-Install Deps | ✅ | ❌ | ❌ | ❌ |
| Git Operations | ✅ | ❌ | ⚠️ | ⚠️ |
| Context Analysis | ✅ | ✅ | ✅ | ⚠️ |
| Open Source | ✅ | ❌ | ❌ | ✅ |

## Installation (15 Minutes)

### Prerequisites

- Python 3.11+
- Node.js 18+
- VS Code 1.80+
- Git

### Backend Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/NNDSrinivas/autonomous-engineering-platform.git
   cd autonomous-engineering-platform
   ```

2. **Install Python dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Register NAVI router** in `backend/main.py`:
   ```python
   from backend.api.routers import navi

   app.include_router(navi.router)
   ```

4. **Start the backend**:
   ```bash
   uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
### VS Code Extension Setup

1. **Install extension dependencies**:
   ```bash
   cd extensions/vscode-aep
   npm install
   ```

2. **Build the webview**:
   ```bash
   cd webview
   npm install
   npm run build
   cd ..
   ```

3. **Package the extension**:
   ```bash
   npm run package
   ```

4. **Install in VS Code**:
   - Open VS Code
   - Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
   - Run: `Extensions: Install from VSIX`
   - Select `vscode-aep-*.vsix`

5. **Configure backend URL**:
   - Open VS Code settings (`Ctrl+,`)
   - Search for "AEP"
   - Set `aep.backendUrl` to `http://localhost:8000`

## Usage Examples

### Component Creation

```
User: create a LoginButton component
NAVI: ✅ Created LoginButton component
      Files: src/components/LoginButton.tsx
             src/components/__tests__/LoginButton.test.tsx
```

### Page Creation

```
User: make a dashboard page
NAVI: ✅ Created Dashboard page with routing
      Files: src/pages/Dashboard.tsx
             src/pages/api/dashboard.ts (if Next.js)
```

### API Endpoint

```
User: add a /users endpoint
NAVI: ✅ Created users API endpoint
      Files: backend/api/users.py (FastAPI)
             backend/api/users.test.py
```

### Feature Addition

```
User: add dark mode to the app
NAVI: ✅ Added dark mode support
      Files: src/contexts/ThemeContext.tsx
             src/hooks/useDarkMode.ts
      Dependencies: Installed @mui/material
```

### Typo Tolerance

```
User: open marketng-webiste-navra project
NAVI: ✅ Opening marketing-website-navra-labs
      (Found despite typos: marketng → marketing, webiste → website)
```

### Git Operations

```
User: commit these changes
NAVI: ✅ Committed changes
      Commit: abc1234 "Add LoginButton component"

User: push and create PR
NAVI: ✅ Pushed to origin/feature/login-button
      ✅ Created PR #42: "Add LoginButton component"
      URL: https://github.com/user/repo/pull/42
```

## API Reference

### POST /api/navi/process

Main processing endpoint.

**Request**:
```json
{
  "message": "create a Button component",
  "workspace": "/path/to/project",
  "context": {
    "currentFile": "src/App.tsx",
    "selection": {
      "text": "import React from 'react'",
      "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 24}}
    }
  }
}
```

**Response**:
```json
{
  "success": true,
  "action": "create_component",
  "message": "Created Button component",
  "result": {
    "component_name": "Button",
    "files": {
      "src/components/Button.tsx": "...code...",
      "src/components/__tests__/Button.test.tsx": "...tests..."
    }
  },
  "vscode_command": {
    "command": "navi.createAndOpenFile",
    "args": ["src/components/Button.tsx", "...code..."]
  },
  "files_created": [
    "src/components/Button.tsx",
    "src/components/__tests__/Button.test.tsx"
  ],
  "dependencies_installed": [],
  "git_operations": []
}
```

### POST /api/navi/v2/plan

Create a plan that requires approval before execution.

**Request**:
```json
{
  "message": "add a login page with validation",
  "workspace": "/path/to/project",
  "llm_provider": "anthropic",
  "context": {
    "currentFile": "src/App.tsx"
  }
}
```

**Response**:
```json
{
  "plan_id": "uuid",
  "message": "I'll create a login page with validation...",
  "requires_approval": true,
  "actions_with_risk": [
    {
      "type": "createFile",
      "path": "src/pages/Login.tsx",
      "risk": "low",
      "warnings": [],
      "preview": "..."
    }
  ]
}
```

### POST /api/navi/v2/plan/{plan_id}/approve

Approve and execute specific actions from a plan.

**Request**:
```json
{
  "approved_action_indices": [0, 1]
}
```

**Response**:
```json
{
  "execution_id": "plan-123-exec",
  "status": "completed",
  "message": "Executed 2 approved actions.",
  "updates": [
    {"type": "action_start", "index": 0, "action": {...}},
    {"type": "action_complete", "index": 0, "success": true},
    {"type": "plan_complete"}
  ]
}
```

### POST /api/navi/v2/plan/{plan_id}/approve/stream

SSE stream for live execution updates.

**Request**:
```json
{
  "approved_action_indices": [0, 1]
}
```

**Response (SSE stream)**:
```
data: {"type":"action_start","index":0,"action":{...}}

data: {"type":"action_complete","index":0,"success":true}

data: {"type":"plan_complete"}
```

### POST /api/navi/apply

Apply `file_edits` and optionally run `commands_run` (for non-VS Code clients).

**Request**:
```json
{
  "workspace": "/path/to/project",
  "file_edits": [
    {"filePath": "src/new.ts", "content": "export const x = 1;", "operation": "create"}
  ],
  "commands_run": ["npm test"],
  "allow_commands": false
}
```

**Response**:
```json
{
  "success": true,
  "files_created": ["/path/to/project/src/new.ts"],
  "files_modified": [],
  "commands_run": [],
  "command_failures": [],
  "warnings": []
}
```

### POST /api/navi/detect-project

Detect project type and technologies.

**Request**:
```json
{
  "workspace": "/path/to/project"
}
```

**Response**:
```json
{
  "project_type": "react",
  "technologies": ["React", "TypeScript", "Vite"],
  "dependencies": {
    "react": "^18.2.0",
    "vite": "^5.0.0",
    "typescript": "^5.0.0"
  },
  "package_manager": "npm"
}
```

### POST /api/navi/stream

Streaming endpoint with Server-Sent Events.

**Request**:
```json
{
  "message": "create a dashboard with charts",
  "workspace": "/path/to/project"
}
```

**Response (SSE stream)**:
```
data: {"type": "status", "message": "Analyzing project..."}

data: {"type": "status", "message": "Generating Dashboard component..."}

data: {"type": "file_created", "path": "src/pages/Dashboard.tsx"}

data: {"type": "status", "message": "Installing dependencies..."}

data: {"type": "dependency_installed", "package": "recharts"}

data: {"type": "complete", "result": {...}}
```

### GET /api/navi/health

Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "service": "navi",
  "version": "1.0.0"
}
```

### GET /api/navi/supported-actions

Get list of supported actions.

**Response**:
```json
{
  "actions": [
    {
      "name": "create_component",
      "description": "Create a new component with tests",
      "examples": ["create a Button component", "make a LoginForm component"]
    }
  ]
}
```

## Supported Project Types

NAVI automatically detects and supports:

### Frontend
- **React** (CRA, Vite, custom)
- **Next.js** (Pages Router, App Router)
- **Vue** (Vue 2, Vue 3, Nuxt)
- **Angular** (Angular 2+)
- **Svelte** (SvelteKit)

### Backend
- **FastAPI** (Python)
- **Django** (Python)
- **Flask** (Python)
- **Express** (Node.js)
- **NestJS** (Node.js)

### Other Languages
- **Go** (standard library, Gin, Echo)
- **Rust** (Actix, Rocket)
- **Java** (Spring Boot)

## Intent Detection Patterns

NAVI understands natural language with high tolerance for:
- Typos
- Incomplete sentences
- Casual language
- Vague requests

### Supported Intents

| Intent | Example Commands |
|--------|-----------------|
| `create_component` | "create a Button component", "make LoginForm", "add UserCard" |
| `create_page` | "create dashboard page", "make settings page", "add profile" |
| `create_api` | "create users endpoint", "add /auth/login API", "make products route" |
| `add_feature` | "add dark mode", "implement authentication", "add search" |
| `refactor_code` | "refactor UserList", "extract reusable logic", "improve error handling" |
| `fix_error` | "fix login error", "debug API call", "resolve type error" |
| `install_package` | "install axios", "add react-router", "install date-fns" |
| `run_command` | "run tests", "build project", "start dev server" |
| `git_commit` | "commit changes", "create commit with message", "commit and push" |
| `create_pr` | "create PR", "make pull request", "open PR for review" |
| `open_project` | "open marketing website", "go to backend project", "show mobile app" |

### Fuzzy Matching

NAVI normalizes user input by:
1. Converting to lowercase
2. Removing hyphens, underscores, spaces
3. Calculating match score (0-1)
4. Selecting best match above threshold (0.7)

Example:
```
Input:    "open marketng-webiste-navra"
Normaliz: "openmarketngwebisitenavra"
Match:    "marketing-website-navra-labs" → Score: 0.85 ✅
```

## Extension Integration

### VS Code Commands

NAVI provides these VS Code commands:

- `navi.createAndOpenFile` - Create file and open in editor
- `navi.openProject` - Open project folder
- `navi.runCommand` - Run terminal command
- `navi.installDependency` - Install package
- `navi.commitChanges` - Commit to git
- `navi.pushChanges` - Push to remote
- `navi.createPR` - Create pull request

### Message Handlers

The webview handles these message types:

- `executeCommand` - Execute VS Code command
- `openFile` - Open file in editor
- `showDiff` - Show file diff
- `installPackage` - Install package
- `runTests` - Run test suite

### Action Execution Flow

1. User types message in NAVI chat
2. Webview sends message to backend `/api/navi/process`
3. Backend parses intent and executes action
4. Backend returns result with `vscode_command`
5. Webview receives response
6. Webview executes VS Code command
7. User sees result (file opened, package installed, etc.)

## Configuration

### Environment Variables

Create `.env` file in backend directory:

```bash
# NAVI Configuration
NAVI_AUTO_COMMIT=true          # Auto-commit created files
NAVI_AUTO_INSTALL=true         # Auto-install dependencies
NAVI_AUTO_PUSH=false           # Auto-push commits (default: false)
NAVI_CONFIDENCE_THRESHOLD=0.8  # Intent confidence threshold
NAVI_MAX_FILE_SIZE=1048576     # Max file size to analyze (1MB)

# Git Configuration
GIT_USER_NAME="NAVI"
GIT_USER_EMAIL="navi@example.com"

# LLM Configuration (optional)
OPENAI_API_KEY=sk-...          # For enhanced code generation
ANTHROPIC_API_KEY=sk-ant-...   # Alternative LLM
```

### VS Code Settings

```json
{
  "aep.backendUrl": "http://localhost:8000",
  "aep.navi.autoCommit": true,
  "aep.navi.autoInstall": true,
  "aep.navi.confidenceThreshold": 0.8,
  "aep.navi.showNotifications": true,
  "aep.navi.enableStreaming": true
}
```

## Testing

### Manual Testing

1. **Component Creation**:
   ```bash
   curl -X POST http://localhost:8000/api/navi/process \
     -H "Content-Type: application/json" \
     -d '{
       "message": "create a Button component",
       "workspace": "/path/to/react-project"
     }'
   ```

2. **Project Detection**:
   ```bash
   curl -X POST http://localhost:8000/api/navi/detect-project \
     -H "Content-Type: application/json" \
     -d '{"workspace": "/path/to/project"}'
   ```

3. **Health Check**:
   ```bash
   curl http://localhost:8000/api/navi/health
   ```

### Automated Tests

Run backend tests:
```bash
cd backend
pytest tests/test_navi_engine.py -v
```

Run extension tests:
```bash
cd extensions/vscode-aep
npm test
```

## Troubleshooting

### NAVI doesn't understand my command

**Problem**: Low confidence score or intent not detected

**Solution**:
1. Use more specific language: "create a Button component" instead of "add button"
2. Check supported intents: `curl http://localhost:8000/api/navi/supported-actions`
3. Lower confidence threshold in settings: `NAVI_CONFIDENCE_THRESHOLD=0.7`

### Files created in wrong location

**Problem**: Files created in root instead of proper directory

**Solution**:
1. Ensure project structure follows conventions (src/, components/, pages/)
2. Provide context: "create Button component in src/components"
3. Check project detection: `POST /api/navi/detect-project`

### Dependencies not installed

**Problem**: Required packages not auto-installed

**Solution**:
1. Enable auto-install: `NAVI_AUTO_INSTALL=true`
2. Check package manager detection
3. Install manually: "install react-router-dom"

### Git operations fail

**Problem**: Commit or push fails

**Solution**:
1. Configure git: `git config user.name` and `git config user.email`
2. Check git status: `git status`
3. Ensure clean working tree
4. Set up git credentials for push

### Backend connection fails

**Problem**: Extension can't reach backend

**Solution**:
1. Check backend is running: `curl http://localhost:8000/api/navi/health`
2. Verify backend URL in VS Code settings
3. Check firewall settings
4. Review backend logs: `tail -f backend/logs/navi.log`

## Enterprise Features

### Team Collaboration

NAVI supports team-wide configurations:

```bash
# .navi/config.yml
project_name: "Marketing Website"
conventions:
  component_dir: "src/components"
  test_dir: "__tests__"
  style: "emotion"
  testing: "jest"

git:
  auto_commit: true
  auto_push: false
  pr_template: ".github/PULL_REQUEST_TEMPLATE.md"

dependencies:
  auto_install: true
  allowed_registries:
    - "https://registry.npmjs.org"
    - "https://private-registry.company.com"
```

### Analytics

Track NAVI usage:

```python
from backend.services.navi_engine import NaviAnalytics

analytics = NaviAnalytics()
stats = analytics.get_stats(timeframe='week')

print(f"Components created: {stats['components_created']}")
print(f"Files generated: {stats['files_generated']}")
print(f"Time saved: {stats['time_saved_hours']}h")
```

### Custom Actions

Define custom actions for your project:

```python
# .navi/custom_actions.py
from backend.services.navi_engine import NaviEngine

class CustomNaviEngine(NaviEngine):
    def custom_create_microservice(self, name: str):
        """Create microservice with our company's template"""
        files = {
            f"services/{name}/main.py": self._generate_service_template(name),
            f"services/{name}/Dockerfile": self._generate_dockerfile(name),
            f"services/{name}/k8s/deployment.yml": self._generate_k8s_manifest(name)
        }
        return self._create_files(files)
```

## Roadmap

### Q2 2026
- [ ] Multi-file refactoring
- [ ] Test generation for all frameworks
- [ ] Code review suggestions
- [ ] Performance optimization hints

### Q3 2026
- [ ] Voice commands
- [ ] Multi-language support (Spanish, Chinese, etc.)
- [ ] Plugin system for custom actions
- [ ] Integration with GitHub Copilot Workspace

### Q4 2026
- [ ] Self-learning from codebase patterns
- [ ] Automatic bug detection and fixes
- [ ] Architecture recommendations
- [ ] Full CI/CD pipeline generation

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

1. Fork the repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes and test
4. Commit: `git commit -m "Add my feature"`
5. Push: `git push origin feature/my-feature`
6. Create Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Support

- **GitHub Issues**: https://github.com/NNDSrinivas/autonomous-engineering-platform/issues
- **Discord**: https://discord.gg/navi-aep
- **Email**: support@navi-aep.com
- **Documentation**: https://docs.navi-aep.com

## Credits

Built with ❤️ by the NAVRA Labs team.

Special thanks to:
- Claude (Anthropic) for AI capabilities
- FastAPI for backend framework
- VS Code team for extension API
- Open source community

---

**NAVI - Because great developers deserve great tools.**
