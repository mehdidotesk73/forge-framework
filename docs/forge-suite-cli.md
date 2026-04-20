# Forge Suite CLI — Full Lifecycle Guide

The Forge Suite CLI lets you create, build, and run Forge projects entirely from the terminal — no webapp required. All commands are available through the `forge-suite` command (activated via the venv) or by passing arguments directly to `forge-suite-cli.command`.

---

## Prerequisites

Run `setup.command` once before using any CLI commands. This installs the venv, forge-framework, and forge-suite.

```bash
bash setup.command   # one-time only
```

Then either:
```bash
# Activate the venv manually:
source .venv/bin/activate

# Or use forge-suite-cli.command which activates it for you:
bash forge-suite-cli.command <command> [args]
```

---

## Quick reference

| Command | What it does |
|---------|-------------|
| `forge-suite init <path>` | Scaffold a new project and register it |
| `forge-suite mount <path>` | Register an existing project |
| `forge-suite list` | List all registered projects |
| `forge-suite sync <path>` | Re-read forge.toml and sync metadata |
| `forge-suite pipeline-run <path> <name>` | Run a named pipeline |
| `forge-suite model-build <path>` | Build schemas + generate SDKs |
| `forge-suite endpoint-build <path>` | Build endpoint descriptor registry |
| `forge-suite project-serve <path>` | Start the project backend (default :8001) |
| `forge-suite project-serve <path> --port N` | Start on a custom port |
| `forge-suite project-serve <path> --app X` | Serve a React app at `/` |
| `forge-suite serve` | Start the Forge Suite management UI |

---

## Full project lifecycle

### 1. Scaffold a new project

```bash
forge-suite init ~/my-projects/my-app
```

This runs `forge init my-app` in `~/my-projects/`, creating the full project scaffold, then immediately registers the new project with Forge Suite.

**Scaffold layout:**

```
my-app/
  forge.toml                  # Project config — source of truth for all UUIDs
  pipelines/                  # Pipeline functions
  models/                     # Model definitions
  endpoint_repos/             # Endpoint packages
  apps/                       # React apps
  data/                       # Source data files (CSV, Parquet, JSON)
  .forge/
    data/                     # Parquet dataset files (git-ignored)
    artifacts/                # Schema JSON + endpoints.json
    generated/
      python/                 # Generated Python SDK
      typescript/             # Generated TypeScript SDK
```

If you already have a project directory, use `mount` instead:

```bash
forge-suite mount ~/my-projects/existing-project
```

---

### 2. Load source data

Source data is loaded using the `forge` CLI directly (not yet wrapped in `forge-suite`). Activate the venv and run:

```bash
cd ~/my-projects/my-app
forge dataset load data/source.csv --name raw_data
```

This assigns a stable UUID to the dataset and copies the data to `.forge/data/`. **Copy the UUID printed** — you will need to wire it into your pipeline source.

Verify the dataset:

```bash
forge dataset list
forge dataset inspect <uuid>
```

---

### 3. Write and run a pipeline

Create `pipelines/normalize.py`:

```python
from forge.pipeline.decorator import forge_pipeline
from forge.pipeline.io import ForgeInput, ForgeOutput

@forge_pipeline(
    inputs=[ForgeInput("aaaaaaaa-0000-0000-0000-000000000001")],  # paste UUID from step 2
    outputs=[ForgeOutput("bbbbbbbb-0000-0000-0000-000000000002")],
)
def run(raw_data):
    df = raw_data.read()
    df["name"] = df["name"].str.strip().str.title()
    return {"bbbbbbbb-0000-0000-0000-000000000002": df}
```

Register the output UUID in `forge.toml`:

```toml
[[datasets]]
id   = "bbbbbbbb-0000-0000-0000-000000000002"
name = "normalized_data"
path = ""

[[pipelines]]
id           = "cccccccc-0000-0000-0000-000000000003"
display_name = "normalize"
module       = "pipelines.normalize"
function     = "run"
```

Run the pipeline:

```bash
forge-suite pipeline-run ~/my-projects/my-app normalize
```

The output dataset now exists in `.forge/data/` and can be used as the backing dataset for a model.

---

### 4. Define a model

Create `models/item.py`:

