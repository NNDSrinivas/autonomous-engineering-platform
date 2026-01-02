# Node AST Engine

**Production-grade AST transformation engine for JavaScript/TypeScript code refactoring**

## Overview

This is a complete Node.js-based AST transformation engine that provides enterprise-level code refactoring capabilities. Built with TypeScript, Babel, and designed for integration with Python backend services.

## Features

### 🔄 **Core Transforms**
- **Rename Symbol**: Intelligent symbol renaming with scope awareness
- **Update Imports**: Module path updates, import additions/removals  
- **Extract Component**: React component/function extraction to separate files
- **Convert JS→TS**: JavaScript to TypeScript conversion with type inference
- **Remove Dead Code**: Unused code elimination with safety checks

### 🚀 **Enterprise Capabilities** 
- JSON-RPC CLI interface for Python integration
- Comprehensive error handling and validation
- Source map support and line number preservation
- TypeScript-aware transformations
- JSX/TSX support with React patterns

### 🛡️ **Safety & Quality**
- Scope-aware transformations prevent naming conflicts
- Side-effect detection for safe dead code removal
- Import dependency analysis for component extraction
- Comprehensive test coverage and validation

## Architecture

```
node_ast_engine/
├── src/
│   ├── index.ts           # CLI entry point
│   ├── runner.ts          # Transform dispatch system
│   ├── utils/
│   │   ├── parse.ts       # Code parsing with full JS/TS support
│   │   └── emit.ts        # Code generation with formatting
│   └── transforms/
│       ├── renameSymbol.ts
│       ├── updateImport.ts  
│       ├── extractComponent.ts
│       ├── convertJsToTs.ts
│       └── removeDeadCode.ts
├── package.json
├── tsconfig.json
└── dist/                  # Compiled output
```

## Usage

### CLI Interface (for Python integration)

```bash
echo '{"command":"renameSymbol","filePath":"./file.js","code":"...","params":{"oldName":"foo","newName":"bar"}}' | node dist/index.js
```

### Transform Commands

#### Rename Symbol
```json
{
  "command": "renameSymbol",
  "filePath": "./component.tsx",
  "code": "const oldName = () => {...}",
  "params": {
    "oldName": "oldName",
    "newName": "newName",
    "scope": "global"
  }
}
```

#### Update Import
```json
{
  "command": "updateImport", 
  "filePath": "./file.ts",
  "code": "import { old } from 'module'",
  "params": {
    "from": "old-module",
    "to": "new-module",
    "addImports": [{"name": "newExport"}],
    "removeImports": ["oldExport"]
  }
}
```

#### Extract Component
```json
{
  "command": "extractComponent",
  "filePath": "./App.tsx", 
  "code": "function MyComponent() {...}",
  "params": {
    "componentName": "MyComponent",
    "newFileName": "./MyComponent.tsx",
    "exportType": "default"
  }
}
```

#### Convert JS to TS
```json
{
  "command": "convertJsToTs",
  "filePath": "./file.js",
  "code": "function test(a, b) { return a + b; }",
  "params": {
    "addTypeAnnotations": true,
    "convertRequire": true
  }
}
```

#### Remove Dead Code  
```json
{
  "command": "removeDeadCode",
  "filePath": "./file.js", 
  "code": "const unused = 123; function used() {...}"
}
```

## Response Format

```json
{
  "success": true,
  "file": "./updated-file.ts",
  "edits": [
    {
      "start": 0,
      "end": 100,
      "replacement": "new code content"
    }
  ],
  "newFile": "./extracted-component.tsx",
  "newFileContent": "export default function...",
  "metadata": {
    "transformType": "renameSymbol",
    "linesChanged": 5,
    "complexity": 3,
    "timestamp": "2025-12-17T..."
  }
}
```

## Installation & Setup

```bash
# Install dependencies
npm install

# Build TypeScript
npm run build

# Test the engine
echo '{"command":"renameSymbol","filePath":"test.js","code":"const old = 1;","params":{"oldName":"old","newName":"new"}}' | npm start
```

## Integration with Python Backend

The engine is designed to be called from Python services:

```python
import subprocess
import json

def transform_code(command, file_path, code, params=None):
    payload = {
        "command": command,
        "filePath": file_path, 
        "code": code,
        "params": params or {}
    }
    
    process = subprocess.run(
        ["node", "node_ast_engine/dist/index.js"],
        input=json.dumps(payload),
        text=True,
        capture_output=True
    )
    
    return json.loads(process.stdout)
```

## Advanced Features

### Scope-Aware Renaming
The rename transform understands JavaScript scoping rules and prevents conflicts:
- Lexical scope analysis
- Binding vs reference detection  
- Object property vs variable distinction
- Import/export handling

### Smart Import Management
Import transforms handle complex scenarios:
- Relative vs absolute path conversion
- Named vs default import switching
- Batch import additions/removals
- Dependency analysis for extraction

### Safe Dead Code Removal
The dead code elimination includes safety checks:
- Side effect detection
- Export analysis
- Cross-reference validation
- Convention-based preservation (underscore prefixes)

### TypeScript Conversion Intelligence
JS→TS conversion includes basic type inference:
- Literal type detection
- Parameter type inference from usage
- Return type analysis
- Module conversion (require → import)

## Error Handling

The engine provides comprehensive error reporting:
- Parse errors with line/column information
- Transform-specific validation errors
- Timeout protection (30s limit)
- Graceful fallbacks for partial failures

## Performance

Optimized for large codebases:
- Streaming processing capability
- Memory-efficient AST operations
- Incremental transformation support
- Parallel processing ready

## License

MIT License - Built for Autonomous Engineering Platform