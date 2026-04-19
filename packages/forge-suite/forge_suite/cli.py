"""forge-suite CLI — starts the Forge backend and management UI."""
from __future__ import annotations

import json
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

import click
from rich.console import Console

console = Console()

# Paths relative to the repo root (works for editable installs from the monorepo)
_PACKAGE_DIR = Path(__file__).resolve().parent.parent          # packages/forge-suite/
_REPO_ROOT = _PACKAGE_DIR.parent.parent                        # forge-framework/
_WEBAPP_DIR = _REPO_ROOT / "examples" / "forge-webapp"
_APP_DIR = _WEBAPP_DIR / "apps" / "forge-webapp"

BACKEND_PORT = 8000
FRONTEND_PORT = 5174


def _bootstrap_webapp() -> None:
    """Create backing datasets, patch models.py, and build artifacts on first run."""
    artifacts_dir = _WEBAPP_DIR / ".forge" / "artifacts"
    if (artifacts_dir / "ForgeProject.schema.json").exists():
        return

    console.print("  [dim]Setting up forge-webapp (first run)…[/dim]")

    import uuid
    import pandas as pd

    forge_dir = _WEBAPP_DIR / ".forge"
    forge_dir.mkdir(parents=True, exist_ok=True)
    (forge_dir / "data").mkdir(exist_ok=True)
    artifacts_dir.mkdir(exist_ok=True)

    webapp_str = str(_WEBAPP_DIR)
    if webapp_str not in sys.path:
        sys.path.insert(0, webapp_str)

    from forge.storage.engine import StorageEngine
    engine = StorageEngine(forge_dir)

    models_path = _WEBAPP_DIR / "models" / "models.py"
    source = models_path.read_text()
    placeholders = [
        "REPLACE_FORGE_PROJECT_UUID",
        "REPLACE_ARTIFACT_STAMP_UUID",
        "REPLACE_PIPELINE_UUID",
        "REPLACE_PIPELINE_RUN_UUID",
        "REPLACE_OBJECT_TYPE_UUID",
        "REPLACE_ENDPOINT_REPO_UUID",
        "REPLACE_ENDPOINT_UUID",
        "REPLACE_APP_UUID",
    ]
    changed = False
    for ph in placeholders:
        if ph in source:
            uid = str(uuid.uuid4())
            engine.write_dataset(uid, pd.DataFrame())
            source = source.replace(ph, uid)
            changed = True
    if changed:
        models_path.write_text(source)

    subprocess.run(
        [sys.executable, "-m", "forge.cli.main", "model", "build"],
        cwd=str(_WEBAPP_DIR), check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "forge.cli.main", "endpoint", "build"],
        cwd=str(_WEBAPP_DIR), check=True,
    )
    console.print("  [dim]forge-webapp ready.[/dim]\n")


@click.group()
@click.version_option(package_name="forge-suite")
def cli() -> None:
    """Forge Suite — framework + management UI"""


@cli.command()
@click.option("--no-open", is_flag=True, default=False, help="Don't open the browser")
def serve(no_open: bool) -> None:
    """Start the Forge backend and management UI, then open the browser."""

    if not _WEBAPP_DIR.exists():
        console.print(f"[red]Error:[/red] webapp directory not found at {_WEBAPP_DIR}")
        console.print("Make sure forge-suite is installed from the forge-framework repo.")
        sys.exit(1)

    console.print("[bold green]Forge Suite[/bold green] — starting servers…\n")

    _bootstrap_webapp()

    backend = subprocess.Popen(
        [sys.executable, "-m", "forge.cli.main", "dev", "serve", "--port", str(BACKEND_PORT)],
        cwd=str(_WEBAPP_DIR),
    )

    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(_APP_DIR),
    )

    def cleanup() -> None:
        backend.terminate()
        frontend.terminate()
        try:
            backend.wait(timeout=5)
            frontend.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend.kill()
            frontend.kill()

    def _on_signal(sig: int, frame: object) -> None:
        console.print("\n[dim]Shutting down…[/dim]")
        cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    def _sync_all_projects() -> None:
        """Wait for backend, then re-sync all registered projects so metadata is fresh."""
        backend_url = f"http://localhost:{BACKEND_PORT}"
        for _ in range(120):
            try:
                urllib.request.urlopen(f"{backend_url}/api/health", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        else:
            return  # backend never came up; give up silently
        try:
            resp = urllib.request.urlopen(f"{backend_url}/api/objects/ForgeProject", timeout=5)
            data = json.loads(resp.read())
            for row in data.get("rows", []):
                project_id = row.get("id")
                if not project_id:
                    continue
                req = urllib.request.Request(
                    f"{backend_url}/endpoints/cccccccc-0004-0000-0000-000000000000",
                    data=json.dumps({"project_id": project_id}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass  # non-fatal; user can sync manually

    threading.Thread(target=_sync_all_projects, daemon=True).start()

    if not no_open:
        def _wait_and_open() -> None:
            url = f"http://localhost:{FRONTEND_PORT}"
            for _ in range(60):
                try:
                    urllib.request.urlopen(url, timeout=1)
                    webbrowser.open(url)
                    return
                except Exception:
                    time.sleep(0.5)
        threading.Thread(target=_wait_and_open, daemon=True).start()

    console.print(f"  UI:      http://localhost:{FRONTEND_PORT}")
    console.print(f"  Backend: http://localhost:{BACKEND_PORT}/api/health")
    console.print("\n[dim]Press Ctrl+C to stop[/dim]")

    try:
        backend.wait()
    finally:
        cleanup()
