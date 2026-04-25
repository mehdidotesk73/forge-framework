"""
Control Layer — module_endpoints
Manages the forge-suite module library: absorb, shed, implant, and list.
"""
from __future__ import annotations

from forge.control import action_endpoint

LIST_MODULES_ID   = "cccccccc-0028-0000-0000-000000000000"
ABSORB_MODULE_ID  = "cccccccc-0029-0000-0000-000000000000"
SHED_MODULE_ID    = "cccccccc-0030-0000-0000-000000000000"
IMPLANT_MODULE_ID = "cccccccc-0031-0000-0000-000000000000"


@action_endpoint(
    name="list_modules",
    endpoint_id=LIST_MODULES_ID,
    description="Return all modules absorbed into this forge-suite instance",
    params=[],
)
def list_modules() -> dict:
    from forge_suite.operations.modules import list_modules as _op
    return _op()


@action_endpoint(
    name="absorb_module",
    endpoint_id=ABSORB_MODULE_ID,
    description="Absorb an existing Forge project as a module into forge-suite",
    params=[
        {"name": "source_path",  "type": "string", "required": True,
         "description": "Absolute path to the Forge project to absorb"},
        {"name": "name",         "type": "string", "required": False, "default": "",
         "description": "Module name slug (inferred from forge.toml if omitted)"},
        {"name": "description",  "type": "string", "required": False, "default": "",
         "description": "Human-readable description of the module"},
    ],
)
def absorb_module(source_path: str, name: str = "", description: str = "") -> dict:
    from forge_suite.operations.modules import absorb_module as _op
    return _op(source_path, name, description)


@action_endpoint(
    name="shed_module",
    endpoint_id=SHED_MODULE_ID,
    description="Remove a module from forge-suite (does not affect managed projects)",
    params=[
        {"name": "module_id",     "type": "string",  "required": True},
        {"name": "drop_datasets", "type": "boolean", "required": False, "default": False,
         "description": "Delete the module's dataset files from forge-webapp (destructive)"},
        {"name": "confirm",       "type": "boolean", "required": False, "default": False,
         "description": "Required to remove a suite-bundled module"},
    ],
)
def shed_module(module_id: str, drop_datasets: bool = False, confirm: bool = False) -> dict:
    from forge_suite.operations.modules import shed_module as _op
    return _op(module_id, drop_datasets, confirm)


@action_endpoint(
    name="implant_module",
    endpoint_id=IMPLANT_MODULE_ID,
    description="Add an absorbed module to a managed Forge project's forge.toml",
    params=[
        {"name": "project_id",   "type": "string", "required": True},
        {"name": "module_name",  "type": "string", "required": True,
         "description": "Name of an absorbed module (from list_modules)"},
    ],
)
def implant_module(project_id: str, module_name: str) -> dict:
    from forge_suite.operations.modules import implant_module as _op
    return _op(project_id, module_name)
