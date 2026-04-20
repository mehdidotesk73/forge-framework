# Forge — Pipeline Layer

## What the Pipeline Layer Does

The Pipeline layer is the data acquisition and transformation backbone of a Forge project. Pipelines are the **only** place in the stack that read from external sources (files, APIs, databases) and write raw datasets. Everything above — models, endpoints, and UI — builds on the datasets that pipelines produce.

A pipeline is a Python function decorated with `@pipeline`. It receives typed input handles (for reading) and output handles (for writing), transforms data however it needs to, and writes the results. The pipeline has zero knowledge of model classes, endpoint logic, or UI widgets.

**When to write a pipeline:**
- Ingesting data from a CSV, Parquet, or JSON file on disk
- Fetching data from an external HTTP API or database
- Transforming or joining one or more existing datasets into a new one
- Any computation that needs to run on a schedule

**When NOT to use a pipeline:** if you need to read data in an endpoint to compute a derived value, use a computed column endpoint instead. Pipelines are for bulk data movements, not request-time computations.

---

## Core Concepts

### Dataset UUIDs

Every dataset in a Forge project is identified by a UUID. Dataset UUIDs are assigned once — at `forge dataset load` time or when the empty dataset is first registered — and never change. A pipeline declares which datasets it reads from and writes to using these UUIDs.

```bash
forge dataset load data/prices.csv --name raw_prices
# Loaded dataset raw_prices → 11111111-0000-0000-0000-000000000001

forge dataset list              # show all datasets and their UUIDs
forge dataset inspect <uuid>    # schema + row count
```

### Immutable Versioning

Every `write()` call creates a new versioned Parquet file: `<uuid>_v<n>.parquet`. Previous versions are retained. Pipeline output is fully auditable — you can always inspect what version N of a dataset looked like.

### ForgeInput and ForgeOutput

`ForgeInput(uuid)` declares a dataset the pipeline reads from. `ForgeOutput(uuid)` declares a dataset the pipeline writes to. Handles are accessed via `inputs.<key>` and `outputs.<key>` using the dict keys you give them in the decorator.

---

## Writing a Pipeline

### Step 1 — Register the output dataset

Before running a pipeline for the first time, the output dataset must exist. If you are creating a brand-new dataset (not loading an existing file), register an empty placeholder:

```python
import uuid, pandas as pd
from pathlib import Path
from forge.storage.engine import StorageEngine

output_id = str(uuid.uuid4())
print(f"Output UUID: {output_id}")   # copy this into your pipeline

engine = StorageEngine(Path(".forge"))
engine.write_dataset(output_id, pd.DataFrame())
```

Or, for a source file you want to register directly as a dataset with no transformation:

```bash
forge dataset load data/prices.csv --name raw_prices
# → prints UUID; use it as SOURCE_ID or OUTPUT_ID in your pipeline
```

### Step 2 — Write the pipeline function

```python
# pipelines/normalize_prices.py
import pandas as pd
from forge.pipeline import pipeline, ForgeInput, ForgeOutput

PIPELINE_ID = "33333333-0000-0000-0000-000000000001"   # pipeline's own run-history ID
RAW_ID      = "11111111-0000-0000-0000-000000000001"   # input dataset UUID
PRICES_ID   = "22222222-0000-0000-0000-000000000001"   # output dataset UUID

@pipeline(
    pipeline_id=PIPELINE_ID,
    inputs={"raw":    ForgeInput(RAW_ID)},
    outputs={"prices": ForgeOutput(PRICES_ID)},
)
def run(inputs, outputs):
    df = inputs.raw.df()

    df = df.rename(columns={"Close": "close", "Volume": "volume", "Date": "ts"})
    df["ts"]     = pd.to_datetime(df["ts"])
    df["close"]  = df["close"].astype(float).round(4)
    df["volume"] = df["volume"].astype(int)
    df           = df.dropna(subset=["close"])
    df           = df.sort_values("ts").reset_index(drop=True)

    outputs.prices.write(df)
```

### Step 3 — Register in forge.toml

```toml
[[pipelines]]
id           = "33333333-0000-0000-0000-000000000001"
display_name = "normalize_prices"
module       = "pipelines.normalize_prices"
function     = "run"
```

The `id` field is the pipeline's own identity (used for run history), not a dataset UUID.

### Step 4 — Run it

```bash
forge pipeline run normalize_prices
forge dataset inspect 22222222-0000-0000-0000-000000000001   # confirm rows
```

---

## @pipeline Decorator Reference

