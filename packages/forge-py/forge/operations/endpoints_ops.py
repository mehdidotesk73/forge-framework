"""CORE endpoint operations — proxy calls to project backends; serve docs."""
from __future__ import annotations

import json
from pathlib import Path


_DOCS_ORDER = [
    "forge-overview",
    "pipeline-layer",
    "model-layer",
    "control-layer",
    "view-layer",
    "todo",
]


def call_project_endpoint(root: Path, endpoint_id: str, payload_json: str, api_port: int | None = None) -> dict:
    """Proxy a JSON call to the project's local forge backend."""
    import urllib.request
    import urllib.error

    if not api_port:
        return {"error": "Project backend is not running. Start an app first or use forge-suite to run the project."}

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


def get_docs(forge_root: Path | None = None) -> dict:
    """Return all Forge framework docs as {name, title, content} objects."""
    if forge_root is None:
        forge_root = Path(__file__).resolve().parents[4]

    docs_dir = forge_root / "docs"
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
