"""forge dataset commands."""
from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _get_engine():
    from forge.config import find_project_root
    from forge.storage.engine import StorageEngine
    root = find_project_root()
    return StorageEngine(root / ".forge"), root


@click.group()
def dataset_group() -> None:
    """Manage datasets."""


@dataset_group.command("load")
@click.argument("file", type=click.Path(exists=True))
@click.option("--name", required=True, help="Dataset name")
def dataset_load(file: str, name: str) -> None:
    """Load a CSV or Parquet file as a named dataset."""
    engine, root = _get_engine()
    meta = engine.load_file(Path(file), name)

    # Update forge.toml with the new dataset entry
    _register_dataset_in_config(root, meta)

    console.print(f"[green]✓[/green] Loaded dataset [bold]{name}[/bold]")
    console.print(f"  ID:   [cyan]{meta.id}[/cyan]")
    console.print(f"  Rows: {meta.row_count:,}")
    console.print(f"  Cols: {', '.join(meta.schema['fields'].keys())}")


@dataset_group.command("list")
def dataset_list() -> None:
    """List all datasets."""
    engine, _ = _get_engine()
    datasets = engine.list_datasets()

    if not datasets:
        console.print("[dim]No datasets. Run: forge dataset load <file> --name <name>[/dim]")
        return

    table = Table(title="Datasets")
    table.add_column("Name", style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Rows", justify="right")
    table.add_column("Version", justify="right")
    table.add_column("Snapshot")
    table.add_column("Created")

    for d in datasets:
        table.add_row(
            d.name,
            d.id[:8] + "...",
            f"{d.row_count:,}",
            str(d.version),
            "✓" if d.is_snapshot else "",
            d.created_at[:19],
        )
    console.print(table)


@dataset_group.command("inspect")
@click.argument("dataset_id_or_name")
def dataset_inspect(dataset_id_or_name: str) -> None:
    """Inspect a dataset's schema and preview rows."""
    engine, _ = _get_engine()
    meta = engine.get_dataset(dataset_id_or_name)
    if meta is None:
        meta = engine.find_dataset_by_name(dataset_id_or_name)
    if meta is None:
        console.print(f"[red]Dataset not found:[/red] {dataset_id_or_name}")
        raise SystemExit(1)

    console.print(f"[bold]{meta.name}[/bold] (ID: {meta.id})")
    console.print(f"  Mode:    {'snapshot' if meta.is_snapshot else 'immutable'}")
    console.print(f"  Rows:    {meta.row_count:,}")
    console.print(f"  Version: {meta.version}")
    console.print(f"  Created: {meta.created_at}")

    console.print("\n[bold]Schema:[/bold]")
    schema_table = Table()
    schema_table.add_column("Field")
    schema_table.add_column("Type")
    schema_table.add_column("Nullable")
    for fname, fmeta in meta.schema.get("fields", {}).items():
        schema_table.add_row(
            fname,
            fmeta.get("type", "?"),
            "yes" if fmeta.get("nullable") else "no",
        )
    console.print(schema_table)

    df = engine.read_dataset(meta.id)
    console.print(f"\n[bold]Preview (first 5 rows):[/bold]")
    preview = Table()
    for col in df.columns:
        preview.add_column(col)
    for _, row in df.head(5).iterrows():
        preview.add_row(*[str(v) for v in row.values])
    console.print(preview)


def _register_dataset_in_config(root: Path, meta) -> None:
    """Add dataset entry to forge.toml."""
    import sys
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    config_path = root / "forge.toml"
    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    datasets = raw.get("datasets", [])
    # Check not already registered
    for d in datasets:
        if d.get("id") == meta.id:
            return

    datasets.append({
        "id": meta.id,
        "name": meta.name,
        "path": meta.parquet_path,
    })
    raw["datasets"] = datasets

    try:
        import tomli_w
        with open(config_path, "wb") as f:
            tomli_w.dump(raw, f)
    except ImportError:
        # tomli_w not available; skip updating config silently
        pass
