#!/usr/bin/env bash
# Publish forge-framework packages to npm and PyPI.
# Usage: bash release.sh [patch|minor|major|--version X.Y.Z] [--dry-run]
#
# Prerequisites (first time only):
#   npm login
#   pip install build twine
#   twine login  (or set TWINE_USERNAME / TWINE_PASSWORD env vars)
set -euo pipefail

DRY_RUN=false
BUMP=""
EXPLICIT_VERSION=""

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    patch|minor|major) BUMP="$arg" ;;
    --version) ;;  # handled below via shift
    *) EXPLICIT_VERSION="$arg" ;;
  esac
done

# Handle --version X.Y.Z
for i in "$@"; do
  if [[ "$i" == "--version" ]]; then
    shift; EXPLICIT_VERSION="${1:-}"; break
  fi
done

if $DRY_RUN; then
  echo "=== DRY RUN — no packages will be published ==="
fi

# ── Read current versions ──────────────────────────────────────────────────────
PY_VER=$(python3 -c "import re; print(re.search(r'\"(.+?)\"', open('packages/forge-py/forge/version.py').read()).group(1))")
TS_VER=$(python3 -c "import json; print(json.load(open('packages/forge-ts/package.json'))['version'])")
SUITE_VER=$(python3 -c "import re; print(re.search(r'^version = \"(.+?)\"', open('packages/forge-suite/pyproject.toml').read(), re.M).group(1))")

echo "Current versions:"
echo "  forge-py:    $PY_VER"
echo "  forge-ts:    $TS_VER"
echo "  forge-suite: $SUITE_VER"

if [[ "$PY_VER" != "$TS_VER" || "$PY_VER" != "$SUITE_VER" ]]; then
  echo "ERROR: version mismatch — all three packages must be on the same version before releasing."
  exit 1
fi

# ── Compute new version ────────────────────────────────────────────────────────
if [[ -n "$EXPLICIT_VERSION" ]]; then
  NEW_VERSION="$EXPLICIT_VERSION"
elif [[ -n "$BUMP" ]]; then
  NEW_VERSION=$(python3 - "$PY_VER" "$BUMP" <<'EOF'
import sys
parts = sys.argv[1].split(".")
major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
bump = sys.argv[2]
if bump == "major":   major += 1; minor = 0; patch = 0
elif bump == "minor": minor += 1; patch = 0
else:                 patch += 1
print(f"{major}.{minor}.{patch}")
EOF
)
else
  echo ""
  echo "Usage: bash release.sh [patch|minor|major|--version X.Y.Z] [--dry-run]"
  echo "  patch   — bump patch version (0.1.0 → 0.1.1)"
  echo "  minor   — bump minor version (0.1.0 → 0.2.0)"
  echo "  major   — bump major version (0.1.0 → 1.0.0)"
  echo "  --version X.Y.Z — set an explicit version"
  exit 1
fi

echo ""
echo "Releasing v$NEW_VERSION  (was v$PY_VER)"
echo ""

# ── Bump versions in all three packages ───────────────────────────────────────
echo "-- Updating versions to $NEW_VERSION..."

python3 - "$NEW_VERSION" <<'EOF'
import re, json, sys
v = sys.argv[1]

# forge-py/forge/version.py
path = "packages/forge-py/forge/version.py"
text = open(path).read()
text = re.sub(r'__version__ = "[^"]+"', f'__version__ = "{v}"', text)
text = re.sub(r'TS_VERSION = "[^"]+"', f'TS_VERSION = "{v}"', text)
open(path, "w").write(text)

# forge-ts/package.json
path = "packages/forge-ts/package.json"
data = json.load(open(path))
data["version"] = v
open(path, "w").write(json.dumps(data, indent=2) + "\n")

# forge-suite/pyproject.toml
path = "packages/forge-suite/pyproject.toml"
text = open(path).read()
text = re.sub(r'^version = "[^"]+"', f'version = "{v}"', text, flags=re.M)
open(path, "w").write(text)

print(f"  packages/forge-py/forge/version.py")
print(f"  packages/forge-ts/package.json")
print(f"  packages/forge-suite/pyproject.toml")
EOF

# ── Bundle docs into forge package ────────────────────────────────────────────
echo "-- Bundling docs into forge package..."
rm -rf packages/forge-py/forge/docs
mkdir -p packages/forge-py/forge/docs
cp docs/*.md packages/forge-py/forge/docs/

# ── TypeScript — build then publish to npm ─────────────────────────────────
echo "-- Building @forge-suite/ts..."
(cd packages/forge-ts && npm run build)

if $DRY_RUN; then
  echo "-- [dry-run] would run: npm publish --access public (in packages/forge-ts)"
else
  echo "-- Publishing @forge-suite/ts@$NEW_VERSION to npm..."
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
    echo "-- Uploading $pkg@$NEW_VERSION to PyPI..."
    (cd "packages/$pkg" && twine upload dist/*)
  fi
done

echo ""
echo "=== Released v$NEW_VERSION ==="
echo ""
echo "Next: commit and tag the release"
echo "  git add packages/forge-py/forge/version.py packages/forge-ts/package.json packages/forge-suite/pyproject.toml"
echo "  git commit -m \"chore: release v$NEW_VERSION\""
echo "  git tag v$NEW_VERSION"
