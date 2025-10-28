# PR Self-Review Checklist

Before pushing code, run through this checklist to catch common review comments:

## Performance
- [ ] Use `set` instead of `list` for membership checks (`if x in collection`)
- [ ] Use `Map` instead of `Set + filter` for deduplication in React
- [ ] Avoid O(n) operations in frequently-called code paths
- [ ] Check `useMemo` dependencies are correct and necessary

## Error Handling
- [ ] No bare `except Exception: pass` - always log errors
- [ ] Catch specific exceptions (e.g., `QueueFull`, `ValueError`)
- [ ] Include `exc_info=True` in error logs for tracebacks
- [ ] Add context to error messages (IDs, params)

## Type Safety (TypeScript/Python)
- [ ] Optional fields marked with `?` in TS interfaces
- [ ] Type guards for runtime validation (SSE messages, API responses)
- [ ] No `any` types without justification
- [ ] Consistent null/undefined handling

## Comments & Documentation
- [ ] Explain *why*, not *what* (code shows what)
- [ ] Document race conditions, edge cases, limitations
- [ ] Update comments when changing logic
- [ ] Remove misleading or outdated comments

## Code Quality
- [ ] No unused imports or variables
- [ ] Consistent naming (camelCase for TS, snake_case for Python)
- [ ] Extract complex logic into named functions
- [ ] Avoid deep nesting (early returns, guard clauses)

## Pre-Push Commands
```bash
# Format
black backend/ tests/
prettier --write frontend/src/

# Lint
ruff check backend/ tests/
npm run lint --prefix frontend

# Type check
npm run type-check --prefix frontend

# Run tests
pytest tests/ -v
npm test --prefix frontend
```

## Common Pitfalls in This Codebase

### Backend (Python/FastAPI)
- JSON array mutations have race conditions - add warnings
- Use exponential thresholds (powers of 2) for log warnings
- Always use sets for threshold checks, not lists
- Log queue failures, don't silently swallow them

### Frontend (React/TypeScript)
- Deduplication: Use Map, not double Sets
- Type guards for SSE/API data validation
- Mark optional fields as optional in interfaces
- Consider performance for 100+ items in lists

### Database
- Document JSON column structures with types (uuid, ISO8601)
- Index frequently-queried columns
- Handle missing foreign key references gracefully

## AI Review Prompts

If using Copilot or AI review, ask it to focus on:
1. Performance bottlenecks (O(n²), unnecessary re-renders)
2. Error handling completeness
3. Race conditions in concurrent code
4. Type safety gaps
