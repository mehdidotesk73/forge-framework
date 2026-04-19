"""
Control Layer — project_endpoints
Manages ForgeProject records and syncs metadata from managed projects.
"""
from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from forge.control import action_endpoint

from models.models import (
    App,
    ArtifactStamp,
    Endpoint,
    EndpointRepo,
    ForgeProject,
    ObjectType,
    Pipeline,
    PipelineRun,
)

REGISTER_PROJECT_ID      = "cccccccc-0001-0000-0000-000000000000"
UNREGISTER_PROJECT_ID    = "cccccccc-0002-0000-0000-000000000000"
SET_ACTIVE_PROJECT_ID    = "cccccccc-0003-0000-0000-000000000000"
SYNC_PROJECT_ID          = "cccccccc-0004-0000-0000-000000000000"
CREATE_PIPELINE_ID       = "cccccccc-0011-0000-0000-000000000000"
LIST_PROJECT_DATASETS_ID = "cccccccc-0015-0000-0000-000000000000"
CREATE_MODEL_ID          = "cccccccc-0016-0000-0000-000000000000"
OPEN_IN_VSCODE_ID        = "cccccccc-0017-0000-0000-000000000000"
CREATE_ENDPOINT_ID       = "cccccccc-0018-0000-0000-000000000000"
GET_DOCS_ID              = "cccccccc-0019-0000-0000-000000000000"
CREATE_APP_ID            = "cccccccc-0020-0000-0000-000000000000"
RUN_APP_ID               = "cccccccc-0021-0000-0000-000000000000"
STOP_APP_ID              = "cccccccc-0022-0000-0000-000000000000"
OPEN_APP_ID              = "cccccccc-0023-0000-0000-000000000000"
PING_APP_ID              = "cccccccc-0024-0000-0000-000000000000"
PREVIEW_DATASET_ID       = "cccccccc-0025-0000-0000-000000000000"
CALL_PROJECT_ENDPOINT_ID = "cccccccc-0026-0000-0000-000000000000"
PREVIEW_MODEL_ID         = "cccccccc-0027-0000-0000-000000000000"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_toml(path: Path) -> dict:
    import sys
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    with open(path, "rb") as f:
        return tomllib.load(f)


def _parse_pipeline_io_from_source(filepath: Path) -> tuple[list, list]:
    """Extract ForgeInput/ForgeOutput dataset IDs from a pipeline source file via AST."""
    import ast
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return [], []

    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                    constants[target.id] = str(node.value.value)

    def resolve_arg(node: ast.expr) -> str:
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.Name):
            return constants.get(node.id, "")
        return ""

    input_ids: list[str] = []
    output_ids: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg in ("inputs", "outputs"):
            if isinstance(node.value, ast.Dict):
                for val in node.value.values:
                    if isinstance(val, ast.Call) and isinstance(val.func, ast.Name):
                        if val.func.id == "ForgeInput" and val.args:
                            uid = resolve_arg(val.args[0])
                            if uid:
                                input_ids.append(uid)
                        elif val.func.id == "ForgeOutput" and val.args:
                            uid = resolve_arg(val.args[0])
                            if uid:
                                output_ids.append(uid)
    return input_ids, output_ids


def _try_load_pipeline_io(root: Path, module: str, function: str) -> tuple[list, list]:
    """Import a pipeline module and read its input/output dataset IDs.

    Falls back to AST parsing of the source file if the import fails (e.g.,
    due to project-specific dependencies not present in the forge-suite venv).
    """
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    try:
        import importlib
        if module in sys.modules:
            mod = importlib.reload(sys.modules[module])
        else:
            mod = importlib.import_module(module)
        func = getattr(mod, function, None)
        if func is None:
            return [], []
        defn = getattr(func, "_forge_pipeline", None)
        if defn is None:
            return [], []
        inputs = list(defn.inputs.values()) if defn.inputs else []
        outputs = list(defn.outputs.values()) if defn.outputs else []
        input_ids = [getattr(i, "dataset_id", "") for i in inputs]
        output_ids = [getattr(o, "dataset_id", "") for o in outputs]
        return input_ids, output_ids
    except Exception:
        # Import failed (missing dependency, syntax error, etc.) — fall back to AST parsing
        module_file = root / module.replace(".", "/")
        for candidate in (module_file.with_suffix(".py"), module_file / "__init__.py"):
            if candidate.exists():
                return _parse_pipeline_io_from_source(candidate)
        return [], []


def _clear_project_records(project_id: str) -> None:
    for cls in (Pipeline, PipelineRun, ObjectType, EndpointRepo, Endpoint, App, ArtifactStamp):
        rows = cls.all()
        for r in rows:
            if getattr(r, "project_id", None) == project_id:
                r.remove()


