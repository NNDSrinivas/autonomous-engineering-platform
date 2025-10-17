# PR-9: Model Router + Real Plan Mode

## Overview
This PR extends the AEP backend (FastAPI) and agent-core to add **Plan Mode** using real LLM calls, routing, caching, telemetry, and cost budgets.

## Features Implemented

### 1. LLM Model Router (`backend/llm/router.py`)
- **Multi-provider support**: OpenAI and Anthropic integration
- **YAML-based configuration**: Flexible routing rules in `config/model-router.yaml`
- **Budget management**: Token and cost limits per route
- **Fallback handling**: Automatic fallback to secondary models
- **Usage tracking**: Real-time statistics and telemetry
- **Cost calculation**: Accurate pricing models for each provider

### 2. Provider Classes
- **OpenAI Provider** (`backend/llm/providers/openai_provider.py`)
  - GPT-4, GPT-3.5 support
  - Input/output token tracking
  - Cost calculation based on current pricing
  - Error handling and retries

- **Anthropic Provider** (`backend/llm/providers/anthropic_provider.py`)
  - Claude-3.5 support
  - Input/output token tracking
  - Cost calculation based on current pricing
  - Error handling and retries

### 3. Plan API Endpoint (`backend/api/plan.py`)
- **POST /api/plan/{key}**: Generate LLM-powered plans
- **GET /api/plan/metrics**: Usage statistics and budget status
- **Caching**: Redis-based caching with TTL
- **Error handling**: Graceful fallbacks for LLM failures
- **Telemetry**: Performance and usage metrics

### 4. Agent-Core TypeScript Client
- **Router module** (`agent-core/src/router.ts`): TypeScript client for plan API
- **Cache module** (`agent-core/src/cache.ts`): Client-side caching with TTL
- **Telemetry module** (`agent-core/src/telemetry.ts`): Metrics collection
- **Type definitions**: Strong typing for Plan API responses

### 5. VS Code Extension Integration
- **New command**: "AEP: Generate Plan (LLM)"
- **Progress indicators**: User feedback during LLM calls
- **Error handling**: User-friendly error messages
- **Integration**: Uses agent-core modules for API communication

### 6. Configuration
- **Model Router Config** (`config/model-router.yaml`):
  ```yaml
  routes:
    plan: claude-3-5    # Plan generation uses Claude
    code: gpt-4.1       # Code generation uses GPT-4
  
  budgets:
    daily_tokens: 120000
    daily_cost: 50.0
  
  fallbacks:
    claude-3-5: gpt-4.1
    gpt-4.1: gpt-3.5
  ```

## API Examples

### Generate Plan
```bash
POST /api/plan/TICKET-123
{
  "contextPack": {
    "ticket": {
      "title": "Add user authentication",
      "description": "Implement JWT-based auth system"
    },
    "files": [...]
  }
}
```

### Response
```json
{
  "plan": {
    "items": [
      {
        "id": "auth-1",
        "kind": "edit",
        "desc": "Create JWT service",
        "files": ["backend/auth/jwt.py"]
      }
    ]
  },
  "telemetry": {
    "model": "claude-3-5-sonnet",
    "tokens": 1250,
    "cost": 0.0375,
    "duration": 2.3
  }
}
```

### Usage Metrics
```bash
GET /api/plan/metrics
```

```json
{
  "usage": {
    "total_calls": 42,
    "total_tokens": 125000,
    "total_cost": 15.75
  },
  "budget": {
    "daily_tokens_remaining": 95000,
    "daily_cost_remaining": 34.25,
    "within_limits": true
  }
}
```

## VS Code Integration

Users can now run `Cmd+Shift+P` → "AEP: Generate Plan (LLM)" to:
1. Analyze current workspace context
2. Send to LLM via the plan API
3. Display the generated plan with progress indicators
4. Handle errors gracefully with user feedback

## Dependencies Added
- `openai>=1.0.0` - OpenAI API client
- `anthropic>=0.25.0` - Anthropic API client
- `pyyaml>=6.0` - YAML configuration parsing
- `redis==5.0.8` - Caching backend
- `prometheus-client==0.20.0` - Metrics collection

## Architecture Benefits

1. **Extensible**: Easy to add new LLM providers
2. **Cost-aware**: Built-in budget management and tracking
3. **Reliable**: Fallback mechanisms and error handling
4. **Performant**: Caching reduces redundant LLM calls
5. **Observable**: Comprehensive telemetry and metrics
6. **Configurable**: YAML-based configuration for easy updates

## Next Steps

- Add support for more LLM providers (Cohere, Local models)
- Implement streaming responses for real-time feedback
- Add A/B testing capabilities for different models
- Enhance prompt engineering with few-shot examples
- Add plan validation and quality scoring

## Testing

All components have been tested for:
- ✅ TypeScript compilation (agent-core, VS Code extension)
- ✅ Python import validation (backend modules)
- ✅ Configuration file parsing
- ✅ Error handling paths
- ✅ Integration between components

Ready for integration testing with live API keys.