# Forge Framework — System Overview

## What Forge Is

Forge is a layered data application framework for building full-stack, data-driven applications. It is **not** a project template or a starter kit — it is an installable dependency that a Forge project declares and builds on top of.

A Forge project defines its own pipelines, models, endpoints, and UI; Forge supplies the runtime, storage engine, code generation, CLI, and development server that connect those pieces together.

**Packages:**
- `forge-framework` (Python, pip) — CLI (`forge`), runtime, storage, code generation
- `@forge-suite/ts` (TypeScript, npm) — React widget library

---

## The Four-Layer Model

Forge enforces a strict four-layer architecture. Each layer has a single responsibility, a defined public interface, and zero knowledge of the layers above it.

```
┌─────────────────────────────────────────────────────────────────┐
│  View Layer                                                     │
│  React widgets; imports generated TS SDK + endpoint IDs only   │
│  Build artifact: composed app (static HTML/JS bundle)          │
├─────────────────────────────────────────────────────────────────┤
│  Control Layer                                                  │
│  @action_endpoint, @computed_attribute_endpoint decorators        │
│  Build artifact: endpoints.json (call-form descriptor registry)│
├─────────────────────────────────────────────────────────────────┤
│  Model Layer                                                    │
│  @forge_model decorator; schema + SDK generation               │
│  Build artifact: <Name>.schema.json, generated Python + TS SDK │
├─────────────────────────────────────────────────────────────────┤
│  Pipeline Layer                                                 │
│  @forge_pipeline decorator; data processing functions          │
│  Build artifact: dataset UUIDs (Parquet files)                 │
└─────────────────────────────────────────────────────────────────┘
```

### Layer Isolation Rules (never violate)

| Layer | May import | Must never import |
|-------|-----------|-------------------|
| Pipeline | Standard libraries, pandas, DuckDB, InputHandle/OutputHandle | Model classes, endpoint decorators, widget code |
| Model | Generated Python SDK, StorageEngine | Endpoint decorators, widget code |
| Control | Model classes, generated Python SDK | Widget code |
| View | Generated TS SDK, endpoint IDs (strings) | Python modules, raw fetch logic, HTTP construction |

The **only** way data flows upward is through build artifacts: a pipeline writes a dataset UUID → the model reads that UUID from config → the model build emits a schema and SDK → the endpoint imports model classes → the view imports the TS SDK.

---

## Storage Design

All data lives inside the project directory under `.forge/`:

```
.forge/
  forge.duckdb           # DuckDB catalog: datasets table, pipeline_runs table
  data/
    <uuid>_v1.parquet    # Immutable dataset (versioned)
    <uuid>_v2.parquet    # New version after pipeline write
    <snapshot_uuid>.parquet  # Snapshot dataset (mutable, overwritten in place)
  artifacts/
    Student.schema.json  # Schema artifact for each model
    endpoints.json       # Endpoint descriptor registry
  generated/
    python/
      student.py         # Generated Python SDK
      __init__.py
    typescript/
      Student.ts         # Generated TypeScript SDK
      index.ts
```

**Immutable datasets** are written by pipelines. Each write produces a new versioned Parquet file (`<uuid>_v<n>.parquet`). Old versions are retained.

**Snapshot datasets** are mutable copies of a backing dataset, created by `forge model build` for models in `mode="snapshot"`. CRUD operations on snapshot models read and write this file in place via atomic upsert/delete.

`StorageEngine` is the single point of access. Never write Parquet files directly.

---

## Configuration: forge.toml

Every Forge project has a `forge.toml` at its root:

```toml
[project]
name = "my-project"

[[datasets]]
id   = "aaaaaaaa-0000-0000-0000-000000000001"
name = "students"
path = "data/students.csv"

[[pipelines]]
id       = "bbbbbbbb-0000-0000-0000-000000000001"
name     = "normalize_students"
module   = "pipelines.normalize"
function = "run"
schedule = "0 6 * * *"          # optional cron

[[models]]
name   = "Student"
mode   = "snapshot"
module = "models.student"
class  = "Student"

[[endpoint_repos]]
name = "student_endpoints"
path = "endpoints/student"

[[apps]]
name = "student_manager"
path = "apps/student-manager"

[auth]
provider = "none"          # stub — reserved for future AuthProvider backends

[database]
provider = "local"         # stub — reserved for future DatabaseProvider backends
```

Dataset UUIDs are assigned once at `forge dataset load` time and must never change. They are the stable contract between layers.

---

