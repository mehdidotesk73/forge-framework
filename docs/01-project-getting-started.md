# Forge — Getting Started

## What Is Forge?

Forge is a layered data application framework. It gives you:

- A **structured way to build data apps** — pipeline → model → endpoint → React UI
- **Generated TypeScript SDKs** from your Python data models
- **Pre-built React widgets** that understand your data types
- **Forge Suite** — a management webapp that runs your pipelines, builds your models, and lets you test endpoints before writing a single line of React

Every Forge project follows the same four-layer pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│  View Layer  (React)                                            │
│  Import generated TS SDK. Call endpoints by UUID.               │
├─────────────────────────────────────────────────────────────────┤
│  Control Layer  (Python endpoints)                              │
│  Business logic. Create, update, delete. Raise to roll back.    │
├─────────────────────────────────────────────────────────────────┤
│  Model Layer  (Python model class)                              │
│  Typed class over a dataset. Generates Python + TS SDKs.        │
├─────────────────────────────────────────────────────────────────┤
│  Pipeline Layer  (Python pipeline)                              │
│  The only place that reads external sources and writes datasets. │
└─────────────────────────────────────────────────────────────────┘
```

Data flows **upward only through build artifacts**:

1. The pipeline writes a Parquet dataset (identified by a stable UUID)
2. The model reads that UUID from `forge.toml` and generates Python + TypeScript SDKs
3. Endpoints import the Python SDK and perform mutations
4. The React app imports the TypeScript SDK and calls endpoints by UUID

---

## Installation

```bash
pip install forge-suite
```

This installs both `forge` (the project CLI) and `forge-suite` (the management webapp CLI).

---

## Starting Forge Suite

```bash
forge-suite serve
```

This starts the Forge Suite management webapp at `http://localhost:5174`. Keep it running while you work.

---

## Creating a New Project

1. Open `http://localhost:5174` in your browser
2. Click **New Project** in the sidebar
3. Enter a project name (e.g. `my-app`)
4. Click **Create**

Forge Suite creates a scaffold directory and registers the project. Open it in VS Code:

- Find the project in the sidebar
- Right-click → **Open in VS Code**

The initial scaffold:

```
my-app/
  forge.toml         ← project config
  pipelines/
    __init__.py
  models/
    __init__.py
  endpoint_repos/    ← empty
  apps/              ← empty
  data/              ← empty
  .forge/
    forge.duckdb
    artifacts/       ← empty until built
    generated/       ← empty until built
```

---

## Full Tutorial: Building a Calculator App

This tutorial builds a calculator with persistent history. By the end you will have all four layers working end-to-end.

**What you'll build:**

- A calculator UI with +, −, ×, ÷
- Persistent history — every calculation saved to a dataset
- Delete from history — remove individual past calculations

**Prerequisites:**

- Forge Suite running at `http://localhost:5174`
- A project named `forge-calculator` already created in the webapp
- VS Code, Node.js 18+, Python 3.11+

---

## How Each Layer Is Structured

Each layer follows the same three-phase pattern:

1. **Initialize from the webapp** — create the component stub; `forge.toml` is updated automatically
2. **Implement in VS Code** — write the actual code
3. **Verify in the webapp** — build and test before moving to the next layer

> **If a component doesn't appear after sync:** confirm its entry exists in `forge.toml`. The webapp reads entirely from `forge.toml` and built artifacts. Add the missing entry manually, then click **Sync**.

---

## Layer 1 — Pipeline: Initialize the Dataset

The pipeline layer produces datasets. `initialize_calculation_dataset` writes an empty Parquet file with the correct column schema so the model layer has something to read.

### 1a — Create the pipeline in the webapp

1. Select **forge-calculator** in the sidebar
2. Click **Pipelines** in the sidebar
3. Click **New Pipeline**
4. Enter the name `initialize_calculation_dataset`
5. Click **Create**

Forge Suite creates two things:

- `pipelines/initialize_calculation_dataset.py` — a stub with a pre-assigned output dataset UUID
- A `[[pipelines]]` entry in `forge.toml`

Switch to VS Code. Your `forge.toml` now contains:

```toml
[project]
name = "forge-calculator"
forge_version = "0.1.0"

[[pipelines]]
id           = "9d66c978-adab-434c-b63c-97b95945ffbe"
display_name = "initialize_calculation_dataset"
module       = "pipelines.initialize_calculation_dataset"
function     = "run"
```

