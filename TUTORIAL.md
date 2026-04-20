# Building a Calculator App with Forge Suite

## A Complete Step-by-Step Tutorial for New Forge Developers

This tutorial walks you through building a simple calculator application with
persistent history using the Forge Framework. You will use the Forge Suite
webapp to run pipelines, build models, and build endpoints, and VS Code to
write the code in each layer.

---

## What We Are Building

A full-stack calculator app with:

- **A calculator UI** — enter two numbers, choose an operation, get a result
- **Persistent history** — every calculation is saved to a dataset
- **Delete from history** — remove individual past calculations

---

## The Four-Layer Architecture

Forge enforces a strict layered architecture. Before writing a single line of
code, understand how data flows through the system:

```
┌─────────────────────────────────────────────────────────────────┐
│  View Layer  (React)                                            │
│  Calculator form + history table                                │
├─────────────────────────────────────────────────────────────────┤
│  Control Layer  (Python endpoints)                              │
│  perform_calculation, delete_calculation                        │
├─────────────────────────────────────────────────────────────────┤
│  Model Layer  (Python model class)                              │
│  Calculation — snapshot model backed by the calculations dataset│
├─────────────────────────────────────────────────────────────────┤
│  Pipeline Layer  (Python pipeline)                              │
│  initialize_calculation_dataset — creates the empty dataset     │
└─────────────────────────────────────────────────────────────────┘
```

Data flows **upward only through build artifacts**:

1. The pipeline writes a dataset (Parquet file with a UUID)
2. The model reads that UUID from `forge.toml` and generates Python + TS SDKs
3. Endpoints import the model class and perform mutations
4. The React app imports the generated TS SDK and calls endpoints by UUID

**A single Python file can hold multiple definitions.** A pipeline module can
define several `@pipeline` functions, a model module can define several
`@forge_model` classes, and an endpoint module can define several
`@action_endpoint` functions — all in one file. Forge picks them up by their
decorators.

**`forge.toml` names are display names.** For pipelines, the `function` field
identifies which function to invoke. For models, the `class` field identifies
which class to load. Endpoint repos need only a `path` — Forge scans every
`.py` file under that path and registers all decorated endpoint functions it
finds automatically.

---

## Prerequisites

- Forge Suite is installed and running (`http://localhost:5174`)
- The **forge-calculator** project has been created in the Forge Suite webapp
- VS Code is installed
- Node.js 18+ and Python 3.11+ are installed

If Forge Suite is not yet running, run this command in the terminal:

```cmd
forge-suite serve
```

---

## Project State at the Start of This Tutorial

You have just created the **forge-calculator** project in the Forge Suite
webapp. The scaffold is registered and visible in the sidebar, but contains
only the base skeleton — no pipelines, models, endpoints, or apps have been
created yet.

### Open the project in VS Code

In the Forge Suite webapp:

1. Find **forge-calculator** in the left sidebar
2. Right-click the project → **Open in VS Code**

VS Code opens with the following base scaffold:

```
forge-calculator/
  forge.toml         ← project config (only [project] section so far)
  pipelines/
    __init__.py
  models/
    __init__.py
  endpoint_repos/    ← empty
  apps/              ← empty
  data/              ← empty
  .forge/
    forge.duckdb
    artifacts/       ← empty (nothing built yet)
    generated/       ← empty
```

Your `forge.toml` currently contains only:

```toml
[project]
name = "forge-calculator"
forge_version = <version number of the installed forge-suite package>
```

Leave VS Code open. You will switch back and forth between VS Code and the
Forge Suite webapp throughout this tutorial.

---

## How This Tutorial Is Structured

Each layer follows the same three-phase pattern:

1. **Initialize from the webapp** — use the Forge Suite UI to create the
   component stub and register it in `forge.toml`
2. **Implement in VS Code** — write the actual code
3. **Verify in the webapp** — sync, build, and test the layer before moving on

> **When something doesn't appear in the webapp:** if a layer component you
> just created doesn't show up in the UI, check that its entry exists in
> `forge.toml`. The webapp reads entirely from `forge.toml` and built
> artifacts — there is no separate registration database. Add the missing entry
> manually, then click **Sync** on the project card.

---

## LAYER 1: Pipeline — Initialize the Calculations Dataset

The pipeline layer produces datasets. `initialize_calculation_dataset` will
write an empty Parquet file with the correct column schema so the model layer
has something to read and generate SDKs from.

### Phase 1a — Initialize the pipeline from the webapp

1. Select **forge-calculator** in the sidebar
2. Click **Pipelines** in the top navigation
3. Click **New Pipeline**
4. Enter the name `initialize_calculation_dataset`
5. Click **Create**

Forge Suite creates two things automatically:

- `pipelines/initialize_calculation_dataset.py` — a stub file with a
  pre-assigned output dataset UUID
- A `[[pipelines]]` entry in `forge.toml`

