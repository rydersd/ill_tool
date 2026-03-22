#!/bin/bash
# Build script for npm package distribution.
# Copies the modular src/adobe_mcp/ package into npm/server/adobe_mcp/
# so the npm launcher can run it with `python -m adobe_mcp`.
#
# Usage: bash scripts/build-npm.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC_PKG="$REPO_ROOT/src/adobe_mcp"
NPM_SERVER="$REPO_ROOT/npm/server"

echo "Building npm package..."

# Clean previous build artifact
rm -rf "$NPM_SERVER/adobe_mcp"
rm -f "$NPM_SERVER/adobe_mcp.py"

# Copy the full package
cp -R "$SRC_PKG" "$NPM_SERVER/adobe_mcp"

# Remove __pycache__ directories
find "$NPM_SERVER/adobe_mcp" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo "Copied $(find "$NPM_SERVER/adobe_mcp" -name "*.py" | wc -l | tr -d ' ') Python files to npm/server/adobe_mcp/"
echo "Done."
