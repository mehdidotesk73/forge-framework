"""forge init <project-name>"""
from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console

console = Console()

_FORGE_TOML = """\
[project]
name = "{name}"
forge_version = "{forge_version}"

# Datasets are managed automatically by forge dataset load
# datasets = []

# [[pipelines]]
# id = "generated-uuid-here"   # stable trigger ID — never changes even if name changes
# name = "my_pipeline"
# module = "pipelines.my_pipeline"
# function = "run"
# schedule = "0 */6 * * *"   # optional cron

# [[models]]
# name = "MyObject"
# mode = "snapshot"          # or "stream"
# module = "models.my_object"
# class = "MyObject"

# [[endpoint_repos]]
# name = "my_endpoints"
# path = "./endpoint_repos/my_endpoints"

# [[apps]]
# name = "my-app"
# path = "./apps/my-app"
"""

_GITIGNORE = """\
# Forge runtime data (local only — excluded from version control)
.forge/data/
.forge/*.duckdb
.forge/*.duckdb.wal

# Forge Suite machine-local files (created by forge-suite, never committed)
.forge-suite/

# Python
.venv/
__pycache__/
*.pyc

# Node
node_modules/
dist/

# Environment
.env
"""

_PIPELINE_EXAMPLE = '''\
"""Example pipeline — replace with your own logic."""
from forge.pipeline import pipeline, ForgeInput, ForgeOutput

# Dataset IDs are assigned by `forge dataset load` — paste them here.
# RAW_DATASET_ID = "paste-uuid-here"

@pipeline(
    inputs={},
    outputs={},
)
def run(inputs, outputs):
    pass
'''

_MODEL_EXAMPLE = '''\
"""Example model definition."""
from forge.model import forge_model, field_def

# @forge_model(mode="snapshot", backing_dataset="paste-dataset-uuid-here")
# class MyObject:
#     id: str = field_def(primary_key=True)
#     name: str = field_def(display="Name")
'''


@click.command()
@click.argument("project_name")
@click.option("--path", default=".", show_default=True, help="Parent directory for the project")
def init_cmd(project_name: str, path: str) -> None:
    """Initialize a new Forge project."""
    parent = Path(path).resolve()
    project_dir = parent / project_name

    if project_dir.exists():
        console.print(f"[red]Directory already exists:[/red] {project_dir}")
        raise SystemExit(1)

    # Create directory structure
    dirs = [
        project_dir,
        project_dir / ".forge" / "data",
        project_dir / ".forge" / "artifacts",
        project_dir / ".forge" / "generated" / "python",
        project_dir / ".forge" / "generated" / "typescript",
        project_dir / ".forge-suite",
        project_dir / "pipelines",
        project_dir / "models",
        project_dir / "endpoint_repos",
        project_dir / "apps",
        project_dir / "data",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    # Write forge.toml
    (project_dir / "forge.toml").write_text(_FORGE_TOML.format(name=project_name, forge_version=__version__))

    # Write .gitignore, requirements.txt, setup.sh
    (project_dir / ".gitignore").write_text(_GITIGNORE)
    from forge.operations.projects import _REQUIREMENTS_TXT, _SETUP_SH, _FORGE_DIR_README, _FORGE_SUITE_DIR_README
    (project_dir / "requirements.txt").write_text(_REQUIREMENTS_TXT.format(version=__version__))
    (project_dir / "setup.sh").write_text(_SETUP_SH)
    (project_dir / ".forge" / "README.md").write_text(_FORGE_DIR_README)
    (project_dir / ".forge-suite" / "README.md").write_text(_FORGE_SUITE_DIR_README)

    # Write placeholder __init__ files
    (project_dir / "pipelines" / "__init__.py").write_text("")
    (project_dir / "models" / "__init__.py").write_text("")

    # Write example stubs
    (project_dir / "pipelines" / "example_pipeline.py").write_text(_PIPELINE_EXAMPLE)
    (project_dir / "models" / "example_model.py").write_text(_MODEL_EXAMPLE)

    # Write .forge/migration_state.json
    import json
    from forge.version import __version__
    state = project_dir / ".forge" / "migration_state.json"
    state.write_text(json.dumps({"forge_version": __version__}))

    console.print(f"[green]✓[/green] Created Forge project [bold]{project_name}[/bold] at {project_dir}")
    console.print()
    console.print("[dim]Setting up Python environment...[/dim]")
    from forge.operations.projects import bootstrap_project_venv
    venv_result = bootstrap_project_venv(project_dir)
    if venv_result.get("installed"):
        console.print("[green]✓[/green] Installed forge-framework into .venv")
    else:
        console.print(f"[yellow]![/yellow] Venv setup incomplete: {venv_result.get('error', 'unknown error')}")
        console.print("  Run [bold]bash setup.sh[/bold] to complete setup manually.")
    console.print()
    console.print("[dim]Next steps:[/dim]")
    console.print(f"  cd {project_name}")
    console.print("  source .venv/bin/activate   # (Windows: .venv\\Scripts\\activate)")
    console.print("  forge dataset load data/my_file.csv --name my_data")
    console.print("  forge pipeline run my_pipeline")
    console.print("  forge model build")
    console.print("  forge dev serve")