Switch to VS Code. The `forge.toml` should now contain:

```toml
[project]
name = "forge-calculator"
forge_version = <version number of the installed forge-suite package>

[[pipelines]]
name = "initialize_calculation_dataset"
module = "pipelines.initialize_calculation_dataset"
function = "run"
```

The stub file at `pipelines/initialize_calculation_dataset.py` looks like:

```python
from forge.pipeline import pipeline, ForgeInput, ForgeOutput

INPUT_DATASET_ID = "ed20d365-8c1f-4c02-86fb-7cc59f9baba0"
OUTPUT_DATASET_ID = "9d66c978-adab-434c-b63c-97b95945ffbe"

@pipeline(
    inputs={
        "source": ForgeInput(INPUT_DATASET_ID),
    },
    outputs={
        "result": ForgeOutput(OUTPUT_DATASET_ID),
    },
)
def run(inputs, outputs):
    df = inputs.source.df()
    # Transform df here
    outputs.result.write(df)
```

> **Note your UUIDs.** Both `INPUT_DATASET_ID` and `OUTPUT_DATASET_ID` were
> assigned by Forge Suite when you clicked Create. `OUTPUT_DATASET_ID` is the
> stable identity of the calculations dataset. Your UUIDs may differ from the
> ones shown above — that is expected.

> **What is `INPUT_DATASET_ID` for?** The stub always generates a generic
> input/output template. For a transformation pipeline it would represent a
> source dataset to read from. For our use case we do not need it — we are
> simply bootstrapping an empty schema, not transforming existing data.
>
> **Data ingestion pipelines** (e.g. reading from a CSV file or fetching from
> a URL) also have no Forge input dataset. Instead, the pipeline accesses the
> raw source directly — via a relative path to the `files/` folder or via an
> HTTP request — and writes the result to the output dataset. Input dataset
> handles are only needed when a pipeline reads data that was previously
> produced by _another_ Forge pipeline.

### Phase 1b — Register the output dataset in forge.toml (VS Code)

The pipeline output dataset has a UUID but is not yet listed as a
`[[datasets]]` entry in `forge.toml`. Without this entry, the model layer
cannot look up the dataset by name.

Open `forge.toml` in VS Code and add the `[[datasets]]` block. Use the
`OUTPUT_DATASET_ID` value from your stub file:

```toml
[project]
name = "forge-calculator"
forge_version = <version number of the installed forge-suite package>

[[pipelines]]
id = "9d66c978-adab-434c-b63c-97b95945ffbe"
display_name = "initialize_calculation_dataset"
module = "pipelines.initialize_calculation_dataset"
function = "run"
```

> **Why is this step manual?** The webapp assigns the UUID for you but does
> not know what name to give the dataset — that is a domain decision you make.
> You name it `"calculations"` here for display in the webapp UI. The model
> references the dataset directly by UUID, not by this name.

### Phase 1c — Implement the pipeline in VS Code

The stub needs three changes: drop the unused `INPUT_DATASET_ID` and its
`inputs` dict, rename the output key and function parameter to `calculations`,
and construct the empty DataFrame with the correct column schema.

Replace the entire file:

```python
"""
Pipeline Layer — initialize_calculation_dataset

Creates an empty calculations dataset with the correct schema.
Run this once to bootstrap the storage for the Calculation model.
"""
import pandas as pd
from forge.pipeline import pipeline, ForgeOutput

OUTPUT_DATASET_ID = "9d66c978-adab-434c-b63c-97b95945ffbe"


@pipeline(
    inputs={},
    outputs={
        "calculations": ForgeOutput(OUTPUT_DATASET_ID),
    },
)
def run(inputs, outputs):
    df = pd.DataFrame({
        "id":         pd.Series([], dtype="str"),
        "operand_a":  pd.Series([], dtype="float64"),
        "operand_b":  pd.Series([], dtype="float64"),
        "operation":  pd.Series([], dtype="str"),
        "result":     pd.Series([], dtype="float64"),
        "created_at": pd.Series([], dtype="str"),
    })
    outputs.calculations.write(df)
```

**What changed and why:**

- `INPUT_DATASET_ID` and the `inputs` dict are removed entirely. An empty
  `inputs={}` tells Forge this pipeline produces data from scratch.
- `ForgeInput` is no longer imported since it is no longer used.
- The output key is renamed from `"result"` to `"calculations"`. Forge passes
  all inputs and outputs to the function as two namespace objects: `inputs`
  and `outputs`. Each key in the `outputs` dict becomes an attribute on the
  `outputs` object, so `outputs.calculations` is the write handle for the
  `"calculations"` output.
- We construct an empty DataFrame with explicit `dtype` columns so Forge can
  infer the full schema even with zero rows.
- `outputs.calculations.write(df)` commits atomically. If the function raises
  before this line, nothing is written and the run is marked as failed.

### Phase 1d — Sync, run the pipeline, and verify in the webapp