def _sync_from_toml(project_id: str, root: Path, cfg: dict) -> None:
    """Populate model records from a parsed forge.toml."""
    import hashlib
    # Pipelines — skip entries whose module file no longer exists on disk
    for p in cfg.get("pipelines", []):
        pid = p.get("id") or p.get("name", "")
        func = p.get("function", "run")
        module = p.get("module", "")
        module_file = root / module.replace(".", "/")
        if not (module_file.with_suffix(".py").exists() or (module_file / "__init__.py").exists()):
            continue
        input_ids, output_ids = _try_load_pipeline_io(root, module, func)
        pid_hash = hashlib.md5(pid.encode()).hexdigest()[:10]
        Pipeline.create(
            id=f"pl-{project_id[:8]}-{pid_hash}",
            project_id=project_id,
            name=p.get("name", ""),
            module=module,
            function_name=func,
            schedule=p.get("schedule", ""),
            input_datasets=json.dumps(input_ids),
            output_datasets=json.dumps(output_ids),
        )

    # Object types — read from artifacts if built
    artifacts_dir = root / ".forge" / "artifacts"
    for m in cfg.get("models", []):
        obj_name = m.get("name", "")
        schema_path = artifacts_dir / f"{obj_name}.schema.json"
        field_count = ""
        built_at = ""
        backing_dataset_id = ""
        mode = m.get("mode", "snapshot")
        if schema_path.exists():
            schema = json.loads(schema_path.read_text())
            field_count = str(len(schema.get("fields", {})))
            built_at = schema.get("built_at", "")
            backing_dataset_id = schema.get("backing_dataset_id", "")
        name_hash = hashlib.md5(obj_name.encode()).hexdigest()[:10]
        ObjectType.create(
            id=f"ot-{project_id[:8]}-{name_hash}",
            project_id=project_id,
            name=obj_name,
            mode=mode,
            module=m.get("module", ""),
            backing_dataset_id=backing_dataset_id,
            field_count=field_count,
            built_at=built_at,
        )

    # Endpoint repos + endpoints from artifacts
    endpoints_json_path = artifacts_dir / "endpoints.json"
    endpoints_registry: dict = {}
    if endpoints_json_path.exists():
        endpoints_registry = json.loads(endpoints_json_path.read_text())

    for repo in cfg.get("endpoint_repos", []):
        repo_name = repo.get("name", "")
        repo_path = repo.get("path", "")
        eps_in_repo = [e for e in endpoints_registry.values() if e.get("repo") == repo_name]
        EndpointRepo.create(
            id=f"er-{project_id[:8]}-{repo_name[:12]}",
            project_id=project_id,
            name=repo_name,
            path=repo_path,
            endpoint_count=str(len(eps_in_repo)),
        )
        for ep in eps_in_repo:
            Endpoint.create(
                id=f"ep-{project_id[:8]}-{ep.get('id', '')[:8]}",
                project_id=project_id,
                repo_name=repo_name,
                endpoint_id=ep.get("id", ""),
                name=ep.get("name", ""),
                kind=ep.get("kind", "action"),
                description=ep.get("description", ""),
                object_type=ep.get("object_type", ""),
            )

    # Apps
    for app in cfg.get("apps", []):
        App.create(
            id=f"ap-{project_id[:8]}-{app.get('name', '')[:12]}",
            project_id=project_id,
            name=app.get("name", ""),
            app_id=app.get("id", app.get("name", "")),
            path=app.get("path", ""),
            port=app.get("port", ""),
        )


_FORGE_TOML_TEMPLATE = """\
[project]
name = "{name}"
forge_version = "0.1.0"
"""

_GITIGNORE = """\
.forge/
__pycache__/
*.pyc
node_modules/
dist/
.env
"""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _write_ide_config(root: Path) -> None:
    """Write VS Code and Pyright config into a project root and its pipelines/ subdir.

    VS Code's Pylance only reads pyrightconfig.json from the workspace root — it
    does not walk up past it. Writing the config to pipelines/ as well means
    import resolution works whether the user opens the full project or just the
    pipelines subfolder. extraPaths is required because Pyright ignores .pth files
    produced by editable pip installs.
    """
    import json as _json
    repo = _repo_root()
    venv_python = repo / ".venv" / "bin" / "python"
    pyright_cfg = _json.dumps({
        "venvPath": str(repo),
        "venv": ".venv",
        "extraPaths": [str(repo / "packages" / "forge-py")],
    }, indent=2)

    vscode_dir = root / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    (vscode_dir / "settings.json").write_text(
        _json.dumps({"python.defaultInterpreterPath": str(venv_python)}, indent=2)
    )
    (root / "pyrightconfig.json").write_text(pyright_cfg)

    pipelines_dir = root / "pipelines"
    if pipelines_dir.exists():
        (pipelines_dir / "pyrightconfig.json").write_text(pyright_cfg)


