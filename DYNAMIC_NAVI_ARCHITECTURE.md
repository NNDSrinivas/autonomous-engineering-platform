# Dynamic NAVI Architecture - Eliminating Hardcoded Patterns

## Overview

This document outlines the transition from hardcoded NAVI features to a dynamic, plugin-based architecture across the entire stack.

## Problem Statement

NAVI currently has hardcoded patterns throughout the codebase:
- **Action types**: Hardcoded if/else chains for routing actions
- **Intent patterns**: Hardcoded regex for natural language understanding
- **Framework detection**: Hardcoded lists of frameworks and their signatures
- **Package managers**: Hardcoded detection and command generation
- **Code generators**: Hardcoded mappings between project types and generators
- **Technology detection**: Hardcoded indicators for tech stack identification

**Impact**: Adding new capabilities requires code changes, recompilation, and redeployment. No extensibility without modifying core code.

## Solution: Plugin-Based Registry System

### Core Principle
> **Capabilities are discovered, not hardcoded**

Instead of:
```typescript
if (action.type === 'createFile') { ... }
else if (action.type === 'editFile') { ... }
else if (action.type === 'runCommand') { ... }
```

Do this:
```typescript
const handler = registry.findHandler(action);
await handler.execute(action);
```

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Registry System                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Handler registers capabilities                    │  │
│  │  2. Action arrives                                    │  │
│  │  3. Registry finds handler by capability match       │  │
│  │  4. Handler executes action                          │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Status

### ✅ COMPLETED: VS Code Extension Action Handling

**Files**:
- `extensions/vscode-aep/src/actions/ActionRegistry.ts`
- `extensions/vscode-aep/src/actions/handlers/*.ts`
- `extensions/vscode-aep/src/extension.ts`

**Commit**: bfbd3900

**What was changed**:
1. Created `ActionRegistry` with plugin-based handler system
2. Implemented 4 handlers:
   - `FileActionHandler`: Handles actions with `filePath` + `content`
   - `CommandActionHandler`: Handles actions with `command` field
   - `NotificationActionHandler`: Handles actions with `message`/`notification`
   - `NavigationActionHandler`: Handles actions with `url`/`path`/`folder`

3. Integrated registry into extension:
   - Initialize on activation
   - Use in `handleAgentApplyAction()`
   - Use in `applyWorkspacePlan()`
   - Keep legacy handlers as fallback

**Benefits**:
- ✅ No more hardcoded action types
- ✅ Actions self-describe their capabilities
- ✅ Easy to add new handlers
- ✅ Backward compatible

### 🔄 IN PROGRESS: Backend Architecture

#### Identified Hardcoded Patterns

| Component | File | Lines | Pattern | Priority |
|-----------|------|-------|---------|----------|
| Action Routing | navi_engine.py | 547-565 | Dict of handlers | HIGH |
| Intent Classification | navi_engine.py | 172-219 | Regex patterns | HIGH |
| Framework Detection (Node.js) | navi_engine.py | 87-118 | If/elif chain | HIGH |
| Framework Detection (Python) | navi_engine.py | 129-139 | If/elif chain | HIGH |
| Package Manager Detection | navi_engine.py | 462-477 | If chain | MEDIUM |
| Package Manager Commands | navi_engine.py | 481-489 | Dict | MEDIUM |
| Component Generators | navi_engine.py | 606-612 | If/elif | MEDIUM |
| Page Generators | navi_engine.py | 620-625 | If | MEDIUM |
| API Generators | navi_engine.py | 629-637 | If/elif | MEDIUM |
| Feature Keywords | navi_engine.py | 750-762 | Hardcoded lists | LOW |
| Technology Indicators | ContextService.ts | 354-367 | Dict | LOW |
| Language Mapping | ContextService.ts | 507-524 | Dict | LOW |

### 🎯 NEXT STEPS

#### Phase 1: Backend Action Registry (Priority: HIGH)
**Goal**: Make action handling dynamic in backend

**Approach**:
```python
# backend/core/action_registry.py
class ActionRegistry:
    def register(self, handler: ActionHandler):
        self.handlers.append(handler)

    def execute(self, action: dict) -> ActionResult:
        handler = self.find_handler(action)
        return handler.execute(action)

class ActionHandler(ABC):
    @abstractmethod
    def can_handle(self, action: dict) -> bool:
        pass

    @abstractmethod
    def execute(self, action: dict) -> ActionResult:
        pass
```

**Tasks**:
- [ ] Create `ActionRegistry` class
- [ ] Create `ActionHandler` interface
- [ ] Implement handlers for each action type
- [ ] Refactor `navi_engine.py` to use registry
- [ ] Update API routers to use registry

#### Phase 2: Intent Pattern Configuration (Priority: HIGH)
**Goal**: Move intent patterns from code to configuration

**Approach**:
```yaml
# config/intent_patterns.yaml
patterns:
  - regex: "open\\s+(.+?)(?:\\s+project)?$"
    action: "open_project"
    confidence: 0.9

  - regex: "(?:create|make|add|new)\\s+(?:a\\s+)?(?:new\\s+)?component"
    action: "create_component"
    confidence: 0.95
```

**Tasks**:
- [ ] Create YAML schema for intent patterns
- [ ] Create pattern loader
- [ ] Refactor `IntentParser` to use loaded patterns
- [ ] Add multi-language pattern support
- [ ] Create pattern validation

#### Phase 3: Framework Detection Registry (Priority: HIGH)
**Goal**: Make framework detection pluggable

**Approach**:
```yaml
# config/frameworks.yaml
frameworks:
  - name: "nextjs"
    type: "nodejs"
    indicators:
      dependencies: ["next"]
      files: ["next.config.js", "pages/"]
    technologies: ["Next.js", "React"]

  - name: "fastapi"
    type: "python"
    indicators:
      imports: ["fastapi"]
      files: ["main.py"]
    technologies: ["FastAPI"]
```

