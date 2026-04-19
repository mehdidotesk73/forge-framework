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

_PACKAGE_DIR    = Path(__file__).resolve().parent                    # forge_suite/
_TEMPLATE_DIR   = _PACKAGE_DIR / "webapp_template"                  # bundled backend template
_WEBAPP_DIR     = Path.home() / ".forge-suite" / "webapp"           # runtime backend (user-writable)
_QUICKSTART_SRC = _PACKAGE_DIR / "QUICKSTART.md"                    # bundled reference doc
_QUICKSTART_DST = Path.home() / ".forge-suite" / "QUICKSTART.md"   # user-accessible copy

SERVE_PORT = 5174


def _bootstrap_webapp() -> None:
    """Copy template and initialise datasets/artifacts on first run."""
    artifacts_dir = _WEBAPP_DIR / ".forge" / "artifacts"
    if (artifacts_dir / "ForgeProject.schema.json").exists():
        return

    console.print("  [dim]Setting up forge-suite (first run)…[/dim]")

    import shutil
    import pandas as pd

    # Copy the backend template to the user's home dir if not present
    if not _WEBAPP_DIR.exists():
        shutil.copytree(str(_TEMPLATE_DIR), str(_WEBAPP_DIR))

    forge_dir = _WEBAPP_DIR / ".forge"
    forge_dir.mkdir(parents=True, exist_ok=True)
    (forge_dir / "data").mkdir(exist_ok=True)
    artifacts_dir.mkdir(exist_ok=True)

    webapp_str = str(_WEBAPP_DIR)
    if webapp_str not in sys.path:
        sys.path.insert(0, webapp_str)

    # Import models to discover dataset UUIDs, then initialise empty datasets
    from forge.storage.engine import StorageEngine
    engine = StorageEngine(forge_dir)

    import importlib.util
    spec = importlib.util.spec_from_file_location("models.models", _WEBAPP_DIR / "models" / "models.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    dataset_ids = [
        v for k, v in vars(mod).items()
        if k.endswith("_DATASET_ID") and isinstance(v, str)
    ]
    for uid in dataset_ids:
        if engine.get_dataset(uid) is None:
            engine.write_dataset(uid, pd.DataFrame())

    # Call builders directly (avoids python -m issues on Windows caused by
    # forge/cli/__init__.py pre-importing forge.cli.main before runpy executes it)
    import os
    _prev_cwd = os.getcwd()
    try:
        os.chdir(str(_WEBAPP_DIR))
        from forge.config import find_project_root, load_config
        from forge.model.builder import ModelBuilder
        from forge.control.builder import EndpointBuilder
        _root = find_project_root()
        _config, _ = load_config(_root)
        if _config.models:
            ModelBuilder(_config, _root, engine).build_all()
        if _config.endpoint_repos:
            EndpointBuilder(_config, _root).build_all()
    finally:
        os.chdir(_prev_cwd)
    console.print("  [dim]forge-suite ready.[/dim]\n")


def _sync_quickstart_file() -> None:
    """Copy the bundled QUICKSTART.md to ~/.forge-suite/ (always up to date)."""
    import shutil
    _QUICKSTART_DST.parent.mkdir(parents=True, exist_ok=True)
    if _QUICKSTART_SRC.exists():
        shutil.copy2(str(_QUICKSTART_SRC), str(_QUICKSTART_DST))


def _maybe_show_quickstart_on_first_run() -> None:
    """On first run after install: copy QUICKSTART.md and print it once."""
    if _QUICKSTART_DST.exists():
        return
    _sync_quickstart_file()
    _print_quickstart()
    console.print(f"  [dim]Guide saved to: [bold]{_QUICKSTART_DST}[/bold][/dim]")
    console.print("  [dim]Run [bold]forge-suite quickstart[/bold] to view it again, or [bold]forge-suite quickstart --open[/bold] to open in your editor.[/dim]\n")


