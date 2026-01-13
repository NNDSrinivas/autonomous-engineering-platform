# ContextService Integration Guide

## Overview

The ContextService provides comprehensive workspace analysis and context gathering for AEP NAVI. It automatically indexes your workspace, detects technologies, tracks file relationships, and provides rich context for AI-powered operations.

## Features

### 1. **Automatic Workspace Indexing**
- Scans all files on extension activation
- Excludes common patterns (node_modules, dist, build, .git, etc.)
- Real-time file watching with debounced re-indexing
- Caches results for fast access

### 2. **Technology Detection**
Automatically identifies:
- **Frontend**: React, Vue, Angular
- **Backend**: Node.js, Python, Java, Go, Rust
- **Infrastructure**: Docker, Kubernetes
- **Languages**: TypeScript, JavaScript, and more

### 3. **Import Analysis**
- Extracts imports from JavaScript/TypeScript files
- Parses Python import statements
- Tracks dependency relationships

### 4. **File Relationships**
- Finds related test files
- Locates files with same name but different extensions
- Tracks import dependencies

### 5. **Code Search**
- Fast in-memory search across workspace
- Returns top matches with line numbers
- Limits results to prevent slowdown

## Usage

### From Extension Code

The ContextService is automatically initialized when the extension activates. It's available globally as `globalContextService`.

#### Get Workspace Context

```typescript
const workspaceContext = await globalContextService.getWorkspaceContext();

console.log('Technologies:', workspaceContext.technologies);
// Output: ['React', 'TypeScript', 'Node.js', 'Python']

console.log('Total Files:', workspaceContext.totalFiles);
// Output: 1523

console.log('Git Branch:', workspaceContext.gitBranch);
// Output: 'migration/pr-4-webview-shell'
```

#### Get Editor Context

```typescript
const editor = vscode.window.activeTextEditor;
if (editor) {
  const editorContext = await globalContextService.getEditorContext(editor);

  console.log('Current File:', editorContext.currentFile);
  console.log('Language:', editorContext.language);
  console.log('Imports:', editorContext.imports);
  console.log('Related Files:', editorContext.relatedFiles);
}
```

#### Search Code

```typescript
const results = await globalContextService.searchCode('authentication');

results.forEach(result => {
  console.log(`File: ${result.file}`);
  result.matches.forEach(match => {
    console.log(`  Line ${match.line}: ${match.text}`);
  });
});
```

#### Get File Tree

```typescript
const fileTree = await globalContextService.getFileTree();

function printTree(nodes: FileNode[], indent = 0) {
  nodes.forEach(node => {
    console.log(' '.repeat(indent) + node.name);
    if (node.children) {
      printTree(node.children, indent + 2);
    }
  });
}

printTree(fileTree);
```

### From Webview

The webview can request workspace context using the `requestWorkspaceContext` message:

```typescript
// In your React component
window.vscode?.postMessage({ type: 'requestWorkspaceContext' });

// Listen for response
useEffect(() => {
  const handler = (event: MessageEvent) => {
    const message = event.data;
    if (message.type === 'workspaceContext') {
      console.log('Workspace Root:', message.workspaceRoot);
      console.log('Technologies:', message.workspaceContext.technologies);
      console.log('Total Files:', message.workspaceContext.totalFiles);
      console.log('Editor Context:', message.workspaceContext.editorContext);
    }
  };

  window.addEventListener('message', handler);
  return () => window.removeEventListener('message', handler);
}, []);
```

### Enhanced NAVI Client API

The webview now has access to comprehensive code generation APIs through `NaviAPIClient`:

```typescript
import { naviClient } from '@/api/navi/client';

// Generate code from prompt
const result = await naviClient.generateCode({
  prompt: 'Create a user authentication function',
  context: workspaceContext,
  language: 'typescript'
});
console.log(result.code);
console.log(result.explanation);

// Explain code
const explanation = await naviClient.explainCode(selectedCode);

// Refactor code
const refactored = await naviClient.refactorCode({
  code: selectedCode,
  context: editorContext,
  language: 'typescript'
});

// Generate tests
const tests = await naviClient.generateTests({
  code: fileContent,
  language: 'typescript',
  filePath: '/path/to/file.ts'
});

// Fix bugs
const fixed = await naviClient.fixBug({
  code: fileContent,
  diagnostics: vscodeDiagnostics,
  context: editorContext
});

// Get inline completion (Copilot-style)
const completion = await naviClient.getInlineCompletion({
  prefix: textBeforeCursor,
  suffix: textAfterCursor,
  language: 'typescript',
  context: editorContext
});

// Search organizational memory
const memoryResults = await naviClient.searchMemory('authentication patterns', 10);

// Get task context from JIRA
const taskContext = await naviClient.getTaskContext('PROJ-123');

// Create pull request
const pr = await naviClient.createPR({
  title: 'Add authentication feature',
  changes: gitChanges,
  context: workspaceContext
});
console.log('PR URL:', pr.url);
```

## API Reference

### ContextService Methods

#### `indexWorkspace(): Promise<void>`
Indexes the entire workspace. Called automatically on activation.

#### `getWorkspaceContext(): Promise<WorkspaceContext>`
Returns comprehensive workspace information:
```typescript
interface WorkspaceContext {
  rootPath: string;
  fileTree: FileNode[];
  packageJson?: any;
  readme?: string;
  gitBranch?: string;
  technologies: string[];
  totalFiles: number;
  totalSize: number;
}
```