def _create_project(root: Path) -> None:
    """Scaffold a new Forge project directory."""
    import json as _json
    from forge.version import __version__

    dirs = [
        root,
        root / ".forge" / "data",
        root / ".forge" / "artifacts",
        root / ".forge" / "generated" / "python",
        root / ".forge" / "generated" / "typescript",
        root / "pipelines",
        root / "models",
        root / "endpoint_repos",
        root / "apps",
        root / "data",
        root / "files",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    (root / "forge.toml").write_text(_FORGE_TOML_TEMPLATE.format(name=root.name))
    (root / ".gitignore").write_text(_GITIGNORE)
    (root / "pipelines" / "__init__.py").write_text("")
    (root / "models" / "__init__.py").write_text("")
    state = root / ".forge" / "migration_state.json"
    state.write_text(_json.dumps({"forge_version": __version__}))

    _write_ide_config(root)


@action_endpoint(
    name="register_project",
    endpoint_id=REGISTER_PROJECT_ID,
    description="Register a Forge project by its root path, creating it if it doesn't exist",
    params=[
        {"name": "root_path", "type": "string", "required": True,
         "description": "Absolute path to the project directory (created if it doesn't exist)"},
    ],
)
def register_project(root_path: str) -> dict:
    root = Path(root_path).resolve()
    toml_path = root / "forge.toml"
    created = False
    if not toml_path.exists():
        _create_project(root)
        created = True

    _write_ide_config(root)

    cfg = _read_toml(toml_path)
    proj_name = cfg.get("project", {}).get("name", root.name)
    forge_ver = cfg.get("project", {}).get("forge_version", "")

    # Deactivate all projects; reuse existing record for this path if present
    existing = None
    for p in ForgeProject.all():
        if p.root_path == str(root):
            existing = p
        else:
            p.is_active = "false"

    if existing:
        project_id = existing.id
        _clear_project_records(project_id)
        existing.name = proj_name
        existing.forge_version = forge_ver
        existing.is_active = "true"
    else:
        project_id = f"fp-{uuid.uuid4().hex[:12]}"
        ForgeProject.create(
            id=project_id,
            name=proj_name,
            root_path=str(root),
            forge_version=forge_ver,
            is_active="true",
            registered_at=_now(),
        )

    _sync_from_toml(project_id, root, cfg)

    return {"project_id": project_id, "name": proj_name, "root_path": str(root), "created": created}


@action_endpoint(
    name="unregister_project",
    endpoint_id=UNREGISTER_PROJECT_ID,
    description="Remove a project and all its associated records",
    params=[
        {"name": "project_id", "type": "string", "required": True},
    ],
)
def unregister_project(project_id: str) -> dict:
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    name = proj.name
    _clear_project_records(project_id)
    proj.remove()
    return {"deleted": project_id, "name": name}


@action_endpoint(
    name="set_active_project",
    endpoint_id=SET_ACTIVE_PROJECT_ID,
    description="Switch the active project shown in the UI",
    params=[
        {"name": "project_id", "type": "string", "required": True},
    ],
)
def set_active_project(project_id: str) -> dict:
    for p in ForgeProject.all():
        p.is_active = "true" if p.id == project_id else "false"
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    return {"active": project_id, "name": proj.name}


@action_endpoint(
    name="sync_project",
    endpoint_id=SYNC_PROJECT_ID,
    description="Re-read forge.toml and artifact files to refresh project metadata",
    params=[
        {"name": "project_id", "type": "string", "required": True},
    ],
)
def sync_project(project_id: str) -> dict:
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    root = Path(proj.root_path)
    toml_path = root / "forge.toml"
    if not toml_path.exists():
        return {"error": f"forge.toml not found at {proj.root_path}"}

    cfg = _read_toml(toml_path)
    _clear_project_records(project_id)
    _sync_from_toml(project_id, root, cfg)
    return {"synced": project_id}


_PIPELINE_TEMPLATE = '''\
"""
Pipeline Layer — {name}
"""
from forge.pipeline import pipeline, ForgeInput, ForgeOutput

# These UUIDs were generated for this pipeline. Load data into them with:
#   forge dataset load <file.csv> --name source     (to populate INPUT_DATASET_ID)
# Or replace them with existing dataset UUIDs from `forge dataset list`.
INPUT_DATASET_ID  = "{input_uuid}"
OUTPUT_DATASET_ID = "{output_uuid}"


@pipeline(
    inputs={{
        "source": ForgeInput(INPUT_DATASET_ID),
    }},
    outputs={{
        "result": ForgeOutput(OUTPUT_DATASET_ID),
    }},
)
def run(inputs, outputs):
    df = inputs.source.df()
    # Transform df here
    outputs.result.write(df)
'''


@action_endpoint(
    name="create_pipeline",
    endpoint_id=CREATE_PIPELINE_ID,
    description="Scaffold a new pipeline file and register it in forge.toml",
    params=[
        {"name": "project_id", "type": "string", "required": True},
        {"name": "pipeline_name", "type": "string", "required": True,
         "description": "Snake_case name for the pipeline (e.g. 'ingest_raw')"},
    ],
)
def create_pipeline(project_id: str, pipeline_name: str) -> dict:
    import re
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}

    name = re.sub(r"[^a-z0-9_]", "_", pipeline_name.lower()).strip("_")
    if not name:
        return {"error": "Invalid pipeline name"}

    root = Path(proj.root_path)
    pipelines_dir = root / "pipelines"
    pipelines_dir.mkdir(parents=True, exist_ok=True)

    init = pipelines_dir / "__init__.py"
    if not init.exists():
        init.write_text("")

    pipeline_file = pipelines_dir / f"{name}.py"
    if pipeline_file.exists():
        return {"error": f"pipelines/{name}.py already exists"}

    input_uuid = str(uuid.uuid4())
    output_uuid = str(uuid.uuid4())
    pipeline_file.write_text(_PIPELINE_TEMPLATE.format(
        name=name, input_uuid=input_uuid, output_uuid=output_uuid,
    ))

    toml_path = root / "forge.toml"
    if toml_path.exists():
        cfg = _read_toml(toml_path)
        already_in_toml = any(p.get("name") == name for p in cfg.get("pipelines", []))
        if not already_in_toml:
            toml_content = toml_path.read_text()
            entry = (
                f'\n[[pipelines]]\n'
                f'name = "{name}"\n'
                f'module = "pipelines.{name}"\n'
                f'function = "run"\n'
            )
            toml_path.write_text(toml_content + entry)
            cfg = _read_toml(toml_path)
        _clear_project_records(project_id)
        _sync_from_toml(project_id, root, cfg)

    return {"file": str(pipeline_file), "name": name}


@action_endpoint(
    name="list_project_datasets",
    endpoint_id=LIST_PROJECT_DATASETS_ID,
    description="List all datasets registered in the active managed project",
    params=[
        {"name": "project_id", "type": "string", "required": True},
    ],
)
def list_project_datasets(project_id: str) -> dict:
    from forge.storage.engine import StorageEngine
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    with StorageEngine(Path(proj.root_path) / ".forge") as engine:
        datasets = engine.list_datasets()
        return {
            "datasets": [
                {
                    "id": d.id,
                    "name": d.name,
                    "row_count": d.row_count,
                    "created_at": d.created_at,
                    "is_snapshot": d.is_snapshot,
                }
                for d in datasets
            ]
        }


