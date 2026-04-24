# Forge Modules — User Guide

This guide covers the full lifecycle of a Forge module: building one from
a standalone project, absorbing it into the monorepo, testing the
integration, and using it in a host project.

---

## What Is a Module?

A module is a pip-installable package that adds models, pipelines, and
endpoints to any Forge project **without copying files into it**. The host
project declares the module in `forge.toml`; the framework imports it
automatically on every `forge dev serve`, `forge model build`, and
`forge endpoint build` invocation.

Modules live in `packages/forge-modules/<name>/` in this monorepo and are
published to PyPI as `forge-modules-<name>`.

---

## Stage 1 — Build Your Module as a Plain Forge Project

Start with a normal Forge project. Build and test it the usual way — you
don't need to think about modules at all during development.

```bash
forge init ai-chat
cd ai-chat
source .venv/bin/activate

# Add datasets, build pipelines, models, endpoints
forge dataset load data/...
forge pipeline run init_datasets
forge model build
forge endpoint build
forge dev serve          # test everything in isolation
```

**Important**: The dataset UUIDs you assign during `forge dataset load` and
inside your pipeline files are **permanent**. They will be embedded in the
published module and must never change. Choose them deliberately — use
random UUIDs from `python -c "import uuid; print(uuid.uuid4())"`.

Your project at this point has the standard layout:

```
ai-chat/
  forge.toml
  models/
  pipelines/
  endpoint_repos/
  apps/
  .forge/
```

---

## Stage 2 — Absorb the Project as a Module

Once the standalone project works end-to-end, absorb it:

```bash
# From the forge-framework monorepo root, with the venv active:
forge module adopt /path/to/ai-chat --name ai-chat
```

This command does the following (in order):

1. **Copies** `ai-chat/` into `packages/forge-modules/ai-chat/`,
   skipping `.venv/`, `node_modules/`, `dist/`, `data/`, and any Parquet
   or DuckDB files.

2. **Generates `pyproject.toml`** so the directory can be published as
   `forge-modules-ai-chat`. Scans endpoint repos for `anthropic`, `openai`,
   or `boto3` imports and adds them as optional dependencies automatically.

3. **Creates the namespace directory** `forge_modules/ai_chat/` with an
   `__init__.py`. Does _not_ create `forge_modules/__init__.py` — this is
   intentional.

4. **Runs `forge module build`** inside the target directory (see Stage 3).

If you want to add the packaging layer to the project _in place_ instead
of copying:

```bash
forge module adopt /path/to/ai-chat --name ai-chat --in-place
```

---

## Stage 3 — Build the Module Artifact

`forge module build` generates `forge_modules/ai_chat/module.py` — the
published manifest of what the module contributes. Run it from inside
the module directory whenever models, pipelines, or endpoints change:

```bash
cd packages/forge-modules/ai-chat
forge module build
```

What it does:

1. Reads `forge.toml` for the pipelines and endpoint repo entries
2. Imports each model module, triggering the `@forge_model` decorators
3. Collects `class_name`, `mode`, and `backing_dataset_id` from each
   registered model
4. Prefixes all module paths with `forge_modules.ai_chat.` — these are
   the importable paths when the package is installed as a pip package
5. Writes `forge_modules/ai_chat/module.py`
6. Warns if any dataset UUID changed vs the previously committed file

**Re-run this whenever you add a model, pipeline, or endpoint repo.**
Commit the resulting `module.py` — it is the contract that host projects
depend on.

The generated file looks like:

```python
# forge_modules/ai_chat/module.py — GENERATED. Do not edit.
from forge.modules import ModuleConfig, ModelEntry, EndpointRepoEntry, PipelineEntry

MODULE_CONFIG = ModuleConfig(
    name="ai-chat",
    models=[
        ModelEntry(class_name="ChatSession", module="forge_modules.ai_chat.models.chat_session", mode="snapshot"),
        ...
    ],
    endpoint_repos=[
        EndpointRepoEntry(module="forge_modules.ai_chat.endpoint_repos.ai_chat_endpoints"),
    ],
    pipelines=[
        PipelineEntry(id="<uuid>", display_name="AI Chat — Init", module="forge_modules.ai_chat.pipelines.init_datasets", function="run"),
    ],
    dataset_ids={
        "ChatSession": "<uuid>",
        ...
    },
)
```