> **Your UUID will differ** from the one above — Forge Suite assigns it when you click Create. Use whatever is in your file.

### 1b — Implement the pipeline (VS Code)

Replace the entire stub file at `pipelines/initialize_calculation_dataset.py`:

```python
import pandas as pd
from forge.pipeline import pipeline, ForgeOutput

OUTPUT_DATASET_ID = "9d66c978-adab-434c-b63c-97b95945ffbe"   # use your UUID


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

**Key points:**

- `inputs={}` means this pipeline produces data from scratch — no Forge input dataset needed
- Explicit `dtype` columns give Forge the schema even with zero rows
- `outputs.calculations.write(df)` is atomic — if the function raises before this line, nothing is written and the run is marked failed

### 1c — Sync, run, and verify

Switch to the Forge Suite webapp.

**Sync** the project (click **Sync** on the project card).

**Run the pipeline:**

1. Click **Pipelines** in the sidebar
2. Find the `initialize_calculation_dataset` card
3. Click **Run**

The inline log should show:

```
Status: success
Rows written: 0
```

Zero rows is correct — the dataset starts empty. What matters is that the column schema is now on disk.

**Verify:**

1. Click **Datasets** in the sidebar
2. Open the `calculations` dataset
3. Confirm 6 columns: `id`, `operand_a`, `operand_b`, `operation`, `result`, `created_at`

> **The pipeline must succeed before building the model.** The model builder reads the live Parquet file to infer the column schema. Nothing can be inferred until the pipeline has written at least the column headers.

---

## Layer 2 — Model: Define the Calculation Type

The model layer wraps the `calculations` dataset in a typed Python class and generates SDKs for both Python and TypeScript.

### 2a — Create the model in the webapp

1. Select **forge-calculator** in the sidebar
2. Click **Models** in the sidebar
3. Click **New Model**
4. Enter the name `Calculation`, select mode `snapshot`, and select the `calculations` backing dataset
5. Click **Create**

Forge Suite adds a `[[models]]` entry to `forge.toml` and generates the full model file from the dataset schema:

```toml
[[models]]
class_name = "Calculation"
mode       = "snapshot"
module     = "models.calculation"
```

### 2b — Review the model (VS Code)

Open `models/calculation.py`. The webapp generated it in full:

```python
from forge.model import forge_model, field_def, ForgeSnapshotModel

DATASET_ID = "9d66c978-adab-434c-b63c-97b95945ffbe"   # your UUID


@forge_model(mode="snapshot", backing_dataset=DATASET_ID)
class Calculation(ForgeSnapshotModel):
    id:         str   = field_def(primary_key=True, display="Id")
    operand_a:  float = field_def(display="Operand A")
    operand_b:  float = field_def(display="Operand B")
    operation:  str   = field_def(display="Operation")
    result:     float = field_def(display="Result")
    created_at: str   = field_def(display="Created At")
```

**Key points:**

- `backing_dataset` always takes a UUID, never a dataset name
- `mode="snapshot"` activates full CRUD — Forge maintains a mutable snapshot file; the pipeline output is never modified by endpoints
- `display="..."` sets the column label in `<ObjectTable>` widgets
- **Relations must be added manually** — if a model holds foreign keys to another model, add the `related(...)` declaration yourself; the initializer does not infer cross-model relationships
- You normally do not need to edit this file after creation

### 2c — Build and verify

Switch to the Forge Suite webapp.

**Sync** the project.

**Build models** — click the **Build Models** button on the project card.

When the build completes:

- `.forge/artifacts/Calculation.schema.json`
- `.forge/generated/python/calculation.py`
- `.forge/generated/typescript/Calculation.ts`

**Verify:**

1. In the sidebar, select **forge-calculator** and click **Models**
2. Find the `Calculation` model, right-click, and select **Preview**
3. The table should appear with all 6 fields. The table is empty for now — that's expected

> In VS Code, open `.forge/generated/typescript/Calculation.ts` to see the generated TypeScript interface and `loadCalculationSet()` function. The React app imports directly from this file in Layer 4.

---

## Layer 3 — Control: Define the Endpoints

The control layer exposes business logic as callable HTTP endpoints. Two endpoints are needed:

- `perform_calculation` — computes a result and saves it to the dataset
- `delete_calculation` — removes a record from the dataset

### 3a — Create the endpoint repo in the webapp

1. Select **forge-calculator** in the sidebar
2. Click **Endpoints** in the sidebar
3. Click **New Endpoint**
4. Enter `perform_calculation` as the endpoint name and `calculator_endpoints` as the repo name. Select **action** as the type.
5. Click **Create Endpoint**

Forge Suite creates the repo scaffold and adds an `[[endpoint_repos]]` entry to `forge.toml`:

```toml
[[endpoint_repos]]
module = "endpoint_repos.calculator_endpoints"
```

The file tree:

```
endpoint_repos/
  calculator_endpoints/
    calculator_endpoints/
      __init__.py
      perform_calculation.py   ← stub
