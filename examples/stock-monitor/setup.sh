#!/usr/bin/env bash
# End-to-end setup script for the stock-monitor example.
# Run from the examples/stock-monitor/ directory.
set -euo pipefail

echo "=== stock-monitor: full setup ==="

echo "-- Installing forge-framework..."
pip install -e ../../packages/forge-py --quiet

# Provision the prices output dataset UUID
PRICES_UUID=$(python3 -c "import uuid; print(uuid.uuid4())")
echo "  prices dataset: $PRICES_UUID"

# Patch pipeline and model files
sed -i.bak \
  -e "s/REPLACE_WITH_PRICES_DATASET_UUID/$PRICES_UUID/g" \
  pipelines/price_pipeline.py \
  models/price.py

# Provision empty dataset
python3 - <<EOF
import sys; sys.path.insert(0, ".")
from forge.storage.engine import StorageEngine
from pathlib import Path
import pandas as pd
e = StorageEngine(Path(".forge"))
e.write_dataset("$PRICES_UUID", pd.DataFrame())
m = e.get_dataset("$PRICES_UUID")
if m:
    m.name = "prices"
    e.register_dataset(m)
print("Prices dataset provisioned.")
EOF

# Register in forge.toml
python3 - <<EOF
import sys; sys.path.insert(0, ".")
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
from pathlib import Path
from forge.storage.engine import StorageEngine

e = StorageEngine(Path(".forge"))
config_path = Path("forge.toml")
with open(config_path, "rb") as f:
    raw = tomllib.load(f)

meta = e.get_dataset("$PRICES_UUID")
datasets = raw.get("datasets", [])
if meta:
    datasets.append({"id": "$PRICES_UUID", "name": "prices", "path": meta.parquet_path})
raw["datasets"] = datasets

try:
    import tomli_w
    with open(config_path, "wb") as f:
        tomli_w.dump(raw, f)
    print("forge.toml updated.")
except ImportError:
    print("tomli_w not available.")
EOF

echo "-- Running price_pipeline (fetches last year of prices)..."
forge pipeline run price_pipeline

echo "-- Building models..."
forge model build

echo "-- Building endpoints..."
forge endpoint build

echo ""
echo "=== Setup complete ==="
echo "Start dev server: forge dev serve"
echo "Start app:        cd apps/monitor && npm install && npm run dev"
echo ""
echo "The pipeline is scheduled: 0 18 * * 1-5 (weekdays at 18:00 UTC)"
echo "Trigger manually: forge pipeline run price_pipeline"