```python
from forge.model.decorator import forge_model
from forge.model.fields import ForgeField

@forge_model(
    name="Item",
    mode="snapshot",
    backing_dataset="bbbbbbbb-0000-0000-0000-000000000002",
)
class Item:
    id:   ForgeField(primary_key=True)
    name: ForgeField(label="Name")
```

Register it in `forge.toml`:

```toml
[[models]]
class_name = "Item"
mode       = "snapshot"
module     = "models.item"
```

Build models (generates schema artifacts and Python + TypeScript SDKs):

```bash
forge-suite model-build ~/my-projects/my-app
```

Output:
- `.forge/artifacts/Item.schema.json`
- `.forge/generated/python/item.py`
- `.forge/generated/typescript/Item.ts`

---

### 5. Write and build endpoints

Create `endpoint_repos/item_endpoints/endpoints.py`:

```python
from forge.control.decorator import action_endpoint
from forge.control.unit_of_work import get_unit_of_work
from forge.generated.python.item import Item

CREATE_ITEM_ID = "dddddddd-0000-0000-0000-000000000004"

@action_endpoint(id=CREATE_ITEM_ID, label="Create Item")
def create_item(name: str) -> dict:
    uow = get_unit_of_work()
    item = Item(name=name)
    uow.items.create(item)
    return {"ok": True}
```

Register the endpoint repo in `forge.toml`:

```toml
[[endpoint_repos]]
module = "endpoint_repos.item_endpoints"
```

Install the repo package then build:

```bash
forge-suite endpoint-build ~/my-projects/my-app
```

Output: `.forge/artifacts/endpoints.json`

---

### 6. Start the project backend

```bash
forge-suite project-serve ~/my-projects/my-app
# Default port: 8001

forge-suite project-serve ~/my-projects/my-app --port 8002
forge-suite project-serve ~/my-projects/my-app --port 8001 --app item-manager
```

Verify it's running:

```bash
curl http://localhost:8001/api/health
curl http://localhost:8001/api/objects/Item
curl http://localhost:8001/api/endpoints
```

The `--app` flag serves a compiled React app at `/`. Without it, only the API is available.

---

### 7. Build and run the React app

In a separate terminal:

```bash
cd ~/my-projects/my-app/apps/item-manager
npm install
npm run dev
```

The app's Vite dev server proxies `/api` and `/endpoints` requests to the project backend automatically — no `configureForge` call needed.

---

### 8. Sync and manage registered projects

After pulling changes or editing `forge.toml`:

```bash
forge-suite sync ~/my-projects/my-app
```

View all projects registered with Forge Suite:

```bash
forge-suite list
```

---

## Loading an example project

The examples already have `setup.sh` for one-time initialization. After that, use the Forge Suite CLI normally.

```bash
# One-time setup (assigns dataset UUIDs — never run again after this)
cd examples/student-manager
bash setup.sh

# Register with Forge Suite
forge-suite mount ~/Sandbox/forge-framework/examples/student-manager

# Run everything
forge-suite pipeline-run ~/Sandbox/forge-framework/examples/student-manager normalize_students
forge-suite model-build ~/Sandbox/forge-framework/examples/student-manager
forge-suite endpoint-build ~/Sandbox/forge-framework/examples/student-manager
forge-suite project-serve ~/Sandbox/forge-framework/examples/student-manager &

# Start the React app
cd examples/student-manager/apps/student-manager
npm install && npm run dev
```

---

## Scheduled pipelines

If a pipeline has a `schedule` cron string in `forge.toml`, it runs automatically when the dev server is up:

```toml
[[pipelines]]
id           = "..."
display_name = "normalize"
module       = "pipelines.normalize"
function     = "run"
schedule     = "0 6 * * *"     # 6 AM daily
```

To trigger it manually at any time:

```bash
forge-suite pipeline-run ~/my-projects/my-app normalize
```

---

## Typical day-to-day commands

```bash
# After pulling changes that touched pipeline/model/endpoint code:
forge-suite pipeline-run ~/my-projects/my-app normalize
forge-suite model-build ~/my-projects/my-app
forge-suite endpoint-build ~/my-projects/my-app

# Start the backend and leave it running:
forge-suite project-serve ~/my-projects/my-app &

# Check what's registered:
forge-suite list
```
