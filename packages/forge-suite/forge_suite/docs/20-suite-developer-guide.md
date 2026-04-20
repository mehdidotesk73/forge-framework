# Forge Suite — Developer Guide

## What Forge Suite Is

Forge Suite is the management layer built on top of the Forge framework. It provides:

- A browser-based UI for registering projects, running pipelines, building models, calling endpoints, and launching React apps
- A CLI (`forge-suite`) that wraps the `forge` CLI for multi-project workflows
- A scheduler that fires cron-configured pipelines while the server is running
- An auto-sync mechanism that re-reads registered projects on startup

Forge Suite is itself a Forge project (`packages/forge-suite/forge-webapp/`). It uses `ForgeProject`, `Pipeline`, `Model`, `Endpoint`, and `App` snapshot models to store registration metadata.

---

## Architecture

```
forge-suite serve
  └── FastAPI backend (port 5174)
        ├── /api/*            — management API (project registration, sync, builds)
        ├── /endpoints/*      — action endpoints for the webapp's own models
        ├── /api/objects/*    — object set API for webapp's own models
        └── StaticFiles       — pre-built forge-webapp React UI (from webapp_dist/)
```

When `--dev` is passed, static serving is disabled and the API runs on port 7999 so the Vite dev server can proxy to it:

```
forge-suite serve --dev        → API on :7999 (no static files)
npm run dev (in forge-webapp)  → Vite dev server on :5174, proxies /api/* to :7999
```

Each registered Forge project has its own `forge dev serve` backend on a separate port. The forge-suite server does not proxy project backends — the project's React app talks directly to its own `forge dev serve` instance.

---

## Dev Workflows

### Who works in this repo

There are three roles with different daily workflows:

**Suite backend developer** — works on `packages/forge-suite/` (server, CLI, scheduler) and/or `packages/forge-py/` (core framework):
- Daily driver: `forge-suite-dev.command` — starts the backend on :7999 + Vite UI on :5174 so backend changes are immediately testable against the live frontend
- Pre-release verification: `forge-suite-verify.command` — confirms the production bundle looks right before tagging

**Suite frontend developer** — works on `packages/forge-suite/forge-webapp/apps/forge-webapp/src/` (the React management UI):
- Daily driver: `forge-suite-dev.command` — Vite live-reloads on every save; API calls proxy automatically to :7999
- Pre-release verification: `forge-suite-verify.command`
- Does not need to touch Python; treats the backend as a stable API

**Forge project developer** — a user of the framework building their own data application in a separate directory:
- Installs `forge-framework` and `forge-suite` via pip; never clones this repo
- Uses `forge-suite serve` (or double-clicks `forge-suite-cli.command` if provided separately)

---

## Starting Forge Suite

### One-time setup

```bash
bash setup.command
```

This creates the venv, installs all Python and Node dependencies, builds the forge-webapp frontend, and makes the `.command` files executable. Run once only.

### Daily development (hot reload)

```bash
bash forge-suite-dev.command
```

Starts the API on :7999 (`forge-suite serve --dev`) and the Vite dev server on :5174 (`npm run dev` inside forge-webapp). The browser opens at `http://localhost:5174`. Changes to frontend source files reload the browser live; changes to Python files require restarting the command.

### Pre-release smoke test

```bash
bash forge-suite-verify.command
```

Starts the forge-suite backend serving the pre-built static bundle on :5174. Use this before tagging a release to confirm the production bundle works end-to-end.

### End-user invocation (post pip install)

```bash
source .venv/bin/activate
forge-suite serve                    # UI + API on :5174
forge-suite serve --port 8080        # Custom port
forge-suite serve --no-open          # Don't open browser automatically
```

---

## Restart Requirements

| What changed | Action required |
|---|---|
| Python source in `packages/forge-py/` or `packages/forge-suite/` | Restart `forge-suite-dev.command` |
| Frontend source in `forge-webapp/apps/forge-webapp/src/` | None — Vite hot-reloads |
| `forge.toml` or artifacts in a registered project | Click **Sync** in the UI, or run `forge-suite sync <path>` |
| `forge-webapp` models or endpoint code | Restart `forge-suite-dev.command` |

---

## CLI Reference

All commands are available via `forge-suite <command>`. No server is required for project operation commands.

### Management UI

| Command | What it does |
|---|---|
| `forge-suite serve` | Start UI + API on :5174 (opens browser) |
| `forge-suite serve --port N` | Start on a custom port |
| `forge-suite serve --no-open` | Start without opening the browser |
| `forge-suite serve --dev` | API-only on :7999 (pair with `npm run dev` for frontend dev) |

### Project management

| Command | What it does |
|---|---|
| `forge-suite init <path>` | Scaffold a new Forge project and register it with Forge Suite |
| `forge-suite mount <path>` | Register an existing project (no scaffolding) |
| `forge-suite list` | List all registered projects with status |
| `forge-suite sync <path>` | Re-read `forge.toml` and built artifacts; update metadata |

