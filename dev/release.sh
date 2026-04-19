#!/usr/bin/env bash
# dev/release.sh — End-to-end release for forge-framework
#
# Usage:
#   bash dev/release.sh patch                      # 0.1.4 → 0.1.5
#   bash dev/release.sh minor                      # 0.1.4 → 0.2.0
#   bash dev/release.sh major                      # 0.1.4 → 1.0.0
#   bash dev/release.sh --version 1.2.3            # explicit version
#   bash dev/release.sh patch --dry-run            # full build, no publish/push
#   bash dev/release.sh patch --from-phase 4       # resume after a failure
#
# Dry-run workflow:
#   --dry-run builds everything for real (catches build errors early) but skips
#   npm publish, PyPI upload, and git commit/tag/push. At the end it reverts the
#   version file changes so the working tree is left clean. To then publish:
#     bash dev/release.sh patch        ← same command, no extra flags needed
#
# Phases:
#   1  Pre-flight checks (git state, credentials, version sync)
#   2  Bump all four version files
#   3  Build @forge-suite/ts and publish to npm
#   4  Build forge-webapp frontend, copy to webapp_dist/
#   5  Build Python wheels (forge-py + forge-suite)
#   6  Publish both wheels to PyPI
#   7  Git commit, tag, and push
#
# Prerequisites:
#   ~/.npmrc   containing  //registry.npmjs.org/:_authToken=npm_xxx
#   ~/.pypirc  configured with [pypi] username/password (or token)
#   Active Python venv with: pip install build twine
set -euo pipefail

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
STATE_FILE="$SCRIPT_DIR/.release-state"
LOG_FILE="$LOG_DIR/release-$(date +%Y%m%d-%H%M%S).log"

mkdir -p "$LOG_DIR"

# Tee all output (stdout + stderr) to the log file
exec > >(tee -a "$LOG_FILE") 2>&1

# ── Colors (best-effort — ANSI codes land in log too, strip with: sed 's/\x1b\[[0-9;]*m//g') ──
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'
B='\033[0;34m'; C='\033[0;36m'; BOLD='\033[1m'; X='\033[0m'

# ── Logging helpers ────────────────────────────────────────────────────────────
log_header() {
  echo -e "\n${BOLD}${B}══════════════════════════════════════════════════════════════════════${X}"
  echo -e "${BOLD}${B}  PHASE $1: $2${X}"
  echo -e "${B}  $(date '+%Y-%m-%d %H:%M:%S')${X}"
  echo -e "${BOLD}${B}══════════════════════════════════════════════════════════════════════${X}"
}

log_step() { echo -e "\n${C}  ▶  $*${X}"; }
log_ok()   { echo -e "${G}     ✓  $*${X}"; }
log_warn() { echo -e "${Y}     ⚠  $*${X}"; }
log_info() { echo -e "     $*"; }

log_phase_done() {
  echo -e "\n${G}  ✓  Phase $1 complete — $(date '+%H:%M:%S')${X}"
}

die() {
  echo -e "\n${R}${BOLD}  ✗  ERROR in Phase $CURRENT_PHASE: $*${X}"
  echo -e "${Y}     To resume from here, re-run with:  --from-phase $CURRENT_PHASE${X}"
  echo -e "     Full log: $LOG_FILE\n"
  exit 1
}

run_cmd() {
  # Echo the command, then run it; die with context on failure
  echo -e "     ${B}\$${X} $*"
  if ! eval "$@"; then
    die "Command failed: $*"
  fi
}

# ── Argument parsing ───────────────────────────────────────────────────────────
DRY_RUN=false
FROM_PHASE=1
BUMP=""
EXPLICIT_VERSION=""
CURRENT_PHASE=0

args=("$@")
i=0
while [ $i -lt ${#args[@]} ]; do
  arg="${args[$i]}"
  case "$arg" in
    --dry-run)    DRY_RUN=true ;;
    --from-phase) i=$((i+1)); FROM_PHASE="${args[$i]}" ;;
    --version)    i=$((i+1)); EXPLICIT_VERSION="${args[$i]}" ;;
    patch|minor|major) BUMP="$arg" ;;
    *) echo -e "${R}Unknown argument: $arg${X}"; exit 1 ;;
  esac
  i=$((i+1))