#### `getEditorContext(editor: TextEditor): Promise<EditorContext>`
Returns context for the current editor:
```typescript
interface EditorContext {
  currentFile: string;
  language: string;
  selection?: {
    text: string;
    range: { start: Position; end: Position };
  };
  surroundingCode: {
    before: string;
    after: string;
  };
  imports: string[];
  dependencies: string[];
  relatedFiles: string[];
}
```

#### `searchCode(query: string): Promise<SearchResult[]>`
Searches code across workspace:
```typescript
interface SearchResult {
  file: string;
  matches: Array<{
    line: number;
    text: string;
  }>;
}
```

#### `getFileTree(): Promise<FileNode[]>`
Returns hierarchical file structure:
```typescript
interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: FileNode[];
  language?: string;
  size?: number;
}
```

#### `getDependenciesForFile(filePath: string): Promise<string[]>`
Gets imports for a specific file.

### NaviAPIClient Methods

#### Code Generation
- `generateCode(request)` - Generate code from natural language
- `explainCode(code)` - Explain code snippets
- `refactorCode(request)` - Intelligent refactoring
- `generateTests(request)` - Framework-aware test generation
- `fixBug(request)` - Diagnostic-based bug fixing
- `getInlineCompletion(request)` - Fast inline completions

#### Git & PR
- `createPR(request)` - Automated PR creation
- `reviewChanges(request)` - Code review automation

#### Memory & Context
- `searchMemory(query, k)` - Search organizational knowledge
- `getTaskContext(taskKey)` - Get full task context

#### Planning & Execution
- `getTasks()` - List JIRA tasks
- `createPlan(request)` - Generate implementation plans
- `executePlan(planId)` - Execute autonomous coding plans

## Configuration

The ContextService uses the following VS Code settings:

```json
{
  "aep.navi.backendUrl": "http://127.0.0.1:8787",
  "aep.navi.orgId": "default",
  "aep.navi.userId": "default_user"
}
```

## Performance Considerations

### File Watching
- Debounced re-indexing (2 second delay)
- Automatically updates on file changes
- Minimal performance impact

### Search Limits
- Maximum 100 files searched per query
- Maximum 5 matches per file
- Maximum 20 files returned

### File Tree Depth
- Default max depth: 3 levels
- Configurable in code if needed

### Caching
- All index data cached in memory
- Fast subsequent access
- Cleared on workspace change

## Console Output

The ContextService logs important events to the console:

```
[AEP] Workspace indexing completed
Indexed 1523 files with technologies: React, TypeScript, Node.js, Python
```

If indexing fails:
```
[AEP] Workspace indexing failed: <error details>
```

Enhanced context failures (non-critical):
```
[AEP] Failed to get enhanced context: <error details>
```

## Troubleshooting

### Indexing Takes Too Long
- Large workspaces (>10k files) may take 10-30 seconds
- Consider adding more ignore patterns if needed
- Indexing happens asynchronously and won't block the UI

### Technologies Not Detected
- Ensure you have the indicator files (package.json, tsconfig.json, etc.)
- Check console for indexing completion message
- Try reloading the window

### Context Not Available in Webview
- Ensure you send `requestWorkspaceContext` message
- Wait for indexing to complete
- Check browser console for errors

### Memory Usage
- ContextService keeps index in memory
- Large workspaces may use 50-100MB
- Index is cleared when extension deactivates

## Examples

### Example 1: Get Project Technologies
```typescript
const context = await globalContextService.getWorkspaceContext();
console.log(`This project uses: ${context.technologies.join(', ')}`);
// Output: This project uses: React, TypeScript, Python, Docker
```

### Example 2: Find All Test Files
```typescript
const results = await globalContextService.searchCode('.test.');
const testFiles = results.map(r => r.file);
console.log('Test files:', testFiles);
```

### Example 3: Get Related Files
```typescript
const editor = vscode.window.activeTextEditor;
if (editor) {
  const context = await globalContextService.getEditorContext(editor);
  console.log('Related files:', context.relatedFiles);
  // Output: ['Button.tsx', 'Button.test.tsx', 'Button.css']
}
```

### Example 4: Generate Context-Aware Code
```typescript
const workspaceCtx = await globalContextService.getWorkspaceContext();
const editorCtx = editor ? await globalContextService.getEditorContext(editor) : null;

const result = await naviClient.generateCode({
  prompt: 'Add error handling',
  context: {
    workspace: workspaceCtx,
    editor: editorCtx
  },
  language: editorCtx?.language || 'typescript'
});

console.log('Generated code:', result.code);
console.log('Explanation:', result.explanation);
```

## Integration Checklist

- [x] ContextService created
- [x] NaviClient created for extension
- [x] NaviAPIClient enhanced in webview
- [x] Auto-indexing on activation
- [x] Enhanced collectWorkspaceContext()
- [x] Type safety improvements (NaviState)
- [x] CSS class name fixes
- [x] Documentation complete

## Next Steps

1. **Backend Implementation**: Implement the `/api/code/*` endpoints
2. **Inline Completions**: Add InlineCompletionProvider
3. **Autonomous Coding**: Implement planning and execution
4. **Testing**: Test all ContextService features
5. **Performance**: Profile and optimize for large workspaces

## Support

For issues or questions:
- Check console logs for errors
- Verify backend is running at configured URL
- Ensure workspace is a valid git repository
- Review this guide for proper usage
