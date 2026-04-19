#!/usr/bin/env bash
# Forge Suite — one-time setup. Re-run after any frontend source changes.
# Double-click on macOS, or run: bash setup.command
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBAPP_DIR="$REPO_ROOT/packages/forge-suite/forge-webapp"
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

# ── Build frontend and copy into package ─────────────────────────────────────

echo "→ Building forge-webapp frontend..."
cd "$REPO_ROOT"
npm run build --workspace=packages/forge-suite/forge-webapp/apps/forge-webapp --silent

DIST_SRC="$REPO_ROOT/packages/forge-suite/forge-webapp/apps/forge-webapp/dist"
DIST_DST="$REPO_ROOT/packages/forge-suite/forge_suite/webapp_dist"
echo "→ Copying dist → forge_suite/webapp_dist..."
rm -rf "$DIST_DST"
cp -r "$DIST_SRC" "$DIST_DST"

# ── Make launch script executable ────────────────────────────────────────────

chmod +x "$REPO_ROOT/forge-suite-webapp.command" "$REPO_ROOT/forge-suite-cli.command"

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "✓ Setup complete."
echo ""
echo "To start Forge Suite:"
echo ""
echo "  Double-click:  forge-suite-webapp.command   (opens the management UI)"
echo "  CLI menu:      forge-suite-cli.command       (project lifecycle commands)"
echo "  Terminal:      source .venv/bin/activate && forge-suite serve"
echo ""
echo "Press Enter to close this window."
read -r