Switch back to the Forge Suite webapp.

**Sync the project** to pick up the `[[datasets]]` change:

1. Find **forge-calculator** in the sidebar
2. Click **Sync** on the project card

The `calculations` dataset should now appear in the **Datasets** panel.

**Run the pipeline:**

1. Click **Pipelines** in the top navigation
2. Find the `initialize_calculation_dataset` card
3. Click **Run**

The inline log should show:

```
Status: success
Rows written: 0
```

Zero rows is correct — the dataset starts empty. What matters is that the
column schema is now written to disk.

**Verify the schema:**

1. Click **Datasets** in the top navigation
2. Open the `calculations` dataset
3. Confirm 6 columns: `id`, `operand_a`, `operand_b`, `operation`, `result`,
   `created_at`

> **Why must the pipeline run before building the model?** The model builder
> reads the live Parquet file to infer the column schema. There is nothing to
> read until the pipeline has written at least the column headers.

---

## LAYER 2: Model — Define the Calculation Type

The model layer wraps the `calculations` dataset in a typed Python class.
Building the model generates a Python SDK for endpoints and a TypeScript SDK
for the React app.

### Phase 2a — Initialize the model from the webapp

1. Select **forge-calculator** in the sidebar
2. Click **Models** in the top navigation
3. Click **New Model**
4. Enter the name `Calculation`, select mode `snapshot`, and select the
   `calculations` backing dataset
5. Click **Create**

Forge Suite adds a `[[models]]` entry to `forge.toml` and creates the complete
model file — the backing dataset UUID and schema fields are inferred
automatically from the selected dataset. Switch to VS Code and confirm
`forge.toml` now contains:

```toml
[[models]]
class_name = "Calculation"
mode = "snapshot"
module = "models.calculation"
```

> **If this entry is missing from forge.toml:** add the block above manually,
> then click **Sync**. The model will not appear in the webapp after building
> unless this entry is present.

### Phase 2b — Review the generated model in VS Code

Open `models/calculation.py`. The webapp created it in full:

```python
"""
Model Layer - Calculation (snapshot)
Backed by dataset 9d66c978-adab-434c-b63c-97b95945ffbe.
"""
from forge.model import forge_model, field_def, ForgeSnapshotModel

DATASET_ID = "9d66c978-adab-434c-b63c-97b95945ffbe"


@forge_model(mode="snapshot", backing_dataset=DATASET_ID)
class Calculation(ForgeSnapshotModel):
    id: str = field_def(primary_key=True, display="Id")
    operand_a: float = field_def(display="Operand A")
    operand_b: float = field_def(display="Operand B")
    operation: str = field_def(display="Operation")
    result: float = field_def(display="Result")
    created_at: str = field_def(display="Created At")
```

**Key things to understand:**

- `DATASET_ID` is the raw UUID of the backing dataset — the same value as
  `OUTPUT_DATASET_ID` in the pipeline. `backing_dataset` always takes a UUID,
  never a dataset name.
- `mode="snapshot"` activates full CRUD. Forge maintains a separate mutable
  snapshot file; the pipeline output file is never modified by endpoints.
- The model file is generated in full by the webapp: the model name, backing
  dataset UUID, and schema fields are all populated automatically from the
  selected dataset. You normally do not need to edit this file.
- The primary key field is selected automatically during initialization: Forge
  looks for a column named `id` (case-insensitive), then `pk`
  (case-insensitive), then falls back to the first column. Verify the detected
  primary key is correct before building.
- **Relations must be added manually.** If a model holds a foreign key or a
  list of foreign keys to another model's primary key, you must add the
  `related(...)` declaration to the model definition yourself — the initializer
  does not infer cross-model relationships.
- `display="..."` sets the column label in the webapp's Objects panel and in
  `<ObjectTable>` widgets in the React app.
- To add more models backed by new datasets you create manually (e.g. when
  hand-coding a pipeline or writing extra endpoint functions), use the
  **Generate UUID** button in the Forge webapp UI to get a fresh UUID for the
  new `DATASET_ID` constant.

### Phase 2c — Build the model and verify in the webapp

Switch back to the Forge Suite webapp.

**Sync** the project (click **Sync** on the project card).

**Build models:**

1. Click the **Build Models** button on the project card

When the build completes, three files are generated:

- `.forge/artifacts/Calculation.schema.json`
- `.forge/generated/python/calculation.py`
- `.forge/generated/typescript/Calculation.ts`

**Verify:**

1. With the **forge-calculator** project active in the sidebar, navigate to **Model**
2. Go to the **Object Types** table, right-click the `Calculation` model, and select **Preview**.
3. The `Calculation` model table should appear with all 6 fields and their
   display labels visible. The table is empty for now, but the schema columns
   confirm the build succeeded.

> The Preview captures live data. Once endpoints are built in the next layer
> you can create, edit, and delete records directly from this table — changes
> appear immediately without a refresh.

