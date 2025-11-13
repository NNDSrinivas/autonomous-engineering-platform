#!/bin/bash
set -e

echo "Testing VS Code extension launch..."
echo "Working directory: $(pwd)"
echo "Node version: $(node --version)"
echo "NPM version: $(npm --version)"

cd "/Users/mounikakapa/Desktop/Personal Projects/autonomous-engineering-platform/extensions/vscode-aep"
echo "Extension directory: $(pwd)"
echo "Checking compiled files..."
ls -la out/

echo "Starting VS Code with extension..."
exec code --extensionDevelopmentPath="$(pwd)" --new-window