#!/usr/bin/env bash
# End-to-end setup script for the student-manager example.
# Run from the examples/student-manager/ directory.
set -euo pipefail

echo "=== student-manager: full setup ==="

# 1. Install the forge Python package (from monorepo)
echo "-- Installing forge-framework..."
pip install -e ../../packages/forge-py --quiet

# 2. Load raw datasets and capture their UUIDs
echo "-- Loading datasets..."
STUDENTS_RAW=$(forge dataset load data/students.csv --name students_raw 2>&1 | grep "ID:" | awk '{print $2}')
GRADES_RAW=$(forge dataset load data/grades.csv --name grades_raw 2>&1 | grep "ID:" | awk '{print $2}')
echo "  students_raw: $STUDENTS_RAW"
echo "  grades_raw:   $GRADES_RAW"

# 3. Provision output dataset UUIDs
STUDENTS_OUT=$(python3 -c "import uuid; print(uuid.uuid4())")
GRADES_OUT=$(python3 -c "import uuid; print(uuid.uuid4())")
COURSES_OUT=$(python3 -c "import uuid; print(uuid.uuid4())")
echo "  students_out: $STUDENTS_OUT"
echo "  grades_out:   $GRADES_OUT"
echo "  courses_out:  $COURSES_OUT"

# 4. Patch pipeline and model files with real UUIDs
sed -i.bak \
  -e "s/REPLACE_WITH_STUDENTS_RAW_UUID/$STUDENTS_RAW/g" \
  -e "s/REPLACE_WITH_GRADES_RAW_UUID/$GRADES_RAW/g" \
  -e "s/REPLACE_WITH_STUDENTS_OUT_UUID/$STUDENTS_OUT/g" \
  -e "s/REPLACE_WITH_GRADES_OUT_UUID/$GRADES_OUT/g" \
  -e "s/REPLACE_WITH_COURSES_OUT_UUID/$COURSES_OUT/g" \
  pipelines/student_pipeline.py \
  models/student.py \
  models/grade.py

# 5. Provision empty output datasets in DuckDB (so pipeline can write to them)
python3 - <<EOF
import sys; sys.path.insert(0, ".")
from forge.storage.engine import StorageEngine
from pathlib import Path
import pandas as pd
e = StorageEngine(Path(".forge"))
for uid, name in [
    ("$STUDENTS_OUT", "students"),
    ("$GRADES_OUT", "grades"),
    ("$COURSES_OUT", "courses"),
]:
    df = pd.DataFrame()
    e.write_dataset(uid, df)
    # Register under the correct name
    m = e.get_dataset(uid)
    if m:
        m.name = name
        e.register_dataset(m)
print("Output datasets provisioned.")
EOF

# 6. Register output datasets in forge.toml
python3 - <<EOF
import sys; sys.path.insert(0, ".")
import sys
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

datasets = raw.get("datasets", [])
for uid, name in [
    ("$STUDENTS_RAW", "students_raw"),
    ("$GRADES_RAW", "grades_raw"),
    ("$STUDENTS_OUT", "students"),
    ("$GRADES_OUT", "grades"),
    ("$COURSES_OUT", "courses"),
]:
    meta = e.get_dataset(uid)
    if meta and not any(d.get("id") == uid for d in datasets):
        datasets.append({"id": uid, "name": name, "path": meta.parquet_path})

raw["datasets"] = datasets
try:
    import tomli_w
    with open(config_path, "wb") as f:
        tomli_w.dump(raw, f)
    print("forge.toml updated with dataset IDs.")
except ImportError:
    print("tomli_w not available; forge.toml dataset section not updated.")
EOF

# 7. Run the pipeline
echo "-- Running student_pipeline..."
forge pipeline run student_pipeline

# 8. Build models
echo "-- Building models..."
forge model build

# 9. Build endpoints
echo "-- Building endpoints..."
forge endpoint build

echo ""
echo "=== Setup complete ==="
echo "Start the dev server: forge dev serve"
echo "Start the app:        cd apps/student-manager && npm install && npm run dev"
echo "Start analytics app:  cd apps/analytics && npm install && npm run dev"