### Project operations (no server required)

| Command | What it does |
|---|---|
| `forge-suite pipeline-run <path> <name>` | Run a named pipeline |
| `forge-suite model-build <path>` | Rebuild model schemas and generate Python + TypeScript SDKs |
| `forge-suite endpoint-build <path>` | Rebuild the endpoint descriptor registry |
| `forge-suite project-serve <path>` | Start the project's `forge dev serve` backend (default :8001) |
| `forge-suite project-serve <path> --port N` | Start on a custom port |
| `forge-suite project-serve <path> --app X` | Serve a compiled React app at `/` |

### Maintenance

| Command | What it does |
|---|---|
| `forge-suite quickstart` | Print the full CLI quick-reference cheat sheet |
| `forge-suite uninstall` | Remove `forge-suite` and `forge-framework` from this Python environment |

---

## Project Registration

When a project is registered (`forge-suite mount` or **Add Project** in the UI):

1. Forge Suite reads `forge.toml` from the given path.
2. It walks `.forge/artifacts/` for schema JSON and `endpoints.json`.
3. It creates `Pipeline`, `Model`, `EndpointRepo`, `Endpoint`, and `App` records linked to the project.
4. The UI reflects all discovered metadata immediately.

On backend startup, Forge Suite automatically re-syncs every previously registered project.

**Sync** re-reads `forge.toml` and all artifacts without touching dataset UUIDs or Parquet files. Run it after any of: pipeline run, model build, endpoint build, or `forge.toml` edit.

---

## Artifact Requirements

For a project to show full metadata in the UI, the following must exist before registration or sync:

| Artifact | Created by |
|---|---|
| `forge.toml` | `forge init` or `setup.sh` |
| `.forge/artifacts/<Name>.schema.json` | `forge model build` |
| `.forge/artifacts/endpoints.json` | `forge endpoint build` |

If a project is registered before building, Forge Suite shows it as registered with no artifacts. Build first, then sync.

---

## Registering the Examples

The bundled examples (`examples/student-manager/`, `examples/stock-monitor/`) each require one-time setup before registration:

```bash
cd examples/student-manager
bash setup.sh       # one-time only — assigns dataset UUIDs, runs builds
```

Then register from the UI (**Add Project**) or CLI:

```bash
forge-suite mount /absolute/path/to/examples/student-manager
```

> **Never run `setup.sh` more than once on the same project.** It regenerates dataset UUIDs on each run, which breaks `forge.toml` and corrupts the artifact chain. If something went wrong, delete `.forge/` and run `setup.sh` once from a clean state.

---

## Running an App via Forge Suite

From the UI: select the project → **Apps** → **Run**. Forge Suite starts the project's `forge dev serve` backend on a free port and the Vite dev server on another port. Once the Vite server is ready, the **Open** button activates.

From the CLI:

```bash
# Start the project backend
forge-suite project-serve ~/my-projects/my-app --port 8001

# In a separate terminal, start the React app
cd ~/my-projects/my-app/apps/my-app
npm install
npm run dev
```

The Vite dev server proxies `/api/*` and `/endpoints/*` to the project backend automatically — no `configureForge` call needed.

---

## Publishing

The release process is managed by `dev/release.sh`. Run it from the repo root with a bump type:

```bash
bash dev/release.sh patch    # 0.1.x → 0.1.(x+1)
bash dev/release.sh minor    # 0.1.x → 0.2.0
bash dev/release.sh major    # 0.x.y → 1.0.0
```

What the script does (in order):
1. Bumps the version in `packages/forge-py/forge/version.py` and `packages/forge-ts/package.json`
2. Installs Python dependencies
3. Runs `npm install && npm run build:ts` to build the widget library
4. Builds the forge-webapp frontend and copies `dist/` to `forge_suite/webapp_dist/`
5. Copies `docs/*.md` to `packages/forge-suite/forge_suite/docs/`
6. Builds wheels for `forge-framework` and `forge-suite`

After the script completes, the wheels in `dist/` are ready to upload to PyPI and the npm package is ready to publish.

**Never bump versions manually.** The script keeps Python and TypeScript versions in sync. A mismatch causes the dev server to emit a warning at runtime.

---

## Typical Suite Developer Workflow

```bash
# Make a Python change in packages/forge-suite/ or packages/forge-py/
# Edit files in your editor

# Restart the dev server to pick up the change
bash forge-suite-dev.command

# Make a frontend change in forge-webapp/apps/forge-webapp/src/
# Edit files — Vite hot-reloads automatically, no restart needed

# Before shipping a release
bash forge-suite-verify.command    # smoke-test the production bundle
bash dev/release.sh patch          # bump + build wheels
```