@action_endpoint(
    endpoint_id=PREVIEW_DATASET_ID,
    description="Return the first N rows of a dataset as column/row arrays for preview",
    params=[
        {"name": "project_id",  "type": "string",  "required": True},
        {"name": "dataset_id",  "type": "string",  "required": True},
        {"name": "limit",       "type": "integer", "required": False},
    ],
)
def preview_dataset(project_id: str, dataset_id: str, limit: int = 100) -> dict:
    from forge.storage.engine import StorageEngine
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    try:
        with StorageEngine(Path(proj.root_path) / ".forge") as engine:
            df = engine.read_dataset(dataset_id).head(int(limit))
            columns = list(df.columns)
            rows = [
                [None if (v != v) else (v.isoformat() if hasattr(v, "isoformat") else v)
                 for v in row]
                for row in df.itertuples(index=False, name=None)
            ]
            return {"columns": columns, "rows": rows}
    except Exception as exc:
        return {"error": str(exc)}


@action_endpoint(
    endpoint_id=PREVIEW_MODEL_ID,
    description="Return the first N rows of a model's snapshot dataset for preview",
    params=[
        {"name": "project_id",  "type": "string",  "required": True},
        {"name": "model_name",  "type": "string",  "required": True},
        {"name": "limit",       "type": "integer", "required": False},
    ],
)
def preview_model(project_id: str, model_name: str, limit: int = 200) -> dict:
    from forge.storage.engine import StorageEngine
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    model_rec = next((m for m in ObjectType.filter(project_id=project_id) if m.name == model_name), None)
    if model_rec is None:
        return {"error": f"Model '{model_name}' not found in project"}
    forge_dir = Path(proj.root_path) / ".forge"
    artifact = forge_dir / "artifacts" / f"{model_name}.schema.json"
    dataset_id = model_rec.backing_dataset_id
    if artifact.exists():
        try:
            snap_id = json.loads(artifact.read_text()).get("snapshot_dataset_id")
            if snap_id:
                dataset_id = snap_id
        except Exception:
            pass
    try:
        with StorageEngine(forge_dir) as engine:
            df = engine.read_dataset(dataset_id).head(int(limit))
            columns = list(df.columns)
            rows = [
                [None if (v != v) else (v.isoformat() if hasattr(v, "isoformat") else v)
                 for v in row]
                for row in df.itertuples(index=False, name=None)
            ]
            return {"columns": columns, "rows": rows}
    except Exception as exc:
        return {"error": str(exc)}


_TYPE_MAP = {
    "integer": "int",
    "float": "float",
    "boolean": "bool",
    "datetime": "str",
    "string": "str",
}

_MODEL_TEMPLATE = '''\
"""
Model Layer — {class_name} ({mode})
Backed by dataset {dataset_id}.
"""
from forge.model import forge_model, field_def, {base_class}

DATASET_ID = "{dataset_id}"


@forge_model(mode="{mode}", backing_dataset=DATASET_ID)
class {class_name}({base_class}):
{fields}
'''


@action_endpoint(
    name="create_model",
    endpoint_id=CREATE_MODEL_ID,
    description="Scaffold a new model file from an existing dataset and register it in forge.toml",
    params=[
        {"name": "project_id", "type": "string", "required": True},
        {"name": "dataset_id", "type": "string", "required": True},
        {"name": "model_name", "type": "string", "required": True,
         "description": "PascalCase class name (e.g. 'BitcoinPrice')"},
        {"name": "mode", "type": "string", "required": False,
         "description": "snapshot (mutable) or immutable (read-only). Defaults to snapshot."},
    ],
)
def create_model(project_id: str, dataset_id: str, model_name: str, mode: str = "snapshot") -> dict:
    import re
    from forge.storage.engine import StorageEngine

    if mode not in ("snapshot", "immutable"):
        return {"error": "mode must be 'snapshot' or 'immutable'"}

    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}

    # Validate and normalise the class name
    class_name = re.sub(r"^[^A-Za-z]+", "", model_name.strip())  # strip leading non-letters
    class_name = re.sub(r"[^A-Za-z0-9_]", "_", class_name)       # replace remaining bad chars
    if not class_name:
        return {"error": "model_name must contain at least one letter"}

    # snake_case module name
    snake_name = re.sub(r"(?<!^)(?=[A-Z])", "_", class_name).lower()
    snake_name = re.sub(r"[^a-z0-9_]", "_", snake_name).strip("_")

    root = Path(proj.root_path)
    models_dir = root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    init = models_dir / "__init__.py"
    if not init.exists():
        init.write_text("")

    model_file = models_dir / f"{snake_name}.py"
    if model_file.exists():
        return {"error": f"models/{snake_name}.py already exists"}

    # Read dataset schema from the managed project's StorageEngine
    with StorageEngine(root / ".forge") as engine:
        meta = engine.get_dataset(dataset_id)
        if meta is None:
            return {"error": f"Dataset {dataset_id} not found in project storage"}
        schema_fields = meta.schema.get("fields", {})

    if not schema_fields:
        return {"error": "Dataset has no schema fields — run the pipeline at least once first"}

    # Pick primary key: prefer 'id' column, else first column
    col_names = list(schema_fields.keys())
    pk_candidates = [c for c in col_names if c.lower() == "id"]
    primary_key = pk_candidates[0] if pk_candidates else col_names[0]

    # Build field_def lines
    field_lines = []
    for col, info in schema_fields.items():
        py_type = _TYPE_MAP.get(info.get("type", "string"), "str")
        display = col.replace("_", " ").title()
        hints = []
        if col == primary_key:
            hints.append("primary_key=True")
        hints.append(f'display="{display}"')
        if info.get("type") == "datetime":
            hints.append('display_hint="date"')
        field_lines.append(f"    {col}: {py_type} = field_def({', '.join(hints)})")

    base_class = "ForgeSnapshotModel" if mode == "snapshot" else "ForgeStreamModel"
    fields_block = "\n".join(field_lines)
    model_file.write_text(_MODEL_TEMPLATE.format(
        class_name=class_name,
        dataset_id=dataset_id,
        fields=fields_block,
        mode=mode,
        base_class=base_class,
    ))

    # Patch forge.toml
    toml_path = root / "forge.toml"
    if toml_path.exists():
        cfg = _read_toml(toml_path)
        already_in_toml = any(m.get("name") == class_name for m in cfg.get("models", []))
        if not already_in_toml:
            entry = (
                f'\n[[models]]\n'
                f'name = "{class_name}"\n'
                f'class = "{class_name}"\n'
                f'module = "models.{snake_name}"\n'
                f'mode = "{mode}"\n'
            )
            toml_path.write_text(toml_path.read_text() + entry)


