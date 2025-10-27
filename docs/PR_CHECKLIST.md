# Pull Request Submission Checklist

## Purpose
This checklist ensures high-quality PRs with minimal review comments. Use this **before** creating a PR to catch common issues early.

---

## 🔍 Pre-Commit Validation

### Code Quality
- [ ] Run `black` formatter on all Python files
- [ ] Run `ruff` linter and fix all errors
- [ ] Run `mypy` for type checking (if configured)
- [ ] Remove all unused imports and variables
- [ ] Remove all debug print statements and commented-out code

### Testing
- [ ] All existing tests pass
- [ ] New functionality has unit tests
- [ ] Integration tests pass (if applicable)
- [ ] Manual testing completed for UI changes

---

## 🗄️ Database & ORM

### SQLAlchemy Models
- [ ] Use `func.now()` instead of raw SQL strings like `"CURRENT_TIMESTAMP"`
- [ ] Use `server_default=func.now()` and `onupdate=func.now()` for timestamps
- [ ] Use proper type imports (e.g., `Vector(EMBED_DIM)` not `UserDefinedType()`)
- [ ] All columns have appropriate indexes for foreign keys and query patterns
- [ ] Use `Mapped[Type]` type hints for all columns
- [ ] Include meaningful `comment=` parameters for columns

### Migrations (Alembic)
- [ ] Migration has descriptive name and docstring
- [ ] Both `upgrade()` and `downgrade()` functions implemented
- [ ] Import specific types from libraries (e.g., `from pgvector.sqlalchemy import Vector`)
- [ ] Test migration on empty database and with existing data
- [ ] Verify migration works on PostgreSQL, SQLite (if multi-database support needed)

### Database Compatibility
- [ ] Avoid database-specific SQL syntax
- [ ] Use SQLAlchemy functions/types instead of raw SQL
- [ ] Test queries on target database engines
- [ ] Consider performance implications of indexes and foreign keys

---

## 🔒 Security

### Input Validation
- [ ] All user inputs validated at API layer (Pydantic models)
- [ ] Use proper validation rules (`ge=`, `le=`, `max_length=`, etc.)
- [ ] No raw SQL queries with string interpolation (SQL injection risk)
- [ ] Use parameterized queries or ORM methods

### XSS Prevention
- [ ] Escape user-provided content in HTML/templates
- [ ] Sanitize data before rendering in UI
- [ ] Use proper Content-Security-Policy headers

### Authentication & Authorization
- [ ] All sensitive endpoints require authentication
- [ ] Check organization/user permissions before data access
- [ ] No hardcoded credentials or API keys
- [ ] Environment variables for sensitive configuration

---

## 🏗️ Architecture & Patterns

### FastAPI Dependency Injection
- [ ] Use per-request instantiation for stateless services: `return ServiceClass()`
- [ ] Avoid module-level singletons for services with mutable state
- [ ] Use `Depends()` for dependency injection
- [ ] Consider using FastAPI lifespan events for app-level singletons

### Validation Layers
- [ ] API layer validates all inputs (single source of truth)
- [ ] Services trust caller has validated inputs (no redundant validation)
- [ ] Document validation assumptions in docstrings
- [ ] Use constants from `backend/core/constants.py` for limits

### Error Handling
- [ ] Specific exception types for different error cases
- [ ] Proper HTTP status codes (400, 401, 403, 404, 500)
- [ ] User-friendly error messages (no stack traces to users)
- [ ] Log errors with sufficient context for debugging

---

## 📝 Code Style & Documentation

### Comments & Docstrings
- [ ] All public functions have docstrings (Google style)
- [ ] Complex logic has explanatory comments
- [ ] Comments explain "why", not "what" (code should be self-explanatory)
- [ ] Remove misleading or outdated comments
- [ ] Avoid redundant comments that duplicate code

### Naming Conventions
- [ ] Variables: `snake_case`
- [ ] Functions: `snake_case`
- [ ] Classes: `PascalCase`
- [ ] Constants: `UPPER_SNAKE_CASE`
- [ ] Descriptive names (avoid `data`, `temp`, `x`, `y`)

### Type Hints
- [ ] All function parameters have type hints
- [ ] All function return types specified
- [ ] Use `Optional[Type]` for nullable values
- [ ] Use `List[Type]`, `Dict[K, V]` instead of generic `list`, `dict`
- [ ] Import types from `typing` module

---

## 🚀 Performance

### Database Queries
- [ ] Use `.select_related()` or `.joinedload()` to avoid N+1 queries
- [ ] Add indexes for columns used in WHERE, JOIN, ORDER BY clauses
- [ ] Limit query results (pagination, `LIMIT` clause)
- [ ] Avoid fetching unnecessary columns (use `.only()` if needed)

### Caching
- [ ] Cache expensive computations
- [ ] Use appropriate cache invalidation strategy
- [ ] Consider using Redis for distributed caching
- [ ] Document cache key patterns

### API Endpoints
- [ ] Implement pagination for list endpoints
- [ ] Add rate limiting for expensive operations
- [ ] Use background tasks for long-running operations
- [ ] Return minimal data (avoid over-fetching)

---

## 🔧 Configuration

