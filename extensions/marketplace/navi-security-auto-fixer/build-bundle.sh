#!/bin/bash
# Bundle Creation Script for NAVI Security Auto-Fixer Extension
# Creates production-ready bundle for marketplace distribution

set -e

echo "🔨 Building NAVI Security Auto-Fixer Extension Bundle..."

# Configuration
EXTENSION_NAME="navi-security-auto-fixer"
VERSION=$(node -p "require('./package.json').version")
BUILD_DIR="dist"
BUNDLE_NAME="${EXTENSION_NAME}-${VERSION}.zip"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Extension: $EXTENSION_NAME${NC}"
echo -e "${BLUE}Version: $VERSION${NC}"

# Clean previous builds
echo -e "${YELLOW}🧹 Cleaning previous builds...${NC}"
rm -rf $BUILD_DIR
rm -f *.zip

# Create build directory
mkdir -p $BUILD_DIR

# Run TypeScript compilation
echo -e "${YELLOW}🔧 Compiling TypeScript...${NC}"
npm run build

# Run tests
echo -e "${YELLOW}🧪 Running test suite...${NC}"
npm test

# Run security audit
echo -e "${YELLOW}🔍 Running security audit...${NC}"
npm audit --audit-level moderate

# Copy necessary files to build directory
echo -e "${YELLOW}📦 Copying files to build directory...${NC}"
cp -r lib/ $BUILD_DIR/
cp manifest.json $BUILD_DIR/
cp permissions.json $BUILD_DIR/
cp package.json $BUILD_DIR/
cp README.md $BUILD_DIR/
cp LICENSE $BUILD_DIR/

# Copy only necessary node_modules (production dependencies)
echo -e "${YELLOW}📚 Installing production dependencies...${NC}"
cd $BUILD_DIR
npm install --only=production --no-optional
cd ..

# Create optimized bundle structure
echo -e "${YELLOW}🗂️ Optimizing bundle structure...${NC}"
cd $BUILD_DIR

# Remove unnecessary files
find . -name "*.map" -delete
find . -name "*.test.js" -delete
find . -name "*.spec.js" -delete
find . -name "test" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "coverage" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.md" -not -name "README.md" -delete
find . -name "LICENSE*" -not -name "LICENSE" -delete

# Minify JavaScript files (optional, comment out if issues)
# echo -e "${YELLOW}⚡ Minifying JavaScript files...${NC}"
# find . -name "*.js" -not -path "./node_modules/*" -exec terser {} -o {} \;

cd ..

# Validate bundle structure
echo -e "${YELLOW}✅ Validating bundle structure...${NC}"
required_files=(
    "$BUILD_DIR/manifest.json"
    "$BUILD_DIR/permissions.json"
    "$BUILD_DIR/lib/index.js"
    "$BUILD_DIR/lib/types.js"
    "$BUILD_DIR/package.json"
    "$BUILD_DIR/README.md"
)

for file in "${required_files[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo -e "${RED}❌ Missing required file: $file${NC}"
        exit 1
    fi
done

echo -e "${GREEN}✅ All required files present${NC}"

# Check manifest.json validity
echo -e "${YELLOW}🔍 Validating manifest.json...${NC}"
if ! python3 -c "import json; json.load(open('$BUILD_DIR/manifest.json'))" 2>/dev/null; then
    echo -e "${RED}❌ Invalid manifest.json format${NC}"
    exit 1
fi

echo -e "${GREEN}✅ manifest.json is valid${NC}"

# Check permissions.json validity
echo -e "${YELLOW}🔍 Validating permissions.json...${NC}"
if ! python3 -c "import json; json.load(open('$BUILD_DIR/permissions.json'))" 2>/dev/null; then
    echo -e "${RED}❌ Invalid permissions.json format${NC}"
    exit 1
fi

echo -e "${GREEN}✅ permissions.json is valid${NC}"

# Calculate bundle size
echo -e "${YELLOW}📏 Calculating bundle size...${NC}"
BUNDLE_SIZE=$(du -sh $BUILD_DIR | cut -f1)
echo -e "${BLUE}Bundle size: $BUNDLE_SIZE${NC}"

# Create ZIP bundle
echo -e "${YELLOW}📦 Creating ZIP bundle...${NC}"
cd $BUILD_DIR
zip -r "../$BUNDLE_NAME" . -x "*.DS_Store" "Thumbs.db"
cd ..

# Validate ZIP bundle
echo -e "${YELLOW}🔍 Validating ZIP bundle...${NC}"
if ! unzip -t "$BUNDLE_NAME" > /dev/null 2>&1; then
    echo -e "${RED}❌ Invalid ZIP bundle created${NC}"
    exit 1
fi

echo -e "${GREEN}✅ ZIP bundle is valid${NC}"

# Generate bundle info
FINAL_SIZE=$(du -sh "$BUNDLE_NAME" | cut -f1)
FILE_COUNT=$(unzip -l "$BUNDLE_NAME" | tail -1 | awk '{print $2}')

# Create bundle metadata
echo -e "${YELLOW}📋 Creating bundle metadata...${NC}"
cat > "${EXTENSION_NAME}-${VERSION}-metadata.json" << EOF
{
  "name": "$EXTENSION_NAME",
  "version": "$VERSION",
  "bundleFile": "$BUNDLE_NAME",
  "bundleSize": "$FINAL_SIZE",
  "fileCount": $FILE_COUNT,
  "buildDate": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "buildNode": "$(node --version)",
  "buildNpm": "$(npm --version)",
  "checksums": {
    "sha256": "$(shasum -a 256 "$BUNDLE_NAME" | cut -d' ' -f1)"
  }
}
EOF

# Security scan of final bundle
echo -e "${YELLOW}🛡️ Running security scan on bundle...${NC}"
if command -v clamscan &> /dev/null; then
    clamscan --recursive $BUILD_DIR || echo -e "${YELLOW}⚠️ ClamAV not available or scan had issues${NC}"
else
    echo -e "${YELLOW}⚠️ ClamAV not available, skipping virus scan${NC}"
fi

# Final report
echo ""
echo -e "${GREEN}🎉 Bundle creation completed successfully!${NC}"
echo -e "${BLUE}Bundle file: $BUNDLE_NAME${NC}"
echo -e "${BLUE}Bundle size: $FINAL_SIZE${NC}"
echo -e "${BLUE}File count: $FILE_COUNT${NC}"
echo -e "${BLUE}SHA256: $(shasum -a 256 "$BUNDLE_NAME" | cut -d' ' -f1)${NC}"

# Cleanup build directory (optional)
if [[ "$1" == "--clean" ]]; then
    echo -e "${YELLOW}🧹 Cleaning build directory...${NC}"
    rm -rf $BUILD_DIR
fi

# Upload instructions
echo ""
echo -e "${YELLOW}📤 Next steps:${NC}"
echo "1. Test the bundle: unzip $BUNDLE_NAME && cd navi-security-auto-fixer"
echo "2. Validate in NAVI: Import the .zip file into NAVI marketplace"
echo "3. Upload to marketplace: Use NAVI CLI or web interface"

echo ""
echo -e "${GREEN}✨ Ready for marketplace distribution!${NC}"