```python
@pipeline(
    inputs:      dict[str, ForgeInput],   # required
    outputs:     dict[str, ForgeOutput],  # required
    pipeline_id: str | None = None,       # optional; used for run history
    name:        str | None = None,       # optional; defaults to function name
    schedule:    str | None = None,       # optional; cron string
)
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `inputs` | yes | Dict of key → `ForgeInput(dataset_uuid)` |
| `outputs` | yes | Dict of key → `ForgeOutput(dataset_uuid)` |
| `pipeline_id` | no | Stable UUID for run history tracking; assign once and keep forever |
| `name` | no | Display name; defaults to the function name |
| `schedule` | no | Cron expression for automatic scheduling |

---

## Reading Data

### Full DataFrame scan

```python
df = inputs.my_source.df()
# Returns: pandas DataFrame with all rows
```

Use `df()` for small-to-medium datasets, simple transformations, or joins.

### DuckDB Relation (lazy SQL)

```python
rel = inputs.transactions.relation()
# Returns: DuckDB Relation — no data loaded yet

result = rel.query(
    "transactions",
    """
    SELECT
        date_trunc('day', ts) AS day,
        SUM(amount)           AS total,
        COUNT(*)              AS count
    FROM transactions
    GROUP BY 1
    ORDER BY 1
    """
)

outputs.daily_totals.write(result)  # DuckDB Relation is accepted directly
```

Use `relation()` when you want to push filtering and aggregation into DuckDB instead of loading the whole dataset into memory. You can also chain DuckDB's Python API: `.filter()`, `.aggregate()`, `.join()`.

---

## Writing Data

```python
outputs.my_output.write(data)
# Accepts: pandas DataFrame, DuckDB Relation, or PyArrow Table
```

`write()` is atomic: the dataset is fully replaced on success. If the pipeline function raises, the write does not occur and the run is marked as failed.

---

## Multi-Input / Multi-Output Pipelines

A pipeline can declare any number of inputs and outputs:

```python
@pipeline(
    pipeline_id="...",
    inputs={
        "students": ForgeInput(STUDENTS_ID),
        "courses":  ForgeInput(COURSES_ID),
    },
    outputs={
        "enrollments": ForgeOutput(ENROLLMENTS_ID),
        "summary":     ForgeOutput(SUMMARY_ID),
    },
)
def run(inputs, outputs):
    sdf = inputs.students.df()
    cdf = inputs.courses.df()

    merged = sdf.merge(cdf, on="course_id")
    outputs.enrollments.write(merged)

    agg = merged.groupby("department")["credits"].sum().reset_index()
    outputs.summary.write(agg)
```

---

## Pipelines With No Inputs

Some pipelines fetch from external sources rather than reading an existing dataset. Omit `inputs` entirely:

```python
@pipeline(
    pipeline_id="...",
    outputs={"prices": ForgeOutput(OUTPUT_ID)},
)
def run(inputs, outputs):
    import requests
    data = requests.get("https://api.example.com/prices").json()
    outputs.prices.write(pd.DataFrame(data))
```

---

## Scheduled Pipelines

Add a cron schedule to run automatically while `forge dev serve` is running:

```toml
[[pipelines]]
id           = "..."
display_name = "daily_refresh"
module       = "pipelines.daily_refresh"
function     = "run"
schedule     = "0 6 * * *"          # 6 AM UTC every day
```

Or set it in the decorator (both are supported; `forge.toml` takes precedence):

```python
@pipeline(
    pipeline_id="...",
    outputs={"data": ForgeOutput(OUTPUT_ID)},
    schedule="*/15 * * * *",    # every 15 minutes
)
def run(inputs, outputs):
    ...
