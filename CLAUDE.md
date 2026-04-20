# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A monorepo for the **Forge framework** — an installable layered data application framework. This repo contains the framework itself, not a Forge project. Forge projects live in separate directories and declare Forge as a dependency.

## Package layout

```
packages/forge-py/    Python package (pip install forge-framework)  CLI: `forge`
packages/forge-ts/    TypeScript package (@forge-suite/ts)       React widget library
packages/forge-suite/ Python package (pip install forge-suite)      CLI: `forge-suite serve`; starts backend + UI
examples/student-manager/              Example 1: snapshot objects, multi-app, action + computed endpoints
examples/stock-monitor/                Example 2: stream objects, scheduled pipeline, chart
packages/forge-suite/forge-webapp/     Forge project that provides the management UI backend for forge-suite
```

## Starting Forge Suite (management UI)

```bash
# One-time setup (creates venv, installs deps, builds frontend, makes .command files executable):
bash setup.command

# Daily development — double-click in Finder or run from terminal:
bash forge-suite-dev.command      # API on :7999 + Vite dev server on :5174 (live reload)

# Release verification — smoke-test the pre-built bundle before shipping:
bash forge-suite-verify.command   # single process: backend + pre-built UI on :5174

# End users (pip install forge-suite) — terminal only, no .command files:
source .venv/bin/activate
forge-suite serve                 # single process: backend + pre-built UI on :5174
```

### Who uses which workflow

**Forge Suite backend developer** — works on `packages/forge-suite/` (server, CLI, scheduler) and/or `packages/forge-py/` (core framework):
- Daily driver: `forge-suite-dev.command` — starts backend on :7999 + Vite UI on :5174 so backend changes are immediately testable against the live frontend
- Pre-release: run `setup.command` then `forge-suite-verify.command` to smoke-test the production bundle before tagging a release
- Never edits the Vite app source; uses the Vite UI purely as a test client

**Forge Suite frontend developer** — works on `packages/forge-suite/forge-webapp/apps/forge-webapp/src/` (the React management UI):
- Daily driver: `forge-suite-dev.command` — Vite live-reloads on every save; API calls proxy automatically to the backend on :7999
- Pre-release: `forge-suite-verify.command` to confirm the built bundle looks right in production mode
- Does not need to touch Python; backend is treated as a stable API

**Forge project developer** — a *user* of the framework who builds their own data application (pipelines, models, endpoints, React app) in a separate project directory:
- `pip install forge-framework forge-suite` — no clone of this repo, no `.command` files
- Uses `forge` CLI in their project: `forge pipeline run`, `forge model build`, `forge endpoint build`, `forge dev serve`
- Uses `forge-suite serve` (terminal) or `forge-suite-cli.command` (if given separately) to manage their project via the Suite UI
- Never works inside the `forge-framework` monorepo

## Setup (framework development)

```bash
# Python — create a venv then install everything the IDE needs
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# TypeScript — install all workspace packages and build the widget library
npm install && npm run build:ts
```

## Build and run

```bash
# Run example end-to-end
cd examples/student-manager && bash setup.sh
forge dev serve          # starts FastAPI on :8000

# Typecheck TypeScript
cd packages/forge-ts && npm run typecheck
```

## CLI commands (all require a forge.toml in scope)

```bash
forge init <name>
forge dataset load <file> --name <n>
forge dataset list / inspect <id>
forge pipeline run <name> / dag / history <name>
forge model build / reinitialize <Type>
forge endpoint build [--repo <name>]
forge build                        # npm run build for each [[apps]] entry
forge export                       # zip project into <name>.forgepkg
forge dev serve [--app <name>] [--port N]
forge upgrade [--dry-run]
forge version
```

## Architecture invariants (never violate)

1. Pipeline layer: zero knowledge of object types, endpoints, or widgets.
2. Model layer: reads datasets, emits schema + SDKs. Does not call endpoints or render UI.
3. Control layer: imports model classes, exposes endpoints. Does not import widget code.
4. View layer: imports generated TS SDK and endpoint IDs only. Never writes fetch logic, never constructs HTTP requests, never imports Python model classes.
5. Each layer's public interface is its build artifact only (dataset UUID / schema artifact / call form descriptor registry / composed app).

## Key files and their roles

