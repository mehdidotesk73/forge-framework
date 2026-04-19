"""forge export — package a forge project into a portable .forgepkg archive."""
from __future__ import annotations

import zipfile
from pathlib import Path

import click
from rich.console import Console

console = Console()

_ALWAYS_INCLUDE = [
    "forge.toml",
]

_SOURCE_GLOBS = [
    "**/*.py",
    "**/*.ts",
    "**/*.tsx",
    "**/*.json",
    "**/*.toml",
    "**/*.html",
    "**/*.css",
]

_EXCLUDE_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    ".git",
}


@click.command("export")
@click.option(
    "--output", "-o", default=None,
    help="Output path for the .forgepkg file (default: <project-name>.forgepkg in cwd)",
)
@click.option(
    "--no-data", is_flag=True, default=False,
    help="Exclude .forge/data/ Parquet files (source + artifacts only)",
)
def export_cmd(output: str | None, no_data: bool) -> None:
    """Package this project into a portable <name>.forgepkg archive.

    The archive includes source code, .forge/artifacts/, .forge/generated/,
    and by default .forge/data/ (the Parquet datasets). Recipients unzip,
    pip install forge-framework, and run `forge dev serve` — no setup.sh needed.
    """
    from forge.config import find_project_root, load_config

    root = find_project_root()
    config, _ = load_config(root)

    pkg_name = f"{config.name}.forgepkg"
    out_path = Path(output) if output else Path.cwd() / pkg_name

    console.print(f"[bold]Exporting[/bold] {config.name} → {out_path}")

    included = 0
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in _collect_files(root, no_data):
            arcname = path.relative_to(root)
            zf.write(path, arcname)
            included += 1

    size_mb = out_path.stat().st_size / 1_048_576
    console.print(f"[green]✓[/green] {included} files, {size_mb:.1f} MB → {out_path.name}")
    console.print()
    console.print("[dim]Distribute this file. Recipient runs:[/dim]")
    console.print(f"[dim]  unzip {out_path.name}[/dim]")
    console.print(f"[dim]  pip install forge-framework[/dim]")
    console.print(f"[dim]  forge dev serve[/dim]")


def _collect_files(root: Path, no_data: bool):
    """Yield all files to include in the export."""
    forge_dir = root / ".forge"

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        # Skip excluded directories anywhere in the path
        if any(part in _EXCLUDE_DIRS for part in path.parts):
            continue
        rel = path.relative_to(root)
        parts = rel.parts

        if parts[0] == ".forge":
            # Always include artifacts and generated
            if len(parts) > 1 and parts[1] in ("artifacts", "generated"):
                yield path
            # Include data unless --no-data
            elif len(parts) > 1 and parts[1] == "data" and not no_data:
                yield path
            # Include forge.duckdb (run history) unless --no-data
            elif path.name == "forge.duckdb" and not no_data:
                yield path
            # Include built app dist/ directories
            elif len(parts) > 1 and parts[1] == "apps":
                yield path
        else:
            yield path
