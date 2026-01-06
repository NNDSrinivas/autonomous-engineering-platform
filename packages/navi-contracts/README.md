# @aep/navi-contracts

## Overview

The `@aep/navi-contracts` package provides shared contracts and utilities for intent classification across the Autonomous Engineering Platform (AEP). This package serves as the **single source of truth** for intent handling, ensuring consistency between the VS Code extension, webview components, and backend services.

## Purpose

- **Intent Classification**: Standardized intent types and normalization logic
- **Type Safety**: Shared TypeScript types across the platform
- **Consistency**: Single implementation prevents drift between components
- **Testing**: Comprehensive test coverage for intent normalization logic

## Core Components

### IntentKind Enum

Defines the standard intent types supported by the platform:

```typescript
export const IntentKind = {
  FIX_PROBLEMS: "FIX_PROBLEMS",
  ANALYZE_PROJECT: "ANALYZE_PROJECT", 
  DEPLOY: "DEPLOY",
  CLARIFY: "CLARIFY",
  GENERAL_CHAT: "GENERAL_CHAT"
} as const;
```

### normalizeIntentKind Function

Converts user input or raw strings into standardized intent types:

```typescript
import { normalizeIntentKind, IntentKind } from '@aep/navi-contracts';

// Exact matches
normalizeIntentKind('fix_problems') // => IntentKind.FIX_PROBLEMS

// Heuristic mapping
normalizeIntentKind('fix the errors') // => IntentKind.FIX_PROBLEMS
normalizeIntentKind('explain project structure') // => IntentKind.ANALYZE_PROJECT
normalizeIntentKind('deploy to staging') // => IntentKind.DEPLOY
normalizeIntentKind('clarify this function') // => IntentKind.CLARIFY

// Default fallback
normalizeIntentKind('hello there') // => IntentKind.GENERAL_CHAT
```

## Usage Examples

### VS Code Extension

```typescript
import { normalizeIntentKind, IntentKind } from '@aep/navi-contracts';

function handleUserInput(userText: string) {
  const intent = normalizeIntentKind(userText);
  
  if (intent === IntentKind.FIX_PROBLEMS) {
    // Route to diagnostic handling
  } else if (intent === IntentKind.ANALYZE_PROJECT) {
    // Route to project analysis
  }
  // ... handle other intents
}
```

### Backend Services

```typescript
import { normalizeIntentKind, IntentKind } from '@aep/navi-contracts';

export function classifyRequest(userInput: string) {
  return {
    intent: normalizeIntentKind(userInput),
    confidence: calculateConfidence(userInput)
  };
}
```

## Priority System

When multiple keywords could match, the system uses:

1. **Position Priority**: Earlier keywords in the text take precedence
2. **Length Priority**: Longer/more specific phrases beat shorter ones at the same position
3. **Phrase Priority**: Multi-word phrases are checked before single words

Example:
```typescript
normalizeIntentKind('fix and deploy') // => FIX_PROBLEMS ('fix' appears first)
normalizeIntentKind('explain project details') // => ANALYZE_PROJECT ('explain project' beats 'explain')
```

## Development

```bash
# Install dependencies
npm install

# Run tests
npm test

# Build the package  
npm run build

# Watch mode for tests
npm run test:watch
```

## Testing

The package includes comprehensive tests covering:
- Exact intent matches
- Heuristic keyword mapping
- Edge cases (null, undefined, empty strings)
- Priority handling for overlapping keywords
- Case sensitivity handling

Run tests with: `npm test`