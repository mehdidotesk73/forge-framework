"""
Control Layer — file_endpoints
Manages ProjectFile records and the files/ directory for managed projects.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path

from forge.control import action_endpoint

from models.models import ForgeProject, ProjectFile

SYNC_FILES_ID   = "cccccccc-0012-0000-0000-000000000000"
UPLOAD_FILE_ID  = "cccccccc-0013-0000-0000-000000000000"
REMOVE_FILE_ID  = "cccccccc-0014-0000-0000-000000000000"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _file_id(project_id: str, filename: str) -> str:
    return f"pf-{project_id[:8]}-{filename[:20]}"


def _rebuild_file_records(project_id: str, files_dir: Path) -> None:
    for r in ProjectFile.all():
        if r.project_id == project_id:
            r.remove()
    for f in sorted(files_dir.iterdir()):
        if f.is_file():
            ProjectFile.create(
                id=_file_id(project_id, f.name),
                project_id=project_id,
                filename=f.name,
                size_bytes=str(f.stat().st_size),
                added_at=datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
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
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}
    files_dir = Path(proj.root_path) / "files"
    files_dir.mkdir(exist_ok=True)
    _rebuild_file_records(project_id, files_dir)
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
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}

    safe_name = Path(filename).name
    if not safe_name:
        return {"error": "Invalid filename"}

    files_dir = Path(proj.root_path) / "files"
    files_dir.mkdir(exist_ok=True)
    dest = files_dir / safe_name

    try:
        content = base64.b64decode(content_b64)
    except Exception:
        return {"error": "Invalid base64 content"}

    dest.write_bytes(content)

    file_id = _file_id(project_id, safe_name)
    existing = ProjectFile.get(file_id)
    if existing:
        existing.size_bytes = str(len(content))
        existing.added_at = _now()
    else:
        ProjectFile.create(
            id=file_id,
            project_id=project_id,
            filename=safe_name,
            size_bytes=str(len(content)),
            added_at=_now(),
        )

    return {"filename": safe_name, "size_bytes": len(content)}


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
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}

    record = ProjectFile.get(file_id)
    if record is None or record.project_id != project_id:
        return {"error": f"File {file_id} not found"}

    dest = Path(proj.root_path) / "files" / record.filename
    if dest.exists():
        dest.unlink()

    record.remove()
    return {"removed": file_id}
