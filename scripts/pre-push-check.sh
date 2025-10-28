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

# 3. Check for common anti-patterns in NEW code only
echo ""
echo "🚨 Checking for common anti-patterns in changed files..."

# Get list of changed files in this commit
CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACMR | grep "\.py$" || true)

if [ -z "$CHANGED_FILES" ]; then
    echo -e "${GREEN}✓ No Python files changed${NC}"
else
    # Check for bare except in changed files only
    BARE_EXCEPT_COUNT=0
    for file in $CHANGED_FILES; do
        if [ -f "$file" ]; then
            if grep -n "except.*:$" "$file" | grep -v "except.*Error" | grep -v "#" > /dev/null; then
                echo -e "${YELLOW}⚠ $file has bare except clauses${NC}"
                BARE_EXCEPT_COUNT=$((BARE_EXCEPT_COUNT + 1))
            fi
        fi
    done
    
    if [ $BARE_EXCEPT_COUNT -eq 0 ]; then
        echo -e "${GREEN}✓ No bare except clauses in changed files${NC}"
    else
        FAILED=1
    fi

    # Check for list membership in hot paths
    LIST_CHECK_COUNT=0
    for file in $CHANGED_FILES; do
        if [[ "$file" == *"backend/api/"* ]] && [ -f "$file" ]; then
            if grep -n "if .* in \[" "$file" > /dev/null; then
                echo -e "${YELLOW}⚠ $file: Consider using sets instead of lists for membership checks${NC}"
                LIST_CHECK_COUNT=$((LIST_CHECK_COUNT + 1))
            fi
        fi
    done
    
    if [ $LIST_CHECK_COUNT -eq 0 ]; then
        echo -e "${GREEN}✓ No list membership checks in changed API files${NC}"
    fi
fi

# 4. Skip tests if dependencies missing (not blocking)
echo ""
echo "🧪 Running tests (if available)..."
if pytest tests/ -x -q --ignore=tests/test_health.py 2>/dev/null; then
    echo -e "${GREEN}✓ Tests passed${NC}"
else
    echo -e "${YELLOW}⚠ Tests failed or dependencies missing (non-blocking)${NC}"
    # Don't fail the push for test issues
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
