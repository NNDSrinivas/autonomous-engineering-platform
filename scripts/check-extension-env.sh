#!/bin/bash

# AEP Extension Development Environment Verification Script
# This script checks that the development environment is properly configured

echo "🔍 AEP Extension Development Environment Check"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
ISSUES=0
SUCCESS=0

# Function to check status
check_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}: $2"
        ((SUCCESS++))
    else
        echo -e "${RED}❌ FAIL${NC}: $2"
        ((ISSUES++))
    fi
}

check_warning() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
}

check_info() {
    echo -e "${BLUE}ℹ️  INFO${NC}: $1"
}

echo ""
echo "1. Checking Extension Directory Structure..."

# Check if aep-professional exists and has package.json
if [ -f "extensions/aep-professional/package.json" ]; then
    check_status 0 "AEP Professional extension directory exists"
else
    check_status 1 "AEP Professional extension directory missing"
fi

# Check if old extensions are disabled
echo ""
echo "2. Checking Old Extensions Are Disabled..."

OLD_EXTENSIONS=("vscode-aep" "vscode-pro" "vscode" "test-minimal" "vscode-old-backup")

for ext in "${OLD_EXTENSIONS[@]}"; do
    if [ -f "extensions/$ext/package.json" ]; then
        check_status 1 "$ext/package.json is ACTIVE (should be disabled)"
    elif [ -f "extensions/$ext/_package.json.disabled" ]; then
        check_status 0 "$ext extension is properly disabled"
    else
        check_info "$ext directory doesn't exist (OK)"
    fi
done

echo ""
echo "3. Checking Extension Configuration..."

# Check package.json publisher and name
if [ -f "extensions/aep-professional/package.json" ]; then
    PUBLISHER=$(grep '"publisher"' extensions/aep-professional/package.json | cut -d'"' -f4)
    NAME=$(grep '"name"' extensions/aep-professional/package.json | head -1 | cut -d'"' -f4)
    
    if [ "$PUBLISHER" = "navralabs" ]; then
        check_status 0 "Publisher is correctly set to 'navralabs'"
    else
        check_status 1 "Publisher should be 'navralabs', found: '$PUBLISHER'"
    fi
    
    if [ "$NAME" = "aep-professional" ]; then
        check_status 0 "Extension name is correctly set to 'aep-professional'"
    else
        check_status 1 "Extension name should be 'aep-professional', found: '$NAME'"
    fi
    
    check_info "Extension ID will be: $PUBLISHER.$NAME"
fi

echo ""
echo "4. Checking Launch Configuration..."

# Check .vscode/launch.json exists and has correct config
if [ -f ".vscode/launch.json" ]; then
    if grep -q "aep-professional" .vscode/launch.json; then
        check_status 0 "Launch configuration points to aep-professional"
    else
        check_status 1 "Launch configuration doesn't reference aep-professional"
    fi
else
    check_status 1 ".vscode/launch.json missing"
fi

echo ""
echo "5. Checking Build Status..."

# Check if TypeScript compiled output exists
if [ -f "extensions/aep-professional/out/extension.js" ]; then
    check_status 0 "Extension is compiled (out/extension.js exists)"
else
    check_warning "Extension not compiled yet (run 'npm run compile')"
    ((ISSUES++))
fi

# Check if node_modules exists
if [ -d "extensions/aep-professional/node_modules" ]; then
    check_status 0 "Dependencies installed (node_modules exists)"
else
    check_warning "Dependencies not installed (run 'npm install')"
    ((ISSUES++))
fi

echo ""
echo "6. Development Workflow Files..."

# Check if development documentation exists
if [ -f "extensions/aep-professional/DEVELOPMENT.md" ]; then
    check_status 0 "Development guide exists"
else
    check_status 1 "Development guide missing"
fi

# Check tsconfig.json
if [ -f "extensions/aep-professional/tsconfig.json" ]; then
    check_status 0 "TypeScript configuration exists"
else
    check_status 1 "TypeScript configuration missing"
fi

echo ""
echo "=============================================="
echo "📊 Summary:"
echo -e "${GREEN}✅ Passed: $SUCCESS${NC}"
echo -e "${RED}❌ Issues: $ISSUES${NC}"

if [ $ISSUES -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 Environment is properly configured!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. cd extensions/aep-professional"
    echo "2. npm install (if not done)"
    echo "3. npm run compile"
    echo "4. Press F5 in VS Code to launch extension"
else
    echo ""
    echo -e "${RED}⚠️  Please fix the issues above before development${NC}"
    echo ""
    echo "Quick fixes:"
    echo "- Disable old extensions: mv extensions/OLD/package.json extensions/OLD/_package.json.disabled"
    echo "- Install dependencies: cd extensions/aep-professional && npm install"
    echo "- Compile extension: npm run compile"
fi

echo ""