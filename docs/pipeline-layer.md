# Forge — Pipeline Layer Developer Guide

## Purpose

The Pipeline layer is responsible for **acquiring, transforming, and writing datasets**. It is the lowest layer in the Forge stack: it has zero knowledge of model classes, endpoints, or UI widgets. Its only outputs are dataset UUIDs (Parquet files written through the StorageEngine).

A pipeline is a pure data-processing function decorated with `@pipeline`. It receives typed input and output handles, reads data, transforms it, and writes results back.

---

## Core Concepts

### InputHandle

Provides read access to a dataset. You receive one per declared input.

```python
handle.df()        # → pandas DataFrame (full scan)
handle.relation()  # → DuckDB Relation (use for SQL queries on large data)
```

Use `relation()` when you want to push filtering/aggregation into DuckDB rather than loading the whole dataset into memory.

### OutputHandle

Provides write access to a dataset. You receive one per declared output.

```python
handle.write(data)  # accepts: pandas DataFrame, DuckDB Relation, or PyArrow Table
```

`write()` is atomic: the dataset is fully replaced on success. If the pipeline function raises, the write does not occur and the run is marked as failed.

### Immutable Versioning

Every `write()` creates a new versioned Parquet file (`<uuid>_v<n>.parquet`). Previous versions are retained. This means pipeline outputs are fully auditable — you can always inspect what version N of a dataset looked like.

---

## Writing a Pipeline

### 1. Declare the function and decorate it

```python
# pipelines/normalize.py
import pandas as pd
from forge.pipeline import pipeline, ForgeInput, ForgeOutput

PIPELINE_ID  = "bbbbbbbb-0000-0000-0000-000000000001"
RAW_ID       = "aaaaaaaa-0000-0000-0000-000000000001"
STUDENTS_ID  = "cccccccc-0000-0000-0000-000000000001"

@pipeline(
    pipeline_id=PIPELINE_ID,
    inputs={"raw":      ForgeInput(RAW_ID)},
    outputs={"students": ForgeOutput(STUDENTS_ID)},
)
def run(inputs, outputs):
    df = inputs.raw.df()

    df["name"]   = df["name"].str.strip()
    df["email"]  = df["email"].str.lower()
    df["status"] = df["status"].fillna("active")

    outputs.students.write(df)
```

Input and output handles are accessed via `inputs.<key>` and `outputs.<key>`, where the key matches the dict key passed to `ForgeInput`/`ForgeOutput` in the decorator.

### 2. Register in forge.toml

```toml
[[pipelines]]
id           = "bbbbbbbb-0000-0000-0000-000000000001"
display_name = "normalize_students"
module       = "pipelines.normalize"
function     = "run"
```

The `id` here is the pipeline's own identity (for run history), not a dataset UUID.

### 3. Run manually

```bash
forge pipeline run normalize_students
```

---

## Dataset UUIDs

Dataset UUIDs are assigned once at `forge dataset load` time and never change. Reference them by UUID in the `@pipeline` decorator:

```bash
forge dataset load data/raw_students.csv --name raw_students
# prints: Loaded dataset raw_students → aaaaaaaa-0000-0000-0000-000000000001

forge dataset list     # show all datasets and their UUIDs
forge dataset inspect <id>  # show schema and row count
```

Never hard-code file paths in pipeline code. Always use the UUID-backed handles.

---

## Multi-Input / Multi-Output Pipelines

A pipeline can declare any number of inputs and outputs:

```python
PIPELINE_ID    = "..."
STUDENTS_ID    = "aaaa..."
COURSES_ID     = "bbbb..."
ENROLLMENTS_ID = "cccc..."
SUMMARY_ID     = "dddd..."

@pipeline(
    pipeline_id=PIPELINE_ID,
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

## Using DuckDB Relations

For large datasets or SQL-friendly transformations, use `relation()` instead of `df()`:

```python
def run(inputs, outputs):
    rel = inputs.transactions.relation()

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

`handle.relation()` returns a live DuckDB `Relation` object. You can chain DuckDB's Python API (`.filter()`, `.aggregate()`, `.join()`, `.query()`) or use `.df()` on it to materialize.

---

## Scheduled Pipelines

Add a cron schedule to `forge.toml` and the pipeline runs automatically while `forge dev serve` is running:

```toml
[[pipelines]]
id           = "..."
display_name = "daily_refresh"
module       = "pipelines.daily_refresh"
function     = "run"
schedule     = "0 6 * * *"   # 6 AM UTC every day
```

Standard cron syntax: `minute hour day-of-month month day-of-week`.

Scheduled runs are recorded in `pipeline_runs` in the DuckDB catalog. View history:

```bash
forge pipeline history daily_refresh
```

---

## Pipeline DAG

Forge infers the DAG from which pipelines consume which datasets as inputs. If pipeline B's input UUID is pipeline A's output UUID, B is downstream of A.

Visualize:

```bash
forge pipeline dag
```

This prints an ASCII tree of the dependency graph. Useful for understanding run order and debugging stale data.

---

## Run History and Status

```bash
forge pipeline history <name>    # last 50 runs: status, duration, rows written, errors
```

Each run records:
- Status: `running`, `success`, `failed`
- Duration in seconds
- Rows written per output handle
- Error message (if failed)

---

## Error Handling

If `run()` raises any exception, the pipeline runner:
1. Marks the run as `failed` with the error message
2. Does **not** write any output datasets (writes are only committed on success)
3. Does not affect previously written versions

Wrap external calls (HTTP fetches, DB queries) in try/except inside your pipeline function and raise a descriptive exception on failure so the history log is useful.

---

## Isolation Rules (AI-enforced)

The Pipeline layer must **never**:

- Import `@forge_model`-decorated classes
- Import `@action_endpoint`, `@computed_attribute_endpoint`, or `@streaming_endpoint` decorators
- Import anything from `forge.control` or `packages/forge-ts`
- Construct HTTP requests or call external APIs (unless fetching raw source data)
- Reference widget types or UI concerns

If you find yourself needing model class methods inside a pipeline, stop and reconsider the architecture. Pipelines write raw data; models provide typed access to that data for the layers above.

---

## Full Example: Stock Price Normalization

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
    schedule="*/15 * * * *",  # every 15 minutes
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
[[pipelines]]
id           = "33333333-0000-0000-0000-000000000001"
display_name = "normalize_prices"
module       = "pipelines.normalize_prices"
function     = "run"
schedule     = "*/15 * * * *"
```
