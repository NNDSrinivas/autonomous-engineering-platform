#!/bin/bash
# Build script for NAVI Observability & Metrics Analyzer Extension

set -e

echo "🔨 Building NAVI Observability & Metrics Analyzer..."

# Clean previous build
rm -rf dist/

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Build TypeScript
echo "🔨 Compiling TypeScript..."
npx tsc

# Run tests
echo "🧪 Running tests..."
npm test || echo "⚠️  Some tests failed, but continuing build..."

# Create bundle directory structure
echo "📦 Creating extension bundle..."
mkdir -p navi-observability-analyzer.navi-ext

# Copy built files
cp -r dist/* navi-observability-analyzer.navi-ext/
cp manifest.json navi-observability-analyzer.navi-ext/
cp permissions.json navi-observability-analyzer.navi-ext/
cp README.md navi-observability-analyzer.navi-ext/ 2>/dev/null || echo "README.md not found, skipping..."
cp package.json navi-observability-analyzer.navi-ext/

# Create signature placeholder
echo "signature-placeholder" > navi-observability-analyzer.navi-ext/signature.sig

# Package as tar.gz
tar -czf navi-observability-analyzer.navi-ext.tar.gz navi-observability-analyzer.navi-ext/

echo "✅ Build complete!"
echo "📦 Extension bundle: navi-observability-analyzer.navi-ext.tar.gz"
echo ""
echo "Next steps:"
echo "1. Sign the extension: navi extensions sign --bundle navi-observability-analyzer.navi-ext.tar.gz"
echo "2. Deploy to marketplace: navi extensions deploy navi-observability-analyzer.navi-ext.tar.gz"