```

### 3b — Implement the endpoints (VS Code)

Create `endpoint_repos/calculator_endpoints/calculator_endpoints/endpoints.py` with both endpoints:

```python
import uuid
from datetime import datetime, timezone

from forge.control import action_endpoint
from models.calculation import Calculation

PERFORM_CALCULATION_ID = "eb59da56-aca6-4399-8fe8-6f6b78bb2709"
DELETE_CALCULATION_ID  = "4271d443-c2eb-47e0-9d16-e35ca425c583"


@action_endpoint(
    name="perform_calculation",
    endpoint_id=PERFORM_CALCULATION_ID,
    description="Perform a calculation and save it to history",
    params=[
        {"name": "operand_a",  "type": "float",  "required": True,  "description": "The first number"},
        {"name": "operand_b",  "type": "float",  "required": True,  "description": "The second number"},
        {"name": "operation",  "type": "string", "required": True,  "description": "One of: add, subtract, multiply, divide"},
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
        raise ValueError(f"Unknown operation '{operation}'. Use add, subtract, multiply, or divide.")

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
        {"name": "calculation_id", "type": "string", "required": True, "description": "The id to delete"},
    ],
)
def delete_calculation(calculation_id: str) -> dict:
    calc = Calculation.get(calculation_id)
    if calc is None:
        raise ValueError(f"Calculation '{calculation_id}' not found")
    calc.remove()
    return {"ok": True}
```

**Key points:**

- **Endpoint UUIDs** — strings you assign once and never change. The React app calls endpoints by these UUIDs. Generate fresh ones with `python -c "import uuid; print(uuid.uuid4())"`.
- Multiple endpoints can live in one file or across many files in the repo — Forge scans every `.py` file under the repo path and registers every decorated function it finds
- `Calculation.create()`, `calc.remove()` — dirty-tracked and flushed atomically when the function returns. If the function raises, nothing is written
- Raise `ValueError` for user-facing errors (`divide by zero`, `not found`). The `<Form>` widget surfaces these messages to the user automatically

### 3c — Build and verify

Switch to the Forge Suite webapp.

**Sync** the project.

**Build endpoints** — click the **Build Endpoints** button on the project card.

**Test `perform_calculation`:**

1. In the sidebar, click **Endpoints**
2. Click **Test** on `perform_calculation`
3. Enter the payload and click **Send**:
   ```json
   { "operand_a": 12, "operand_b": 5, "operation": "multiply" }
   ```
4. The response should be:
   ```json
   { "id": "c...", "operand_a": 12.0, "operand_b": 5.0, "operation": "multiply", "result": 60.0, "created_at": "..." }
   ```

**Test `delete_calculation`:**

1. In the sidebar, click **Models** and preview the `Calculation` model — copy the `id` from the row just created
2. Click **Endpoints**, then **Test** on `delete_calculation`
3. Enter `{ "calculation_id": "<id from above>" }` and click **Send**
4. The response is `{ "ok": true }` and the row is gone from the preview

The full create-and-delete cycle works before any React code is written. This is the benefit of testing each layer in the webapp before moving on.

---

## Layer 4 — View: Build the React App

The view layer is a standard React + TypeScript app powered by Vite. It imports the generated TypeScript SDK and calls endpoints by the UUIDs defined in Layer 3.

### 4a — Register the app in the webapp

1. Select **forge-calculator** in the sidebar
2. Click **Apps** in the sidebar
3. Click **New App**
4. Enter the name `calculator`
5. Click **Create**

`forge.toml` now contains:

```toml
[[apps]]
name = "calculator"
path = "apps/calculator"
```

### 4b — Scaffold the React app (terminal)

From the project root:

```bash
cd apps
npm create vite@latest calculator -- --template react-ts
cd calculator
npm install
npm install @forge-suite/ts
```

### 4c — Configure the Vite proxy (VS Code)

Replace the entire contents of `apps/calculator/vite.config.ts`:

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api":       "http://localhost:8001",
      "/endpoints": "http://localhost:8001",
    },
  },
});
```

