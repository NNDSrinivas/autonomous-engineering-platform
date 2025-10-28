#!/bin/bash
# Pre-push validation script to catch common review issues
# Run: ./scripts/pre-push-check.sh

set -e

echo "🔍 Running pre-push validation checks..."
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track failures
FAILED=0

# 1. Format check
echo "📝 Checking code formatting..."
if black --check backend/ tests/ 2>/dev/null; then
    echo -e "${GREEN}✓ Python formatting OK${NC}"
else
    echo -e "${YELLOW}⚠ Python formatting issues - run: black backend/ tests/${NC}"
    FAILED=1
fi

# 2. Linting
echo ""
echo "🔎 Running linters..."
if ruff check backend/ tests/ 2>/dev/null; then
    echo -e "${GREEN}✓ Python linting passed${NC}"
else
    echo -e "${RED}✗ Python linting failed${NC}"
    FAILED=1
fi

# 3. Check for common anti-patterns
echo ""
echo "🚨 Checking for common anti-patterns..."

# Check for bare except
if grep -rn "except.*:$" backend/ tests/ --include="*.py" | grep -v "except.*Error" | grep -v "#"; then
    echo -e "${YELLOW}⚠ Found bare except clauses - consider catching specific exceptions${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ No bare except clauses${NC}"
fi

# Check for list in membership checks in hot paths
if grep -rn "if .* in \[" backend/api/ --include="*.py"; then
    echo -e "${YELLOW}⚠ Found list membership checks - consider using sets for O(1) lookup${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ No list membership checks in API code${NC}"
fi

# 4. Run quick tests
echo ""
echo "🧪 Running quick tests..."
if pytest tests/ -x -q 2>/dev/null; then
    echo -e "${GREEN}✓ Tests passed${NC}"
else
    echo -e "${RED}✗ Tests failed${NC}"
    FAILED=1
fi

# Summary
echo ""
echo "=================================="
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed! Safe to push.${NC}"
    exit 0
else
    echo -e "${RED}❌ Some checks failed. Please fix before pushing.${NC}"
    echo ""
    echo "Quick fixes:"
    echo "  - Format: black backend/ tests/"
    echo "  - Lint: ruff check backend/ tests/ --fix"
    echo "  - Review: .github/pr-checklist.md"
    exit 1
fi
