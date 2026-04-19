#!/usr/bin/env bash
# Publish forge-framework packages to npm and PyPI.
# Usage: bash release.sh [--dry-run]
#
# Prerequisites (first time only):
#   npm login
#   pip install build twine
#   twine login  (or set TWINE_USERNAME / TWINE_PASSWORD env vars)
set -euo pipefail

DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
  echo "=== DRY RUN — no packages will be published ==="
fi

# ── Version check ─────────────────────────────────────────────────────────────
PY_VER=$(python3 -c "import re; print(re.search(r'\"(.+?)\"', open('packages/forge-py/forge/version.py').read()).group(1))")
TS_VER=$(python3 -c "import json; print(json.load(open('packages/forge-ts/package.json'))['version'])")
SUITE_VER=$(python3 -c "import re; print(re.search(r'^version = \"(.+?)\"', open('packages/forge-suite/pyproject.toml').read(), re.M).group(1))")

echo "forge-py:    $PY_VER"
echo "forge-ts:    $TS_VER"
echo "forge-suite: $SUITE_VER"

if [[ "$PY_VER" != "$TS_VER" || "$PY_VER" != "$SUITE_VER" ]]; then
  echo "ERROR: version mismatch — all three packages must be on the same version before releasing."
  exit 1
fi

VERSION="$PY_VER"
echo ""
echo "Releasing v$VERSION"
echo ""

# ── TypeScript — build then publish to npm ─────────────────────────────────
echo "-- Building @forge-framework/ts..."
(cd packages/forge-ts && npm run build)

if $DRY_RUN; then
  echo "-- [dry-run] would run: npm publish --access public (in packages/forge-ts)"
else
  echo "-- Publishing @forge-framework/ts@$VERSION to npm..."
  (cd packages/forge-ts && npm publish --access public)
fi

# ── forge-webapp — pre-build frontend into forge_suite/webapp_dist/ ──────────
echo "-- Building forge-webapp frontend..."
(cd packages/forge-suite/forge-webapp/apps/forge-webapp && npm run build)
rm -rf packages/forge-suite/forge_suite/webapp_dist
cp -r packages/forge-suite/forge-webapp/apps/forge-webapp/dist \
      packages/forge-suite/forge_suite/webapp_dist

# ── Python — build then upload to PyPI ────────────────────────────────────
for pkg in forge-py forge-suite; do
  echo "-- Building $pkg..."
  (cd "packages/$pkg" && rm -rf dist && python3 -m build --quiet)

  if $DRY_RUN; then
    echo "-- [dry-run] would run: twine upload dist/* (in packages/$pkg)"
  else
    echo "-- Uploading $pkg@$VERSION to PyPI..."
    (cd "packages/$pkg" && twine upload dist/*)
  fi
done

echo ""
echo "=== Released v$VERSION ==="
