"""forge upgrade."""
from __future__ import annotations

import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--dry-run", is_flag=True, help="Show what would happen without making changes")
def upgrade_cmd(dry_run: bool) -> None:
    """Upgrade the project to the current installed Forge version."""
    from forge.config import find_project_root, load_config
    from forge.storage.engine import StorageEngine
    from forge.model.builder import ModelBuilder
    from forge.control.builder import EndpointBuilder
    from forge.migrations.base import MigrationRunner
    from forge.version import __version__

    root = find_project_root()
    config, _ = load_config(root)

    migration_runner = MigrationRunner(root)
    current = migration_runner.get_current_version()

    console.print(f"[bold]Forge Upgrade[/bold]")
    console.print(f"  Current version: {current}")
    console.print(f"  Target version:  {__version__}")

    pending = migration_runner.get_pending_migrations(__version__)

    if not pending:
        console.print("[green]✓[/green] Already up to date.")
    else:
        console.print(f"\nPending migrations ({len(pending)}):")
        for m in pending:
            console.print(f"  {m.from_version} → {m.to_version}: {m.description}")

        if dry_run:
            console.print("\n[dim](dry-run — no changes made)[/dim]")
            return

        with console.status("Running migrations..."):
            applied = migration_runner.run_migrations(__version__)
        for step in applied:
            console.print(f"  [green]✓[/green] {step}")

    if not dry_run:
        # Regenerate all build artifacts
        console.print("\nRegenerating build artifacts...")
        engine = StorageEngine(root / ".forge")

        if config.models:
            builder = ModelBuilder(config, root, engine)
            with console.status("forge model build..."):
                builder.build_all()
            console.print("[green]✓[/green] Models rebuilt")

        if config.endpoint_repos:
            ep_builder = EndpointBuilder(config, root)
            with console.status("forge endpoint build..."):
                ep_builder.build_all()
            console.print("[green]✓[/green] Endpoints rebuilt")

        migration_runner.set_current_version(__version__)
        console.print(f"\n[green]✓[/green] Project upgraded to {__version__}")