| File | Role |
|------|------|
| `packages/forge-py/forge/storage/engine.py` | DuckDB + Parquet storage engine; all dataset reads/writes; run history |
| `packages/forge-py/forge/pipeline/decorator.py` | `@pipeline` decorator; global pipeline registry |
| `packages/forge-py/forge/pipeline/runner.py` | Pipeline execution; wraps func with typed input/output bundles |
| `packages/forge-py/forge/model/builder.py` | `forge model build`; snapshot creation; calls both codegen modules |
| `packages/forge-py/forge/model/codegen_python.py` | Jinja2 → Python SDK (dataclass + Set class with CRUD for snapshots) |
| `packages/forge-py/forge/model/codegen_typescript.py` | Jinja2 → TypeScript SDK (interface + `load<Type>Set`) |
| `packages/forge-py/forge/control/decorator.py` | `@action_endpoint` and `@computed_attribute_endpoint`; global endpoint registry |
| `packages/forge-py/forge/control/builder.py` | Walks endpoint repos, emits `.forge/artifacts/endpoints.json` |
| `packages/forge-py/forge/server/app.py` | FastAPI app; mounts all API routes; serves object sets and endpoints |
| `packages/forge-py/forge/scheduler/scheduler.py` | APScheduler wrapper; fires pipelines on cron schedule |
| `packages/forge-py/forge/migrations/base.py` | `@register_migration` decorator; `MigrationRunner` |
| `packages/forge-py/forge/providers/auth.py` | `AuthProvider` Protocol + `NoAuthProvider` no-op; `make_auth_provider()` |
| `packages/forge-py/forge/providers/database.py` | `DatabaseProvider` Protocol + `LocalDatabaseProvider`; `make_database_provider()` |
| `packages/forge-py/forge/cli/dev_cmd.py` | `forge dev serve`; `_ensure_forge_ts_linked()` auto-symlinks `@forge-suite/ts` for out-of-monorepo projects |
| `packages/forge-suite/forge_suite/cli.py` | `forge-suite serve`; `_bootstrap_webapp()` auto-runs first-run setup |
| `packages/forge-ts/src/widgets/ObjectTable.tsx` | Smart table; fetches computed columns; resolves state bindings |
| `packages/forge-ts/src/widgets/Form.tsx` | Auto-renders from call form descriptor fetched by endpoint UUID |
| `packages/forge-ts/src/types/index.ts` | All shared types: `ForgeObjectSet`, `ForgeAction`, `InteractionConfig`, `StateBinding` |
| `packages/forge-ts/src/runtime/client.ts` | All HTTP calls; `configureForge()` to set base URL |

## Storage design

- All datasets are Parquet files under `.forge/data/` inside the project.
- DuckDB catalog at `.forge/forge.duckdb` holds `datasets` and `pipeline_runs` tables.
- Immutable datasets: each write produces a new versioned file (`<uuid>_v<n>.parquet`).
- Snapshot datasets: mutable, single file, overwritten in place on mutation.
- `StorageEngine` is the single point of access; never write Parquet files directly.

## Code generation

`forge model build` for each registered model:
1. Loads the `@forge_model`-decorated class by importing the configured module
2. For snapshot models, creates a snapshot copy of the backing dataset if none exists
3. Reads the live dataset schema and merges with declared field metadata
4. Writes `<Name>.schema.json` to `.forge/artifacts/`
5. Generates Python SDK via `codegen_python.py` → `.forge/generated/python/<name>.py`
6. Generates TypeScript SDK via `codegen_typescript.py` → `.forge/generated/typescript/<Name>.ts`
7. Regenerates both index files

## Dataset UUID flow

Dataset UUIDs are assigned at load time (`forge dataset load`). Pipeline functions declare input/output UUIDs in their `@pipeline` decorator. Model definitions reference dataset UUIDs in `@forge_model(backing_dataset=...)`. The view layer never sees UUIDs.

## Versioning

Python (`forge/version.py`) and TypeScript (`packages/forge-ts/package.json`) must always have matching versions. The dev server warns on mismatch. `forge upgrade` runs declared migrations then regenerates all artifacts.

## Adding a new widget

Add to `packages/forge-ts/src/widgets/`, export from `src/widgets/index.ts`, then re-export from `src/index.ts`. Keep the widget taxonomy minimal — add only when existing widgets cannot be configured to cover the need.

## Adding a migration

```python
from forge.migrations import register_migration

@register_migration("0.1.0", "0.2.0", "Rename foo field to bar in all schema artifacts")
def migrate_foo_to_bar(project_root):
    ...
```

## Debugging a Forge project

Use the `/debug` slash command when helping a user diagnose a problem in their Forge project. It instructs Claude Code to:
- Diagnose using read-only tools first (no writes)
- Never re-run `setup.sh` or regenerate dataset UUIDs
- Never edit framework files (`packages/forge-py/`, `packages/forge-ts/`, `packages/forge-suite/`) unless the user explicitly asks
- Never edit `.forge/artifacts/` or `.forge/generated/` by hand

See `.claude/commands/debug.md` for the full rule set.

## Documentation maintenance

Whenever you make a change to framework behaviour, CLI commands, UI flows, or any user-facing feature, update the relevant docs in `docs/` in the same session — do not defer doc updates to a separate pass. This applies especially to changes that affect developers building Forge projects (pipelines, models, endpoints, app scaffold, build commands, Forge Suite UI flows). If a doc describes behaviour that no longer matches the code, correct the doc before closing the task.

## Documentation

Full developer documentation lives in `docs/`:

| File | Contents |
|------|----------|
| `docs/01-project-getting-started.md` | Install, init, and build your first Forge project |
| `docs/02-project-widget-reference.md` | All widgets with copy-paste examples |
| `docs/10-layer-pipeline.md` | `@pipeline` decorator, scheduling, run history, DuckDB |
| `docs/11-layer-model.md` | `@forge_model`, field defs, snapshot vs. stream, CRUD |
| `docs/12-layer-control.md` | `@action_endpoint`, `@computed_attribute_endpoint`, UoW |
| `docs/13-layer-view.md` | React widgets, generated TS SDK, state bindings |
| `docs/20-suite-developer-guide.md` | Forge Suite architecture, dev workflows, CLI reference, publishing |
| `docs/21-suite-todo.md` | Open items by layer |