### Environment Variables
- [ ] All configuration in environment variables (not hardcoded)
- [ ] Document new env vars in `.env.example`
- [ ] Provide sensible defaults where appropriate
- [ ] Validate required env vars on startup

### Dependencies
- [ ] New packages added to `requirements.txt`
- [ ] Specify version constraints (`>=`, `==`)
- [ ] Verify package versions are compatible
- [ ] Check for security vulnerabilities in dependencies

---

## 🧪 Testing Strategy

### Unit Tests
- [ ] Test happy path and edge cases
- [ ] Test error conditions and exceptions
- [ ] Mock external dependencies (APIs, databases)
- [ ] Aim for >80% code coverage on new code

### Integration Tests
- [ ] Test API endpoints end-to-end
- [ ] Test database interactions
- [ ] Test authentication/authorization flows
- [ ] Use test fixtures for consistent test data

### Manual Testing
- [ ] Test in development environment
- [ ] Verify UI changes in multiple browsers
- [ ] Test with realistic data volumes
- [ ] Check logs for errors/warnings

---

## 📊 Code Consistency

### Pattern Consistency
- [ ] Follow existing patterns in codebase
- [ ] Use same approach for similar problems
- [ ] Consistent error handling across modules
- [ ] Consistent logging patterns

### File Organization
- [ ] Files in correct directory structure
- [ ] Related code grouped together
- [ ] Imports organized (standard lib → third party → local)
- [ ] No circular dependencies

---

## 📄 Pull Request Description

### PR Title
- [ ] Clear, concise description of change
- [ ] Format: `[Component] Brief description` (e.g., `[API] Add memory graph endpoints`)

### PR Description
- [ ] **What**: What does this PR do?
- [ ] **Why**: Why is this change needed?
- [ ] **How**: How does it work? (high-level approach)
- [ ] **Testing**: How was it tested?
- [ ] **Screenshots**: For UI changes
- [ ] **Breaking Changes**: Document any breaking changes
- [ ] **Migration Notes**: Steps needed to deploy

### Linked Issues
- [ ] Link to related issues/tickets
- [ ] Use `Fixes #123` or `Closes #123` for automatic closing

---

## 🎯 Final Checks

### Before Pushing
- [ ] Review your own code changes
- [ ] Remove debug code and console logs
- [ ] Check for sensitive data (passwords, tokens, PII)
- [ ] Ensure commit messages are descriptive
- [ ] Squash unnecessary commits (optional)

### Before Creating PR
- [ ] Pull latest changes from main branch
- [ ] Resolve merge conflicts
- [ ] Verify all CI checks pass
- [ ] Review file changes in GitHub UI
- [ ] Add appropriate labels/reviewers

---

## 🛠️ Common Issues to Avoid

Based on PR #22 (96 comments addressed), avoid these common mistakes:

### Database Issues
- ❌ Using `"CURRENT_TIMESTAMP"` → ✅ Use `func.now()`
- ❌ Using `sa.types.UserDefinedType()` → ✅ Use specific types like `Vector(EMBED_DIM)`
- ❌ Inconsistent timestamp handling → ✅ Use same pattern everywhere

### Dependency Injection Issues
- ❌ Module-level singletons with mutable state → ✅ Per-request instantiation
- ❌ Using `@lru_cache` for DI → ✅ Standard FastAPI DI patterns
- ❌ Global state management → ✅ Stateless services

### Validation Issues
- ❌ Defensive validation in multiple layers → ✅ Validate at API boundary only
- ❌ Redundant checks in services → ✅ Trust caller has validated
- ❌ Unclear validation boundaries → ✅ Document assumptions

### Type Safety Issues
- ❌ Generic types (`UserDefinedType()`) → ✅ Specific library types (`Vector()`)
- ❌ Missing type hints → ✅ Full type coverage
- ❌ Using `Any` unnecessarily → ✅ Specific types

### Pattern Issues
- ❌ Regex without proper escaping → ✅ Use proper Unicode escapes (`\u0060`)
- ❌ Overly restrictive patterns → ✅ Allow common variations (`\s*` not `\s+`)
- ❌ Redundant conditional logic → ✅ Simplify and consolidate

### Documentation Issues
- ❌ Long, confusing comments → ✅ Concise, clear documentation
- ❌ Comments about "defensive" code → ✅ Document actual contract
- ❌ Missing context for complex logic → ✅ Explain "why"

---

## 📚 Resources

- [SQLAlchemy Best Practices](https://docs.sqlalchemy.org/en/20/orm/queryguide/index.html)
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Pydantic Validation](https://docs.pydantic.dev/latest/concepts/validators/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Security Best Practices](https://owasp.org/www-project-top-ten/)

---

## 🎓 Learning from PR #22

**Stats:** 96 improvements across 23 rounds
**Key Takeaway:** Consistency and proper patterns upfront save significant review time.

**Most Common Issues:**
1. Database compatibility (10+ comments)
2. Type safety (8+ comments)
3. Dependency injection patterns (6+ comments)
4. Validation boundaries (5+ comments)
5. Documentation clarity (10+ comments)

**Prevention:** Use this checklist before every PR submission to catch these issues early.

---

**Last Updated:** October 27, 2025  
**Based on:** PR #22 learnings (Memory Graph & Temporal Reasoning Engine)