**Tasks**:
- [ ] Create framework registry
- [ ] Create framework detector interface
- [ ] Load framework definitions from config
- [ ] Refactor `ProjectDetector` to use registry

#### Phase 4: Package Manager Registry (Priority: MEDIUM)
**Goal**: Make package managers configurable

**Approach**:
```yaml
# config/package_managers.yaml
package_managers:
  - name: "npm"
    lock_files: ["package-lock.json", "package.json"]
    install_command: ["npm", "install"]
    add_command: ["npm", "install", "{package}"]
    add_dev_command: ["npm", "install", "--save-dev", "{package}"]

  - name: "yarn"
    lock_files: ["yarn.lock"]
    install_command: ["yarn", "install"]
    add_command: ["yarn", "add", "{package}"]
    add_dev_command: ["yarn", "add", "-D", "{package}"]
```

**Tasks**:
- [ ] Create package manager registry
- [ ] Create PM configuration loader
- [ ] Refactor PM detection to use registry
- [ ] Refactor command generation to use registry

#### Phase 5: Code Generator Registry (Priority: MEDIUM)
**Goal**: Make code generation pluggable

**Approach**:
```python
class GeneratorRegistry:
    def register(self, project_type: str, generator: CodeGenerator):
        self.generators[project_type] = generator

    def get_generator(self, project_type: str) -> CodeGenerator:
        return self.generators.get(project_type, self.default_generator)

# Register generators
registry.register("react", ReactGenerator())
registry.register("vue", VueGenerator())
registry.register("fastapi", FastAPIGenerator())
```

**Tasks**:
- [ ] Create generator registry
- [ ] Create generator interface
- [ ] Extract existing generators to separate classes
- [ ] Refactor to use registry

## Benefits of Dynamic Architecture

### For Development
- ✅ Add new capabilities without touching core code
- ✅ Test handlers in isolation
- ✅ Easy to mock for testing
- ✅ Clear separation of concerns

### For Users
- ✅ Extend NAVI with custom actions
- ✅ Add custom frameworks/languages
- ✅ Configure intent patterns for their domain
- ✅ No need to wait for official support

### For Deployment
- ✅ Hot-reload new capabilities
- ✅ A/B test different implementations
- ✅ Feature flags at handler level
- ✅ Gradual rollout of new features

## Migration Strategy

### 1. Parallel Implementation
- Keep existing hardcoded logic
- Add registry alongside
- Route through registry first, fallback to legacy

### 2. Gradual Migration
- Migrate high-traffic actions first
- Monitor performance and behavior
- Migrate remaining actions

### 3. Legacy Removal
- Mark legacy code as deprecated
- Remove once registry is stable
- Clean up technical debt

## Configuration Management

### Structure
```
config/
├── actions/
│   ├── file_operations.yaml
│   ├── git_operations.yaml
│   └── code_generation.yaml
├── intents/
│   ├── english.yaml
│   ├── spanish.yaml
│   └── custom.yaml
├── frameworks/
│   ├── javascript.yaml
│   ├── python.yaml
│   └── go.yaml
└── package_managers/
    └── definitions.yaml
```

### Hot Reload
- Watch configuration files
- Reload changed configs
- No restart required
- Validate before applying

## Testing Strategy

### Unit Tests
- Test each handler in isolation
- Test registry routing logic
- Test configuration loading

### Integration Tests
- Test full action execution flow
- Test fallback to legacy handlers
- Test configuration hot-reload

### E2E Tests
- Test user workflows
- Test backward compatibility
- Test performance

## Performance Considerations

### Registry Lookup
- Use hash maps for O(1) lookup
- Cache handler selection
- Profile hot paths

### Configuration Loading
- Load configs once at startup
- Cache parsed configurations
- Lazy load when needed

### Memory Usage
- Limit number of registered handlers
- Unregister unused handlers
- Monitor memory footprint

## Security Considerations

### Handler Validation
- Validate handler capabilities
- Sanitize action inputs
- Rate limit handler execution

### Configuration Security
- Validate config schema
- Restrict config file permissions
- Audit config changes

## Monitoring & Observability

### Metrics
- Handler execution time
- Handler success/failure rates
- Registry lookup performance
- Configuration reload frequency

### Logging
- Log handler selection
- Log action execution
- Log fallback to legacy
- Log configuration changes

## Documentation

### For Developers
- How to create a handler
- How to register capabilities
- How to test handlers
- How to contribute handlers

### For Users
- How to configure intents
- How to add custom frameworks
- How to extend NAVI
- Configuration reference

## Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| VS Code Extension | 1 day | ✅ Complete |
| Backend Action Registry | 2 days | 🔄 Next |
| Intent Configuration | 1 day | ⏳ Pending |
| Framework Registry | 1 day | ⏳ Pending |
| Package Manager Registry | 0.5 day | ⏳ Pending |
| Code Generator Registry | 1 day | ⏳ Pending |
| Testing & Documentation | 1 day | ⏳ Pending |

**Total Estimated Time**: 7.5 days

## Conclusion

The dynamic architecture eliminates hardcoded patterns across NAVI, making it:
- **Extensible**: Add capabilities without code changes
- **Flexible**: Configure for different domains
- **Maintainable**: Clear separation of concerns
- **Testable**: Isolated, mockable components
- **Scalable**: Hot-reload, A/B testing, feature flags

This transformation enables NAVI to grow organically as users add their own capabilities, frameworks, and domain-specific patterns.

---

**Status**: Phase 1 Complete (VS Code Extension) ✅
**Next**: Phase 2 (Backend Action Registry) 🎯
**Updated**: 2026-01-13