> In VS Code, open `.forge/generated/typescript/Calculation.ts` to see the
> generated TypeScript interface and `loadCalculationSet()` function. The React
> app will import directly from this file in Layer 4.

---

## LAYER 3: Control — Define the Calculator Endpoints

The control layer exposes business logic as callable endpoints. We need two:

- `perform_calculation` — computes a result and saves it to the dataset
- `delete_calculation` — removes a record from the dataset

### Phase 3a — Initialize the endpoint repo from the webapp

The **New Endpoint** form takes two fields:

- **endpoint_name** — the snake_case name for this specific endpoint function
  (e.g. `perform_calculation`)
- **repo_name** — the snake_case name of the endpoint repo to add it to; enter
  an existing repo name to add to it, or a new name to create a fresh repo

The form creates a stub `.py` file inside the repo with the basic
`@action_endpoint` skeleton for that one endpoint. Additional endpoints are
added either by using the form again with the same repo name, or by writing
them directly in VS Code — any decorated function in any `.py` file under the
repo path is picked up automatically at build time.

1. With the **forge-calculator** project active in the sidebar, navigate to **Endpoints**
2. Click **New Endpoint**
3. Enter `perform_calculation` as the endpoint name and `calculator_endpoints`
   as the repo name. Select action as the endpoint type.
4. Click **Create Endpoint**

Forge Suite creates the repo scaffold and a stub file for `perform_calculation`,
and adds an `[[endpoint_repos]]` entry to `forge.toml`. Switch to VS Code and
confirm `forge.toml` now contains:

```toml
[[endpoint_repos]]
module = "endpoint_repos.calculator_endpoints"
```

> **If this entry is missing from forge.toml:** add the block above manually,
> then click **Sync**.

You should also see this structure in VS Code:

```
endpoint_repos/
  calculator_endpoints/
    calculator_endpoints/
      __init__.py
      perform_calculation.py   ← stub created by the webapp
```

> **If the scaffold was not created:** create these files manually. The
> contents are in Phase 3b below.

### Phase 3b — Implement the endpoints in VS Code

The webapp stub created `perform_calculation.py` with a basic skeleton. Replace
both stubs (or create a single consolidated file) with the full implementation.

**Create `endpoint_repos/calculator_endpoints/calculator_endpoints/endpoints.py`:**

```python
"""
Control Layer — Calculator Endpoints

Two action endpoints:
  - perform_calculation: computes a result and saves it to history
  - delete_calculation: removes a record from history
"""
import uuid
from datetime import datetime, timezone

from forge.control import action_endpoint
from models.calculation import Calculation

# Endpoint UUIDs — assigned once, never change.
# These are the stable IDs the React app uses to call these endpoints.
PERFORM_CALCULATION_ID = "eb59da56-aca6-4399-8fe8-6f6b78bb2709"
DELETE_CALCULATION_ID  = "4271d443-c2eb-47e0-9d16-e35ca425c583"


@action_endpoint(
    name="perform_calculation",
    endpoint_id=PERFORM_CALCULATION_ID,
    description="Perform a calculation and save it to history",
    params=[
        {
            "name":        "operand_a",
            "type":        "float",
            "required":    True,
            "description": "The first number",
        },
        {
            "name":        "operand_b",
            "type":        "float",
            "required":    True,
            "description": "The second number",
        },
        {
            "name":        "operation",
            "type":        "string",
            "required":    True,
            "description": "One of: add, subtract, multiply, divide",
        },
    ],
)
def perform_calculation(operand_a: float, operand_b: float, operation: str) -> dict:
    if operation == "add":
        result = operand_a + operand_b
    elif operation == "subtract":
        result = operand_a - operand_b
    elif operation == "multiply":
        result = operand_a * operand_b
    elif operation == "divide":
        if operand_b == 0:
            raise ValueError("Cannot divide by zero")
        result = operand_a / operand_b
    else:
        raise ValueError(
            f"Unknown operation: '{operation}'. Use add, subtract, multiply, or divide."
        )

    calc = Calculation.create(
        id=f"c{uuid.uuid4().hex[:8]}",
        operand_a=operand_a,
        operand_b=operand_b,
        operation=operation,
        result=result,
        created_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
    return calc._to_dict()


@action_endpoint(
    name="delete_calculation",
    endpoint_id=DELETE_CALCULATION_ID,
    description="Remove a calculation from history",
    params=[
        {
            "name":        "calculation_id",
            "type":        "string",
            "required":    True,
            "description": "The id of the calculation to delete",
        },
    ],
)
def delete_calculation(calculation_id: str) -> dict:
    calc = Calculation.get(calculation_id)
    if calc is None:
        raise ValueError(f"Calculation '{calculation_id}' not found")
    calc.remove()
    return {"ok": True}
```

**Key things to understand:**

