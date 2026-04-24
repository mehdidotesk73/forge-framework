# Modules Wire-up

Changes required in `packages/forge-py/` and `packages/forge-suite/` to make the
`ai-chat` module (and any future module) work. None of these changes have been made
yet — this document describes what needs to land and why.

---

## 1. `forge/config.py` — add `forge_modules` to `ProjectConfig`

**Why:** `load_config` currently only processes `[[models]]`, `[[endpoint_repos]]`,
`[[pipelines]]`, and `[[apps]]`. A host project that wants to activate this module
adds a `[[forge_modules]]` block to its `forge.toml`. Without a matching field on
`ProjectConfig`, that block is silently ignored.

**What to add:**

```python
# New dataclass
@dataclass
class ForgeModuleConfig:
    name:       str
    package:    str
    config_var: str   # dotted.module.path:ATTR  e.g. "forge_modules.ai_chat.module:MODULE_CONFIG"

# Add field to ProjectConfig
@dataclass
class ProjectConfig:
    ...
    forge_modules: list[ForgeModuleConfig] = field(default_factory=list)
```

**Augmentation in `load_config`:**

After parsing the TOML, iterate `config.forge_modules`, import each `config_var`,
and merge its `ModelEntry` and `EndpointRepoEntry` lists into `config.models` and
`config.endpoint_repos`:

```python
for mod_cfg in config.forge_modules:
    module_path, attr = mod_cfg.config_var.split(":")
    m = importlib.import_module(module_path)
    module_config = getattr(m, attr)
    for entry in module_config.models:
        config.models.append(ModelConfig(
            class_name=entry.class_name,
            module=entry.module,
            mode=entry.mode,
        ))
    for entry in module_config.endpoint_repos:
        config.endpoint_repos.append(EndpointRepoConfig(module=entry.module))
    for entry in module_config.pipelines:
        config.pipelines.append(PipelineConfig(
            module=entry.module,
            function=entry.function,
            display_name=entry.display_name,
        ))
```

---

## 2. `forge/modules.py` — new file defining `ModuleConfig` types

**Why:** `module.py` (the generated artifact inside each module) imports
`ModuleConfig`, `ModelEntry`, `EndpointRepoEntry`, and `PipelineEntry` from
`forge.modules`. That import will fail until this file exists.

**Note:** The current `module.py` in `ai-chat` inlines these dataclasses as a
temporary workaround so the module is importable before this framework change lands.
Once `forge/modules.py` exists, regenerate `module.py` to import from there.

**What to create:**

```python
# packages/forge-py/forge/modules.py
from dataclasses import dataclass, field

@dataclass
class ModelEntry:
    class_name: str
    module:     str
    mode:       str   # "snapshot" | "stream"

@dataclass
class EndpointRepoEntry:
    module: str

@dataclass
class PipelineEntry:
    module:       str
    function:     str
    display_name: str

@dataclass
class ModuleConfig:
    name:           str
    models:         list[ModelEntry]         = field(default_factory=list)
    endpoint_repos: list[EndpointRepoEntry]  = field(default_factory=list)
    pipelines:      list[PipelineEntry]      = field(default_factory=list)
    dataset_ids:    dict[str, str]           = field(default_factory=dict)
```

---

## 3. `forge/server/app.py` — two changes

### 3a. `load_endpoint_modules` path fallback for pip-installed modules

**Why:** `load_endpoint_modules` currently resolves the endpoint module path by
joining `root / repo_cfg.module.replace(".", "/")`. This works when the endpoint
repo is a sub-directory of the project, but fails for pip-installed modules whose
code lives in `site-packages`, not in the project directory.

**Fix:** When the resolved path does not exist under `root`, fall back to
`importlib.util.find_spec()`:

```python
import importlib.util

repo_path = (root / repo_cfg.module.replace(".", "/")).resolve()
if not repo_path.exists():
    spec = importlib.util.find_spec(repo_cfg.module)
    if spec and spec.submodule_search_locations:
        repo_path = Path(list(spec.submodule_search_locations)[0])
```

Once `repo_path` is resolved the existing rglob + `importlib.import_module` logic
runs unchanged.

### 3b. Module dataset bootstrap on startup

**Why:** The `ai-chat` module declares three dataset UUIDs. When the module is
first installed into a project those UUIDs have no corresponding Parquet files in
`.forge/data/`. The server will fail at query time if the files don't exist.

`forge-suite`'s `_bootstrap_webapp()` already does exactly this for the webapp's
own models. The same logic needs to run for activated modules.

**Fix:** In the startup sequence (alongside the existing `_bootstrap_webapp` call),
iterate `config.forge_modules`, import each `MODULE_CONFIG`, read its `dataset_ids`,
and call `engine.ensure_dataset(uuid)` for any UUID not yet registered:

```python
for mod_cfg in config.forge_modules:
    module_path, attr = mod_cfg.config_var.split(":")
    m = importlib.import_module(module_path)
    module_config = getattr(m, attr)
    for dataset_id in module_config.dataset_ids.values():
        if engine.get_dataset(dataset_id) is None:
            engine.create_empty_dataset(dataset_id)
```

---

## 4. `forge/cli/main.py` — `forge module` command group

**Why:** Developers need a way to add and remove modules from a project without
manually editing `forge.toml`.

**Commands to add:**

```
forge module add <name>
    pip-installs forge-modules-<name>
    appends [[forge_modules]] entry to forge.toml
    bootstraps module datasets

forge module remove <name>
    removes [[forge_modules]] entry from forge.toml
    optionally drops module datasets (prompted)

forge module list
    lists active modules and installed versions

forge module build
    (run inside a module directory)
    introspects @forge_model decorators + forge.toml
    regenerates module.py (MODULE_CONFIG artifact)
    warns if any dataset UUID changed vs previous build
```

---

## 5. `forge-suite/forge-webapp/` — Modules page

**Why:** The Suite UI currently has no visibility into which modules are installed
in a project or their status.

**What to add:**

```python
# forge-suite/forge-webapp/models/models.py
@forge_model(mode="snapshot", backing_dataset=MODULE_DATASET_ID)
class ForgeModule(ForgeSnapshotModel):
    id:           str = field_def(primary_key=True, display="ID")
    project_id:   str = field_def(display="Project ID")
    name:         str = field_def(display="Module")
    package:      str = field_def(display="Package")
    version:      str = field_def(display="Version")
    installed_at: str = field_def(display="Installed At", display_hint="datetime")
    status:       str = field_def(display="Status")   # "active" | "error"
```

- Add corresponding `[[models]]` entry to `forge-webapp/forge.toml`
- Add endpoints for `list_modules`, `sync_modules` (reads `forge.toml` and upserts records)
- Add a **Modules** page to the React management UI alongside Pipelines / Models / Endpoints / Apps

---

## Non-breaking — nothing breaks today

Until items 1–3 above land:

- The `ai-chat` module works as a **standalone Forge project** (`forge dev serve` from
  its own directory, `npm run dev` in `apps/ai-chat-app/`).
- A host project **cannot** activate it via `[[forge_modules]]` yet — that requires
  items 1 and 3.
- The `module.py` inline dataclasses are a temporary bridge; they are safe to leave
  in place until `forge/modules.py` is shipped.
