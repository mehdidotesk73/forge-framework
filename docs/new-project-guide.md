# Building a New Forge Project

This guide walks you through creating a Forge project from scratch — from an empty directory to a running full-stack data application with pipelines, models, endpoints, and a React UI.

---

## Quick-start — complete CLI sequence

```bash
# 1. Scaffold and enter the project
forge init my-project
cd my-project

# 2. Write a pipeline that ingests your source data (see section 2 below)
#    then run it to produce the output dataset
forge pipeline run ingest_prices

# 3. Build model schemas + generate Python and TypeScript SDKs
forge model build

# 4. Build the endpoint call-form descriptor registry
forge endpoint build

# 5. Start the Forge backend (FastAPI on :8000)
forge dev serve

# 6. (In a separate terminal) Start your React app
cd apps/my-app && npm install && npm run dev
```

Each step is explained in detail in the sections below. Dataset UUIDs are the only manual wiring — you assign them once when writing your pipeline and model definitions.

---

## Prerequisites

- `forge-framework` installed: `pip install forge-framework` (or `pip install -e packages/forge-py` from the monorepo)
- `@forge-suite/ts` available via your workspace (or `npm install @forge-suite/ts`)
- Node 18+, Python 3.11+

---

## 1. Initialise the project

```bash
forge init my-project
cd my-project
```

This creates the full scaffold:

```
my-project/
  forge.toml                  # Project config — source of truth for all UUIDs
  .forge/
    data/                     # Parquet dataset files (git-ignored)
    artifacts/                # Schema JSON + endpoints.json (git-ignored)
    generated/
      python/                 # Generated Python SDK (git-ignored)
      typescript/             # Generated TypeScript SDK (git-ignored)
  pipelines/
    __init__.py
  models/
    __init__.py
  endpoint_repos/
  apps/
  data/                       # Source files (CSV, Parquet, etc.)
  files/
  .gitignore
```

---

## 2. Write a data ingestion pipeline

Data enters a Forge project through pipelines. A pipeline is a Python function that reads from a source — a local file, an external API, a database, a web feed — and writes the result as a versioned dataset. The pipeline output dataset is what models are built on top of.

**Output UUID flow** — every dataset needs a UUID assigned before the pipeline can run. Generate one and register an empty placeholder:

```python
import uuid, pandas as pd
from pathlib import Path
from forge.storage.engine import StorageEngine

output_id = str(uuid.uuid4())
print(f"Output UUID: {output_id}")   # copy this

engine = StorageEngine(Path(".forge"))
engine.write_dataset(output_id, pd.DataFrame())
```

Register it in `forge.toml` and paste the UUID into your pipeline `ForgeOutput(...)` — this is the only manual wiring step. Then run the pipeline:

```bash
forge pipeline run ingest_prices
forge dataset list                   # confirm the dataset has rows
forge dataset inspect <uuid>
```

**Loading a raw source file directly** — if you just need to register an existing CSV or Parquet file as a dataset (no transformation needed), use:

```bash
forge dataset load data/prices.csv --name raw_prices
# → prints: ID: a1b2c3d4-...
```

This is a shortcut for static source files. For anything that fetches, transforms, or schedules, write a pipeline.

---

## 3. Pipeline examples

A pipeline is a Python function decorated with `@pipeline` — it receives typed input and output handles, reads data, and writes results. It has zero knowledge of models, endpoints, or the UI.

**Ingestion pipeline — pull from a CSV on disk:**

```python
# pipelines/ingest_prices.py
import pandas as pd
from forge.pipeline import pipeline
from forge.pipeline.runner import ForgeInput, ForgeOutput

@pipeline(
    inputs={"source": ForgeInput("a1b2c3d4-YOUR-SOURCE-UUID")},
    outputs={"prices": ForgeOutput("e5f6a7b8-YOUR-OUTPUT-UUID")},
)
def run(source, prices):
    df = source.df()
    df["price_usd"] = df["close"].round(2)
    prices.write(df[["date", "symbol", "price_usd"]])
```

