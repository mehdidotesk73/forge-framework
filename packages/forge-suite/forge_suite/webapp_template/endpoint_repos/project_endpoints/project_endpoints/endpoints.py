"""
Control Layer — project_endpoints
Manages ForgeProject records and syncs metadata from managed projects.
"""
from __future__ import annotations

from pathlib import Path

from forge.control import action_endpoint

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


def _get_root(project_id: str) -> Path | None:
    from models.models import ForgeProject
    proj = ForgeProject.get(project_id)
    return Path(proj.root_path) if proj else None


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
    from forge_suite.operations.projects import register_project as _op
    return _op(root_path)


@action_endpoint(
    name="unregister_project",
    endpoint_id=UNREGISTER_PROJECT_ID,
    description="Remove a project and all its associated records",
    params=[
        {"name": "project_id", "type": "string", "required": True},
    ],
)
def unregister_project(project_id: str) -> dict:
    from forge_suite.operations.projects import unregister_project as _op
    return _op(project_id)


@action_endpoint(
    name="set_active_project",
    endpoint_id=SET_ACTIVE_PROJECT_ID,
    description="Switch the active project shown in the UI",
    params=[
        {"name": "project_id", "type": "string", "required": True},
    ],
)
def set_active_project(project_id: str) -> dict:
    from forge_suite.operations.projects import set_active_project as _op
    return _op(project_id)


@action_endpoint(
    name="sync_project",
    endpoint_id=SYNC_PROJECT_ID,
    description="Re-read forge.toml and artifact files to refresh project metadata",
    params=[
        {"name": "project_id", "type": "string", "required": True},
    ],
)
def sync_project(project_id: str) -> dict:
    from forge_suite.operations.projects import sync_project as _op
    return _op(project_id)


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
    from forge.operations.scaffolding import create_pipeline as _op
    from forge_suite.operations.projects import sync_project as _sync
    root = _get_root(project_id)
    if root is None:
        return {"error": f"Project {project_id} not found"}
    result = _op(root, pipeline_name)
    if "error" not in result:
        _sync(project_id)
    return result


@action_endpoint(
    name="list_project_datasets",
    endpoint_id=LIST_PROJECT_DATASETS_ID,
    description="List all datasets registered in the active managed project",
    params=[
        {"name": "project_id", "type": "string", "required": True},
    ],
)
def list_project_datasets(project_id: str) -> dict:
    from forge.operations.datasets import list_project_datasets as _op
    root = _get_root(project_id)
    if root is None:
        return {"error": f"Project {project_id} not found"}
    return _op(root)


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
    from forge.operations.datasets import preview_dataset as _op
    root = _get_root(project_id)
    if root is None:
        return {"error": f"Project {project_id} not found"}
    return _op(root, dataset_id, limit)


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
    from forge.operations.datasets import preview_model as _op
    root = _get_root(project_id)
    if root is None:
        return {"error": f"Project {project_id} not found"}
    return _op(root, model_name, limit)


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
    from forge.operations.scaffolding import create_model as _op
    from forge_suite.operations.projects import sync_project as _sync
    root = _get_root(project_id)
    if root is None:
        return {"error": f"Project {project_id} not found"}
    result = _op(root, dataset_id, model_name, mode)
    if result is not None and "error" not in result:
        _sync(project_id)
    return result or {}


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
    from forge.operations.ide import open_in_vscode as _op
    return _op(folder_path, file_path)


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
         "description": "action | streaming | computed_attribute (default: action)"},
    ],
)
def create_endpoint(
    project_id: str,
    endpoint_name: str,
    repo_name: str,
    kind: str = "action",
) -> dict:
    from forge.operations.scaffolding import create_endpoint as _op
    from forge_suite.operations.projects import sync_project as _sync
    root = _get_root(project_id)
    if root is None:
        return {"error": f"Project {project_id} not found"}
    result = _op(root, endpoint_name, repo_name, kind)
    if "error" not in result:
        _sync(project_id)
    return result


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
    import traceback
    from forge.operations.scaffolding import create_app as _op
    from forge_suite.operations.projects import sync_project as _sync
    root = _get_root(project_id)
    if root is None:
        return {"error": f"Project {project_id} not found"}
    try:
        result = _op(root, app_name, port)
    except Exception as exc:
        return {"error": str(exc), "detail": traceback.format_exc()}
    if "error" not in result:
        _sync(project_id)
    return result


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
    from forge_suite.operations.apps import run_app as _op
    return _op(project_id, app_name)


@action_endpoint(
    name="ping_app",
    endpoint_id=PING_APP_ID,
    description="Check whether an app's dev server is accepting connections",
    params=[
        {"name": "project_id", "type": "string", "required": True},
        {"name": "app_name", "type": "string", "required": True},
    ],
)
def ping_app(project_id: str, app_name: str) -> dict:
    from forge_suite.operations.apps import ping_app as _op
    return _op(project_id, app_name)


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
    from forge_suite.operations.apps import stop_app as _op
    return _op(project_id, app_name)


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
    from forge_suite.operations.apps import open_app as _op
    return _op(project_id, app_name)


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
    from forge.operations.endpoints_ops import call_project_endpoint as _op
    from forge_suite.operations.apps import _ensure_api_running
    root = _get_root(project_id)
    if root is None:
        return {"error": f"Project {project_id} not found"}
    try:
        api_port = _ensure_api_running(root)
    except RuntimeError as exc:
        return {"error": str(exc)}
    return _op(root, endpoint_id, payload_json, api_port=api_port)


@action_endpoint(
    name="get_docs",
    endpoint_id=GET_DOCS_ID,
    description="Return all Forge framework docs as a list of {name, title, content} objects",
    params=[],
)
def get_docs() -> dict:
    from forge.operations.endpoints_ops import get_docs as _op
    return _op()
