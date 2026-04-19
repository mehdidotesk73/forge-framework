# Forge Suite Webapp — Full Lifecycle Guide

The Forge Suite webapp provides a browser-based management UI for registering projects, browsing object sets, running pipelines, calling endpoints, and monitoring project health. Everything the CLI can do, the webapp exposes through a point-and-click interface.

---

## Prerequisites

Run `setup.command` once. This installs all dependencies and bootstraps the webapp itself.

```bash
bash setup.command   # one-time only
```

---

## Starting the webapp

```bash
# In Finder — double-click forge-suite-webapp.command
# In Terminal:
bash forge-suite-webapp.command
```

This runs `forge-suite serve` — a single process that serves both the backend API and the pre-built management UI on **`http://localhost:5174`**. The browser opens automatically. Press `Ctrl+C` to stop.

---

## Full project lifecycle

### 1. Create a new project

The webapp does not scaffold new project directories — use the CLI for that step:

```bash
bash forge-suite-cli.command init ~/my-projects/my-app
```

Or if you have an existing project, skip to step 2.

---

### 2. Register a project

In the webapp:

1. Click **Add Project** (top-right of the Projects panel)
2. Enter the **absolute path** to your project directory (the folder containing `forge.toml`)
3. Click **Register**

The project appears in the left sidebar. Forge Suite reads `forge.toml` and any built artifacts immediately — no server restart required.

**Loading an example project:**

The examples need one-time setup before registration:

```bash
cd examples/student-manager
bash setup.sh    # one-time only — assigns dataset UUIDs
```

Then register from the webapp using the full path (e.g. `/Users/yourname/Sandbox/forge-framework/examples/student-manager`).

> **Never run `setup.sh` more than once on the same project.** It regenerates dataset UUIDs, which breaks `forge.toml` and corrupts all registered data.

---

### 3. Write and run pipelines (data ingestion)

The primary way data enters a Forge project is through pipelines. A pipeline is a Python function decorated with `@pipeline` that reads from source files, external APIs, or other datasets and writes the results as a versioned dataset. Write your pipelines in the project's `pipelines/` directory, then run them from the webapp.

In the webapp, select your project → click **Pipelines** → click **Run** on any pipeline card. The run log appears inline. Each successful run produces a new dataset version.

If you have a one-time raw source file to register (CSV, Parquet), you can also load it directly with the CLI:

```bash
source .venv/bin/activate
cd ~/my-projects/my-app
forge dataset load data/source.csv --name raw_data
```

After any dataset change, click **Sync** on the project card in the webapp.

---

### 4. Browse datasets

Select your project → click **Datasets**. Each registered dataset shows its UUID, row count, column names and types, and version history.

---

### 6. Monitor pipeline runs

Select your project → click **Pipelines**. Each pipeline card shows:

- Name and schedule (if any)
- Last run status and timestamp
- Input and output dataset UUIDs

Click **Run** on any pipeline to trigger it immediately. The run log appears inline. After a successful run, click **Sync** to update the project view with new dataset versions.

Pipelines with a `schedule` cron string run automatically while the Forge Suite backend is up — the webapp shows the next scheduled run time.

---

### 7. Inspect and build models

Select your project → click **Models**. Each model registered in `forge.toml` shows:

- Object type name and mode (snapshot / stream)
- Backing dataset UUID
- Field definitions (if schema artifact exists)
- Build status (built / not built)

To build models (generates schema artifacts and Python + TypeScript SDKs):

Click **Build Models** on the project card, or use the CLI:

```bash
bash forge-suite-cli.command model-build ~/my-projects/my-app
```

After a successful build, the Models panel shows the full field schema. Click **Sync** to reflect the updated artifacts.

---

### 8. Build endpoints

Select your project → click **Endpoints**. Registered endpoint repos are listed.

To build the endpoint descriptor registry:

Click **Build Endpoints** on the project card, or use the CLI:

```bash
bash forge-suite-cli.command endpoint-build ~/my-projects/my-app
```

After a successful build, the Endpoints panel shows each endpoint's:
- UUID
- Label
- Parameter form (rendered from the call form descriptor)

---

### 9. Browse and filter object sets

Select your project → click **Objects**, then choose an object type. The table shows all objects in the live dataset (snapshot or stream), with:

- Sortable columns
- Pagination (limit / offset)
- Computed column values (if a computed column endpoint is configured)

For snapshot objects, the webapp supports:
- **Create** — fills in and submits a create action endpoint form
- **Update** — inline edit via an action endpoint
- **Delete** — triggers a delete action endpoint

---

### 10. Call action endpoints

Select your project → click **Endpoints** → choose an endpoint. The webapp renders the call form automatically from the endpoint descriptor. Fill in the parameters and click **Run**. The response JSON appears below the form.

This is the same form the `Form` widget renders in your React app — it's generated from the endpoint's Python type annotations.

---

### 11. Run and open a React app

Select your project → click **Apps**. Each app registered in `forge.toml` appears as a card.

Click **Run** on an app card. Forge Suite:
1. Runs `npm install` automatically if `node_modules` is missing
2. Starts the project's `forge dev serve` backend on a free port
3. Starts the Vite dev server (`npm run dev`) on another free port

While the app is starting up, the card shows a spinner. Once the Vite server is ready, the **Open** button becomes active — click it to open the app in the browser.

Click **Stop** to shut down both the Vite dev server and the project backend (the backend stops only when no other apps from the same project are still running).

---

### 12. Sync after changes

Whenever you edit `forge.toml`, run a pipeline, or rebuild models/endpoints, click **Sync** on the project card to refresh the webapp's view. Sync reads the current `forge.toml` and all built artifacts without touching dataset UUIDs or Parquet files.

---

## Managing multiple projects

The left sidebar lists all registered projects. Each project:

- Shows a green indicator when its backend is running and reachable
- Shows a grey indicator when the backend is offline (webapp features still work for inspection and building)

To remove a project from Forge Suite, click the **···** menu on the project card and select **Remove**. This only removes the registration — it does not delete any project files.

---

## Typical workflow

```
Day 1 (new project):
  forge-suite-cli.command init ~/my-projects/my-app   ← CLI only
  write pipelines to ingest data (files, APIs, etc.)  ← editor + CLI
  register in webapp → Add Project
  run pipeline → Pipelines panel → Run
  build models → Build Models button
  build endpoints → Build Endpoints button
  run app → Apps panel → Run → Open

Day 2+ (iterating):
  run pipeline → Pipelines panel → Run
  (if schema changed) build models → Build Models
  (if endpoints changed) build endpoints → Build Endpoints
  click Sync to refresh webapp view
```