- **Endpoint UUIDs** are strings you invent once. They are the stable contract
  between the backend and the React app. Copy them — you will use the same
  values in `App.tsx` in Layer 4.
- **Multiple endpoints can live in one file**, or be spread across many files
  in the repo — Forge scans all `.py` files under the repo path and registers
  every `@action_endpoint`-decorated function it finds. In this tutorial both
  endpoints are placed in a single `endpoints.py` for simplicity.
- Model operations inside an endpoint (`Calculation.create()`, `calc.remove()`)
  are dirty-tracked and flushed atomically when the function returns. If the
  function raises, nothing is written.
- `Calculation.get(id)` returns `None` if the record does not exist. We
  validate before calling `.remove()` so the caller receives a clear error.

### Phase 3c — Build endpoints and verify in the webapp

Switch back to the Forge Suite webapp.

**Sync** the project.

**Build endpoints:**

1. Click the **Build Endpoints** button on the project card

This scans all `.py` files under the endpoint repo path, collects every
`@action_endpoint`-decorated function, and writes `.forge/artifacts/endpoints.json`.

**Verify and test from the webapp:**

1. You should see two endpoint rows: `perform_calculation` and `delete_calculation`
2. Click **Test** on `perform_calculation` to expand it — a **Request payload (JSON)**
   text area appears
3. Replace `{}` with the payload and click **Send**:
   ```json
   {
     "operand_a": 12,
     "operand_b": 5,
     "operation": "multiply"
   }
   ```
4. The response JSON should appear:
   ```json
   {
     "id": "<autogenerated ID>",
     "operand_a": 12.0,
     "operand_b": 5.0,
     "operation": "multiply",
     "result": 60.0,
     "created_at": "2026-04-19 10:00:00 UTC"
   }
   ```

**Test `delete_calculation`:**

1. Navigate to the **Model** and preview the Calulation model. You will see the recent calculation; copy the id field and navigate back to **Endpoints**.
2. Click **Test** on `delete_calculation`
3. Replace `{}` with the payload using the `id` from the previous response, and click **Send**:
   ```json
   { "calculation_id": "<ID read from the Model preview>" }
   ```
4. The record is removed

The full create-and-delete cycle works before any React code has been written.
This is the advantage of testing each layer in the webapp before moving on.

---

## LAYER 4: View — Build the React Calculator App

The view layer is a standard React + TypeScript application powered by Vite.
It imports the TypeScript SDK that Forge generated in Layer 2 and calls
endpoints by the UUIDs defined in Layer 3.

### Phase 4a — Initialize the app from the webapp

1. Select **forge-calculator** in the sidebar
2. Click **Apps** in the top navigation
3. Click **New App**
4. Enter the name `calculator`
5. Click **Create**

Forge Suite adds an `[[apps]]` entry to `forge.toml`:

```toml
[[apps]]
name = "calculator"
path = "apps/calculator"
```

> **If this entry is missing from forge.toml:** add it manually, then click
> **Sync**.

### Phase 4b — Scaffold the React app (Terminal)

The webapp registers the app slot in `forge.toml`, but the React project must
be scaffolded with Vite. In a terminal at the project root:

```cmd
cd apps
npm create vite@latest calculator -- --template react-ts
cd calculator
npm install
npm install @forge-suite/ts
```

Your `apps/calculator/` directory now contains the standard Vite scaffold.

---

## Phase 4c — Configure the Vite proxy (VS Code)

Open `apps/calculator/vite.config.ts` and replace its entire contents:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8001",
      "/endpoints": "http://localhost:8001",
    },
  },
});
```

> **Port 8001** — the Forge project backend runs here. Port 8000 is reserved
> for the Forge Suite management webapp itself.

## Phase 4d — Write the calculator component (VS Code)

The webapp scaffold creates `apps/calculator/src/pages/landing.tsx` with a
placeholder. The calculator logic lives in a dedicated component.

**Create `apps/calculator/src/components/calculator.tsx`:**

```tsx
import { useState, useEffect, useCallback } from "react";
import {
  Container,
  ButtonGroup,
  ObjectTable,
  callEndpoint,
  fetchObjectSet,
} from "@forge-suite/ts";
import { loadCalculationSet } from "../../../../.forge/generated/typescript/Calculation";
import type { ForgeObjectSet } from "@forge-suite/ts";

const PERFORM_CALCULATION_ID = "eb59da56-aca6-4399-8fe8-6f6b78bb2709";
const DELETE_CALCULATION_ID = "4271d443-c2eb-47e0-9d16-e35ca425c583";

const OP_SYMBOL: Record<string, string> = {
  add: "+",
  subtract: "−",
  multiply: "×",
  divide: "÷",
};

type CalculationRecord = {
  id: string;
  operand_a: number;
  operand_b: number;
  operation: string;
  result: number;
  created_at: string;
};

