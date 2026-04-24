"""Root CLI group."""
import click
from rich.console import Console

console = Console()


@click.group()
@click.version_option(package_name="forge-framework")
def cli() -> None:
    """Forge — Layered Data Application Framework"""


# Register sub-command groups
from forge.cli.init_cmd import init_cmd
from forge.cli.dataset_cmd import dataset_group
from forge.cli.pipeline_cmd import pipeline_group
from forge.cli.model_cmd import model_group
from forge.cli.endpoint_cmd import endpoint_group
from forge.cli.app_cmd import app_group
from forge.cli.dev_cmd import dev_group
from forge.cli.upgrade_cmd import upgrade_cmd
from forge.cli.build_cmd import build_cmd
from forge.cli.export_cmd import export_cmd
from forge.cli.module_cmd import module_group

cli.add_command(init_cmd, name="init")
cli.add_command(dataset_group, name="dataset")
cli.add_command(pipeline_group, name="pipeline")
cli.add_command(model_group, name="model")
cli.add_command(endpoint_group, name="endpoint")
cli.add_command(app_group, name="app")
cli.add_command(dev_group, name="dev")
cli.add_command(upgrade_cmd, name="upgrade")
cli.add_command(build_cmd, name="build")
cli.add_command(export_cmd, name="export")
cli.add_command(module_group, name="module")


@cli.command()
def version() -> None:
    """Show Forge version."""
    from forge.version import __version__, TS_VERSION
    console.print(f"[bold]forge-framework[/bold] {__version__} (Python)")
    console.print(f"[bold]@forge-suite/ts[/bold] {TS_VERSION} (TypeScript)")


if __name__ == "__main__":
    cli()
