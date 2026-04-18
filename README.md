# Forge Framework

Forge is an installable framework for building layered data applications. A Forge project declares Forge as a dependency and contains only project-specific assets: pipelines, models, endpoint repos, and apps. Developers start a new project by installing Forge and running `forge init`, not by forking this repo.

## Architecture

Forge enforces four strictly separated layers. Each layer has its own developer persona, its own build artifact, and zero knowledge of layers above or below it except through defined interfaces.

```
┌─────────────────────────────────────────────────────────┐
│  Layer 4 — View                                         │
│  React widget library. Imports TypeScript SDK only.      │
│  Assembles pages from widgets. Never writes fetch logic. │
├─────────────────────────────────────────────────────────┤
│  Layer 3 — Control                                       │
│  Python endpoint functions. Imports model classes.       │
│  Exposes HTTP endpoints + call form descriptor registry. │
├─────────────────────────────────────────────────────────┤
│  Layer 2 — Model                                         │
│  Object type definitions. Reads datasets; emits schema   │
│  artifact + Python SDK + TypeScript SDK.                 │
├─────────────────────────────────────────────────────────┤
│  Layer 1 — Pipeline                                      │
│  Python transform functions. Reads/writes dataset UUIDs. │
│  Zero knowledge of object types, endpoints, or UI.       │
└─────────────────────────────────────────────────────────┘
         ↕ all layers sit on DuckDB + Parquet storage
```

### Layer boundaries (never violated)

| Layer | Knows about | Does NOT know about |
|-------|------------|---------------------|
| Pipeline | Dataset UUIDs, schemas | Object types, endpoints, widgets |
| Model | Datasets, schemas | Endpoint logic, widget structure |
| Control | Model classes, endpoint decorators | Widget code, page layout |
| View | Generated TS SDK, endpoint IDs | Python classes, DuckDB, dataset UUIDs |

## Snapshot vs Stream Objects

**Snapshot** objects back a mutable copy of a dataset. On `forge model build`, the backing dataset is snapshotted and severed from the upstream pipeline. All mutations (create/update/delete) write to the snapshot. Run `forge model reinitialize <Type>` to drop and recreate the snapshot from the current pipeline output.

**Stream** objects stay linked to a live pipeline output. When the pipeline reruns the object set reflects new data automatically. Streams are read-only.

## Scheduled Pipelines

A pipeline can declare a cron schedule. When `forge dev serve` is running, Forge's internal scheduler fires the pipeline automatically. External schedulers (cloud schedulers, CI) can also trigger any pipeline on demand via:

```bash
forge pipeline run <name>
# or HTTP:
POST /api/pipelines/<name>/run
```

The internal scheduler is optional. In production you can rely entirely on external schedulers.

## Computed Column Endpoints

A computed column endpoint accepts a list of objects and optional parameters and returns per-object computed values. The view layer attaches one or more computed column endpoints to an `ObjectTable` widget. Parameters can be bound to local UI state — when state changes the widget refetches automatically.

```tsx
<ObjectTable
  objectSet={studentSet}
  computedColumns={[{
    endpointId: COMPUTE_METRICS_ID,
    params: { timeframe: bindState("timeframe") },
  }]}
  localState={{ timeframe }}
/>
```

## Endpoint Repos

Endpoint logic lives in independently versioned endpoint repos — separate Python packages each with their own git history. The project config declares repos by local path or remote git URL. Each repo imports from the shared generated Python SDK and has no knowledge of other repos.

```toml
[[endpoint_repos]]
name = "student_endpoints"
path = "./endpoint_repos/student_endpoints"
```

Build a single repo in isolation:
```bash
forge endpoint build --repo student_endpoints
```

## Multi-App Projects

A single Forge project supports multiple independently developed apps. Apps share the same pipeline, model, and endpoint layers but compose entirely different pages from the widget library. Widget state is not shared between apps.

## Versioning

The Python package and TypeScript package are always released together under the same version. The CLI warns if installed versions are mismatched. `forge upgrade` detects the current version, runs any declared migration steps for intermediate versions, and regenerates all build artifacts.

## Build Sequence

```bash
forge dataset load data/raw.csv --name raw_data
forge pipeline run my_pipeline
forge model build
forge endpoint build
forge dev serve
```

## Four Developer Personas

| Persona | Works in | Runs | Doesn't touch |
|---------|----------|------|---------------|
| Data engineer | `pipelines/` | `forge pipeline run` | Models, endpoints, UI |
| Data modeler | `models/` | `forge model build` | Pipeline logic, endpoints, UI |
| API developer | `endpoint_repos/` | `forge endpoint build` | Pipeline, UI code |
| UI developer | `apps/` | `npm run dev` | Python, DuckDB, dataset UUIDs |

## Monorepo Layout

```
forge-framework/
├── packages/
│   ├── forge-py/           Python package (pip install forge-framework)
│   └── forge-ts/           TypeScript package (@forge-framework/ts)
└── examples/
    ├── student-manager/    Snapshot objects, action endpoints, multi-app
    └── stock-monitor/      Stream objects, scheduled pipeline, chart display
```

## Examples

### student-manager

```bash
cd examples/student-manager
bash setup.sh
forge dev serve &
cd apps/student-manager && npm install && npm run dev
```

Demonstrates: snapshot Student object, stream Grade object, `create_student` action endpoint, `compute_student_metrics` computed column endpoint (GPA + rank), Selector bound to timeframe parameter, Modal + auto-rendered Form, two independent apps.

### stock-monitor

```bash
cd examples/stock-monitor
bash setup.sh
forge dev serve &
cd apps/monitor && npm install && npm run dev
```

Demonstrates: stream Price object, scheduled pipeline (yfinance, falls back to synthetic data), `compute_moving_average` computed column endpoint, Selector controlling MA window, Chart with price overlay.
