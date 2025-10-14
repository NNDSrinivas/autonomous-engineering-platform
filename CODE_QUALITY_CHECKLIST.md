# CODE QUALITY CHECKLIST
## ⚠️ MANDATORY CHECKS BEFORE ANY COMMIT ⚠️

### **IMPORT STANDARDS**
- [ ] No duplicate imports (e.g., `import datetime` + `datetime as dt`)
- [ ] Consistent import aliases (`datetime as dt`, not mixed)
- [ ] No unused imports
- [ ] Proper import grouping (stdlib, third-party, local)
- [ ] No wildcard imports (`from module import *`)

### **TYPE SAFETY**
- [ ] All functions have return type hints (`-> None`, `-> str`, etc.)
- [ ] All parameters have type hints
- [ ] No unsafe slicing operations (`dict.get()[:n]` without type check)
- [ ] Proper None checks before operations
- [ ] Consistent use of `str | None` vs `Optional[str]`

### **CONSTANTS & CONFIGURATION**
- [ ] No magic numbers (replace `8000` with `MAX_LENGTH = 8000`)
- [ ] Configuration constants at top of file
- [ ] Meaningful constant names (`MAX_DESCRIPTION_LENGTH` not `LIMIT`)
- [ ] No hardcoded URLs, ports, or paths in functions

### **ERROR HANDLING**
- [ ] Try-catch blocks around external API calls
- [ ] Proper HTTP error responses (not generic Exception)
- [ ] Logging on error paths
- [ ] Database session cleanup in finally blocks
- [ ] Meaningful error messages

### **DATETIME HANDLING**
- [ ] Use `dt.datetime.now(dt.timezone.utc)` NOT `datetime.utcnow()`
- [ ] Consistent timezone handling
- [ ] Import as `import datetime as dt` for clarity

### **DATABASE PATTERNS**
- [ ] Proper session management (try/finally)
- [ ] No direct string concatenation in queries
- [ ] Use SQLAlchemy select() for queries
- [ ] Proper foreign key relationships
- [ ] Index on frequently queried columns

### **API PATTERNS**
- [ ] Proper HTTP status codes (201 for create, 200 for get, etc.)
- [ ] Request/Response models with Pydantic
- [ ] Error responses with detail messages
- [ ] Consistent endpoint naming (`/api/resource/action`)
- [ ] Proper dependency injection for database sessions

### **TESTING REQUIREMENTS**
- [ ] Tests use TestClient, not live servers
- [ ] Integration tests skip gracefully if services unavailable
- [ ] No hardcoded test data
- [ ] Proper test isolation (no shared state)

### **SECURITY CHECKS**
- [ ] No secrets in code
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention
- [ ] Proper authentication/authorization patterns

## **PRE-COMMIT VALIDATION SCRIPT**
```bash
# Run this before every commit:
python -m py_compile $(find backend -name "*.py")
python -m pytest tests/ -v
python -c "from backend.api.main import app; print('✅ API validates')"
```

## **COMMON MISTAKES TO AVOID**
1. **Reactive Development**: Fix issues systematically, not one-by-one
2. **Import Chaos**: Always check for duplicate/unused imports
3. **Type Blindness**: Add type hints as you write, not after
4. **Magic Numbers**: Extract constants immediately
5. **Error Swallowing**: Always handle errors properly
6. **Test Neglect**: Write tests that work in CI/CD, not just locally

## **ESCALATION RULES**
- If same mistake appears twice → Add automated check
- If PR gets >3 comments → Full codebase audit needed
- If build fails → Stop everything, fix systematically

---
**Remember**: Code quality is not optional. These checks prevent the comment-fix-comment cycle.