@action_endpoint(
    name="open_in_vscode",
    endpoint_id=OPEN_IN_VSCODE_ID,
    description="Open a file in VS Code, reusing the existing window if one is open",
    params=[
        {"name": "folder_path", "type": "string", "required": True},
        {"name": "file_path", "type": "string", "required": True},
    ],
)
def open_in_vscode(folder_path: str, file_path: str) -> dict:
    import os
    import shutil
    import subprocess
    FALLBACK = "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"
    code_bin = shutil.which("code") or (FALLBACK if os.path.exists(FALLBACK) else None)
    if not code_bin:
        return {"error": "'code' CLI not found — install it via VS Code: Shell Command: Install 'code' command in PATH"}
    subprocess.Popen([code_bin, "--reuse-window", folder_path, file_path])
    return {"ok": True}


_ENDPOINT_REPO_SETUP = 'from setuptools import setup, find_packages\nsetup(name="{repo_name}", packages=find_packages())\n'

_ENDPOINT_FILE_NEW: dict[str, str] = {
    "action": '''\
"""
Control Layer — {repo_name}
"""
from __future__ import annotations

from forge.control import action_endpoint

{CONST_NAME}_ID = "{endpoint_uuid}"


@action_endpoint(
    name="{endpoint_name}",
    endpoint_id={CONST_NAME}_ID,
    description="TODO: describe what this endpoint does",
    params=[
        {{"name": "input", "type": "string", "required": True}},
    ],
)
def {endpoint_name}(input: str) -> dict:
    return {{"result": input}}
''',
    "streaming": '''\
"""
Control Layer — {repo_name}
"""
from __future__ import annotations

from forge.control import streaming_endpoint, StreamEvent

{CONST_NAME}_ID = "{endpoint_uuid}"


@streaming_endpoint(
    name="{endpoint_name}",
    endpoint_id={CONST_NAME}_ID,
    description="TODO: describe what this endpoint does",
    params=[
        {{"name": "input", "type": "string", "required": True}},
    ],
)
def {endpoint_name}(input: str):
    # TODO: yield StreamEvent(data="...", event="log") for each update
    yield StreamEvent(data="done", event="done")
''',
    "computed_column": '''\
"""
Control Layer — {repo_name}
"""
from __future__ import annotations

from forge.control import computed_column_endpoint

{CONST_NAME}_ID = "{endpoint_uuid}"


@computed_column_endpoint(
    object_type="MyModel",
    columns=["my_column"],
    endpoint_id={CONST_NAME}_ID,
    name="{endpoint_name}",
    description="TODO: describe what this computed column does",
)
def {endpoint_name}(objects, **kwargs) -> dict:
    # TODO: compute a value per object; keys must be object IDs
    return {{obj.id: {{"my_column": None}} for obj in objects}}
''',
}

_ENDPOINT_SNIPPET: dict[str, str] = {
    "action": '''

from forge.control import action_endpoint  # noqa: F811

{CONST_NAME}_ID = "{endpoint_uuid}"


@action_endpoint(
    name="{endpoint_name}",
    endpoint_id={CONST_NAME}_ID,
    description="TODO: describe what this endpoint does",
    params=[
        {{"name": "input", "type": "string", "required": True}},
    ],
)
def {endpoint_name}(input: str) -> dict:
    return {{"result": input}}
''',
    "streaming": '''

from forge.control import streaming_endpoint, StreamEvent  # noqa: F811

{CONST_NAME}_ID = "{endpoint_uuid}"


@streaming_endpoint(
    name="{endpoint_name}",
    endpoint_id={CONST_NAME}_ID,
    description="TODO: describe what this endpoint does",
    params=[
        {{"name": "input", "type": "string", "required": True}},
    ],
)
def {endpoint_name}(input: str):
    yield StreamEvent(data="done", event="done")
''',
    "computed_column": '''

from forge.control import computed_column_endpoint  # noqa: F811

{CONST_NAME}_ID = "{endpoint_uuid}"


@computed_column_endpoint(
    object_type="MyModel",
    columns=["my_column"],
    endpoint_id={CONST_NAME}_ID,
    name="{endpoint_name}",
    description="TODO: describe what this computed column does",
)
def {endpoint_name}(objects, **kwargs) -> dict:
    return {{obj.id: {{"my_column": None}} for obj in objects}}
''',
}


