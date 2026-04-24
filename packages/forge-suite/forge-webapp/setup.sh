#!/usr/bin/env bash
# End-to-end setup for the forge-webapp management UI.
# Run from the packages/forge-suite/forge-webapp/ directory.
set -euo pipefail

echo "=== forge-webapp: setup ==="

echo "-- Installing forge-framework..."
pip install -e ../../../packages/forge-py --quiet

echo "-- Provisioning datasets and patching models/models.py..."
python3 - <<'PYEOF'
import sys, uuid, re
sys.path.insert(0, ".")
from forge.storage.engine import StorageEngine
from pathlib import Path
import pandas as pd

models_path = Path("models/models.py")
source = models_path.read_text()
e = StorageEngine(Path(".forge"))

pairs = [
    ("forge_projects",  "REPLACE_FORGE_PROJECT_UUID",  "FORGE_PROJECT_DATASET_ID"),
    ("artifact_stamps", "REPLACE_ARTIFACT_STAMP_UUID",  "ARTIFACT_STAMP_DATASET_ID"),
    ("pipelines",       "REPLACE_PIPELINE_UUID",        "PIPELINE_DATASET_ID"),
    ("pipeline_runs",   "REPLACE_PIPELINE_RUN_UUID",    "PIPELINE_RUN_DATASET_ID"),
    ("object_types",    "REPLACE_OBJECT_TYPE_UUID",     "OBJECT_TYPE_DATASET_ID"),
    ("endpoint_repos",  "REPLACE_ENDPOINT_REPO_UUID",   "ENDPOINT_REPO_DATASET_ID"),
    ("endpoints",       "REPLACE_ENDPOINT_UUID",        "ENDPOINT_DATASET_ID"),
    ("apps",            "REPLACE_APP_UUID",             "APP_DATASET_ID"),
    ("project_files",   "REPLACE_PROJECT_FILE_UUID",    "PROJECT_FILE_DATASET_ID"),
]

for dataset_name, placeholder, var_name in pairs:
    if placeholder in source:
        # First run: generate a new UUID and patch the placeholder
        uid = str(uuid.uuid4())
        source = source.replace(placeholder, uid)
    else:
        # Re-run: extract the existing UUID already written into models.py
        m = re.search(rf'{var_name}\s*=\s*"([^"]+)"', source)
        uid = m.group(1) if m else str(uuid.uuid4())

    if e.get_dataset(uid) is None:
        e.write_dataset(uid, pd.DataFrame())
        print(f"  {dataset_name}: {uid} (new)")
    else:
        print(f"  {dataset_name}: {uid} (existing)")

models_path.write_text(source)
print("models/models.py checked.")
PYEOF

echo "-- Building models..."
forge model build

echo "-- Building endpoints..."
forge endpoint build

echo ""
echo "=== Setup complete ==="
echo "Start the dev server:  forge dev serve"
echo "Start the app:         cd apps/forge-webapp && npm install && npm run dev"
