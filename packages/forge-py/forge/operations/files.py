"""CORE file operations — manage the files/ directory in a project."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path


def _file_mtime_iso(f: Path) -> str:
    return datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat()


def sync_project_files(root: Path) -> list[dict]:
    """Reconcile the files/ directory; return list of file metadata dicts."""
    files_dir = root / "files"
    files_dir.mkdir(exist_ok=True)
    return [
        {
            "filename": f.name,
            "size_bytes": f.stat().st_size,
            "added_at": _file_mtime_iso(f),
        }
        for f in sorted(files_dir.iterdir())
        if f.is_file()
    ]


def upload_file(root: Path, filename: str, content_b64: str) -> dict:
    safe_name = Path(filename).name
    if not safe_name:
        return {"error": "Invalid filename"}

    files_dir = root / "files"
    files_dir.mkdir(exist_ok=True)

    try:
        content = base64.b64decode(content_b64)
    except Exception:
        return {"error": "Invalid base64 content"}

    (files_dir / safe_name).write_bytes(content)
    return {"filename": safe_name, "size_bytes": len(content)}


def remove_file(root: Path, filename: str) -> dict:
    dest = root / "files" / Path(filename).name
    if not dest.exists():
        return {"error": f"File not found: {filename}"}
    dest.unlink()
    return {"removed": filename}