```

**Standard cron syntax:** `minute hour day-of-month month day-of-week`

Common examples:
| Schedule | Meaning |
|----------|---------|
| `*/15 * * * *` | Every 15 minutes |
| `0 6 * * *` | Daily at 6 AM UTC |
| `0 18 * * 1-5` | Weekdays at 6 PM UTC |
| `0 0 * * 0` | Weekly, Sunday midnight |

Manual execution always works regardless of schedule:

```bash
forge pipeline run daily_refresh
```

---

## Pipeline DAG

Forge infers the dependency graph from which pipelines consume which datasets as inputs. If pipeline B's input UUID matches pipeline A's output UUID, B is downstream of A.

```bash
forge pipeline dag                      # print full DAG
forge pipeline dag normalize_prices     # print subtree rooted at this pipeline
```

---

## Run History

```bash
forge pipeline history normalize_prices    # last 50 runs
```

Each run records:
- Status: `running`, `success`, `failed`
- Duration in seconds
- Rows written per output handle
- Error message (if failed)

---

## Error Handling

If `run()` raises any exception:
1. The run is marked `failed` with the error message
2. No output datasets are written (all writes are rolled back)
3. Previously written versions are untouched

Wrap external calls (HTTP, DB) in try/except and raise descriptive exceptions so the history log is useful:

```python
def run(inputs, outputs):
    try:
        resp = requests.get("https://api.example.com/prices", timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Price API unavailable: {e}") from e

    outputs.prices.write(pd.DataFrame(resp.json()))
```

---

## Isolation Rules

A pipeline function must **never**:

- Import `@forge_model`-decorated classes from the `models/` layer
- Import `@action_endpoint` or `@computed_attribute_endpoint` decorators
- Import anything from `forge.control` or `packages/forge-ts`
- Reference widget types or UI concerns

If you need derived values at request time (not at pipeline run time), implement a computed column endpoint instead.

---

## Full Example — Stock Price Normalization

```python
# pipelines/normalize_prices.py
import pandas as pd
from forge.pipeline import pipeline, ForgeInput, ForgeOutput

PIPELINE_ID = "33333333-0000-0000-0000-000000000001"
RAW_ID      = "11111111-0000-0000-0000-000000000001"
PRICES_ID   = "22222222-0000-0000-0000-000000000001"

@pipeline(
    pipeline_id=PIPELINE_ID,
    inputs={"raw":    ForgeInput(RAW_ID)},
    outputs={"prices": ForgeOutput(PRICES_ID)},
    schedule="*/15 * * * *",
)
def run(inputs, outputs):
    df = inputs.raw.df()

    df = df.rename(columns={"Close": "close", "Volume": "volume", "Date": "ts"})
    df["ts"]     = pd.to_datetime(df["ts"])
    df["close"]  = df["close"].astype(float).round(4)
    df["volume"] = df["volume"].astype(int)
    df           = df.dropna(subset=["close"])
    df           = df.sort_values("ts").reset_index(drop=True)

    outputs.prices.write(df)
```

```toml
# forge.toml snippet
[[datasets]]
id   = "11111111-0000-0000-0000-000000000001"
name = "raw_prices"

[[datasets]]
id   = "22222222-0000-0000-0000-000000000001"
name = "prices"

[[pipelines]]
id           = "33333333-0000-0000-0000-000000000001"
display_name = "normalize_prices"
module       = "pipelines.normalize_prices"
function     = "run"
schedule     = "*/15 * * * *"
```

---

## Full Example — Multi-Source Student Ingestion

```python
# pipelines/student_pipeline.py
from forge.pipeline import pipeline, ForgeInput, ForgeOutput

PIPELINE_ID     = "aaaaaaaa-0000-0000-0000-000000000001"
STUDENTS_RAW_ID = "a869ec83-62b1-4f5c-89ed-a72df7f98d5f"
GRADES_RAW_ID   = "9c751038-6bf0-489f-aff6-9aab30378fc5"
STUDENTS_OUT_ID = "de271075-b375-4b05-bd79-eb710df8b2c3"
GRADES_OUT_ID   = "df13b4b7-8704-4082-8822-895de3d4ec41"
COURSES_OUT_ID  = "5904497f-dbc0-4f21-a9e8-a9eec9a7c6c8"

@pipeline(
    pipeline_id=PIPELINE_ID,
    inputs={
        "students_raw": ForgeInput(STUDENTS_RAW_ID),
        "grades_raw":   ForgeInput(GRADES_RAW_ID),
    },
    outputs={
        "students": ForgeOutput(STUDENTS_OUT_ID),
        "grades":   ForgeOutput(GRADES_OUT_ID),
        "courses":  ForgeOutput(COURSES_OUT_ID),
    },
)
def run(inputs, outputs):
    students_df = inputs.students_raw.df()
    grades_df   = inputs.grades_raw.df()

    # Normalize students
    students = students_df[["id", "name", "email", "major", "enrolled_at", "status"]].copy()
    students["grade_keys"] = "[]"
    outputs.students.write(students)

    # Normalize grades
    grades = grades_df[["id", "student_id", "course", "semester", "grade", "credits"]].copy()
    outputs.grades.write(grades)

    # Derive courses from grades
    courses = (
        grades_df[["course"]]
        .drop_duplicates()
        .rename(columns={"course": "code"})
        .assign(name=lambda df: df["code"])
    )
    outputs.courses.write(courses)
```
