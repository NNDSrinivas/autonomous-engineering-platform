#!/bin/bash
set -euo pipefail

EXT_DIR="extensions/vscode-aep"

if [ ! -f "$EXT_DIR/package.json" ]; then
  echo "Extension package.json not found at $EXT_DIR."
  exit 1
fi

if [ ! -d "$EXT_DIR/node_modules" ] && [ ! -d "node_modules" ]; then
  echo "Dependencies not installed. Run: npm install (workspace root) or (cd $EXT_DIR && npm install)"
  exit 1
fi

echo "Running TypeScript compile for VS Code extension..."
npm --prefix "$EXT_DIR" run compile

echo "Extension compile check passed."
