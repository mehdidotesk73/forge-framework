#!/usr/bin/env bash
# Forge Suite — one-time setup.
# Double-click on macOS, or run: bash setup.command
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBAPP_DIR="$REPO_ROOT/examples/forge-webapp"
VENV="$REPO_ROOT/.venv"

echo "=== Forge Suite Setup ==="
echo ""

# ── Python virtual environment ────────────────────────────────────────────────

if [ ! -d "$VENV" ]; then
  echo "→ Creating Python virtual environment..."
  python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"

echo "→ Installing Python dependencies..."
pip install -e "$REPO_ROOT/packages/forge-py" -e "$REPO_ROOT/packages/forge-suite" --quiet

# ── Node dependencies ─────────────────────────────────────────────────────────

echo "→ Installing npm dependencies..."
npm install --prefix "$REPO_ROOT" --silent

# ── Stop any running forge backend (releases DuckDB lock) ────────────────────

FORGE_PIDS=$(pgrep -f "forge.cli.main" 2>/dev/null || true)
if [ -n "$FORGE_PIDS" ]; then
  echo "→ Stopping running Forge backend (releases database lock)..."
  echo "$FORGE_PIDS" | xargs kill 2>/dev/null || true
  sleep 1
fi

# ── forge-webapp bootstrap ────────────────────────────────────────────────────

echo "→ Setting up forge-webapp..."
cd "$WEBAPP_DIR"
bash setup.sh

# ── Make launch script executable ────────────────────────────────────────────

chmod +x "$REPO_ROOT/forge-suite.command"

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "✓ Setup complete."
echo ""
echo "To start Forge Suite:"
echo ""
echo "  Double-click:  forge-suite.command"
echo "  CLI:           source .venv/bin/activate && forge-suite serve"
echo ""
echo "Press Enter to close this window."
read -r
