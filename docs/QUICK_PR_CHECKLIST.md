# Quick PR Checklist ⚡

**Print this and keep it visible while coding!**

---

## ✅ Before Every Commit

```bash
# 1. Format & Lint
black backend/ frontend/
ruff check backend/
mypy backend/  # if configured

# 2. Test
pytest tests/
# Manual testing for UI changes

# 3. Check
git diff  # Review your changes
# Remove debug code, print statements
```

---

## 🗄️ Database Code

- [ ] `func.now()` not `"CURRENT_TIMESTAMP"`
- [ ] Import specific types (e.g., `Vector(1536)` not `UserDefinedType()`)
- [ ] All indexes defined for foreign keys
- [ ] Migrations have both `upgrade()` and `downgrade()`

---

## 🔒 Security

- [ ] All inputs validated at API layer (Pydantic)
- [ ] No SQL string interpolation
- [ ] XSS escaping in templates
- [ ] Auth required on sensitive endpoints

---

## 🏗️ FastAPI Patterns

- [ ] Per-request services: `return ServiceClass()`
- [ ] No module-level singletons with mutable state
- [ ] Validate once at API boundary
- [ ] Use `Depends()` for DI

---

## 📝 Code Quality

- [ ] Type hints on all functions
- [ ] Docstrings on public APIs
- [ ] No redundant comments
- [ ] Descriptive variable names
- [ ] Remove unused imports

---

## 🎯 Common Mistakes (from PR #22)

| ❌ Don't | ✅ Do |
|---------|-------|
| `"CURRENT_TIMESTAMP"` | `func.now()` |
| `@lru_cache` for DI | `return ServiceClass()` |
| `UserDefinedType()` | `Vector(EMBED_DIM)` |
| `\s+` (requires space) | `\s*` (optional space) |
| Module singleton | Per-request instance |
| Defensive validation | Trust API validation |

---

## 📄 Before Creating PR

- [ ] Pull latest from `main`
- [ ] All CI checks pass
- [ ] Descriptive commit messages
- [ ] PR description includes What/Why/How
- [ ] Link related issues (`Fixes #123`)

---

## 🚨 Red Flags to Fix Immediately

1. **Raw SQL strings** → Use SQLAlchemy functions
2. **Missing type hints** → Add them
3. **Hardcoded values** → Use environment variables
4. **Global mutable state** → Use per-request instances
5. **No error handling** → Add try-except with proper status codes

---

**Full checklist:** `docs/PR_CHECKLIST.md`  
**Last Updated:** October 27, 2025
