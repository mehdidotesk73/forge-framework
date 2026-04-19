"""forge pipeline commands."""
from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _get_runner():
    from forge.config import find_project_root, load_config
    from forge.storage.engine import StorageEngine
    from forge.pipeline.runner import PipelineRunner
    root = find_project_root()
    config, _ = load_config(root)
    engine = StorageEngine(root / ".forge")
    runner = PipelineRunner(engine, root)
    return config, engine, runner, root


@click.group()
def pipeline_group() -> None:
    """Manage and run pipelines."""


@pipeline_group.command("run")
@click.argument("name")
def pipeline_run(name: str) -> None:
    """Run a registered pipeline."""
    config, engine, runner, root = _get_runner()
    pipeline_cfg = config.pipeline_by_name.get(name)
    if pipeline_cfg is None:
        console.print(f"[red]Pipeline '{name}' not found in forge.toml[/red]")
        available = [p.name for p in config.pipelines]
        if available:
            console.print(f"Available: {', '.join(available)}")
        raise SystemExit(1)

    import sys
    import contextlib

    console.print(f"[cyan]Running pipeline:[/cyan] {name}")
    try:
        defn = runner.load_pipeline(pipeline_cfg.module, pipeline_cfg.function)
        # console.status() uses a background thread that triggers WinError 10038
        # on Windows (WSAENOTSOCK in the Console API cleanup path).
        status_ctx = (
            console.status(f"Executing {pipeline_cfg.module}.{pipeline_cfg.function}...")
            if sys.platform != "win32"
            else contextlib.nullcontext()
        )
        with status_ctx:
            result = runner.run(defn, config_name=name)
    except Exception as exc:
        import traceback
        console.print(f"[red]Pipeline failed:[/red] {exc}")
        console.print("[dim]" + traceback.format_exc() + "[/dim]")
        raise SystemExit(1) from exc

    console.print(f"[green]OK[/green] ({result['duration_seconds']:.2f}s)")
    if result.get("rows_written"):
        for output_name, count in result["rows_written"].items():
            console.print(f"  {output_name}: {count:,} rows written")


@pipeline_group.command("dag")
def pipeline_dag() -> None:
    """Display the pipeline dependency DAG."""
    from forge.config import find_project_root, load_config
    from forge.storage.engine import StorageEngine
    from forge.pipeline.runner import PipelineRunner
    from forge.pipeline.dag import build_dag, render_dag
    import sys

    root = find_project_root()
    config, _ = load_config(root)
    engine = StorageEngine(root / ".forge")
    runner = PipelineRunner(engine, root)

    pipeline_defs = []
    for p in config.pipelines:
        try:
            defn = runner.load_pipeline(p.module, p.function)
            defn.name = p.name  # use config name for DAG display
            pipeline_defs.append(defn)
        except Exception as exc:
            console.print(f"[yellow]Warning: could not load {p.name}: {exc}[/yellow]")

    nodes, edges = build_dag(pipeline_defs)
    console.print(render_dag(nodes, edges))


@pipeline_group.command("list")
def pipeline_list() -> None:
    """List all registered pipelines with their IDs."""
    config, engine, runner, root = _get_runner()
    if not config.pipelines:
        console.print("[dim]No pipelines registered in forge.toml[/dim]")
        return
    from rich.table import Table
    table = Table(title="Pipelines")
    table.add_column("Name", style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Schedule")
    table.add_column("Module")
    for p in config.pipelines:
        table.add_row(p.name, p.id, p.schedule or "-", p.module)
    console.print(table)


@pipeline_group.command("create")
@click.argument("name")
def pipeline_create(name: str) -> None:
    """Scaffold a new pipeline file and register it in forge.toml."""
    from forge.config import find_project_root
    from forge.operations.scaffolding import create_pipeline
    root = find_project_root()
    result = create_pipeline(root, name)
    if "error" in result:
        console.print(f"[red]Error:[/red] {result['error']}")
        raise SystemExit(1)
    console.print(f"[green]OK[/green] Created [bold]{result['name']}[/bold]")
    console.print(f"  {result['file']}")


@pipeline_group.command("history")
@click.argument("name")
def pipeline_history(name: str) -> None:
    """Show run history for a pipeline (by name or ID)."""
    config, engine, runner, root = _get_runner()
    # Accept either name or UUID
    pipeline_cfg = config.pipeline_by_name.get(name) or config.pipeline_by_id.get(name)
    resolved_name = pipeline_cfg.name if pipeline_cfg else name
    history = engine.get_pipeline_history(resolved_name)

    if not history:
        console.print(f"[dim]No runs recorded for pipeline '{name}'[/dim]")
        return

    table = Table(title=f"Run history: {name}")
    table.add_column("Status", style="bold")
    table.add_column("Started")
    table.add_column("Duration")
    table.add_column("Rows Written")
    table.add_column("Error")

    for run in history:
        status_style = "green" if run["status"] == "success" else "red"
        duration = f"{run['duration_seconds']:.2f}s" if run["duration_seconds"] else "-"
        rows = str(run["rows_written"]) if run["rows_written"] else "-"
        table.add_row(
            f"[{status_style}]{run['status']}[/{status_style}]",
            (run["started_at"] or "")[:19],
            duration,
            rows,
            (run["error"] or "")[:60],
        )
    console.print(table)