def _open_in_editor(path: Path) -> None:
    """Open a file in the OS default application."""
    import platform
    system = platform.system()
    if system == "Windows":
        import os
        os.startfile(str(path))
    elif system == "Darwin":
        subprocess.run(["open", str(path)], check=False)
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def _print_quickstart() -> None:
    """Print the Forge Suite quick-reference cheat sheet."""
    console.print()
    console.rule("[bold cyan]Forge Suite — Quick Reference[/bold cyan]")
    console.print("""
[bold]Management UI[/bold]
  forge-suite serve                        Start UI at http://localhost:5174
  forge-suite serve --port 8080            Custom port
  forge-suite serve --no-open              Don't open browser automatically

[bold]Project management[/bold]
  forge-suite init <path>                  Scaffold + register a new project
  forge-suite mount <path>                 Register an existing project
  forge-suite list                         List all registered projects
  forge-suite sync <path>                  Re-sync project from forge.toml

[bold]Project operations[/bold] [dim](no server required)[/dim]
  forge-suite pipeline-run <path> <name>   Run a named pipeline
  forge-suite model-build <path>           Rebuild model schemas + SDKs
  forge-suite endpoint-build <path>        Rebuild endpoint descriptor registry
  forge-suite project-serve <path>         Start project backend only (:8001)

[bold]Maintenance[/bold]
  forge-suite quickstart                   Show this reference
  forge-suite uninstall                    Remove forge-suite + forge-framework
""")
    console.rule("[bold]forge CLI[/bold] [dim](run inside a project directory)[/dim]")
    console.print("""
  forge init <name>                        Scaffold a new Forge project
  forge dev serve                          Start dev server (:8000)
  forge pipeline run <name>                Run a pipeline
  forge pipeline dag                       Show pipeline dependency graph
  forge pipeline history <name>            Show run history for a pipeline
  forge model build                        Build model schemas + SDKs
  forge model reinitialize <Type>          Reset a model's backing dataset
  forge endpoint build                     Build endpoint descriptor registry
  forge dataset load <file> --name <n>     Load a dataset from a file
  forge dataset list                       List all datasets
  forge dataset inspect <id>               Inspect a dataset
  forge build                              Build frontend apps (npm run build)
  forge export                             Export project as .forgepkg
  forge upgrade [--dry-run]                Run migrations + rebuild artifacts
  forge version                            Show framework version
""")
    console.rule()


@click.group()
@click.version_option(package_name="forge-suite")
def cli() -> None:
    """Forge Suite — framework + management UI"""
    _maybe_show_quickstart_on_first_run()


@cli.command()
@click.option("--no-open", is_flag=True, default=False, help="Don't open the browser")
@click.option("--port", default=SERVE_PORT, show_default=True, type=int, help="Port to serve on")
def serve(no_open: bool, port: int) -> None:
    """Start the Forge Suite management UI."""

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


@cli.command("quickstart")
@click.option("--open", "open_editor", is_flag=True, default=False,
              help="Open QUICKSTART.md in your default text editor.")
def quickstart(open_editor: bool) -> None:
    """Print all forge-suite and forge CLI commands (or open in editor)."""
    _sync_quickstart_file()
    if open_editor:
        console.print(f"  Opening [bold]{_QUICKSTART_DST}[/bold] in your default editor…")
        _open_in_editor(_QUICKSTART_DST)
    else:
        _print_quickstart()
        console.print(f"  [dim]Guide file: [bold]{_QUICKSTART_DST}[/bold]  (run with [bold]--open[/bold] to open in editor)[/dim]\n")


@cli.command("help")
@click.option("--open", "open_editor", is_flag=True, default=False,
              help="Open QUICKSTART.md in your default text editor.")
def help_cmd(open_editor: bool) -> None:
    """Alias for quickstart — print all forge-suite and forge CLI commands."""
    _sync_quickstart_file()
    if open_editor:
        console.print(f"  Opening [bold]{_QUICKSTART_DST}[/bold] in your default editor…")
        _open_in_editor(_QUICKSTART_DST)
    else:
        _print_quickstart()
        console.print(f"  [dim]Guide file: [bold]{_QUICKSTART_DST}[/bold]  (run with [bold]--open[/bold] to open in editor)[/dim]\n")


@cli.command("uninstall")
def uninstall_self() -> None:
    """Remove forge-suite and forge-framework from this Python environment."""
    console.print("[yellow]Uninstalling forge-suite and forge-framework…[/yellow]")
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "forge-suite", "forge-framework", "-y"]
    )
    if result.returncode == 0:
        console.print("[green]✓[/green] Uninstalled successfully.")
    else:
        console.print("[red]✗[/red] pip exited with an error (see above).")
        sys.exit(result.returncode)


if __name__ == "__main__":
    cli()
