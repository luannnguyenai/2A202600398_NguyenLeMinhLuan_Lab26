#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p .npm-cache
PYTHON_BIN="${PYTHON_BIN:-$PWD/.venv312/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3)"
fi
NPM_CONFIG_CACHE="$PWD/.npm-cache" npx -y @modelcontextprotocol/inspector "$PYTHON_BIN" "$PWD/implementation/mcp_server.py"
