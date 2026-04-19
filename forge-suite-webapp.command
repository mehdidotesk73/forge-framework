#!/usr/bin/env bash
# Forge Suite — start the management UI and open it in the browser.
# Double-click on macOS, or run: bash forge-suite-webapp.command
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$REPO_ROOT/.venv"
PORT=5174

# ── Environment check ─────────────────────────────────────────────────────────

if [ ! -d "$VENV" ]; then
  echo "✗ Virtual environment not found. Run setup.command first."
  echo ""
  echo "Press Enter to close."
  read -r
  exit 1
fi

source "$VENV/bin/activate"

if ! python -c "import forge_suite" 2>/dev/null; then
  echo "✗ forge-suite not installed. Run setup.command first."
  echo ""
  echo "Press Enter to close."
  read -r
  exit 1
fi

# ── Start Forge Suite (single process — backend + pre-built UI) ───────────────

exec forge-suite serve --port "$PORT"