**Ingestion pipeline — fetch from the internet:**

```python
# pipelines/fetch_prices.py
import pandas as pd
import requests
from forge.pipeline import pipeline
from forge.pipeline.runner import ForgeOutput

@pipeline(
    outputs={"prices": ForgeOutput("e5f6a7b8-YOUR-OUTPUT-UUID")},
)
def run(prices):
    data = requests.get("https://api.example.com/prices").json()
    prices.write(pd.DataFrame(data))
```

Register the pipeline and its output dataset in `forge.toml`:

```toml
[[datasets]]
id = "e5f6a7b8-..."
name = "prices"

[[pipelines]]
display_name = "ingest_prices"
module       = "pipelines.ingest_prices"
function     = "run"
```

Run and inspect:

```bash
forge pipeline run ingest_prices
forge pipeline dag ingest_prices    # visualise inputs/outputs
forge pipeline history ingest_prices
```

**Scheduled pipelines** — add a cron schedule to `[[pipelines]]`:

```toml
[[pipelines]]
display_name = "price_pipeline"
module       = "pipelines.price_pipeline"
function     = "run"
schedule     = "0 18 * * 1-5"          # weekdays at 6 pm UTC
```

The scheduler fires automatically when the dev server is running. `forge pipeline run` always works for manual execution.

---

## 4. Define a model

A model declares a typed Python class over a dataset. `forge model build` reads the live dataset schema and emits a schema artifact plus Python and TypeScript SDKs.

```python
# models/price.py
from forge.model import forge_model, field_def

@forge_model(
    name="Price",
    mode="snapshot",                     # mutable CRUD; use "stream" for read-only
    backing_dataset="e5f6a7b8-...",      # the pipeline's output UUID
)
class Price:
    id:         str = field_def(primary_key=True)
    date:       str = field_def(label="Date")
    symbol:     str = field_def(label="Symbol")
    price_usd:  float = field_def(label="Price (USD)", format="currency")
```

Register the model in `forge.toml`:

```toml
[[models]]
class_name = "Price"
mode       = "snapshot"
module     = "models.price"
```

Build the model to generate all artifacts:

```bash
forge model build
# Creates: .forge/artifacts/Price.schema.json
#          .forge/generated/python/price.py
#          .forge/generated/typescript/Price.ts
```

**Field modes:**

| Mode | Description |
|------|-------------|
| `snapshot` | Mutable. Creates a snapshot copy on first build. Supports create/update/remove. |
| `stream` | Read-only. Points directly at the pipeline output dataset. |

**Using the generated Python SDK** (in endpoints):

```python
from forge.generated.python.price import PriceSet

prices = PriceSet.all()
price = PriceSet.get(some_id)
filtered = PriceSet.filter(symbol="BTC")
```

---

## 5. Write endpoints

Endpoints expose business logic over HTTP. They live in endpoint repos — Python packages under `endpoint_repos/`.

```python
# endpoint_repos/price_endpoints/endpoints.py
from forge.control import action_endpoint, computed_attribute_endpoint

UPDATE_PRICE_ID = "aaaaaaaa-0001-0000-0000-000000000000"
CHANGE_PCT_ID   = "aaaaaaaa-0002-0000-0000-000000000000"

@action_endpoint(
    endpoint_id=UPDATE_PRICE_ID,
    name="update_price",
    description="Update the USD value of a price record",
    params=[
        {"name": "id",        "type": "string", "required": True},
        {"name": "price_usd", "type": "number", "required": True},
    ],
)
def update_price(id: str, price_usd: float) -> dict:
    from forge.generated.python.price import PriceSet
    price = PriceSet.get(id)
    if not price:
        return {"error": "not found"}
    price.price_usd = price_usd
    PriceSet.flush()
    return {"ok": True}


@computed_attribute_endpoint(
    endpoint_id=CHANGE_PCT_ID,
    name="change_pct",
    description="Calculate daily change % for a price record",
    params=[{"name": "id", "type": "string", "required": True}],
)
def change_pct(id: str) -> dict:
    from forge.generated.python.price import PriceSet
    price = PriceSet.get(id)
    return {"value": price.price_usd * 0.03 if price else 0}
```