@action_endpoint(
    name="create_endpoint",
    endpoint_id=CREATE_ENDPOINT_ID,
    description="Scaffold a new endpoint function and register its repo in forge.toml",
    params=[
        {"name": "project_id", "type": "string", "required": True},
        {"name": "endpoint_name", "type": "string", "required": True,
         "description": "Snake_case function name (e.g. 'get_summary')"},
        {"name": "repo_name", "type": "string", "required": True,
         "description": "Endpoint repo to add to (existing name or new snake_case name)"},
        {"name": "kind", "type": "string", "required": False,
         "description": "action | streaming | computed_column (default: action)"},
    ],
)
def create_endpoint(
    project_id: str,
    endpoint_name: str,
    repo_name: str,
    kind: str = "action",
) -> dict:
    import re

    if kind not in ("action", "streaming", "computed_column"):
        return {"error": "kind must be 'action', 'streaming', or 'computed_column'"}

    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}

    name = re.sub(r"[^a-z0-9_]", "_", endpoint_name.lower()).strip("_")
    if not name:
        return {"error": "Invalid endpoint name"}

    repo = re.sub(r"[^a-z0-9_]", "_", repo_name.lower()).strip("_")
    if not repo:
        return {"error": "Invalid repo name"}

    const_name = name.upper()
    endpoint_uuid = str(uuid.uuid4())
    root = Path(proj.root_path)
    toml_path = root / "forge.toml"
    cfg = _read_toml(toml_path) if toml_path.exists() else {}

    existing_repo = next(
        (r for r in cfg.get("endpoint_repos", []) if r.get("name") == repo), None
    )
    repo_root = root / "endpoint_repos" / repo
    pkg_dir = repo_root / repo
    endpoints_file = pkg_dir / "endpoints.py"

    if existing_repo is None:
        # New repo — scaffold full package structure
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "__init__.py").write_text("")
        (repo_root / "setup.py").write_text(
            _ENDPOINT_REPO_SETUP.format(repo_name=repo)
        )
        endpoints_file.write_text(
            _ENDPOINT_FILE_NEW[kind].format(
                repo_name=repo,
                CONST_NAME=const_name,
                endpoint_uuid=endpoint_uuid,
                endpoint_name=name,
            )
        )
        if toml_path.exists():
            toml_path.write_text(
                toml_path.read_text()
                + f'\n[[endpoint_repos]]\nname = "{repo}"\npath = "./endpoint_repos/{repo}"\n'
            )
    else:
        # Existing repo — append snippet to endpoints.py
        pkg_dir.mkdir(parents=True, exist_ok=True)
        if not (pkg_dir / "__init__.py").exists():
            (pkg_dir / "__init__.py").write_text("")
        existing = endpoints_file.read_text() if endpoints_file.exists() else ""
        if f'def {name}(' in existing:
            return {"error": f"Function '{name}' already exists in {repo}/endpoints.py"}
        endpoints_file.write_text(
            existing + _ENDPOINT_SNIPPET[kind].format(
                CONST_NAME=const_name,
                endpoint_uuid=endpoint_uuid,
                endpoint_name=name,
            )
        )

    cfg = _read_toml(toml_path) if toml_path.exists() else {}
    _clear_project_records(project_id)
    _sync_from_toml(project_id, root, cfg)

    return {"file": str(endpoints_file), "name": name, "repo": repo, "kind": kind}


_APP_COMMAND = '''\
#!/usr/bin/env bash
# {app_name} — start the dev server and open the app in a browser.
# Double-click on macOS, or run: bash {app_name}.command
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
APP_DIR="$PROJECT_ROOT/apps/{app_name}"
PORT={port}

if [ ! -d "$APP_DIR/node_modules" ]; then
  echo "→ Installing npm dependencies (first run)..."
  npm install --prefix "$APP_DIR" --silent
fi

echo "→ Starting {app_name} dev server on :$PORT..."
npm --prefix "$APP_DIR" run dev &
DEV_PID=$!

echo "→ Waiting for server to be ready..."
for _ in $(seq 1 60); do
  if curl -s "http://localhost:$PORT" > /dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

echo "✓ {app_name} running at http://localhost:$PORT"
if command -v open &>/dev/null; then open "http://localhost:$PORT"
elif command -v xdg-open &>/dev/null; then xdg-open "http://localhost:$PORT"
fi

echo "Press Ctrl+C to stop."
cleanup() {{ kill "$DEV_PID" 2>/dev/null || true; }}
trap cleanup EXIT INT TERM
wait "$DEV_PID"
'''

_APP_PACKAGE_JSON = '''\
{{
  "name": "{app_name}",
  "version": "0.1.0",
  "private": true,
  "scripts": {{
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "@tanstack/react-query": "^5.40.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  }},
  "devDependencies": {{
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.4.5",
    "vite": "^5.3.1"
  }}
}}
'''

_APP_VITE_CONFIG = '''\
import {{ defineConfig }} from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({{
  plugins: [react()],
  resolve: {{
    alias: {{
      "@forge-framework/ts": "{forge_ts_src}",
    }},
  }},
  server: {{
    port: {port},
    proxy: {{
      "/api": "http://localhost:8000",
      "/endpoints": "http://localhost:8000",
    }},
  }},
}});
'''

_APP_INDEX_HTML = '''\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{app_name}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
'''

_APP_TSCONFIG = '''\
{{
  "compilerOptions": {{
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  }},
  "include": ["src"]
}}
'''

_APP_MAIN_TSX = '''\
import React from "react";
import {{ createRoot }} from "react-dom/client";
import {{ QueryClient, QueryClientProvider }} from "@tanstack/react-query";
import {{ App }} from "./App.js";

const queryClient = new QueryClient();

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={{queryClient}}>
    <App />
  </QueryClientProvider>
);
'''

