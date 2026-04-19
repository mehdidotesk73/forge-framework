# Registering a Project with Forge Suite

Forge Suite is the management UI that lets you browse, build, and manage multiple Forge projects from a single interface. Any Forge project — new or existing, including the bundled examples — can be registered and managed through it.

---

## How registration works

The forge-suite webapp is itself a Forge project. It maintains a `ForgeProject` model that stores a record for each managed project, keyed by its absolute `root_path` on disk.

When a project is registered:
1. Forge Suite reads `forge.toml` from the given path.
2. It walks the `.forge/artifacts/` directory for built schema and endpoint artifacts.
3. It creates `Pipeline`, `Model`, `EndpointRepo`, `Endpoint`, and `App` records linked to that project.
4. The UI reflects all discovered metadata immediately.

When the forge-suite backend starts, it automatically re-syncs every previously registered project so metadata stays current.

---

## Prerequisites

Forge Suite must be running. Start it from the repo root:

```bash
# One-time setup (first run only):
bash setup.command

# Start the management UI:
bash forge-suite-webapp.command
# or, with the venv active:
source .venv/bin/activate
forge-suite serve
```

The management UI opens at `http://localhost:5174`.

---

## Registering a new project through the UI

1. Open `http://localhost:5174`.
2. Click **Add Project**.
3. Enter the **absolute path** to the project directory (the folder containing `forge.toml`).
4. Click **Register**.

Forge Suite calls `register_project(root_path)` internally, reads `forge.toml`, and surfaces all pipelines, models, endpoints, and apps in the sidebar.

If the project has not been set up yet (no `.forge/artifacts/`), the UI will show it as registered but with no artifacts. Run the project's build commands first (see below), then click **Sync** to refresh.

---

## Loading an example project from the repo

The bundled examples (`examples/student-manager/` and `examples/stock-monitor/`) are fully working Forge projects. Follow these steps to run one and load it into Forge Suite.

### Step 1 — Activate the virtual environment

```bash
source .venv/bin/activate
```

### Step 2 — Run the example's setup script

Each example ships with a `setup.sh` that handles the one-time UUID provisioning, dataset loading, and artifact build:

```bash
# Student Manager (snapshot models, CRUD endpoints, two React apps)
cd examples/student-manager
bash setup.sh

# Stock Monitor (stream model, scheduled pipeline, chart app)
cd examples/stock-monitor
bash setup.sh
```

`setup.sh` does the following:
- Loads source CSV/Parquet files into DuckDB and captures their UUIDs
- Generates UUIDs for pipeline output datasets and provisions empty placeholders
- Patches `REPLACE_WITH_*_UUID` sentinels in pipeline and model source files
- Registers all datasets in `forge.toml`
- Runs pipelines to populate output datasets
- Runs `forge model build` and `forge endpoint build`

> **Never run `setup.sh` twice on the same project.** It generates new UUIDs for every dataset on each run, which breaks the existing `forge.toml` registry and corrupts the artifact chain. If something went wrong on first run, delete the `.forge/` directory and start fresh, then run `setup.sh` once.

### Step 3 — Register with Forge Suite

With the management UI open, click **Add Project** and enter the absolute path to the example:

```
/Users/you/Sandbox/forge-framework/examples/student-manager
```

The UI will immediately display the project's pipelines, models, endpoints, and apps.

### Step 4 — Start the example's backend

Each registered project needs its own `forge dev serve` instance. Open a new terminal tab:

```bash
cd examples/student-manager
source /path/to/.venv/bin/activate
forge dev serve --port 8001
```

Use a different port for each project (the forge-suite backend uses `:8000` by default).

### Step 5 — Launch the React app

From the Forge Suite UI, select the project → select an App → click **Run App**. Forge Suite will start the Vite dev server and open the app in the browser.

Alternatively, start it manually:

```bash
cd examples/student-manager/apps/student-manager
npm install
npm run dev
# → http://localhost:5200
```

---

## Syncing after changes

If you change `forge.toml`, rebuild models, or rebuild endpoints in a registered project, click **Sync** in the project's detail view. This re-reads all artifacts without re-generating UUIDs.

Sync is also available via the CLI endpoint proxy:

```bash
# POST to the forge-suite backend (while it is running)
curl -s -X POST http://localhost:8000/endpoints/cccccccc-0004-0000-0000-000000000000 \
  -H "Content-Type: application/json" \
  -d '{"project_id": "<your-project-uuid>"}'
```

---

## Removing a project

Click the project in the sidebar → **Unregister**. This removes all associated metadata records from Forge Suite's database. It does **not** delete any files in the project directory.

---

## Forge Suite artifact requirements

For a project to show full metadata in the UI, the following must exist before registration (or before a sync):

| Artifact | Created by |
|----------|-----------|
| `forge.toml` | `forge init` or `setup.sh` |
| `.forge/artifacts/<Name>.schema.json` | `forge model build` |
| `.forge/artifacts/endpoints.json` | `forge endpoint build` |

If a project is registered before building, Forge Suite shows it with zero pipelines/models/endpoints. Run `forge model build && forge endpoint build` in the project directory, then sync.

---

## Managing multiple projects

Forge Suite supports any number of registered projects simultaneously. Each project:
- Has its own `forge dev serve` backend process on a unique port
- Has its own `.forge/` directory and artifact tree
- Is independently buildable and runnable

The `forge-suite-webapp.command` script starts `forge-suite serve` — a single process serving the backend API and management UI on port 5174. Each managed project's backend is started on demand from the UI or manually via `forge dev serve`.
