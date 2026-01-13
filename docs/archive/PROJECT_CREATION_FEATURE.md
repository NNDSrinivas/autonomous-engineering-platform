# NAVI Project Creation Feature - Complete Implementation

## Overview

NAVI can now create new projects from natural language requests! When you ask "Create a new project called NAVI marketing website", NAVI will:
1. Detect the project creation intent
2. Extract project details using LLM
3. Scaffold the appropriate project type
4. Initialize git repository
5. Open the new project in VSCode

## Implementation Details

### 1. Project Scaffolding Service

**File**: [backend/services/project_scaffolder.py](backend/services/project_scaffolder.py)

A comprehensive service that supports multiple project types:

#### Supported Project Types

- **Next.js** - `npx create-next-app` with TypeScript and Tailwind
- **React** - `npx create-react-app` with optional TypeScript
- **Vite (React/Vue)** - `npm create vite` with templates
- **Express.js** - Custom scaffolding with TypeScript support
- **Python** - Basic Python project structure
- **Static HTML** - HTML/CSS/JS static website
- **Generic** - Basic project with README

#### Key Features

- **Automatic Project Type Detection**: Uses LLM to analyze natural language and determine project type
- **Smart Scaffolding**: Runs appropriate CLI tools (create-next-app, create-react-app, etc.)
- **Git Integration**: Automatically initializes git and creates initial commit
- **Dependency Installation**: Optionally runs `npm install` after scaffolding
- **Security Validation**: Prevents directory traversal and validates paths

#### Example Usage

```python
from backend.services.project_scaffolder import ProjectScaffolder, ProjectScaffoldRequest, ProjectType

scaffolder = ProjectScaffolder()

# Detect project type from description
project_type = scaffolder.detect_project_type("Create a Next.js marketing website")
# Returns: ProjectType.NEXTJS

# Create the project
request = ProjectScaffoldRequest(
    project_name="navi-marketing-website",
    project_type=ProjectType.NEXTJS,
    parent_directory="/Users/username/dev",
    description="A marketing website for NAVI",
    typescript=True,
    git_init=True,
    install_dependencies=True,
)

result = await scaffolder.scaffold_project(request)

if result.success:
    print(f"Project created at: {result.project_path}")
    print(f"Commands run: {result.commands_run}")
```

### 2. API Endpoint