> **Port 8001** — the Forge project backend runs here. Port 5174 is the Forge Suite management webapp.

### 4d — Write the calculator component (VS Code)

Create `apps/calculator/src/components/calculator.tsx`:

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
const DELETE_CALCULATION_ID  = "4271d443-c2eb-47e0-9d16-e35ca425c583";

const OP_SYMBOL: Record<string, string> = {
  add: "+", subtract: "−", multiply: "×", divide: "÷",
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
  const [input, setInput]       = useState("0");
  const [operandA, setOperandA] = useState<number | null>(null);
  const [pendingOp, setPendingOp] = useState<string | null>(null);
  const [expression, setExpression] = useState("");
  const [justEval, setJustEval] = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [calcSet, setCalcSet]   = useState<ForgeObjectSet<CalculationRecord> | null>(null);

  const loadHistory = useCallback(async () => {
    const { rows } = await fetchObjectSet<CalculationRecord>("Calculation", { limit: 100 });
    setCalcSet(loadCalculationSet(rows));
  }, []);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const compute = useCallback(
    async (a: number, op: string, b: number, onSuccess: (result: number) => void) => {
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

  const appendDigit = useCallback((d: string) => {
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
  }, [justEval]);

  const clear = useCallback(() => {
    setInput("0"); setOperandA(null); setPendingOp(null);
    setExpression(""); setJustEval(false); setError(null);
  }, []);

  const backspace = useCallback(() => {
    setError(null);
    if (justEval) return;
    setInput((prev) => (prev.length > 1 ? prev.slice(0, -1) : "0"));
  }, [justEval]);

  const toggleSign = useCallback(() => {
    setInput((prev) => prev === "0" ? "0" : prev.startsWith("-") ? prev.slice(1) : "-" + prev);
  }, []);

  const pressOperation = useCallback((op: string) => {
    setError(null);
    const parsed = parseFloat(input);
    if (operandA !== null && pendingOp !== null && !justEval) {
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
  }, [input, operandA, pendingOp, justEval, compute]);

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

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ("0123456789.".includes(e.key)) appendDigit(e.key);
      else if (e.key === "+") pressOperation("add");
      else if (e.key === "-") pressOperation("subtract");
      else if (e.key === "*") pressOperation("multiply");
      else if (e.key === "/") { e.preventDefault(); pressOperation("divide"); }
      else if (e.key === "Enter" || e.key === "=") pressEquals();
      else if (e.key === "Backspace") backspace();
      else if (e.key === "Escape") clear();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [appendDigit, pressOperation, pressEquals, backspace, clear]);

  const handleDelete = useCallback(async (calc: CalculationRecord) => {
    try {
      await callEndpoint(DELETE_CALCULATION_ID, { calculation_id: calc.id });
      await loadHistory();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  }, [loadHistory]);

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
      {/* Calculator pad */}
      <Container direction="column" gap={6} style={{ width: 280, flexShrink: 0 }}>
        <div style={{
          minHeight: 22, padding: "0 8px", textAlign: "right", fontSize: 13,
          color: error ? "var(--color-danger)" : "var(--fg-muted)",
        }}>
          {error ?? expression}
        </div>
        <div style={{
          background: "var(--bg-input)", border: "1px solid var(--border)",
          borderRadius: 6, padding: "8px 12px", fontSize: 30,
          fontVariantNumeric: "tabular-nums", textAlign: "right",
          overflow: "hidden", whiteSpace: "nowrap",
        }}>
          {input}
        </div>

        <ButtonGroup orientation="horizontal" buttons={[
          { label: "C",  variant: "danger",     action: { kind: "ui", handler: clear } },
          { label: "⌫",  variant: "secondary",  action: { kind: "ui", handler: backspace } },
          { label: "±",  variant: "secondary",  action: { kind: "ui", handler: toggleSign } },
          op("÷", "divide"),
        ]} />
        <ButtonGroup orientation="horizontal" buttons={[digit("7"), digit("8"), digit("9"), op("×", "multiply")]} />
        <ButtonGroup orientation="horizontal" buttons={[digit("4"), digit("5"), digit("6"), op("−", "subtract")]} />
        <ButtonGroup orientation="horizontal" buttons={[digit("1"), digit("2"), digit("3"), op("+", "add")]} />
        <ButtonGroup orientation="horizontal" buttons={[
          digit("0"),
          digit("."),
          { label: "=", variant: "primary", action: { kind: "ui", handler: pressEquals } },
          { variant: "ghost", action: { kind: "ui", handler: () => {} } },
        ]} />
      </Container>

      {/* History */}
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

Update `apps/calculator/src/pages/landing.tsx` to import the component:

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

**Key points:**

- `fetchObjectSet<T>('ModelName', { limit })` fetches rows from the backend. It returns `{ rows, total, schema }`.
- `loadCalculationSet(rows)` (generated by `forge model build`) wraps the rows in a typed `ForgeObjectSet` that `<ObjectTable>` consumes. It takes a raw `Calculation[]` — not `{ limit, offset }`. Always fetch first, then wrap.
- The endpoint UUID constants must exactly match the values in `endpoints.py`. Any mismatch results in a 404.
- `callEndpoint` handles all HTTP serialization. Never write `fetch` calls in a Forge app.
- `ButtonGroup` takes an array of button config objects. Use `{ kind: 'ui', handler: fn }` for in-component logic. There is no standalone `Button` widget — always use `ButtonGroup`.
- Context menu handlers receive the row as `unknown` — cast it: `row as CalculationRecord`

### 4e — Start the backend and run the app

**Start the project backend** in a terminal at the project root:

```bash
forge dev serve --port 8001
```

You should see:

```
INFO:     Uvicorn running on http://0.0.0.0:8001
```

**Run the app** — either from the Forge Suite webapp (sidebar → **Apps** → **Run**) or manually:

```bash
cd apps/calculator
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Testing the Full App

1. Press `7`, then `×`, then `6`, then `=` — the expression bar shows `7 × 6 =` and the display shows `42`
2. The History table updates with the new row
3. Right-click a row → **Delete** — the row disappears

Every calculation persists across page reloads. Switch to the Forge Suite webapp, click **Models** in the sidebar, right-click **Calculation**, and select **Preview** to see the same records — and create new ones directly from the preview table.

---

## Final forge.toml

```toml
[project]
name         = "forge-calculator"
forge_version = "0.1.0"

[[pipelines]]
id           = "9d66c978-adab-434c-b63c-97b95945ffbe"
display_name = "initialize_calculation_dataset"
module       = "pipelines.initialize_calculation_dataset"
function     = "run"

[[models]]
class_name = "Calculation"
mode       = "snapshot"
module     = "models.calculation"

[[endpoint_repos]]
module = "endpoint_repos.calculator_endpoints"

[[apps]]
name = "calculator"
path = "apps/calculator"
```

> Replace the pipeline `id` with the actual UUID from your stub file.

---

## Files Created

| File | Layer | Created by |
|------|-------|-----------|
| `pipelines/initialize_calculation_dataset.py` | Pipeline | Webapp stub → VS Code |
| `models/calculation.py` | Model | Webapp |
| `endpoint_repos/calculator_endpoints/calculator_endpoints/endpoints.py` | Control | VS Code |
| `apps/calculator/vite.config.ts` | View | Vite scaffold → VS Code edit |
| `apps/calculator/src/components/calculator.tsx` | View | VS Code |
| `apps/calculator/src/pages/landing.tsx` | View | VS Code |

---

## Troubleshooting

### A layer component doesn't appear after sync

Check that the corresponding entry exists in `forge.toml`. Add the missing entry manually, then click **Sync**.

### "Module not found: models.calculation" during endpoint build

Endpoints import from `models.calculation` relative to the project root. Always run **Build Endpoints** from the project card (or `forge endpoint build` from the project root), never from inside `endpoint_repos/`. Also confirm the model was built in Layer 2.

### "Cannot find module '…/.forge/generated/typescript/Calculation'"

The model has not been built yet. Complete Layer 2 (click **Build Models**). Verify `.forge/generated/typescript/Calculation.ts` exists before running the React app.

### History table is empty after a calculation

Check the browser DevTools Network tab. `/endpoints/...` requests should return 200.

- `ECONNREFUSED` — the backend is not running. Start it with `forge dev serve --port 8001`.
- 404 — the proxy port in `vite.config.ts` does not match the backend port.

### Forge Suite shows 0 endpoints after Build Endpoints

Confirm the endpoint functions are decorated with `@action_endpoint` and the files are saved. Any syntax error or missing import in a scanned file causes that file to be skipped silently — check the build log for import errors.
