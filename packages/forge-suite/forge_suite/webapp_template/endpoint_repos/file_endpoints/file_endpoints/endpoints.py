"""
Control Layer — file_endpoints
Manages ProjectFile records and the files/ directory for managed projects.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from forge.control import action_endpoint

from models.models import ForgeProject, ProjectFile

SYNC_FILES_ID   = "cccccccc-0012-0000-0000-000000000000"
UPLOAD_FILE_ID  = "cccccccc-0013-0000-0000-000000000000"
REMOVE_FILE_ID  = "cccccccc-0014-0000-0000-000000000000"


def _file_id(project_id: str, filename: str) -> str:
    return f"pf-{project_id[:8]}-{filename[:20]}"


def _rebuild_file_records(project_id: str, file_metas: list[dict]) -> None:
    for r in ProjectFile.all():
        if r.project_id == project_id:
            r.remove()
    for meta in file_metas:
        ProjectFile.create(
            id=_file_id(project_id, meta["filename"]),
            project_id=project_id,
            filename=meta["filename"],
            size_bytes=str(meta["size_bytes"]),
            added_at=meta["added_at"],
        )


@action_endpoint(
    name="sync_files",
    endpoint_id=SYNC_FILES_ID,
    description="Reconcile the files/ directory with ProjectFile records",
    params=[
        {"name": "project_id", "type": "string", "required": True},
    ],
)
def sync_files(project_id: str) -> dict:
    from forge.operations.files import sync_project_files
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    file_metas = sync_project_files(Path(proj.root_path))
    _rebuild_file_records(project_id, file_metas)
    return {"synced": project_id}


@action_endpoint(
    name="upload_file",
    endpoint_id=UPLOAD_FILE_ID,
    description="Upload a file to the project's files/ directory",
    params=[
        {"name": "project_id", "type": "string", "required": True},
        {"name": "filename", "type": "string", "required": True},
        {"name": "content_b64", "type": "string", "required": True,
         "description": "Base64-encoded file content"},
    ],
)
def upload_file(project_id: str, filename: str, content_b64: str) -> dict:
    from forge.operations.files import upload_file as _op
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}

    result = _op(Path(proj.root_path), filename, content_b64)
    if "error" in result:
        return result

    safe_name = result["filename"]
    now = datetime.now(timezone.utc).isoformat()
    file_id = _file_id(project_id, safe_name)
    existing = ProjectFile.get(file_id)
    if existing:
        existing.size_bytes = str(result["size_bytes"])
        existing.added_at = now
    else:
        ProjectFile.create(
            id=file_id,
            project_id=project_id,
            filename=safe_name,
            size_bytes=str(result["size_bytes"]),
            added_at=now,
        )
    return result


@action_endpoint(
    name="remove_file",
    endpoint_id=REMOVE_FILE_ID,
    description="Remove a file from the project's files/ directory and delete its record",
    params=[
        {"name": "project_id", "type": "string", "required": True},
        {"name": "file_id", "type": "string", "required": True},
    ],
)
def remove_file(project_id: str, file_id: str) -> dict:
    from forge.operations.files import remove_file as _op
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}

    record = ProjectFile.get(file_id)
    if record is None or record.project_id != project_id:
        return {"error": f"File {file_id} not found"}

    result = _op(Path(proj.root_path), record.filename)
    if "error" not in result:
        record.remove()
    return result
