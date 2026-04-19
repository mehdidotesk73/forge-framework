"""SUITE project operations — manage ForgeProject registry records."""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path


def _models():
    from models.models import (
        App, ArtifactStamp, Endpoint, EndpointRepo,
        ForgeProject, ObjectType, Pipeline, PipelineRun,
    )
    return App, ArtifactStamp, Endpoint, EndpointRepo, ForgeProject, ObjectType, Pipeline, PipelineRun


def clear_project_records(project_id: str) -> None:
    App, ArtifactStamp, Endpoint, EndpointRepo, ForgeProject, ObjectType, Pipeline, PipelineRun = _models()
    for cls in (Pipeline, PipelineRun, ObjectType, EndpointRepo, Endpoint, App, ArtifactStamp):
        for r in cls.all():
            if getattr(r, "project_id", None) == project_id:
                r.remove()


def sync_project_records(project_id: str, root: Path, cfg: dict) -> None:
    """Write Pipeline/ObjectType/EndpointRepo/Endpoint/App records from parsed forge.toml data."""
    from forge.operations.projects import sync_from_toml_raw
    App, ArtifactStamp, Endpoint, EndpointRepo, ForgeProject, ObjectType, Pipeline, PipelineRun = _models()

    data = sync_from_toml_raw(root, cfg)

    for pl in data["pipelines"]:
        pid_hash = hashlib.md5(pl["name"].encode()).hexdigest()[:10]
        Pipeline.create(
            id=f"pl-{project_id[:8]}-{pid_hash}",
            project_id=project_id,
            name=pl["name"],
            module=pl["module"],
            function_name=pl["function"],
            schedule=pl["schedule"],
            input_datasets=json.dumps(pl["input_ids"]),
            output_datasets=json.dumps(pl["output_ids"]),
        )

    for m in data["models"]:
        name_hash = hashlib.md5(m["name"].encode()).hexdigest()[:10]
        ObjectType.create(
            id=f"ot-{project_id[:8]}-{name_hash}",
            project_id=project_id,
            name=m["name"],
            mode=m["mode"],
            module=m["module"],
            backing_dataset_id=m["backing_dataset_id"],
            backing_dataset_name=m.get("backing_dataset_name", ""),
            field_count=m["field_count"],
            built_at=m["built_at"],
        )

    for repo in data["endpoint_repos"]:
        repo_name = repo["name"]
        eps = repo["endpoints"]
        EndpointRepo.create(
            id=f"er-{project_id[:8]}-{repo_name[:12]}",
            project_id=project_id,
            name=repo_name,
            path=repo["path"],
            endpoint_count=str(len(eps)),
        )
        for ep in eps:
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

    for app in data["apps"]:
        App.create(
            id=f"ap-{project_id[:8]}-{app['name'][:12]}",
            project_id=project_id,
            name=app["name"],
            app_id=app["app_id"],
            path=app["path"],
            port=str(app.get("port", "")),
        )


def register_project(root_path: str, suite_root: Path | None = None) -> dict:
    """Register a Forge project, creating it if forge.toml doesn't exist."""
    from forge.operations.projects import read_toml, write_ide_config, create_project
    App, ArtifactStamp, Endpoint, EndpointRepo, ForgeProject, ObjectType, Pipeline, PipelineRun = _models()

    from datetime import datetime, timezone
    def _now():
        return datetime.now(timezone.utc).isoformat()

    root = Path(root_path).resolve()
    toml_path = root / "forge.toml"
    created = False
    if not toml_path.exists():
        create_project(root, suite_root=suite_root)
        created = True
    else:
        write_ide_config(root, suite_root=suite_root)

    cfg = read_toml(toml_path)
    proj_name = cfg.get("project", {}).get("name", root.name)
    forge_ver = cfg.get("project", {}).get("forge_version", "")

    existing = None
    for p in ForgeProject.all():
        if p.root_path == str(root):
            existing = p
        else:
            p.is_active = "false"

    if existing:
        project_id = existing.id
        clear_project_records(project_id)
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

    sync_project_records(project_id, root, cfg)

    return {"project_id": project_id, "name": proj_name, "root_path": str(root), "created": created}


def unregister_project(project_id: str) -> dict:
    App, ArtifactStamp, Endpoint, EndpointRepo, ForgeProject, ObjectType, Pipeline, PipelineRun = _models()
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    name = proj.name
    clear_project_records(project_id)
    proj.remove()
    return {"deleted": project_id, "name": name}


def set_active_project(project_id: str) -> dict:
    App, ArtifactStamp, Endpoint, EndpointRepo, ForgeProject, ObjectType, Pipeline, PipelineRun = _models()
    for p in ForgeProject.all():
        p.is_active = "true" if p.id == project_id else "false"
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    return {"active": project_id, "name": proj.name}


def sync_project(project_id: str) -> dict:
    from forge.operations.projects import read_toml
    App, ArtifactStamp, Endpoint, EndpointRepo, ForgeProject, ObjectType, Pipeline, PipelineRun = _models()

    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    root = Path(proj.root_path)
    toml_path = root / "forge.toml"
    if not toml_path.exists():
        return {"error": f"forge.toml not found at {proj.root_path}"}

    cfg = read_toml(toml_path)
    clear_project_records(project_id)
    sync_project_records(project_id, root, cfg)
    return {"synced": project_id}
