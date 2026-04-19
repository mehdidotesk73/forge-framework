#!/usr/bin/env bash
# Forge Suite CLI — manage and operate Forge projects from the terminal.
# Double-click on macOS, or run: bash forge-suite-cli.command
# Pass arguments to run a command directly:
#   bash forge-suite-cli.command init ~/my-projects/my-app
#   bash forge-suite-cli.command pipeline-run ~/my-projects/my-app normalize_data
#   bash forge-suite-cli.command model-build ~/my-projects/my-app
#   bash forge-suite-cli.command endpoint-build ~/my-projects/my-app
#   bash forge-suite-cli.command project-serve ~/my-projects/my-app
#   bash forge-suite-cli.command mount /path/to/existing-project
#   bash forge-suite-cli.command list
#   bash forge-suite-cli.command sync /path/to/project
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$REPO_ROOT/.venv"

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

# ── If arguments were passed, run that command and exit ──────────────────────

if [ "$#" -gt 0 ]; then
  forge-suite "$@"
  exit $?
fi

# ── Interactive menu ──────────────────────────────────────────────────────────

echo "╔══════════════════════════════════════════════════════════╗"
echo "║       Forge Suite CLI                                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Project lifecycle:"
echo ""
echo "  forge-suite init <path>                    Scaffold + register a new project"
echo "  forge-suite mount <path>                   Register an existing project"
echo "  forge-suite list                           List all registered projects"
echo "  forge-suite sync <path>                    Re-sync a project from forge.toml"
echo ""
echo "Build and run:"
echo ""
echo "  forge-suite pipeline-run <path> <name>     Run a pipeline"
echo "  forge-suite model-build <path>             Build model schemas + SDKs"
echo "  forge-suite endpoint-build <path>          Build endpoint descriptor registry"
echo "  forge-suite project-serve <path>           Start project backend on :8001"
echo "  forge-suite project-serve <path> --port N  Start on a custom port"
echo "  forge-suite project-serve <path> --app X   Serve React app at /"
echo ""
echo "Management UI:"
echo ""
echo "  forge-suite serve                          Start the Forge Suite webapp"
echo ""
echo "Examples:"
echo ""
echo "  forge-suite init ~/my-projects/my-app"
echo "  forge-suite pipeline-run ~/my-projects/my-app normalize_data"
echo "  forge-suite model-build ~/my-projects/my-app"
echo "  forge-suite endpoint-build ~/my-projects/my-app"
echo "  forge-suite project-serve ~/my-projects/my-app --port 8002"
echo "  forge-suite mount /Users/$(whoami)/Sandbox/forge-framework/examples/student-manager"
echo "  forge-suite list"
echo ""

while true; do
  echo -n "Enter command (or 'q' to quit): "
  read -r INPUT

  if [ "$INPUT" = "q" ] || [ "$INPUT" = "quit" ] || [ "$INPUT" = "exit" ]; then
    echo "Done."
    break
  fi

  if [ -z "$INPUT" ]; then
    continue
  fi

  eval "forge-suite $INPUT" || true
  echo ""
done