**File**: [backend/api/routers/autonomous_coding.py](backend/api/routers/autonomous_coding.py#L430-L479)

**Endpoint**: `POST /api/autonomous/create-project`

#### Request Body

```json
{
  "project_name": "navi-marketing-website",
  "description": "A marketing website for NAVI with homepage, about, and contact pages",
  "parent_directory": "/Users/username/dev",
  "project_type": "nextjs",  // optional, auto-detected if not provided
  "typescript": true,
  "git_init": true,
  "install_dependencies": true
}
```

#### Response

```json
{
  "success": true,
  "project_path": "/Users/username/dev/navi-marketing-website",
  "project_type": "nextjs",
  "message": "Next.js project created successfully at /Users/username/dev/navi-marketing-website",
  "commands_run": [
    "npx create-next-app@latest navi-marketing-website --typescript --tailwind --app --no-src-dir --import-alias @/*",
    "git init",
    "git add .",
    "git commit -m 'Initial commit from NAVI'"
  ],
  "error": null
}
```

### 3. Chat Endpoint Integration

**File**: [backend/api/chat.py](backend/api/chat.py#L392-L568)

#### Detection Patterns

The chat endpoint detects project creation requests using these patterns:
- "create a new project"
- "create a project"
- "new project called"
- "create new workspace"
- "create a new app"
- "build a new project"
- "make a new project"
- "start a new project"
- "scaffold a new"

#### Two-Step Confirmation Flow

**Step 1: Extract Project Details**

When NAVI detects a project creation request, it uses LLM to extract:
- Project name (converted to kebab-case)
- Description
- Suggested parent directory

Example response:
```
I'll help you create **navi-marketing-website**!

**Description**: A marketing website for NAVI with homepage, about, and contact pages

To create this project, I need to know where you'd like it:

📁 **Suggested location**: `/Users/username/dev/navi-marketing-website`

Please reply with one of:
1. "yes" or "create it" - to use the suggested location
2. "use /path/to/directory" - to specify a different parent directory
3. Provide your preferred directory path

Once you confirm, I'll:
- Create the project structure
- Set up scaffolding (Next.js, React, etc. based on your description)
- Initialize git repository
- Open it in VSCode for you
```

**Step 2: Create Project**

When user confirms with "yes", "create it", or provides a custom path:
- Calls the `/api/autonomous/create-project` endpoint
- Scaffolds the project
- Returns success message with details
- Triggers VSCode to open the new project

Example success response:
```
✅ **Project created successfully!**

📁 **Location**: `/Users/username/dev/navi-marketing-website`
🎯 **Type**: nextjs

**Commands executed**:
```bash
npx create-next-app@latest navi-marketing-website --typescript --tailwind --app --no-src-dir --import-alias @/*
git init
git add .
git commit -m 'Initial commit from NAVI'
```

Next.js project created successfully at /Users/username/dev/navi-marketing-website

I'll now open this project in VSCode for you. Once it opens, I can help you customize it further!
```

### 4. Frontend Integration

**File**: [extensions/vscode-aep/webview/src/components/navi/NaviChatPanel.tsx](extensions/vscode-aep/webview/src/components/navi/NaviChatPanel.tsx#L1040-L1051)

When NAVI successfully creates a project, the frontend receives a response with:

```typescript
{
  agentRun: {
    mode: 'project_created',
    project_path: '/path/to/new/project',
    open_in_vscode: true
  }
}
```

The frontend then sends a message to the VSCode extension:

```typescript
window.vscode?.postMessage({
  type: 'openFolder',
  folderPath: projectPath,
  newWindow: true,
});
```

### 5. VSCode Extension Handler

**File**: [extensions/vscode-aep/src/extension.ts](extensions/vscode-aep/src/extension.ts#L4140-L4151)

The extension handles the `openFolder` message:

```typescript
case 'openFolder': {
  const { folderPath, newWindow } = msg;
  console.log('[AEP] React webview: Open folder request', { folderPath, newWindow });

  // Convert to URI and open the folder
  const folderUri = vscode.Uri.file(folderPath);
  await vscode.commands.executeCommand('vscode.openFolder', folderUri, newWindow !== false);

  // Show notification
  vscode.window.showInformationMessage(`Opening project: ${path.basename(folderPath)}`);
  break;
}
```

This executes VSCode's native `openFolder` command, which:
- Opens the new project in a new VSCode window
- Closes the current NAVI chat (expected behavior)
- User can then re-open NAVI in the new project to continue customization

## User Workflow

### Example 1: Create a Next.js Marketing Website

**User**: "Create a new project called NAVI marketing website"

**NAVI**:
```
I'll help you create **navi-marketing-website**!

**Description**: A Next.js marketing website for NAVI

📁 **Suggested location**: `/Users/username/dev/navi-marketing-website`

Please reply with one of:
1. "yes" or "create it" - to use the suggested location
2. "use /path/to/directory" - to specify a different parent directory
```

**User**: "yes"

**NAVI**:
```
✅ **Project created successfully!**

📁 **Location**: `/Users/username/dev/navi-marketing-website`
🎯 **Type**: nextjs

**Commands executed**:
npx create-next-app@latest navi-marketing-website --typescript --tailwind --app...
git init
git add .
git commit -m 'Initial commit from NAVI'

I'll now open this project in VSCode for you!
```

*VSCode opens the new project in a new window*

### Example 2: Custom Directory

**User**: "Create a React dashboard app"

**NAVI**: *Suggests default location*

**User**: "use /Users/username/projects"

**NAVI**: *Creates project in custom directory*

### Example 3: Static HTML Site

**User**: "Create a simple HTML landing page"

**NAVI**: *Detects static HTML project type*

**Result**: Creates index.html, styles.css, script.js with basic structure

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Input                            │
│          "Create a new project called X"                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Chat Endpoint                               │
│  backend/api/chat.py:navi_chat()                            │
│  - Detects project creation patterns                        │
│  - Extracts details using LLM                               │
│  - Returns confirmation prompt                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              User Confirmation                               │
│          "yes" / "create it" / custom path                   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          Project Creation API                                │
│  POST /api/autonomous/create-project                        │
│  - Validates request                                        │
│  - Calls ProjectScaffolder                                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          ProjectScaffolder                                   │
│  backend/services/project_scaffolder.py                     │
│  - Detects project type                                     │
│  - Runs scaffolding commands                                │
│  - Initializes git                                          │
│  - Returns result                                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          Chat Response                                       │
│  - Success message with details                             │
│  - agentRun: { mode: 'project_created', project_path }     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          Frontend Handler                                    │
│  NaviChatPanel.tsx                                          │
│  - Detects project_created mode                             │
│  - Sends openFolder message to extension                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          VSCode Extension                                    │
│  extension.ts                                               │
│  - Receives openFolder message                              │
│  - Executes vscode.openFolder command                       │
│  - Opens new project in new window                          │
└─────────────────────────────────────────────────────────────┘
```

## Project Type Detection

The system uses keyword matching to detect project types:

| Keywords | Detected Type |
|----------|---------------|
| "next.js", "nextjs", "next" | Next.js |
| "react", "react app" | React |
| "react" + "vite" | Vite + React |
| "vue", "vue.js" | Vite + Vue |
| "express", "node server", "api server" | Express.js |
| "python", "fastapi", "flask", "django" | Python |
| "html", "static site", "landing page" | Static HTML |

If no match, creates a generic project with README.

## Error Handling

### 1. Directory Already Exists

```
❌ **Failed to create project**

Directory already exists: /path/to/project

Would you like to try a different location or project name?
```

### 2. Missing Tools

If `npm` is not installed:
```
❌ **Failed to create project**

npx is not available. Please install Node.js and npm.
```

### 3. Command Failure

If scaffolding command fails:
```
❌ **Failed to create project**

Failed to create Next.js project: [error details]

Would you like to try again with different settings?
```

## Configuration

### Default Parent Directory

The system suggests `~/dev` as the default parent directory. This can be customized in the LLM prompt.

### Project Naming

Project names are automatically converted to kebab-case:
- "NAVI Marketing Website" → "navi-marketing-website"
- "My Cool App" → "my-cool-app"

### TypeScript Default

TypeScript is enabled by default for supported project types. Users can request JavaScript explicitly: "Create a JavaScript React app"

## Testing

### Manual Testing

1. **Start the backend**:
   ```bash
   cd /Users/mounikakapa/dev/autonomous-engineering-platform
   ./start_backend_dev.sh
   ```

2. **Open VSCode extension**

3. **Test project creation**:
   ```
   User: "Create a new project called my-test-app"
   Expected: NAVI asks for confirmation with suggested location

   User: "yes"
   Expected: Project created, VSCode opens new window
   ```

### Test Cases

- ✅ Next.js project creation
- ✅ React project creation
- ✅ Static HTML project creation
- ✅ Custom directory specification
- ✅ Directory already exists error
- ✅ Project opens in VSCode
- ✅ Git initialization
- ✅ TypeScript/JavaScript selection

## Future Enhancements

### 1. Template Selection

Allow users to choose from multiple templates:
- Next.js: "blog", "e-commerce", "dashboard", "landing-page"
- React: "admin", "saas", "mobile-first"

### 2. Configuration Wizard

Interactive configuration for:
- ESLint/Prettier setup
- Testing framework (Jest, Vitest, Cypress)
- UI library (Material-UI, Chakra UI, shadcn/ui)
- State management (Redux, Zustand, Jotai)

### 3. Project Customization After Creation

After creating the project, NAVI could:
- Add specific pages ("Add a login page")
- Configure API routes
- Set up authentication
- Add database integration

### 4. Monorepo Support

Support creating projects within monorepos:
- Detect existing monorepo structure
- Use appropriate package manager (npm, yarn, pnpm)
- Configure workspace properly

### 5. Docker Integration

Automatically create Docker configuration:
- Dockerfile
- docker-compose.yml
- .dockerignore

## Known Limitations

1. **Long Installation Time**: npm install can take several minutes
   - Timeout set to 5 minutes
   - User sees "Creating project..." message during this time

2. **VSCode Window Closes**: When opening new project, current NAVI chat closes
   - This is expected VSCode behavior
   - User can re-open NAVI in new project

3. **No Streaming Progress**: During project creation, no real-time progress updates
   - Future: Stream command output to user

4. **Single Project Type**: Cannot create multi-project workspaces in one command
   - Future: "Create a fullstack app with React frontend and Express backend"

## Dependencies

### Backend
- `structlog` - Logging
- `httpx` - HTTP client for API calls
- Node.js and npm - Required for JS project scaffolding
- Git - Required for repository initialization

### Frontend
- VSCode API - For opening folders
- React - UI framework

## Security Considerations

1. **Path Validation**: All paths are validated to prevent directory traversal
2. **Command Injection**: Commands are parameterized, not string-concatenated
3. **Tool Availability**: Checks for required tools before execution
4. **Permission Checks**: Validates write permissions before creating directories

## Conclusion

This feature significantly enhances NAVI's capabilities by allowing users to bootstrap new projects entirely through conversation. No more manual scaffolding, directory creation, or git initialization - NAVI handles it all!

**Status**: ✅ Complete and ready for testing

**Next Steps**:
1. Test with various project types
2. Gather user feedback
3. Iterate on UX (confirmation flow, error messages)
4. Add more project templates

---

*Created: 2026-01-12*
*Last Updated: 2026-01-12*
