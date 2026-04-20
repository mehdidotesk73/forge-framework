# Forge Framework

Forge is a layered data application framework for building full-stack, data-driven applications. A Forge project declares Forge as a dependency and defines its own pipelines, models, endpoints, and React UI.

**This repo is the framework itself.** Forge projects live in separate directories and install Forge as a dependency via pip.

---

## Getting Started

If you are building a Forge project (not developing the framework itself), start here:

**[docs/01-project-getting-started.md](docs/01-project-getting-started.md)** — install, init, build, and run a complete Forge project from scratch.

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

### Key design decisions

| Decision | Rationale |
|----------|-----------|
| Decorator-based registration | Zero configuration — import the module and Forge discovers it |
| Dataset UUIDs assigned at load time | Stable identity across schema changes and renames |
| Immutable datasets + mutable snapshots | Pipeline outputs are auditable; model mutations are fast |
| Unit of Work with dirty tracking | One atomic transaction per endpoint call; no explicit transaction management in user code |
| Dual-language SDK generation | Type safety maintained across the Python/TypeScript boundary |
| Context variables for engine/UoW | Thread-safe request-scoped access without explicit parameter passing |
| JSON key lists for relations | No foreign-key constraint machinery; relations expressed in plain data |
| Provider Protocol interfaces | `AuthProvider` and `DatabaseProvider` are `typing.Protocol` stubs today; swap implementations without changing project code |

---

## Documentation

| Document | Contents |
|----------|----------|
| `docs/01-project-getting-started.md` | Install, init, and build your first Forge project |
| `docs/02-project-widget-reference.md` | All widgets with copy-paste examples |
| `docs/10-layer-pipeline.md` | `@pipeline` decorator, scheduling, run history, DuckDB |
| `docs/11-layer-model.md` | `@forge_model`, field defs, snapshot vs. stream, CRUD |
| `docs/12-layer-control.md` | `@action_endpoint`, `@computed_attribute_endpoint`, UoW |
| `docs/13-layer-view.md` | React widgets, generated TS SDK, state bindings |
| `docs/20-suite-developer-guide.md` | Forge Suite architecture, dev workflows, CLI reference, publishing |
| `docs/21-suite-todo.md` | Open items by layer |

---

## Monorepo Layout

```
forge-framework/
├── setup.command                    First-run installer (framework development only)
├── forge-suite-dev.command          Daily dev driver: API on :7999 + Vite UI on :5174
├── forge-suite-verify.command       Pre-release smoke test: pre-built UI + API on :5174
├── packages/
│   ├── forge-py/                    Python package (pip install forge-framework)  CLI: forge
│   ├── forge-ts/                    TypeScript package (@forge-suite/ts)
│   └── forge-suite/                 Python package (pip install forge-suite)      CLI: forge-suite
│       └── forge-webapp/            Management UI — a Forge project itself
└── examples/
    ├── student-manager/             Snapshot objects, action + computed endpoints, multi-app
    └── stock-monitor/               Stream objects, scheduled pipeline, chart
```

---

## Framework Development

To work on the framework itself (not a Forge project):

```bash
# One-time setup
bash setup.command

# Daily development (hot reload)
bash forge-suite-dev.command      # API on :7999 + Vite dev server on :5174

# Pre-release smoke test
bash forge-suite-verify.command   # backend + pre-built UI on :5174
```

See `docs/20-suite-developer-guide.md` for the full developer guide.

---

## Examples

### student-manager

```bash
cd examples/student-manager
bash setup.sh          # one-time only — assigns dataset UUIDs
forge dev serve &
cd apps/student-manager && npm install && npm run dev
```

Demonstrates: snapshot Student and Grade objects, `create_student`/`edit_student`/`delete_student` action endpoints, `compute_student_metrics` computed column endpoint, Selector bound to timeframe, Modal + Form, two independent apps.

### stock-monitor

```bash
cd examples/stock-monitor
bash setup.sh          # one-time only
forge dev serve &
cd apps/monitor && npm install && npm run dev
```

Demonstrates: stream StockPrice object, scheduled pipeline, `compute_moving_average` computed column endpoint, Selector controlling MA window, Chart with price overlay.

> **Never run `setup.sh` more than once on the same project.** It regenerates dataset UUIDs on each run, which breaks `forge.toml` and corrupts the artifact chain.

---

## Versioning

Python (`forge/version.py`) and TypeScript (`packages/forge-ts/package.json`) always carry the same version. The dev server warns on mismatch. Never bump versions manually — use `bash dev/release.sh patch` (or `minor`/`major`).
