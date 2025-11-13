#!/bin/bash
echo "🔧 Quick reinstall of AEP extension..."
cd "/Users/mounikakapa/Desktop/Personal Projects/autonomous-engineering-platform/extensions/vscode-aep"
npx @vscode/vsce package --allow-star-activation --out aep-debug.vsix
echo "✅ Packaged as aep-debug.vsix"
echo ""
echo "Now install via VS Code:"
echo "1. Cmd+Shift+P → 'Extensions: Install from VSIX...'"
echo "2. Select: aep-debug.vsix"