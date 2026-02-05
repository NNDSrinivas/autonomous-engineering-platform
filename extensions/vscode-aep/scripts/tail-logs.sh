#!/bin/bash

# Tail Claude Code Chat Panel Logs in Real-Time
echo "🔍 Tailing Claude Code Extension Logs..."
echo "=========================================="
echo ""

# Find the most recent extension host log
EXTHOST_LOG=$(find "$HOME/Library/Application Support/Code/logs" -path "*/exthost/*.log" -type f -mmin -120 | sort -t/ -k9 -r | head -1)

if [ -z "$EXTHOST_LOG" ]; then
  echo "❌ No recent extension host log found."
  echo ""
  echo "Make sure:"
  echo "1. VS Code is running"
  echo "2. The extension is activated"
  echo "3. You have made a request in the chat panel"
  echo ""
  echo "Alternative: Open VS Code and press Cmd+Shift+U, then select 'Extension Host' from dropdown"
  exit 1
fi

echo "📁 Watching: $EXTHOST_LOG"
echo ""
echo "Filtering for [AEP] logs related to chat panel..."
echo "Press Ctrl+C to stop"
echo ""
echo "─────────────────────────────────────────────────────────────"
echo ""

# Tail the log and filter for AEP-related entries
tail -f "$EXTHOST_LOG" | grep --line-buffered "\[AEP\]"
