#!/usr/bin/env bash
# Forge Suite — daily development workflow (backend + frontend, live reload).
# Starts the API backend on :7999 and the Vite dev server on :5174.
# Use this for all forge-suite development — backend and frontend alike.
# To verify a release build, use forge-suite-verify.command instead.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$REPO_ROOT/.venv"
WEBAPP_APP="$REPO_ROOT/packages/forge-suite/forge-webapp/apps/forge-webapp"

if [ ! -d "$VENV" ]; then
  echo "✗ Virtual environment not found. Run setup.command first."
  echo ""
  echo "Press Enter to close."
  read -r
  exit 1
fi

if [ -f "$VENV/Scripts/activate" ]; then
  source "$VENV/Scripts/activate"   # Windows / Git Bash
else
  source "$VENV/bin/activate"
fi

# Start backend API on :7999 (no static frontend)
forge-suite serve --dev &
BACKEND_PID=$!

# Give the backend a moment to start
sleep 2

# Start Vite dev server on :5174
cd "$WEBAPP_APP"
npm run dev &
VITE_PID=$!

# Give Vite a moment to start, then open the browser
sleep 3
# open browser cross-platform
if command -v open &>/dev/null; then
  open "http://localhost:5174"
elif command -v xdg-open &>/dev/null; then
  xdg-open "http://localhost:5174"
elif command -v start &>/dev/null; then
  start "http://localhost:5174"
fi

echo ""
echo "Forge Suite dev mode running:"
echo "  API:     http://localhost:7999/api/health"
echo "  UI:      http://localhost:5174  (live reload)"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $VITE_PID 2>/dev/null; exit 0" INT TERM

wait