done

if [[ -z "$BUMP" && -z "$EXPLICIT_VERSION" && "$FROM_PHASE" -eq 1 ]]; then
  echo "Usage: bash dev/release.sh [patch|minor|major|--version X.Y.Z] [--dry-run] [--from-phase N]"
  exit 1
fi

# ── Auto-activate repo venv if none is active ─────────────────────────────────
if [[ -z "${VIRTUAL_ENV:-}" ]] && [[ -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  echo "  (activating $REPO_ROOT/.venv)"
  # shellcheck source=/dev/null
  source "$REPO_ROOT/.venv/bin/activate"
fi

# ── Detect Python + Twine ─────────────────────────────────────────────────────
PYTHON="${VIRTUAL_ENV:+$VIRTUAL_ENV/bin/python3}"
PYTHON="${PYTHON:-$(command -v python3)}"
TWINE="${VIRTUAL_ENV:+$VIRTUAL_ENV/bin/twine}"
TWINE="${TWINE:-$(command -v twine 2>/dev/null || echo "")}"

# ── Banner ─────────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}${C}forge-framework release script${X}"
echo -e "Log file: ${B}$LOG_FILE${X}"
echo -e "Started:  $(date '+%Y-%m-%d %H:%M:%S')"
$DRY_RUN && echo -e "${Y}  DRY-RUN MODE — nothing will be published or pushed${X}"
[ "$FROM_PHASE" -gt 1 ] && echo -e "${Y}  Resuming from phase $FROM_PHASE${X}"

# ── Read current versions from files (always, even when resuming) ──────────────
PY_VER=$(python3 -c "import re; print(re.search(r'\"(.+?)\"', open('$REPO_ROOT/packages/forge-py/forge/version.py').read()).group(1))")
PY_TOML_VER=$(python3 -c "import re; print(re.search(r'^version = \"(.+?)\"', open('$REPO_ROOT/packages/forge-py/pyproject.toml').read(), re.M).group(1))")
TS_VER=$(python3 -c "import json; print(json.load(open('$REPO_ROOT/packages/forge-ts/package.json'))['version'])")
SUITE_VER=$(python3 -c "import re; print(re.search(r'^version = \"(.+?)\"', open('$REPO_ROOT/packages/forge-suite/pyproject.toml').read(), re.M).group(1))")

# If resuming from phase >= 2, versions are already bumped — read NEW_VERSION from state
if [ "$FROM_PHASE" -ge 2 ] && [ -f "$STATE_FILE" ]; then
  # shellcheck source=/dev/null
  source "$STATE_FILE"
  log_info "Resuming release of v$NEW_VERSION (loaded from $STATE_FILE)"
elif [[ -n "$EXPLICIT_VERSION" ]]; then
  NEW_VERSION="$EXPLICIT_VERSION"
elif [[ -n "$BUMP" ]]; then
  NEW_VERSION=$(python3 - "$PY_VER" "$BUMP" <<'PYEOF'
import sys
major, minor, patch = map(int, sys.argv[1].split("."))
bump = sys.argv[2]
if   bump == "major": major += 1; minor = 0; patch = 0
elif bump == "minor": minor += 1; patch = 0
else:                 patch += 1
print(f"{major}.{minor}.{patch}")
PYEOF
)
else
  # Resuming without state file — derive NEW_VERSION from already-bumped files
  NEW_VERSION="$PY_VER"
  log_warn "No state file found; using current file version ($NEW_VERSION) as release target."
fi

echo -e "\n  Current: ${Y}v$PY_VER${X}  →  Target: ${G}${BOLD}v$NEW_VERSION${X}"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Pre-flight checks
# ═══════════════════════════════════════════════════════════════════════════════
CURRENT_PHASE=1
if [ "$FROM_PHASE" -le 1 ]; then
  log_header 1 "Pre-flight checks"

  # 1a. Working tree
  log_step "Checking git working tree..."
  cd "$REPO_ROOT"
  DIRTY=$(git status --porcelain 2>/dev/null | grep -v '^??' || true)
  if [[ -n "$DIRTY" ]]; then
    echo "$DIRTY"
    # If a previous dry-run left state behind, guide the user to --from-phase
    if [[ -f "$STATE_FILE" ]]; then
      source "$STATE_FILE" 2>/dev/null || true
      echo -e "\n${Y}  A previous dry-run already bumped version files to v${NEW_VERSION:-?}."
      echo -e "  To publish that version without re-bumping, run:${X}"
      echo -e "    ${BOLD}bash dev/release.sh --from-phase 3${X}"
      echo -e "${Y}  To start fresh with a new bump, commit the changes above first (do NOT tag):${X}"
      echo -e "    ${BOLD}git add -u${X}"
      echo -e "    ${BOLD}git commit -m 'chore: pre-release cleanup'${X}"
      echo -e "  Then re-run:  ${BOLD}bash dev/release.sh $BUMP${DRY_RUN:+ --dry-run}${X}\n"
    else
      echo -e "\n${Y}  These look like source edits that haven't been committed yet."
      echo -e "  Commit them first (do NOT tag — the script creates the tag in Phase 7):${X}"
      echo -e "    ${BOLD}git add -u${X}"
      echo -e "    ${BOLD}git commit -m 'chore: pre-release cleanup'${X}"
      echo -e "  Then re-run:  ${BOLD}bash dev/release.sh $BUMP${DRY_RUN:+ --dry-run}${X}\n"
    fi
    die "Working tree has uncommitted changes."
  fi
  log_ok "Git working tree is clean"

  # 1b. On main branch (warn, not fail)
  BRANCH=$(git rev-parse --abbrev-ref HEAD)
  if [[ "$BRANCH" != "main" && "$BRANCH" != "master" ]]; then
    log_warn "Not on main/master (currently on '$BRANCH') — proceeding anyway"
  else
    log_ok "On branch: $BRANCH"
  fi

  # 1c. npm credentials
  log_step "Checking npm credentials..."
  NPM_TOKEN=$(grep -s '//registry.npmjs.org/:_authToken=' "$HOME/.npmrc" | head -1 || true)
  if [[ -z "$NPM_TOKEN" ]]; then
    die "npm auth token not found in ~/.npmrc. Add: //registry.npmjs.org/:_authToken=npm_xxx"
  fi
  log_ok "npm auth token found in ~/.npmrc"

  # 1d. PyPI credentials
  log_step "Checking PyPI credentials..."
  if [[ ! -f "$HOME/.pypirc" ]]; then
    die "~/.pypirc not found. Create it with [pypi] credentials (see: https://pypi.org/manage/account/token/)"
  fi
  if ! grep -q '\[pypi\]' "$HOME/.pypirc"; then
    die "~/.pypirc exists but has no [pypi] section."
  fi
  log_ok "~/.pypirc found with [pypi] section"

  # 1e. Python build + twine
  log_step "Checking Python build tools..."
  if ! "$PYTHON" -m build --version >/dev/null 2>&1; then
    die "python 'build' module not found. Run: pip install build twine"
  fi
  log_ok "python -m build: $("$PYTHON" -m build --version)"
  if [[ -z "$TWINE" ]]; then
    die "twine not found. Run: pip install twine"
  fi
  log_ok "twine: $("$TWINE" --version)"

  # 1f. Version sync
  log_step "Checking version consistency across packages..."
  log_info "  forge-py/version.py    : $PY_VER"
  log_info "  forge-py/pyproject.toml: $PY_TOML_VER"
  log_info "  forge-ts/package.json  : $TS_VER"
  log_info "  forge-suite/pyproject  : $SUITE_VER"
  if [[ "$PY_VER" != "$TS_VER" || "$PY_VER" != "$SUITE_VER" || "$PY_VER" != "$PY_TOML_VER" ]]; then
    die "Version mismatch between packages. Fix manually before releasing."
  fi
  log_ok "All packages at v$PY_VER — consistent"

  # 1g. Tag doesn't already exist
  log_step "Checking tag v$NEW_VERSION doesn't already exist..."
  if git rev-parse "v$NEW_VERSION" >/dev/null 2>&1; then
    die "Tag v$NEW_VERSION already exists. Choose a different version."
  fi
  log_ok "Tag v$NEW_VERSION is available"

  # 1h. npm package not already published
  log_step "Checking @forge-suite/ts@$NEW_VERSION not already on npm..."
  if npm view "@forge-suite/ts@$NEW_VERSION" version >/dev/null 2>&1; then
    die "@forge-suite/ts@$NEW_VERSION already exists on npm. Choose a different version."
  fi
  log_ok "@forge-suite/ts@$NEW_VERSION not yet on npm"

  log_phase_done 1
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Bump version files
# ═══════════════════════════════════════════════════════════════════════════════
CURRENT_PHASE=2
if [ "$FROM_PHASE" -le 2 ]; then
  log_header 2 "Bump version files  ($PY_VER → $NEW_VERSION)"

  log_step "Updating all four version files..."
  "$PYTHON" - "$NEW_VERSION" "$REPO_ROOT" <<'PYEOF'
import re, json, sys
v, root = sys.argv[1], sys.argv[2]

def patch_file(path, fn):
    text = open(path).read()
    open(path, "w").write(fn(text))
    print(f"     updated: {path}")

patch_file(f"{root}/packages/forge-py/forge/version.py", lambda t:
    re.sub(r'__version__ = "[^"]+"', f'__version__ = "{v}"',
    re.sub(r'TS_VERSION = "[^"]+"',  f'TS_VERSION = "{v}"', t)))

patch_file(f"{root}/packages/forge-py/pyproject.toml", lambda t:
    re.sub(r'^version = "[^"]+"', f'version = "{v}"', t, flags=re.M))

path = f"{root}/packages/forge-ts/package.json"
data = json.load(open(path))
data["version"] = v
open(path, "w").write(json.dumps(data, indent=2) + "\n")
print(f"     updated: {path}")

patch_file(f"{root}/packages/forge-suite/pyproject.toml", lambda t:
    re.sub(r'^version = "[^"]+"', f'version = "{v}"', t, flags=re.M))
PYEOF

  log_ok "Version files updated to v$NEW_VERSION"

  # Persist state so --from-phase can recover the target version
  echo "NEW_VERSION=$NEW_VERSION" > "$STATE_FILE"
  log_info "Release state saved to $STATE_FILE"

  log_phase_done 2
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — Build + publish @forge-suite/ts to npm
# ═══════════════════════════════════════════════════════════════════════════════
CURRENT_PHASE=3
if [ "$FROM_PHASE" -le 3 ]; then
  log_header 3 "Build + publish @forge-suite/ts@$NEW_VERSION"

  log_step "TypeScript typecheck..."
  run_cmd "(cd '$REPO_ROOT/packages/forge-ts' && npm run typecheck)"
  log_ok "Typecheck passed"

  log_step "Building @forge-suite/ts..."
  run_cmd "(cd '$REPO_ROOT/packages/forge-ts' && npm run build)"
  log_ok "TypeScript build complete"

  if $DRY_RUN; then
    log_warn "[dry-run] Skipping: npm publish --access public"
  else
    log_step "Publishing @forge-suite/ts@$NEW_VERSION to npm..."
    run_cmd "(cd '$REPO_ROOT/packages/forge-ts' && npm publish --access public)"
    log_ok "@forge-suite/ts@$NEW_VERSION published to npm"

    # Small pause to let the registry propagate before forge-webapp install
    log_step "Waiting 10 s for npm registry propagation..."
    sleep 10
    log_ok "Done waiting"
  fi

  log_phase_done 3
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4 — Build forge-webapp frontend → copy to webapp_dist/
# ═══════════════════════════════════════════════════════════════════════════════
CURRENT_PHASE=4
WEBAPP_APP_DIR="$REPO_ROOT/packages/forge-suite/forge-webapp/apps/forge-webapp"
WEBAPP_DIST_DST="$REPO_ROOT/packages/forge-suite/forge_suite/webapp_dist"

if [ "$FROM_PHASE" -le 4 ]; then
  log_header 4 "Build forge-webapp frontend"

  log_step "Installing forge-webapp npm dependencies..."
  log_info "  (resolves @forge-suite/ts from local npm workspace)"
  run_cmd "(cd '$WEBAPP_APP_DIR' && npm install)"
  log_ok "Dependencies installed"

  log_step "Building forge-webapp (vite)..."
  run_cmd "(cd '$WEBAPP_APP_DIR' && npm run build)"
  log_ok "Vite build complete"

  log_step "Copying dist → forge_suite/webapp_dist/..."
  rm -rf "$WEBAPP_DIST_DST"
  cp -r "$WEBAPP_APP_DIR/dist" "$WEBAPP_DIST_DST"
  ASSET_COUNT=$(find "$WEBAPP_DIST_DST" -type f | wc -l | tr -d ' ')
  DIST_SIZE=$(du -sh "$WEBAPP_DIST_DST" | cut -f1)
  log_ok "Copied $ASSET_COUNT files ($DIST_SIZE) to forge_suite/webapp_dist/"

  log_phase_done 4
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 5 — Build Python wheels
# ═══════════════════════════════════════════════════════════════════════════════
CURRENT_PHASE=5
if [ "$FROM_PHASE" -le 5 ]; then
  log_header 5 "Build Python wheels"

  # Bundle docs into forge-py
  log_step "Bundling docs into forge-py package..."
  rm -rf "$REPO_ROOT/packages/forge-py/forge/docs"
  mkdir -p "$REPO_ROOT/packages/forge-py/forge/docs"
  cp "$REPO_ROOT/docs/"*.md "$REPO_ROOT/packages/forge-py/forge/docs/"
  DOC_COUNT=$(ls "$REPO_ROOT/packages/forge-py/forge/docs/" | wc -l | tr -d ' ')
  log_ok "Bundled $DOC_COUNT docs files"

  for pkg in forge-py forge-suite; do
    PKG_DIR="$REPO_ROOT/packages/$pkg"
    log_step "Building $pkg wheel..."
    run_cmd "(cd '$PKG_DIR' && rm -rf dist && '$PYTHON' -m build --wheel)"

    # Show what was built
    WHEEL=$(ls "$PKG_DIR/dist/"*.whl 2>/dev/null | head -1)
    if [[ -z "$WHEEL" ]]; then
      die "No .whl file found in $PKG_DIR/dist/ after build"
    fi
    WHEEL_SIZE=$(du -sh "$WHEEL" | cut -f1)
    WHEEL_NAME=$(basename "$WHEEL")
    log_ok "Built: $WHEEL_NAME ($WHEEL_SIZE)"

    # For forge-suite: verify webapp_dist was packaged
    if [[ "$pkg" == "forge-suite" ]]; then
      log_step "Verifying webapp_dist is included in forge-suite wheel..."
      DIST_FILE_COUNT=$("$PYTHON" -c "
import zipfile
with zipfile.ZipFile('$WHEEL') as z:
    n = sum(1 for f in z.namelist() if 'webapp_dist' in f)
    print(n)
")
      if [[ "$DIST_FILE_COUNT" -eq 0 ]]; then
        die "webapp_dist NOT found inside $WHEEL_NAME — check pyproject.toml force-include"
      fi
      log_ok "webapp_dist present in wheel ($DIST_FILE_COUNT files)"
    fi

    # twine check
    log_step "Running twine check on $pkg dist..."
    run_cmd "'$TWINE' check '$PKG_DIR/dist/'*"
    log_ok "twine check passed"
  done

  log_phase_done 5
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 6 — Publish to PyPI
# ═══════════════════════════════════════════════════════════════════════════════
CURRENT_PHASE=6
if [ "$FROM_PHASE" -le 6 ]; then
  log_header 6 "Publish to PyPI"

  for pkg in forge-py forge-suite; do
    PKG_DIR="$REPO_ROOT/packages/$pkg"
    WHEEL=$(ls "$PKG_DIR/dist/"*.whl 2>/dev/null | head -1)
    if [[ -z "$WHEEL" ]]; then
      die "No wheel found in $PKG_DIR/dist/ — did Phase 5 complete?"
    fi

    if $DRY_RUN; then
      log_warn "[dry-run] Skipping upload of $(basename "$WHEEL")"
    else
      log_step "Uploading $pkg@$NEW_VERSION to PyPI..."
      run_cmd "'$TWINE' upload '$PKG_DIR/dist/'*"
      log_ok "$(basename "$WHEEL") uploaded to PyPI"
    fi
  done

  if ! $DRY_RUN; then
    log_info ""
    log_info "  PyPI links:"
    log_info "    https://pypi.org/project/forge-framework/$NEW_VERSION/"
    log_info "    https://pypi.org/project/forge-suite/$NEW_VERSION/"
  fi

  log_phase_done 6
fi

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 7 — Git commit, tag, push
# ═══════════════════════════════════════════════════════════════════════════════
CURRENT_PHASE=7
if [ "$FROM_PHASE" -le 7 ]; then
  log_header 7 "Git commit, tag, push"

  cd "$REPO_ROOT"

  log_step "Staging version and build-artifact files..."
  run_cmd "git add \
    packages/forge-py/forge/version.py \
    packages/forge-py/pyproject.toml \
    packages/forge-ts/package.json \
    packages/forge-suite/pyproject.toml \
    packages/forge-suite/forge_suite/cli.py"

  # Stage any package-lock.json files updated by npm install/build steps
  while IFS= read -r lockfile; do
    run_cmd "git add '$lockfile'"
  done < <(git diff --name-only | grep 'package-lock\.json' || true)

  # Stage any other tracked files that changed (e.g. dev/ scripts)
  STAGED=$(git diff --cached --name-only)
  log_info "  Staged files:"
  echo "$STAGED" | while read -r f; do log_info "    $f"; done

  # Also check for other unstaged tracked changes
  UNSTAGED=$(git diff --name-only)
  if [[ -n "$UNSTAGED" ]]; then
    log_warn "Other unstaged changes not included in this commit:"
    echo "$UNSTAGED" | while read -r f; do log_warn "    $f"; done
  fi

  if $DRY_RUN; then
    log_warn "[dry-run] Skipping: git commit, git tag, git push"
  else
    log_step "Creating release commit..."
    run_cmd "git commit -m 'chore: release v$NEW_VERSION'"
    log_ok "Committed"

    log_step "Tagging v$NEW_VERSION..."
    run_cmd "git tag v$NEW_VERSION"
    log_ok "Tagged v$NEW_VERSION"

    log_step "Pushing commit and tag to origin..."
    run_cmd "git push origin HEAD"
    run_cmd "git push origin v$NEW_VERSION"
    log_ok "Pushed"
  fi

  log_phase_done 7
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Dry-run cleanup — revert version bumps so the tree is clean afterward
# ═══════════════════════════════════════════════════════════════════════════════
if $DRY_RUN; then
  echo -e "\n${C}  Reverting version file changes (dry-run cleanup)…${X}"
  git checkout -- \
    packages/forge-py/forge/version.py \
    packages/forge-py/pyproject.toml \
    packages/forge-ts/package.json \
    packages/forge-suite/pyproject.toml
  rm -f "$STATE_FILE"
  echo -e "${G}     ✓  Version files restored to v$PY_VER — working tree clean${X}"
  echo -e "${G}     ✓  To publish for real, run:  ${BOLD}bash dev/release.sh $BUMP${X}"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
echo -e "\n${BOLD}${G}══════════════════════════════════════════════════════════════════════${X}"
if $DRY_RUN; then
  echo -e "${BOLD}${Y}  DRY-RUN COMPLETE — v$NEW_VERSION was built but NOT published${X}"
else
  echo -e "${BOLD}${G}  RELEASE COMPLETE — v$NEW_VERSION${X}"
fi
echo -e "${BOLD}${G}══════════════════════════════════════════════════════════════════════${X}"
echo -e "  Finished: $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "  Log file: $LOG_FILE"
if ! $DRY_RUN; then
  echo -e "\n  Published:"
  echo -e "    npm  : https://www.npmjs.com/package/@forge-suite/ts/v/$NEW_VERSION"
  echo -e "    PyPI : https://pypi.org/project/forge-framework/$NEW_VERSION/"
  echo -e "    PyPI : https://pypi.org/project/forge-suite/$NEW_VERSION/"
  echo -e "    Git  : tag v$NEW_VERSION pushed to origin"
fi
echo ""

# Clean up state file on successful real release
if ! $DRY_RUN; then
  rm -f "$STATE_FILE"
fi