## Build Sequence

To stand up a Forge project from scratch:

```bash
# 1. Load source data (assigns UUIDs, stores Parquet)
forge dataset load data/students.csv --name students

# 2. Run any pipelines that transform raw data
forge pipeline run normalize_students

# 3. Build model schemas and generate SDKs
forge model build

# 4. Build endpoint descriptor registry
forge endpoint build

# 5. (Optional) Build React apps for production
forge build

# 6. Start the development server
forge dev serve
```

In practice, `forge dev serve` auto-discovers all registered pipelines, models, and endpoints on startup — steps 3 and 4 are only needed when the schema or endpoint definitions change. `forge build` runs `npm run build` for each `[[apps]]` entry and is only needed to produce static bundles for production or for Forge Suite to serve the app.

---

## Development Server

`forge dev serve` starts a FastAPI server (default `:8000`) with:

- `POST /endpoints/{id}` — Execute any registered endpoint
- `GET  /api/objects/{ObjectType}` — Fetch object sets with limit/offset
- `GET  /api/endpoints` — Full endpoint descriptor registry
- `POST /api/datasets/upload` — Upload CSV/Parquet/JSON files
- `POST /api/pipelines/{name}/run` — Trigger a pipeline
- `GET  /api/pipelines/{name}/history` — Pipeline run history
- `GET  /docs` — Auto-generated OpenAPI UI

When `--app <name>` is provided, the server also serves the compiled React app at `/`.

---

## Code Generation

`forge model build` generates two SDKs per model from the live dataset schema:

**Python SDK** (`.forge/generated/python/<name>.py`):
- A `@dataclass` for the model
- A `<Name>Set` class with `_load()`, `create()`, `update()`, `delete()` for snapshot models

**TypeScript SDK** (`.forge/generated/typescript/<Name>.ts`):
- A TypeScript `interface` for the model
- A `load<Name>Set()` async function
- The schema object for widget introspection

Barrel exports are regenerated automatically in both `__init__.py` and `index.ts`.

---

## Versioning and Migrations

Python (`forge/version.py`) and TypeScript (`packages/forge-ts/package.json`) must always carry the same version. The dev server warns on mismatch.

Migrations are declared with `@register_migration` and run by `forge upgrade`:

```python
from forge.migrations import register_migration

@register_migration("0.1.0", "0.2.0", "Rename email field to contact_email")
def migrate(project_root):
    ...
```

`forge upgrade --dry-run` shows which migrations would run without executing them.

---

## Scheduler

Pipelines with a `schedule` cron string in `forge.toml` are registered with APScheduler and run automatically when the dev server is running. The scheduler runs in a background thread; run history is persisted to `pipeline_runs` in the DuckDB catalog.

---

## Documentation Index

| Document | Contents |
|----------|----------|
| `forge-overview.md` | This file — architecture, storage, build sequence, design decisions |
| `pipeline-layer.md` | `@pipeline` decorator, InputHandle/OutputHandle, scheduling, run history |
| `model-layer.md` | `@forge_model`, field definitions, snapshot vs. stream, CRUD, relations |
| `control-layer.md` | `@action_endpoint`, `@computed_attribute_endpoint`, business logic patterns |
| `view-layer.md` | React widgets, generated TS SDK, state bindings, form handling |
| `new-project-guide.md` | End-to-end guide: init → pipeline → model → endpoint → app → dev server |
| `forge-suite-cli.md` | Full project lifecycle via the Forge Suite CLI |
| `forge-suite-webapp.md` | Full project lifecycle via the Forge Suite webapp UI |
| `forge-suite-integration.md` | Registering projects with Forge Suite; loading examples into the UI |
| `todo.md` | Roadmap and known limitations |

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Decorator-based registration | Zero configuration; import the module and Forge discovers it |
| Dataset UUIDs assigned at load time | Stable identity across schema changes and renames |
| Immutable datasets + mutable snapshots | Pipeline outputs are auditable; model mutations are fast |
| Unit of Work with dirty tracking | One atomic transaction per endpoint call, no explicit transaction management in user code |
| Dual-language SDK generation | Type safety maintained across the Python/TypeScript boundary |
| Context variables for engine/UoW | Thread-safe request-scoped access without explicit parameter passing |
| JSON key lists for relations | No foreign-key constraint machinery; relations expressed in plain data |
| Provider Protocol interfaces | `AuthProvider` and `DatabaseProvider` are `typing.Protocol` stubs today; swap implementations without changing project code |