_APP_APP_TSX = '''\
import React from "react";

export function App() {{
  return (
    <div style={{{{ fontFamily: "system-ui, sans-serif", padding: 24 }}}}>
      <h1>{app_name}</h1>
      <p>
        Your Forge app. Import from <code>@forge-framework/ts</code> to fetch
        object sets and call endpoints.
      </p>
    </div>
  );
}}
'''


@action_endpoint(
    name="create_app",
    endpoint_id=CREATE_APP_ID,
    description="Scaffold a new Vite+React app in the project's apps/ directory and register it in forge.toml",
    params=[
        {"name": "project_id", "type": "string", "required": True},
        {"name": "app_name", "type": "string", "required": True,
         "description": "kebab-case app name (e.g. 'my-dashboard')"},
        {"name": "port", "type": "string", "required": False,
         "description": "Dev server port (default: 5177)"},
    ],
)
def create_app(project_id: str, app_name: str, port: str = "5177") -> dict:
    import re
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}

    name = re.sub(r"[^a-z0-9\-_]", "-", app_name.lower()).strip("-_")
    if not name:
        return {"error": "Invalid app name"}

    root = Path(proj.root_path)
    app_dir = root / "apps" / name
    if app_dir.exists():
        return {"error": f"apps/{name} already exists"}

    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "src").mkdir(exist_ok=True)

    forge_ts_src = str(_repo_root() / "packages" / "forge-ts" / "src" / "index.ts")

    (app_dir / "package.json").write_text(_APP_PACKAGE_JSON.format(app_name=name))
    (app_dir / "vite.config.ts").write_text(_APP_VITE_CONFIG.format(
        forge_ts_src=forge_ts_src, port=port,
    ))
    (app_dir / "index.html").write_text(_APP_INDEX_HTML.format(app_name=name))
    (app_dir / "tsconfig.json").write_text(_APP_TSCONFIG)
    (app_dir / "src" / "main.tsx").write_text(_APP_MAIN_TSX)
    (app_dir / "src" / "App.tsx").write_text(_APP_APP_TSX.format(app_name=name))

    command_file = root / f"{name}.command"
    command_file.write_text(_APP_COMMAND.format(app_name=name, port=port))
    command_file.chmod(0o755)

    toml_path = root / "forge.toml"
    if toml_path.exists():
        cfg = _read_toml(toml_path)
        already = any(a.get("name") == name for a in cfg.get("apps", []))
        if not already:
            app_id = re.sub(r"[^a-z0-9_]", "_", name)
            entry = (
                f'\n[[apps]]\n'
                f'name = "{name}"\n'
                f'id = "{app_id}"\n'
                f'path = "./apps/{name}"\n'
                f'port = "{port}"\n'
            )
            toml_path.write_text(toml_path.read_text() + entry)
            cfg = _read_toml(toml_path)
        _clear_project_records(project_id)
        _sync_from_toml(project_id, root, cfg)

    return {"path": str(app_dir), "name": name, "port": port}


