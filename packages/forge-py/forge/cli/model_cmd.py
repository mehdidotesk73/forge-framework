"""forge model commands."""
from __future__ import annotations

import click
from rich.console import Console

console = Console()


def _get_builder():
    from forge.config import find_project_root, load_config
    from forge.storage.engine import StorageEngine
    from forge.model.builder import ModelBuilder
    root = find_project_root()
    config, _ = load_config(root)
    engine = StorageEngine(root / ".forge")
    return ModelBuilder(config, root, engine), config


@click.group()
def model_group() -> None:
    """Build model SDKs and manage snapshot datasets."""


@model_group.command("build")
def model_build() -> None:
    """Generate schema artifacts and Python/TypeScript SDKs for all models."""
    builder, config = _get_builder()
    if not config.models:
        console.print("[yellow]No models registered in forge.toml[/yellow]")
        return

    with console.status("Building models..."):
        results = builder.build_all()

    for r in results:
        console.print(f"[green]✓[/green] [bold]{r['name']}[/bold] ({r['mode']})")
        console.print(f"    Schema:  {r['artifact']}")
        console.print(f"    Python:  {r['python_sdk']}")
        console.print(f"    TypeScript: {r['typescript_sdk']}")


@model_group.command("reinitialize")
@click.argument("object_type")
def model_reinitialize(object_type: str) -> None:
    """Drop and recreate a snapshot dataset from its source."""
    builder, _ = _get_builder()
    result = builder.reinitialize(object_type)
    console.print(f"[green]✓[/green] Reinitialized [bold]{result['name']}[/bold]")
    console.print(f"  New snapshot ID: {result['new_snapshot_id']}")
