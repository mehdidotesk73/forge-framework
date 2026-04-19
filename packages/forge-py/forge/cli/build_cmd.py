"""forge build — build all app frontends into each app's dist/ directory."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command("build")
@click.option("--app", default=None, help="Build only the named app")
def build_cmd(app: str | None) -> None:
    """Build app frontends into .forge/apps/<name>/dist/ for static serving."""
    from forge.config import find_project_root, load_config

    root = find_project_root()
    config, _ = load_config(root)

    if not config.apps:
        console.print("[yellow]No [[apps]] declared in forge.toml.[/yellow]")
        return

    apps_to_build = [a for a in config.apps if app is None or a.name == app]
    if not apps_to_build:
        console.print(f"[red]App '{app}' not found in forge.toml.[/red]")
        sys.exit(1)

    built = 0
    for a in apps_to_build:
        app_dir = (root / a.path).resolve()
        if not app_dir.exists():
            console.print(f"[red]✗[/red] [{a.name}] directory not found: {app_dir}")
            continue

        pkg_json = app_dir / "package.json"
        if not pkg_json.exists():
            console.print(f"[yellow]⚠[/yellow] [{a.name}] no package.json, skipping")
            continue

        console.print(f"[dim]Building[/dim] {a.name}…")
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(app_dir),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[red]✗[/red] [{a.name}] build failed:\n{result.stderr}")
            sys.exit(1)

        console.print(f"[green]✓[/green] {a.name} → {a.path}/dist/")
        built += 1

    console.print(f"\nBuilt {built}/{len(apps_to_build)} app(s).")
    if built == len(apps_to_build):
        console.print("[dim]Run `forge dev serve` to serve them.[/dim]")
