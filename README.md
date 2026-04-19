# Forge Framework

Forge is a layered data application framework for building full-stack, data-driven applications. A Forge project declares Forge as a dependency and defines its own pipelines, models, endpoints, and React UI. This repo is the framework itself — install it and run `forge init` to start a project.

---

## Installation

Run `setup.command` once to set up the Python virtual environment and install all dependencies:

```bash
# In Finder — double-click setup.command
# In Terminal:
bash setup.command
```

This creates `.venv/`, installs `forge-framework` and `forge-suite`, installs npm workspace dependencies, and bootstraps the Forge Suite management webapp. Run it only once — re-running it after a project has been created will regenerate dataset UUIDs and break any registered projects.

---

## Running Forge Suite

After setup, choose your preferred interface:

### CLI — `forge-suite-cli.command`

A terminal-based interface for managing and operating Forge projects without the webapp.

```bash
# In Finder — double-click forge-suite-cli.command
# In Terminal (direct command):
bash forge-suite-cli.command init ~/my-projects/my-app
bash forge-suite-cli.command pipeline-run ~/my-projects/my-app normalize_data
bash forge-suite-cli.command model-build ~/my-projects/my-app
bash forge-suite-cli.command endpoint-build ~/my-projects/my-app
bash forge-suite-cli.command project-serve ~/my-projects/my-app
```

See `docs/forge-suite-cli.md` for the full command reference and lifecycle walkthrough.

### Webapp — `forge-suite-webapp.command`

A browser-based management UI for registering projects, viewing object sets, triggering pipelines, and calling endpoints.

```bash
# In Finder — double-click forge-suite-webapp.command
# In Terminal:
bash forge-suite-webapp.command
# Opens http://localhost:5174 automatically
```

See `docs/forge-suite-webapp.md` for the full UI walkthrough and lifecycle guide.

---

## Architecture

Forge enforces four strictly separated layers. Each layer has its own build artifact and zero knowledge of layers above it except through defined interfaces.

```
┌─────────────────────────────────────────────────────────┐
│  Layer 4 — View                                         │
│  React widget library. Imports TypeScript SDK only.     │
│  Assembles pages from widgets. Never writes fetch logic.│
├─────────────────────────────────────────────────────────┤
│  Layer 3 — Control                                      │
│  Python endpoint functions. Imports model classes.      │
│  Exposes HTTP endpoints + call form descriptor registry.│
├─────────────────────────────────────────────────────────┤
│  Layer 2 — Model                                        │
│  Object type definitions. Reads datasets; emits schema  │
│  artifact + Python SDK + TypeScript SDK.                │
├─────────────────────────────────────────────────────────┤
│  Layer 1 — Pipeline                                     │
│  Python transform functions. Reads/writes dataset UUIDs.│
│  Zero knowledge of object types, endpoints, or UI.      │
└─────────────────────────────────────────────────────────┘
         ↕ all layers sit on DuckDB + Parquet storage
```

| Layer | Knows about | Does NOT know about |
|-------|-------------|---------------------|
| Pipeline | Dataset UUIDs, schemas | Object types, endpoints, widgets |
| Model | Datasets, schemas | Endpoint logic, widget structure |
| Control | Model classes, endpoint decorators | Widget code, page layout |
| View | Generated TS SDK, endpoint IDs | Python classes, DuckDB, dataset UUIDs |

---

## Documentation

| Document | Contents |
|----------|----------|
| `docs/forge-overview.md` | Full architecture reference: storage, build sequence, design decisions |
| `docs/new-project-guide.md` | End-to-end guide: init → pipeline → model → endpoint → app → dev server |
| `docs/forge-suite-cli.md` | Full project lifecycle via the Forge Suite CLI |
| `docs/forge-suite-webapp.md` | Full project lifecycle via the Forge Suite webapp UI |
| `docs/pipeline-layer.md` | `@pipeline` decorator, scheduling, run history |
| `docs/model-layer.md` | `@forge_model`, field defs, snapshot vs. stream, CRUD |
| `docs/control-layer.md` | `@action_endpoint`, `@computed_attribute_endpoint`, business logic |
| `docs/view-layer.md` | React widgets, generated TS SDK, state bindings |

---

## Monorepo Layout

```
forge-framework/
├── setup.command                    First-run installer
├── forge-suite-cli.command          CLI interface launcher
├── forge-suite-webapp.command       Webapp interface launcher
├── packages/
│   ├── forge-py/                    Python package (pip install forge-framework)  CLI: forge
│   ├── forge-ts/                    TypeScript package (@forge-framework/ts)
│   └── forge-suite/                 Python package (pip install forge-suite)      CLI: forge-suite
│       └── forge-webapp/            Management UI — a Forge project itself
└── examples/
    ├── student-manager/             Snapshot objects, action + computed endpoints, multi-app
    └── stock-monitor/               Stream objects, scheduled pipeline, chart
```

---

## Examples

### student-manager

```bash
cd examples/student-manager
bash setup.sh          # one-time only — generates dataset UUIDs
forge dev serve &
cd apps/student-manager && npm install && npm run dev
```

Demonstrates: snapshot Student object, stream Grade object, `create_student` action endpoint, `compute_student_metrics` computed column endpoint, Selector bound to timeframe, Modal + Form, two independent apps.

### stock-monitor

```bash
cd examples/stock-monitor
bash setup.sh          # one-time only
forge dev serve &
cd apps/monitor && npm install && npm run dev
```

Demonstrates: stream Price object, scheduled pipeline, `compute_moving_average` computed column endpoint, Selector controlling MA window, Chart with price overlay.

---

## Snapshot vs Stream Objects

**Snapshot** objects back a mutable copy of a dataset. On `forge model build`, the backing dataset is snapshotted and severed from the upstream pipeline. CRUD operations write to the snapshot. Run `forge model reinitialize <Type>` to drop and recreate the snapshot from the current pipeline output.

**Stream** objects stay linked to a live pipeline output. When the pipeline reruns, the object set reflects new data automatically. Streams are read-only.

---

## Versioning

Python (`forge/version.py`) and TypeScript (`packages/forge-ts/package.json`) always carry the same version. The dev server warns on mismatch. `forge upgrade` runs declared migration steps for all intermediate versions and regenerates all artifacts.
