#!/usr/bin/env bash
# End-to-end setup for the forge-webapp management UI.
# Run from the packages/forge-suite/forge-webapp/ directory.
set -euo pipefail

echo "=== forge-webapp: setup ==="

echo "-- Installing forge-framework..."
pip install -e ../../../packages/forge-py --quiet

echo "-- Provisioning datasets and patching models/models.py..."
python3 - <<'PYEOF'
import sys, uuid
sys.path.insert(0, ".")
from forge.storage.engine import StorageEngine
from pathlib import Path
import pandas as pd

e = StorageEngine(Path(".forge"))
names = [
    ("forge_projects",  "REPLACE_FORGE_PROJECT_UUID"),
    ("artifact_stamps", "REPLACE_ARTIFACT_STAMP_UUID"),
    ("pipelines",       "REPLACE_PIPELINE_UUID"),
    ("pipeline_runs",   "REPLACE_PIPELINE_RUN_UUID"),
    ("object_types",    "REPLACE_OBJECT_TYPE_UUID"),
    ("endpoint_repos",  "REPLACE_ENDPOINT_REPO_UUID"),
    ("endpoints",       "REPLACE_ENDPOINT_UUID"),
    ("apps",            "REPLACE_APP_UUID"),
    ("project_files",   "REPLACE_PROJECT_FILE_UUID"),
]

models_path = Path("models/models.py")
source = models_path.read_text()

for dataset_name, placeholder in names:
    uid = str(uuid.uuid4())
    e.write_dataset(uid, pd.DataFrame())
    print(f"  {dataset_name}: {uid}")
    source = source.replace(placeholder, uid)

models_path.write_text(source)
print("models/models.py patched.")
PYEOF

echo "-- Building models..."
forge model build

echo "-- Building endpoints..."
forge endpoint build

echo ""
echo "=== Setup complete ==="
echo "Start the dev server:  forge dev serve"
echo "Start the app:         cd apps/forge-webapp && npm install && npm run dev"
