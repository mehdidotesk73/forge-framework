#!/usr/bin/env bash
# Forge Suite — release verification.
# Serves the pre-built production bundle (no live reload).
# Use this to smoke-test a release build before shipping, not for daily dev.
# For daily development, use forge-suite-dev.command instead.
# Double-click on macOS, or run: bash forge-suite-verify.command
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

if [ -f "$VENV/Scripts/activate" ]; then
  source "$VENV/Scripts/activate"   # Windows / Git Bash
else
  source "$VENV/bin/activate"
fi

if ! python -c "import forge_suite" 2>/dev/null; then
  echo "✗ forge-suite not installed. Run setup.command first."
  echo ""
  echo "Press Enter to close."
  read -r
  exit 1
fi

# ── Start Forge Suite (single process — backend + pre-built UI) ───────────────

exec forge-suite serve --port "$PORT"
