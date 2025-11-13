#!/bin/bash

# Script to reinstall the AEP extension with debugging enhancements
# Run this in Terminal.app (not VS Code's integrated terminal)

echo "🔧 Reinstalling AEP Professional extension..."

# Navigate to the extension directory
cd "/Users/mounikakapa/Desktop/Personal Projects/autonomous-engineering-platform/extensions/vscode-aep"

# Compile the latest changes
echo "📦 Compiling extension..."
npm run compile

# Package the extension
echo "🎁 Packaging extension..."
npx @vscode/vsce package --allow-star-activation

# Install the extension (this will replace the existing one)
echo "🚀 Installing extension..."
code --install-extension aep-professional.vsix --force

echo "✅ Extension reinstalled! Now try opening the AEP panel in VS Code:"
echo "   1. Open Command Palette (Cmd+Shift+P)"
echo "   2. Type 'AEP: Show Panel'"
echo "   3. Or look for the AEP icon in the Activity Bar"
echo ""
echo "🔍 Check the Debug Console in VS Code for detailed logs!"