export function Calculator() {
  const [input, setInput] = useState("0");
  const [operandA, setOperandA] = useState<number | null>(null);
  const [pendingOp, setPendingOp] = useState<string | null>(null);
  const [expression, setExpression] = useState("");
  const [justEval, setJustEval] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [calcSet, setCalcSet] =
    useState<ForgeObjectSet<CalculationRecord> | null>(null);

  const loadHistory = useCallback(async () => {
    const { rows } = await fetchObjectSet<CalculationRecord>("Calculation", {
      limit: 100,
    });
    setCalcSet(loadCalculationSet(rows));
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // ── core compute ─────────────────────────────────────────────
  const compute = useCallback(
    async (
      a: number,
      op: string,
      b: number,
      onSuccess: (result: number) => void,
    ) => {
      try {
        const rec = await callEndpoint<CalculationRecord>(
          PERFORM_CALCULATION_ID,
          { operand_a: a, operand_b: b, operation: op },
        );
        await loadHistory();
        onSuccess(rec.result);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Error";
        setError(msg);
        setExpression(msg);
        setInput("0");
        setOperandA(null);
        setPendingOp(null);
        setJustEval(false);
      }
    },
    [loadHistory],
  );

  // ── digit / decimal ──────────────────────────────────────────
  const appendDigit = useCallback(
    (d: string) => {
      setError(null);
      if (justEval) {
        setInput(d === "." ? "0." : d === "0" ? "0" : d);
        setJustEval(false);
        return;
      }
      setInput((prev) => {
        if (prev === "0" && d !== ".") return d;
        if (d === "." && prev.includes(".")) return prev;
        if (prev.replace("-", "").length >= 12) return prev;
        return prev + d;
      });
    },
    [justEval],
  );

  // ── clear / backspace / sign ──────────────────────────────────
  const clear = useCallback(() => {
    setInput("0");
    setOperandA(null);
    setPendingOp(null);
    setExpression("");
    setJustEval(false);
    setError(null);
  }, []);

  const backspace = useCallback(() => {
    setError(null);
    if (justEval) return;
    setInput((prev) => (prev.length > 1 ? prev.slice(0, -1) : "0"));
  }, [justEval]);

  const toggleSign = useCallback(() => {
    setInput((prev) => {
      if (prev === "0") return "0";
      return prev.startsWith("-") ? prev.slice(1) : "-" + prev;
    });
  }, []);

  // ── operation ────────────────────────────────────────────────
  const pressOperation = useCallback(
    (op: string) => {
      setError(null);
      const parsed = parseFloat(input);
      if (operandA !== null && pendingOp !== null && !justEval) {
        // chain: compute current result then set up next op
        compute(operandA, pendingOp, parsed, (result) => {
          setOperandA(result);
          setPendingOp(op);
          setExpression(`${result} ${OP_SYMBOL[op]}`);
          setInput("0");
          setJustEval(false);
        });
      } else {
        const a = justEval && operandA !== null ? operandA : parsed;
        setOperandA(a);
        setPendingOp(op);
        setExpression(`${a} ${OP_SYMBOL[op]}`);
        setInput("0");
        setJustEval(false);
      }
    },
    [input, operandA, pendingOp, justEval, compute],
  );

  // ── equals ───────────────────────────────────────────────────
  const pressEquals = useCallback(() => {
    if (operandA === null || pendingOp === null) return;
    setError(null);
    const b = parseFloat(input);
    compute(operandA, pendingOp, b, (result) => {
      setExpression(`${operandA} ${OP_SYMBOL[pendingOp]} ${b} =`);
      setInput(String(result));
      setOperandA(result);
      setPendingOp(null);
      setJustEval(true);
    });
  }, [operandA, pendingOp, input, compute]);

  // ── keyboard ─────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ("0123456789.".includes(e.key)) appendDigit(e.key);
      else if (e.key === "+") pressOperation("add");
      else if (e.key === "-") pressOperation("subtract");
      else if (e.key === "*") pressOperation("multiply");
      else if (e.key === "/") {
        e.preventDefault();
        pressOperation("divide");
      } else if (e.key === "Enter" || e.key === "=") pressEquals();
      else if (e.key === "Backspace") backspace();
      else if (e.key === "Escape") clear();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [appendDigit, pressOperation, pressEquals, backspace, clear]);

  // ── delete from history ──────────────────────────────────────
  const handleDelete = useCallback(
    async (calc: CalculationRecord) => {
      try {
        await callEndpoint(DELETE_CALCULATION_ID, { calculation_id: calc.id });
        await loadHistory();
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Delete failed");
      }
    },
    [loadHistory],
  );

  // ── button builder helpers ───────────────────────────────────
  const digit = (d: string) => ({
    label: d,
    variant: "secondary" as const,
    action: { kind: "ui" as const, handler: () => appendDigit(d) },
  });
  const op = (label: string, key: string) => ({
    label,
    variant: "secondary" as const,
    action: { kind: "ui" as const, handler: () => pressOperation(key) },
  });

  return (
    <Container direction="row" gap={32}>
      {/* ── Calculator pad ─────────────────────────────────── */}
      <Container
        direction="column"
        gap={6}
        style={{ width: 280, flexShrink: 0 }}
      >
        {/* Expression display */}
        <div
          style={{
            minHeight: 22,
            padding: "0 8px",
            textAlign: "right",
            fontSize: 13,
            color: error ? "var(--color-danger)" : "var(--fg-muted)",
          }}
        >
          {error ?? expression}
        </div>

        {/* Input display */}
        <div
          style={{
            background: "var(--bg-input)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: "8px 12px",
            fontSize: 30,
            fontVariantNumeric: "tabular-nums",
            textAlign: "right",
            overflow: "hidden",
            whiteSpace: "nowrap",
          }}
        >
          {input}
        </div>

        {/* Row 1: C ⌫ ± ÷ */}
        <ButtonGroup
          orientation="horizontal"
          buttons={[
            {
              label: "C",
              variant: "danger",
              action: { kind: "ui", handler: clear },
            },
            {
              label: "⌫",
              variant: "secondary",
              action: { kind: "ui", handler: backspace },
            },
            {
              label: "±",
              variant: "secondary",
              action: { kind: "ui", handler: toggleSign },
            },
            op("÷", "divide"),
          ]}
        />

        {/* Row 2: 7 8 9 × */}
        <ButtonGroup
          orientation="horizontal"
          buttons={[digit("7"), digit("8"), digit("9"), op("×", "multiply")]}
        />

        {/* Row 3: 4 5 6 − */}
        <ButtonGroup
          orientation="horizontal"
          buttons={[digit("4"), digit("5"), digit("6"), op("−", "subtract")]}
        />

        {/* Row 4: 1 2 3 + */}
        <ButtonGroup
          orientation="horizontal"
          buttons={[digit("1"), digit("2"), digit("3"), op("+", "add")]}
        />

        {/* Row 5: 0 . = (ghost placeholder for grid alignment) */}
        <ButtonGroup
          orientation="horizontal"
          buttons={[
            digit("0"),
            digit("."),
            {
              label: "=",
              variant: "primary",
              action: { kind: "ui", handler: pressEquals },
            },
            { variant: "ghost", action: { kind: "ui", handler: () => {} } },
          ]}
        />
      </Container>

      {/* ── History ─────────────────────────────────────────── */}
      <Container direction="column" gap={8} size={1}>
        <h2 style={{ margin: 0 }}>History</h2>
        {!calcSet && <p>Loading…</p>}
        {calcSet && calcSet.rows.length === 0 && <p>No calculations yet.</p>}
        {calcSet && calcSet.rows.length > 0 && (
          <ObjectTable
            objectSet={calcSet}
            interaction={{
              visibleFields: ["operand_a", "operand_b", "operation", "result"],
              contextMenu: [
                {
                  label: "Delete",
                  action: {
                    kind: "ui",
                    handler: (row) => handleDelete(row as CalculationRecord),
                  },
                },
              ],
            }}
          />
        )}
      </Container>
    </Container>
  );
}
```

**`landing.tsx`** already imports Calculator from `../components/calculator.js`
— that import was added when you created the component. No changes needed:

```tsx
import React from "react";
import { Container } from "@forge-suite/ts";
import { Calculator } from "../components/calculator.js";

export function Landing() {
  return (
    <Container direction="row" padding={24} alignItems="center">
      <Calculator />
    </Container>
  );
}
```

`App.tsx` and `Sidebar.tsx` need no changes from the initialized scaffold.

**Key things to understand:**

- `fetchObjectSet<T>('ModelName', { limit })` fetches rows from the Forge
  backend. It returns `{ rows, total, schema }`. You then pass `rows` to
  `loadCalculationSet(rows)` (generated by Forge) to get a typed
  `ForgeObjectSet` that `ObjectTable` can consume.
- `loadCalculationSet` takes a raw `Calculation[]` array — it does **not**
  accept a `{ limit, offset }` object. Always fetch first, then wrap.
- The endpoint UUID constants must exactly match the values in `endpoints.py`.
  Any mismatch results in a 404 when the button is clicked.
- `callEndpoint` handles all HTTP serialization. You never write `fetch` calls
  directly in a Forge app.
- `OP_SYMBOL` maps internal operation keys (`add`, `subtract`, etc.) to the
  display symbols shown in the expression bar (`+`, `−`, `×`, `÷`).
- `ButtonGroup` takes an array of `ButtonConfig` objects. Every button uses
  `{ kind: 'ui', handler: fn }` for in-component logic. There is no bare
  `Button` widget — always wrap in `ButtonGroup`.
- The calculator has two displays: a small **expression bar** (shows the
  pending operation like `12 ×`) and a large **input display** (current
  number). After pressing `=`, the expression bar shows the full equation.
- Chaining operations (e.g. `3 + 4 ×`) calls the endpoint immediately to
  resolve the first operation before setting up the next.
- The `useEffect` keyboard handler is cleaned up in its return function so
  stale closures don't accumulate on re-render.
- `<ObjectTable>` right-click menus use `interaction={{ contextMenu: [...] }}`
  where each item has `label` and `action: ForgeAction` (not `onClick`). The
  `handler` receives the row as `unknown`, so cast it: `row as CalculationRecord`.

### Phase 4e — Start the backend and run the app from the webapp

Two processes are needed: the Forge project backend and the Vite dev server.

**Start the project backend** in a terminal at the project root:

```cmd
forge dev serve --port 8001
```

Keep this terminal open. You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8001
```

Switch to the Forge Suite webapp and **Sync** the project.

**Run the app from the webapp:**

1. Select **forge-calculator** in the sidebar
2. Click **Apps** in the top navigation
3. Find the `calculator` card
4. Click **Run**

Forge Suite runs `npm install` if needed, starts the Vite dev server, and
shows a spinner. When the **Open** button appears, click it to open the app
in your browser.

**Alternatively, start Vite manually:**

```cmd
cd apps/calculator
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Testing the Full App

1. Enter `12` in **First Number**, select **× Multiply**, enter `5` in
   **Second Number**
2. Click **Calculate**
3. **Result: 60** appears below the form
4. The **Calculation History** table updates with the new row
5. Right-click the row → **Delete** to remove it from history

Every calculation persists across page reloads — data is stored in the Forge
snapshot dataset, not in React state.

Switch to the Forge Suite webapp, go to the **Model** tab in the left sidebar,
right-click **Calculation** in the Object Types table, and select **Preview**
to see the same records and create new ones directly from there.

---

## Summary of All Files Created

| File                                                                    | Layer    | Created by                           |
| ----------------------------------------------------------------------- | -------- | ------------------------------------ |
| `pipelines/initialize_calculation_dataset.py`                           | Pipeline | Webapp stub → VS Code implementation |
| `models/calculation.py`                                                 | Model    | VS Code                              |
| `endpoint_repos/calculator_endpoints/pyproject.toml`                    | Control  | Webapp scaffold or VS Code           |
| `endpoint_repos/calculator_endpoints/calculator_endpoints/__init__.py`  | Control  | Webapp scaffold or VS Code           |
| `endpoint_repos/calculator_endpoints/calculator_endpoints/endpoints.py` | Control  | VS Code                              |
| `apps/calculator/vite.config.ts`                                        | View     | Vite scaffold → VS Code edit         |
| `apps/calculator/src/App.tsx`                                           | View     | VS Code                              |

---

## Final forge.toml

```toml
[project]
name = "forge-calculator"
forge_version = "0.1.0"

[[pipelines]]
id = "9d66c978-adab-434c-b63c-97b95945ffbe"
display_name = "initialize_calculation_dataset"
module = "pipelines.initialize_calculation_dataset"
function = "run"

[[models]]
class_name = "Calculation"
mode = "snapshot"
module = "models.calculation"

[[endpoint_repos]]
module = "endpoint_repos.calculator_endpoints"

[[apps]]
name = "calculator"
path = "apps/calculator"
```

> **Replace the dataset `id`** with the actual UUID from your
> `pipelines/initialize_calculation_dataset.py` stub file.

---

## Troubleshooting

### A layer component doesn't appear in the webapp after creation or sync

Check that the corresponding entry exists in `forge.toml`. The webapp reads
entirely from `forge.toml` and built artifacts — there is no separate
registration database. Add the missing entry manually and click **Sync**.

### "Module not found: models.calculation" during endpoint build

The endpoint package imports `from models.calculation import Calculation`.
This resolves relative to the project root. Always run **Build Endpoints**
from Forge Suite (or `forge endpoint build` from the project root), never
from inside the `endpoint_repos/` subdirectory. Also confirm the model was
built successfully in Layer 2.

### "Cannot find module '../../../.forge/generated/typescript/Calculation'"

The model has not been built yet. Complete Layer 2 (click **Build Models** in
the webapp). Verify `.forge/generated/typescript/Calculation.ts` exists before
running the React app.

### The history table is empty after a calculation

Check the browser DevTools Network tab. `/endpoints/...` requests should
return 200. A `ECONNREFUSED` error means the backend is not running — start it
with `forge dev serve --port 8001`. A 404 means the proxy port in
`vite.config.ts` does not match the backend port.

### "Cannot divide by zero"

This is the validation inside `perform_calculation`. The error bubbles through
`callEndpoint` as a thrown Error and is surfaced in the app's error state.

### Forge Suite shows 0 endpoints after Build Endpoints

Check that the endpoint functions are decorated with `@action_endpoint` and
that the files are saved. The build scans all `.py` files under the repo path
— any syntax error or missing import in those files will cause the scan to
skip that file.
