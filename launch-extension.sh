#!/bin/bash

# Manual Extension Development Script
# This launches VS Code in extension development mode manually

set -e

EXTENSION_PATH="/Users/mounikakapa/Desktop/Personal Projects/autonomous-engineering-platform/extensions/vscode-aep"

echo "🔧 Compiling extension..."
cd "$EXTENSION_PATH"
npm run compile

echo "🚀 Launching VS Code in extension development mode..."
echo "Extension path: $EXTENSION_PATH"

# Try different launch methods
echo "Attempting method 1: Direct code command..."
code --new-window --extensionDevelopmentPath="$EXTENSION_PATH" || {
    echo "Method 1 failed, trying method 2..."
    
    # Method 2: Use open command
    open -n "/Users/mounikakapa/Desktop/Visual Studio Code.app" --args --extensionDevelopmentPath="$EXTENSION_PATH" || {
        echo "Method 2 failed, trying method 3..."
        
        # Method 3: Direct app launch
        "/Users/mounikakapa/Desktop/Visual Studio Code.app/Contents/MacOS/Electron" --extensionDevelopmentPath="$EXTENSION_PATH" --new-window
    }
}

echo "✅ Extension development window should be opening..."