@action_endpoint(
    name="run_app",
    endpoint_id=RUN_APP_ID,
    description="Start an app's Vite dev server as a background process",
    params=[
        {"name": "project_id", "type": "string", "required": True},
        {"name": "app_name", "type": "string", "required": True},
    ],
)
def run_app(project_id: str, app_name: str) -> dict:
    import shutil
    import subprocess
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    root = Path(proj.root_path)
    app_record = next((a for a in App.all() if a.project_id == project_id and a.name == app_name), None)
    if app_record is None:
        return {"error": f"App '{app_name}' not found"}
    app_dir = (root / app_record.path).resolve()
    if not app_dir.exists():
        return {"error": f"App directory not found: {app_dir}"}
    npm = shutil.which("npm")
    if npm is None:
        return {"error": "npm not found in PATH"}
    if not (app_dir / "node_modules").exists():
        result = subprocess.run([npm, "install"], cwd=str(app_dir), capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return {"error": f"npm install failed: {result.stderr[:500]}"}
    import sys
    import time
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    # Read api_port from the project's forge.toml
    api_port = None
    toml_path = root / "forge.toml"
    if toml_path.exists():
        with open(toml_path, "rb") as f:
            raw_cfg = tomllib.load(f)
        api_port = raw_cfg.get("project", {}).get("api_port")

    # Start the project's forge backend if configured and not already running
    if api_port:
        check = subprocess.run(["lsof", "-ti", f"tcp:{api_port}"], capture_output=True, text=True)
        if not check.stdout.strip():
            # Prefer venv forge binary, then PATH
            forge_bin = str(root / ".venv" / "bin" / "forge")
            if not Path(forge_bin).exists():
                forge_bin = shutil.which("forge") or "forge"
            with open(root / ".forge-api.log", "w") as api_log:
                subprocess.Popen(
                    [forge_bin, "dev", "serve", "--port", str(api_port)],
                    cwd=str(root),
                    start_new_session=True,
                    stdout=api_log,
                    stderr=api_log,
                )

    log_file = app_dir / ".forge-dev.log"
    with open(log_file, "w") as log:
        proc = subprocess.Popen(
            [npm, "run", "dev"],
            cwd=str(app_dir),
            start_new_session=True,
            stdout=log,
            stderr=log,
        )
    time.sleep(0.8)
    if proc.poll() is not None:
        tail = log_file.read_text(encoding="utf-8", errors="replace")[-800:] if log_file.exists() else ""
        return {"error": f"Dev server exited immediately.\n{tail}"}
    port = app_record.port or "?"
    return {"ok": True, "url": f"http://localhost:{port}", "port": port}


@action_endpoint(
    name="ping_app",
    endpoint_id=PING_APP_ID,
    description="Check whether an app's dev server is accepting connections",
    params=[
        {"name": "port", "type": "string", "required": True},
    ],
)
def ping_app(port: str) -> dict:
    import urllib.request
    try:
        urllib.request.urlopen(f"http://localhost:{int(port)}/", timeout=1)
        return {"live": True}
    except Exception:
        return {"live": False}


@action_endpoint(
    name="stop_app",
    endpoint_id=STOP_APP_ID,
    description="Stop a running app's Vite dev server by killing the process on its port",
    params=[
        {"name": "project_id", "type": "string", "required": True},
        {"name": "app_name", "type": "string", "required": True},
    ],
)
def stop_app(project_id: str, app_name: str) -> dict:
    import subprocess
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    app_record = next((a for a in App.all() if a.project_id == project_id and a.name == app_name), None)
    if app_record is None:
        return {"error": f"App '{app_name}' not found"}
    import sys
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    port = app_record.port
    if not port:
        return {"error": f"App '{app_name}' has no port configured"}

    # Read api_port from the project's forge.toml
    root = Path(proj.root_path)
    api_port = None
    toml_path = root / "forge.toml"
    if toml_path.exists():
        with open(toml_path, "rb") as f:
            raw_cfg = tomllib.load(f)
        api_port = raw_cfg.get("project", {}).get("api_port")

    # Kill the app's Vite dev server
    all_pids = []
    result = subprocess.run(["lsof", "-ti", f"tcp:{port}"], capture_output=True, text=True)
    all_pids.extend(result.stdout.strip().splitlines())

    # Kill the forge backend only if no other apps in this project are still running
    if api_port:
        other_apps = [a for a in App.all() if a.project_id == project_id and a.name != app_name and a.port]
        other_running = any(
            subprocess.run(["lsof", "-ti", f"tcp:{a.port}"], capture_output=True, text=True).stdout.strip()
            for a in other_apps
        )
        if not other_running:
            result = subprocess.run(["lsof", "-ti", f"tcp:{api_port}"], capture_output=True, text=True)
            all_pids.extend(result.stdout.strip().splitlines())

    if not all_pids:
        return {"ok": True, "stopped": False, "message": f"No process found on port {port}"}
    for pid in all_pids:
        subprocess.run(["kill", pid.strip()], capture_output=True)
    return {"ok": True, "stopped": True, "port": port, "pids": all_pids}


@action_endpoint(
    name="open_app",
    endpoint_id=OPEN_APP_ID,
    description="Open an app in the default browser",
    params=[
        {"name": "project_id", "type": "string", "required": True},
        {"name": "app_name", "type": "string", "required": True},
    ],
)
def open_app(project_id: str, app_name: str) -> dict:
    import subprocess
    import shutil
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    app_record = next((a for a in App.all() if a.project_id == project_id and a.name == app_name), None)
    if app_record is None:
        return {"error": f"App '{app_name}' not found"}
    port = app_record.port
    if not port:
        return {"error": f"App '{app_name}' has no port configured"}
    url = f"http://localhost:{port}"
    opener = shutil.which("open") or shutil.which("xdg-open")
    if opener:
        subprocess.Popen([opener, url])
    return {"ok": True, "url": url}


_DOCS_ORDER = [
    "forge-overview",
    "pipeline-layer",
    "model-layer",
    "control-layer",
    "view-layer",
    "todo",
]


@action_endpoint(
    name="call_project_endpoint",
    endpoint_id=CALL_PROJECT_ENDPOINT_ID,
    description="Proxy a test call to the active project's backend endpoint",
    params=[
        {"name": "project_id",   "type": "string", "required": True, "description": "Active project ID"},
        {"name": "endpoint_id",  "type": "string", "required": True, "description": "Target endpoint UUID"},
        {"name": "payload_json", "type": "string", "required": True, "description": "JSON payload string"},
    ],
)
def call_project_endpoint(project_id: str, endpoint_id: str, payload_json: str) -> dict:
    import urllib.request
    import urllib.error

    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}

    root = Path(proj.root_path)
    toml_path = root / "forge.toml"
    if not toml_path.exists():
        return {"error": "forge.toml not found in project root"}

    cfg = _read_toml(toml_path)
    api_port = cfg.get("project", {}).get("api_port")
    if not api_port:
        return {"error": "api_port not configured in forge.toml [project] section"}

    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid JSON payload: {exc}"}

    url = f"http://localhost:{api_port}/endpoints/{endpoint_id}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            try:
                result = json.loads(body)
            except Exception:
                result = body
            return {"status": resp.status, "result": result}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            err_detail = json.loads(body)
        except Exception:
            err_detail = body
        return {"status": exc.code, "error": err_detail}
    except Exception as exc:
        return {"error": str(exc)}


@action_endpoint(
    name="get_docs",
    endpoint_id=GET_DOCS_ID,
    description="Return all Forge framework docs as a list of {name, title, content} objects",
    params=[],
)
def get_docs() -> dict:
    docs_dir = Path(__file__).resolve().parents[5] / "docs"
    if not docs_dir.exists():
        return {"docs": [], "error": f"Docs directory not found: {docs_dir}"}

    files = {f.stem: f for f in sorted(docs_dir.glob("*.md"))}
    ordered = [s for s in _DOCS_ORDER if s in files]
    remaining = [s for s in sorted(files) if s not in ordered]
    results = []
    for stem in ordered + remaining:
        f = files[stem]
        content = f.read_text(encoding="utf-8")
        first_line = content.lstrip().splitlines()[0] if content.strip() else stem
        title = first_line.lstrip("# ").strip() if first_line.startswith("#") else stem
        results.append({"name": stem, "title": title, "content": content})
    return {"docs": results}
