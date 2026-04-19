"""forge endpoint commands."""
from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _get_builder():
    from forge.config import find_project_root, load_config
    from forge.control.builder import EndpointBuilder
    root = find_project_root()
    config, _ = load_config(root)
    return EndpointBuilder(config, root), config


@click.group()
def endpoint_group() -> None:
    """Build and inspect endpoints."""


@endpoint_group.command("create")
@click.argument("name")
@click.option("--repo", required=True, help="Endpoint repo to add to (existing or new name)")
@click.option("--kind", default="action", show_default=True,
              type=click.Choice(["action", "streaming", "computed_attribute"]),
              help="Endpoint kind")
def endpoint_create(name: str, repo: str, kind: str) -> None:
    """Scaffold a new endpoint function in an endpoint repo."""
    from forge.config import find_project_root
    from forge.operations.scaffolding import create_endpoint
    root = find_project_root()
    result = create_endpoint(root, name, repo, kind)
    if "error" in result:
        console.print(f"[red]✗[/red] {result['error']}")
        raise SystemExit(1)
    console.print(f"[green]✓[/green] Created [bold]{result['name']}[/bold] ({result['kind']}) in repo [bold]{result['repo']}[/bold]")
    console.print(f"  {result['file']}")


@endpoint_group.command("build")
@click.option("--repo", default=None, help="Build a single endpoint repo by name")
def endpoint_build(repo: str | None) -> None:
    """Build endpoint descriptors from all registered endpoint repos."""
    builder, config = _get_builder()

    if not config.endpoint_repos:
        console.print("[yellow]No endpoint repos registered in forge.toml[/yellow]")
        return

    if repo:
        repo_cfg = next((r for r in config.endpoint_repos if r.name == repo), None)
        if repo_cfg is None:
            console.print(f"[red]Endpoint repo '{repo}' not found[/red]")
            raise SystemExit(1)
        with console.status(f"Building repo {repo}..."):
            descriptors = builder.build_repo(repo_cfg)
        # Merge into existing registry
        existing = builder.load_registry()
        existing.update(descriptors)
        builder._write_registry(existing)
    else:
        with console.status("Building all endpoint repos..."):
            descriptors = builder.build_all()

    table = Table(title="Registered Endpoints")
    table.add_column("Name", style="bold")
    table.add_column("Kind")
    table.add_column("ID", style="cyan")
    table.add_column("Repo")
    table.add_column("Params")

    registry = builder.load_registry()
    for ep_id, ep in registry.items():
        kind_style = "blue" if ep["kind"] == "action" else "magenta"
        table.add_row(
            ep["name"],
            f"[{kind_style}]{ep['kind']}[/{kind_style}]",
            ep_id[:8] + "...",
            ep.get("repo", ""),
            str(len(ep.get("params", []))),
        )
    console.print(table)
