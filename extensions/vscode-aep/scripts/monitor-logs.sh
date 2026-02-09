#!/bin/bash

# Monitor Claude Code Chat Panel Logs
# This script helps monitor the extension logs in real-time

echo "🔍 Claude Code Chat Panel Log Monitor"
echo "========================================"
echo ""
echo "This script will help you monitor the extension logs."
echo ""
echo "To view live extension logs in VS Code:"
echo "1. Press Cmd+Shift+P (Mac) or Ctrl+Shift+P (Windows/Linux)"
echo "2. Type 'Developer: Show Logs'"
echo "3. Select 'Extension Host'"
echo ""
echo "OR:"
echo "1. Press Cmd+Shift+U (Mac) or Ctrl+Shift+U (Windows/Linux) to open Output panel"
echo "2. Select 'Extension Host' from the dropdown"
echo ""
echo "Key log patterns to watch for:"
echo "  [AEP] 📡 - Streaming requests"
echo "  [AEP] 🚀 - Backend API calls"
echo "  [AEP] ❌ - Errors"
echo "  [AEP] ⚠️ - Warnings"
echo "  [AEP] ✅ - Success messages"
echo ""
echo "Chat-specific logs:"
echo "  - 'Using V2 tool-use streaming'"
echo "  - 'Using Autonomous mode'"
echo "  - 'About to fetch streaming URL'"
echo "  - 'Streaming failed, falling back'"
echo "  - 'Response sent to webview'"
echo ""
echo "To see logs from a development VS Code window:"
echo "1. Run your extension with F5"
echo "2. In the main VS Code window (not the extension development window):"
echo "   - Open Help > Toggle Developer Tools"
echo "   - Go to the Console tab"
echo "   - Filter for '[AEP]' to see extension logs"
echo ""
echo "Press Ctrl+C to exit"
echo ""

# Check if there are any recent log files
LOG_DIRS=(
  "$HOME/Library/Application Support/Code/logs"
  "$HOME/.config/Code/logs"
  "$HOME/Library/Logs"
)

echo "Checking for recent log files..."
for dir in "${LOG_DIRS[@]}"; do
  if [ -d "$dir" ]; then
    echo "Found log directory: $dir"
    find "$dir" -name "*.log" -mmin -60 2>/dev/null | head -5 | while read logfile; do
      echo "  - $logfile"
    done
  fi
done

echo ""
echo "To tail VS Code extension host logs (if available):"
echo "  tail -f ~/Library/Application\\ Support/Code/logs/*/exthost*/exthost.log"
echo ""