---

## Stage 4 — Install and Test the Module Locally

Install the module package as editable so changes take effect immediately:

```bash
# From the forge-framework monorepo root:
pip install -e packages/forge-modules/ai-chat
```

Verify the namespace import works:

```bash
python -c "from forge_modules.ai_chat.module import MODULE_CONFIG; print(MODULE_CONFIG)"
```

---

## Stage 5 — Add the Module to a Host Project

```bash
# In your host project directory, with its venv active:
cd /path/to/my-project
source .venv/bin/activate

# If testing a local editable install (not PyPI):
pip install -e /path/to/forge-framework/packages/forge-modules/ai-chat

# Then add it to the project:
forge module add ai-chat --no-install   # --no-install because you already did pip install above

# For a published package on PyPI (installs automatically):
forge module add ai-chat
```

`forge module add` does three things:

1. Verifies `MODULE_CONFIG` is importable from the installed package
2. Appends this block to `forge.toml`:
   ```toml
   [[forge_modules]]
   name       = "ai-chat"
   package    = "forge-modules-ai-chat"
   config_var = "forge_modules.ai_chat.module:MODULE_CONFIG"
   ```
3. Bootstraps empty dataset files for each UUID in `MODULE_CONFIG.dataset_ids`
   — creates the Parquet files and registers them in DuckDB so the module's
   models have somewhere to read from immediately

---

## Stage 6 — Test the Integration

```bash
# Regenerate schemas and SDKs to pick up module models
forge model build
# Should show ChatSession, ChatMessage, SkillIndex (or whatever the module contributes)

# Regenerate endpoint registry
forge endpoint build
# Module endpoints should appear in .forge/artifacts/endpoints.json

# Start the dev server
forge dev serve
# Module datasets are bootstrapped automatically on startup

# Verify the module's object type is queryable
curl http://localhost:8000/api/objects/ChatSession
# → {"total": 0, "rows": [], "schema": {...}}

# Run the module's initialization pipeline
forge pipeline run "AI Chat — Initialize Datasets"
# Or trigger it via the API:
# curl -X POST http://localhost:8000/api/pipelines/<id>/run
```

---

## Stage 7 — List and Remove Modules

```bash
# See all modules configured in this project
forge module list

# Remove a module (keeps the dataset files)
forge module remove ai-chat

# Remove and delete dataset files
forge module remove ai-chat --drop-datasets
```

After removal, the `[[forge_modules]]` block is gone from `forge.toml`.
The module's models, endpoints, and pipelines are no longer available until
you `forge module add` again.

---

## Developing a Module Iteratively

Once absorbed, you can keep iterating on the module source. Since it's
installed as editable (`pip install -e`), changes to Python files take
effect the next time the server restarts. When you change model definitions
or add new pipelines:

```bash
# In the module directory:
cd packages/forge-modules/ai-chat
forge module build        # regenerate module.py

# In the host project:
forge model build         # regenerate schemas and SDKs
forge endpoint build      # rebuild endpoint registry
forge dev serve           # restart the server
```

---

## Important Constraints

**Dataset UUIDs are permanent.** Once you run `forge module build` and
commit `module.py`, the UUIDs in `dataset_ids` must never change. If you
change a UUID, any host project that already bootstrapped the old UUID will
have orphaned data files with no path to migrate automatically. `forge module build`
warns if it detects a UUID changed vs the committed file.

**Module Python code must not import from the host project.** Module code
imports from `forge.*`, `forge_modules.<name>.*`, and declared pip
dependencies only. Cross-module imports are allowed if declared as a
dependency in `pyproject.toml`.

**`forge module adopt` is non-destructive.** It does not modify your
original standalone project. The copy in `packages/forge-modules/` is
independent.