Register the repo in `forge.toml` and build:

```toml
[[endpoint_repos]]
module = "endpoint_repos.price_endpoints"
```

```bash
forge endpoint build
# Creates: .forge/artifacts/endpoints.json
```

**Endpoint ID rules:**
- IDs must be stable UUIDs — never regenerate or reassign them.
- The view layer references endpoints by ID (string constant), never by name.
- Assign them once in source and leave them forever.

---

## 6. Build a React app

```bash
forge app create my-dashboard --port 5177
```

This scaffolds `apps/my-dashboard/` as a Vite+React project pre-wired to `@forge-suite/ts`.

```tsx
// apps/my-dashboard/src/App.tsx
import { ObjectTable, loadPriceSet } from "@forge-suite/ts";

const UPDATE_PRICE_ID = "aaaaaaaa-0001-0000-0000-000000000000";
const CHANGE_PCT_ID   = "aaaaaaaa-0002-0000-0000-000000000000";

export default function App() {
  const prices = loadPriceSet();

  return (
    <ObjectTable
      data={prices}
      columns={["date", "symbol", "price_usd"]}
      computedColumns={[
        { key: "change_pct", label: "Change %", endpointId: CHANGE_PCT_ID },
      ]}
      interactions={[
        {
          label: "Edit Price",
          endpointId: UPDATE_PRICE_ID,
          kind: "action",
        },
      ]}
    />
  );
}
```

**View layer rules:**
- Import only from `@forge-suite/ts` and your generated TypeScript SDK (`load<Name>Set`).
- Reference endpoints by UUID string constant — never construct URLs by hand.
- Never import Python model classes or call `fetch()` directly.

---

## 7. Build sequence summary

Every time you change models or endpoints, re-run the build commands in order:

```bash
forge model build       # reads datasets → emits schema + SDK
forge endpoint build    # reads endpoint repos → emits endpoints.json
```

Then restart the dev server for changes to take effect.

---

## 8. Run the development server

```bash
forge dev serve                    # FastAPI on :8000
forge dev serve --port 8001        # custom port
forge dev serve --app my-dashboard # serve a specific app on its declared port
```

In a separate terminal, start the React app:

```bash
cd apps/my-dashboard
npm install
npm run dev
# → http://localhost:5177
```

Alternatively, use the generated launch script:

```bash
bash my-dashboard.command
```

---

## 9. Useful CLI commands

```bash
forge dataset list                          # all registered datasets
forge dataset inspect <uuid>                # schema + row count
forge pipeline run <name>                   # run a pipeline manually
forge pipeline dag <name>                   # print input/output graph
forge pipeline history <name>               # list past runs
forge model build                           # rebuild all model artifacts
forge model reinitialize <ClassName>        # reset snapshot dataset from source
forge endpoint build                        # rebuild endpoints.json
forge dev serve                             # start backend
forge version                               # installed framework version
forge upgrade                               # run pending migrations
```

---

## Layer isolation cheatsheet

When something breaks, check which layer is involved and what it is (and is not) allowed to import:

| Layer | Can import | Cannot import |
|-------|-----------|---------------|
| Pipeline | pandas, DuckDB, stdlib | Model classes, endpoints, widgets |
| Model | Generated Python SDK, StorageEngine | Endpoints, widgets |
| Control | Model classes, generated Python SDK | Widgets, raw HTTP, view code |
| View | Generated TS SDK, endpoint ID strings | Python, `fetch()`, model classes |

Cross-layer data flows **only through build artifacts** (dataset UUID → schema JSON → generated SDK → TypeScript interface → rendered widget). Never skip a layer.
