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
.forge/
__pycache__/
*.pyc
node_modules/
dist/
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

    # Write .gitignore
    (project_dir / ".gitignore").write_text(_GITIGNORE)

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
    console.print("[dim]Next steps:[/dim]")
    console.print(f"  cd {project_name}")
    console.print("  forge dataset load data/my_file.csv --name my_data")
    console.print("  forge pipeline run my_pipeline")
    console.print("  forge model build")
    console.print("  forge dev serve")
