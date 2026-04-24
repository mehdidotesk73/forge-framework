"""forge dev serve."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()
log = logging.getLogger(__name__)


@click.group()
def dev_group() -> None:
    """Development server commands."""


@dev_group.command("serve")
@click.option("--app", default=None, help="Serve a specific app by name")
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
@click.option("--reload/--no-reload", default=True, show_default=True)
def dev_serve(app: str | None, host: str, port: int, reload: bool) -> None:
    """Start the Forge development server."""
    import uvicorn
    from forge.config import find_project_root, load_config
    from forge.storage.engine import StorageEngine
    from forge.pipeline.runner import PipelineRunner
    from forge.scheduler.scheduler import ForgeScheduler
    from forge.server.app import create_app, load_endpoint_modules, load_model_modules
    from forge.version import __version__, TS_VERSION

    # Version mismatch check
    _check_version_mismatch(__version__, TS_VERSION, find_project_root())

    root = find_project_root()
    config, _ = load_config(root)
    engine = StorageEngine(root / ".forge")
    runner = PipelineRunner(engine, root)

    # Load model modules first so _CLASS_REGISTRY is populated
    load_model_modules(config, root)
    # Load endpoint modules so decorators register
    load_endpoint_modules(config, root)

    scheduler = ForgeScheduler(config, runner, engine)
    api = create_app(config, root, engine, runner, scheduler)

    # Start background scheduler
    scheduler.start()

    console.print(f"[bold green]Forge dev server[/bold green] — {config.name}")
    console.print(f"  API:    http://{host}:{port}/api/health")
    console.print(f"  Docs:   http://{host}:{port}/docs")
    if config.apps:
        for a in config.apps:
            if app is None or a.name == app:
                app_path = (root / a.path).resolve()
                _ensure_forge_ts_linked(app_path, root)
                dist_exists = (app_path / "dist").exists()
                if dist_exists:
                    console.print(f"  App [{a.name}]: http://{host}:{port + 1}/")
                else:
                    console.print(
                        f"  App [{a.name}]: [dim]cd {a.path} && npm run dev[/dim]"
                        f"  [dim](run npm run build to serve here)[/dim]"
                    )
    console.print()
    console.print("[dim]Press Ctrl+C to stop[/dim]")

    # Mount static files for apps if built
    _mount_app_static(api, config, root, app)

    try:
        uvicorn.run(
            api,
            host=host,
            port=port,
            log_level="warning",
        )
    finally:
        scheduler.stop()


def _ensure_forge_ts_linked(app_dir: Path, project_root: Path) -> None:
    """Symlink @forge-suite/ts into app node_modules if missing.

    Outside the monorepo the package isn't resolvable via walk-up; this
    finds the nearest installed copy and links it so Vite can resolve it.
    """
    import os

    scope_dir = app_dir / "node_modules" / "@forge-framework"
    link_target = scope_dir / "ts"

    if link_target.exists() or link_target.is_symlink():
        return

    # Walk up from both the project root and the forge package itself.
    # The second walk handles projects that live outside the monorepo tree —
    # forge-py is inside the monorepo so its walk-up reaches the workspace root.
    forge_ts_src: Path | None = None
    search_roots = [project_root, Path(__file__).resolve()]
    for start in search_roots:
        for candidate in [start, *start.parents]:
            pkg = candidate / "node_modules" / "@forge-framework" / "ts"
            if pkg.is_dir():
                forge_ts_src = pkg
                break
        if forge_ts_src:
            break

    if forge_ts_src is None:
        console.print(
            "[yellow][![/yellow] @forge-suite/ts not found — "
            "run `npm install` in the app directory after publishing to npm."
        )
        return

    scope_dir.mkdir(parents=True, exist_ok=True)
    os.symlink(str(forge_ts_src), str(link_target))
    console.print(f"[dim]Linked @forge-suite/ts → {forge_ts_src}[/dim]")


def _mount_app_static(api, config, root: Path, app_filter: str | None) -> None:
    """Mount built app dist/ directories as static files."""
    from fastapi.staticfiles import StaticFiles
    for a in config.apps:
        if app_filter and a.name != app_filter:
            continue
        dist = (root / a.path / "dist").resolve()
        if dist.exists():
            api.mount(f"/apps/{a.name}", StaticFiles(directory=str(dist), html=True), name=a.name)


def _check_version_mismatch(py_version: str, ts_version: str, root: Path) -> None:
    """Warn if installed TS package version differs from Python package."""
    ts_pkg_json = root / "node_modules" / "@forge-framework" / "ts" / "package.json"
    if ts_pkg_json.exists():
        import json
        installed_ts = json.loads(ts_pkg_json.read_text()).get("version", "unknown")
        if installed_ts != ts_version:
            console.print(
                f"[yellow][!] Version mismatch: Python={py_version}, "
                f"TypeScript={installed_ts} (expected {ts_version}). "
                f"Run `forge upgrade` to synchronize.[/yellow]"
            )
