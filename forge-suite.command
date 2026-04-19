#!/usr/bin/env bash
# Forge Suite — start the Forge backend and management UI.
# Double-click on macOS, or run: bash forge-suite.command
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBAPP_DIR="$REPO_ROOT/examples/forge-webapp"
APP_DIR="$WEBAPP_DIR/apps/forge-webapp"
VENV="$REPO_ROOT/.venv"
BACKEND_PORT=8000
FRONTEND_PORT=5174

# ── One-time setup ────────────────────────────────────────────────────────────

if [ ! -d "$VENV" ]; then
  echo "→ Creating Python virtual environment..."
  python3 -m venv "$VENV"
fi

source "$VENV/bin/activate"

if ! python -c "import forge_suite" 2>/dev/null; then
  echo "→ Installing Python dependencies (first run)..."
  pip install -e "$REPO_ROOT/packages/forge-py" -e "$REPO_ROOT/packages/forge-suite" --quiet
fi

if [ ! -d "$REPO_ROOT/node_modules" ]; then
  echo "→ Installing npm dependencies (first run)..."
  npm install --prefix "$REPO_ROOT" --silent
fi

# ── One-time webapp bootstrap ─────────────────────────────────────────────────

if [ ! -f "$WEBAPP_DIR/.forge/artifacts/ForgeProject.schema.json" ]; then
  echo "→ Setting up forge-webapp (first run)..."
  cd "$WEBAPP_DIR"
  bash setup.sh
fi

# ── Start servers ─────────────────────────────────────────────────────────────

echo "→ Starting Forge backend on :$BACKEND_PORT..."
cd "$WEBAPP_DIR"
forge dev serve --port $BACKEND_PORT &
BACKEND_PID=$!

echo "→ Starting management UI on :$FRONTEND_PORT..."
cd "$APP_DIR"
npm run dev &
FRONTEND_PID=$!

# ── Wait for UI, then open browser ────────────────────────────────────────────

echo "→ Waiting for servers to be ready..."
for _ in $(seq 1 60); do
  if curl -s "http://localhost:$FRONTEND_PORT" > /dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

echo "✓ Forge Suite running"
echo "  UI:      http://localhost:$FRONTEND_PORT"
echo "  Backend: http://localhost:$BACKEND_PORT/api/health"
echo ""
echo "Press Ctrl+C to stop."

if command -v open &>/dev/null; then
  open "http://localhost:$FRONTEND_PORT"
elif command -v xdg-open &>/dev/null; then
  xdg-open "http://localhost:$FRONTEND_PORT"
fi

# ── Cleanup on exit ───────────────────────────────────────────────────────────

cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait "$BACKEND_PID" "$FRONTEND_PID"
