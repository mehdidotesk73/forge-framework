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

# Paths relative to this package (works for editable installs from the monorepo)
_PACKAGE_DIR = Path(__file__).resolve().parent.parent          # packages/forge-suite/
_WEBAPP_DIR = _PACKAGE_DIR / "forge-webapp"

SERVE_PORT = 5174


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
@click.option("--port", default=SERVE_PORT, show_default=True, type=int, help="Port to serve on")
def serve(no_open: bool, port: int) -> None:
    """Start the Forge Suite management UI."""

    if not _WEBAPP_DIR.exists():
        console.print(f"[red]Error:[/red] webapp directory not found at {_WEBAPP_DIR}")
        console.print("Make sure forge-suite is installed from the forge-framework repo.")
        sys.exit(1)

    console.print("[bold green]Forge Suite[/bold green] — starting…\n")

    _bootstrap_webapp()

    from forge_suite.server import create_app, stop_scheduler
    import uvicorn

    api = create_app()

    def _on_signal(sig: int, frame: object) -> None:
        console.print("\n[dim]Shutting down…[/dim]")
        stop_scheduler()
        sys.exit(0)

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    def _sync_all_projects() -> None:
        """Re-sync all registered projects after the server is ready."""
        base = f"http://localhost:{port}"
        for _ in range(120):
            try:
                urllib.request.urlopen(f"{base}/api/health", timeout=1)
                break
            except Exception:
                time.sleep(0.5)
        else:
            return
        try:
            resp = urllib.request.urlopen(f"{base}/api/objects/ForgeProject", timeout=5)
            data = json.loads(resp.read())
            for row in data.get("rows", []):
                project_id = row.get("id")
                if not project_id:
                    continue
                req = urllib.request.Request(
                    f"{base}/endpoints/cccccccc-0004-0000-0000-000000000000",
                    data=json.dumps({"project_id": project_id}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass

    threading.Thread(target=_sync_all_projects, daemon=True).start()

    if not no_open:
        def _wait_and_open() -> None:
            url = f"http://localhost:{port}"
            for _ in range(60):
                try:
                    urllib.request.urlopen(url, timeout=1)
                    webbrowser.open(url)
                    return
                except Exception:
                    time.sleep(0.5)
        threading.Thread(target=_wait_and_open, daemon=True).start()

    console.print(f"  UI:      http://localhost:{port}")
    console.print(f"  API:     http://localhost:{port}/api/health")
    console.print("\n[dim]Press Ctrl+C to stop[/dim]")

    try:
        uvicorn.run(api, host="127.0.0.1", port=port, log_level="warning")
    finally:
        stop_scheduler()


def _ensure_webapp_on_path() -> None:
    """Add the forge-webapp directory to sys.path so model imports resolve."""
    webapp_str = str(_WEBAPP_DIR)
    if webapp_str not in sys.path:
        sys.path.insert(0, webapp_str)


@cli.command()
@click.argument("project_path")
def mount(project_path: str) -> None:
    """Register a Forge project with Forge Suite (no server required)."""
    _ensure_webapp_on_path()
    from forge_suite.operations.projects import register_project
    result = register_project(project_path)
    if "error" in result:
        console.print(f"[red]✗[/red] {result['error']}")
        sys.exit(1)
    action = "Created and registered" if result.get("created") else "Registered"
    console.print(f"[green]✓[/green] {action}: [bold]{result['name']}[/bold]")
    console.print(f"  Path: {result['root_path']}")
    console.print(f"  ID:   {result['project_id']}")


@cli.command("list")
def list_projects() -> None:
    """List all projects registered with Forge Suite."""
    _ensure_webapp_on_path()
    from models.models import ForgeProject
    projects = ForgeProject.all()
    if not projects:
        console.print("[dim]No projects registered.[/dim]")
        console.print("  Register one with:  forge-suite mount <path>")
        return
    for p in sorted(projects, key=lambda x: x.name):
        active = "[green]●[/green]" if getattr(p, "is_active", "") == "true" else "[dim]○[/dim]"
        console.print(f"  {active} [bold]{p.name}[/bold]  {p.root_path}  [dim]{p.id}[/dim]")


@cli.command()
@click.argument("project_path")
def sync(project_path: str) -> None:
    """Re-sync a registered project from its forge.toml (no server required)."""
    _ensure_webapp_on_path()
    from models.models import ForgeProject
    from forge_suite.operations.projects import sync_project
    root = str(Path(project_path).resolve())
    match = next((p for p in ForgeProject.all() if p.root_path == root), None)
    if match is None:
        console.print(f"[red]✗[/red] Project not registered: {root}")
        console.print("  Register it first with:  forge-suite mount <path>")
        sys.exit(1)
    result = sync_project(match.id)
    if "error" in result:
        console.print(f"[red]✗[/red] {result['error']}")
        sys.exit(1)
    console.print(f"[green]✓[/green] Synced: [bold]{match.name}[/bold]")


@cli.command("init")
@click.argument("project_path")
@click.option("--name", default=None, help="Project name (defaults to directory name)")
def init_project(project_path: str, name: str | None) -> None:
    """Scaffold a new Forge project at the given path, then register it."""
    dest = Path(project_path).resolve()
    project_name = name or dest.name
    parent = dest.parent
    parent.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold]Initialising[/bold] {project_name} → {dest}")
    result = subprocess.run(
        [sys.executable, "-m", "forge.cli.main", "init", project_name],
        cwd=str(parent),
    )
    if result.returncode != 0:
        console.print("[red]✗[/red] forge init failed.")
        sys.exit(1)

    _ensure_webapp_on_path()
    from forge_suite.operations.projects import register_project
    reg = register_project(str(dest))
    if "error" in reg:
        console.print(f"[yellow]⚠[/yellow] Project created but not registered: {reg['error']}")
        console.print("  Run:  forge-suite mount <path>  when ready.")
    else:
        console.print(f"[green]✓[/green] Created and registered: [bold]{reg['name']}[/bold]")
        console.print(f"  Path: {reg['root_path']}")
        console.print(f"  ID:   {reg['project_id']}")


@cli.command("pipeline-run")
@click.argument("project_path")
@click.argument("pipeline_name")
def pipeline_run(project_path: str, pipeline_name: str) -> None:
    """Run a named pipeline inside a Forge project."""
    root = str(Path(project_path).resolve())
    console.print(f"[bold]Running pipeline[/bold] {pipeline_name} in {root}")
    result = subprocess.run(
        [sys.executable, "-m", "forge.cli.main", "pipeline", "run", pipeline_name],
        cwd=root,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)
    console.print(f"[green]✓[/green] Pipeline [bold]{pipeline_name}[/bold] completed.")


@cli.command("model-build")
@click.argument("project_path")
def model_build(project_path: str) -> None:
    """Build model schemas and regenerate SDKs for a Forge project."""
    root = str(Path(project_path).resolve())
    console.print(f"[bold]Building models[/bold] in {root}")
    result = subprocess.run(
        [sys.executable, "-m", "forge.cli.main", "model", "build"],
        cwd=root,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)
    console.print("[green]✓[/green] Models built.")


@cli.command("endpoint-build")
@click.argument("project_path")
@click.option("--repo", default=None, help="Build a single endpoint repo by name")
def endpoint_build(project_path: str, repo: str | None) -> None:
    """Build the endpoint descriptor registry for a Forge project."""
    root = str(Path(project_path).resolve())
    cmd = [sys.executable, "-m", "forge.cli.main", "endpoint", "build"]
    if repo:
        cmd += ["--repo", repo]
    console.print(f"[bold]Building endpoints[/bold] in {root}")
    result = subprocess.run(cmd, cwd=root)
    if result.returncode != 0:
        sys.exit(result.returncode)
    console.print("[green]✓[/green] Endpoints built.")


@cli.command("project-serve")
@click.argument("project_path")
@click.option("--port", default=8001, show_default=True, help="Port for the project backend")
@click.option("--app", default=None, help="App name to serve at /")
def project_serve(project_path: str, port: int, app: str | None) -> None:
    """Start the Forge dev server for a project (backend only, no management UI)."""
    root = str(Path(project_path).resolve())
    cmd = [sys.executable, "-m", "forge.cli.main", "dev", "serve", "--port", str(port)]
    if app:
        cmd += ["--app", app]
    console.print(f"[bold]Serving[/bold] {root} on :{port}")
    console.print("[dim]Press Ctrl+C to stop.[/dim]")
    try:
        subprocess.run(cmd, cwd=root)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")
