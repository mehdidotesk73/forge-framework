"""forge app commands."""
from __future__ import annotations

import click
from rich.console import Console

console = Console()


@click.group()
def app_group() -> None:
    """Scaffold and manage Forge apps."""


@app_group.command("create")
@click.argument("name")
@click.option("--port", default="5177", show_default=True, help="Vite dev server port")
def app_create(name: str, port: str) -> None:
    """Scaffold a new Vite+React app in the project's apps/ directory."""
    from forge.config import find_project_root
    from forge.operations.scaffolding import create_app
    root = find_project_root()
    result = create_app(root, name, port)
    if "error" in result:
        console.print(f"[red]✗[/red] {result['error']}")
        raise SystemExit(1)
    console.print(f"[green]✓[/green] Created app [bold]{result['name']}[/bold] (port {result['port']})")
    console.print(f"  {result['path']}")
    if result.get("npm_installed"):
        console.print("  Dependencies installed — run: npm run dev")
    else:
        console.print("  Run: cd apps/{} && npm install && npm run dev".format(result['name']))
        if not result.get("npm_installed"):
            console.print("  [yellow](npm not found — install Node.js to use the dev server)[/yellow]")
