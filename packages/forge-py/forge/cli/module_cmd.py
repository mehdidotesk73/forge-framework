"""forge module — manage Forge modules."""
from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _name_to_package(name: str) -> str:
    return f"forge-modules-{name}"


def _name_to_underscored(name: str) -> str:
    return name.replace("-", "_")


def _default_config_var(name: str) -> str:
    snake = _name_to_underscored(name)
    return f"forge_modules.{snake}.module:MODULE_CONFIG"


# ── Group ─────────────────────────────────────────────────────────────────────

@click.group("module")
def module_group() -> None:
    """Manage Forge modules."""


# ── forge module add ──────────────────────────────────────────────────────────

@module_group.command("add")
@click.argument("name")
@click.option(
    "--package",
    default=None,
    help="Override pip package name (default: forge-modules-<name>)",
)
@click.option(
    "--no-install",
    is_flag=True,
    help="Skip pip install (package already installed)",
)
def module_add(name: str, package: str | None, no_install: bool) -> None:
    """Add a module to this Forge project."""
    from forge.config import find_project_root, load_config, ForgeModuleConfig
    from forge.storage.engine import StorageEngine
    from forge.server.app import bootstrap_module_datasets

    root = find_project_root()
    config, _ = load_config(root)

    # Check not already added
    if any(m.name == name for m in config.forge_modules):
        console.print(f"[yellow][!][/yellow] Module [bold]{name}[/bold] is already in forge.toml")
        return

    pip_package = package or _name_to_package(name)

    if not no_install:
        console.print(f"[dim]Installing {pip_package}...[/dim]")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pip_package],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[red]pip install failed:[/red]\n{result.stderr}")
            raise SystemExit(1)
        console.print(f"[green]OK[/green] Installed {pip_package}")

    config_var = _default_config_var(name)

    # Verify the module config can be imported
    module_path, attr = config_var.split(":")
    try:
        m = importlib.import_module(module_path)
        mc = getattr(m, attr)
    except Exception as exc:
        console.print(
            f"[red]Could not import MODULE_CONFIG from {module_path}:[/red] {exc}\n"
            f"Ensure the package is installed and exports MODULE_CONFIG at {config_var}"
        )
        raise SystemExit(1) from exc

    # Patch forge.toml — append [[forge_modules]] block as text
    toml_path = root / "forge.toml"
    existing = toml_path.read_text(encoding="utf-8")
    block = (
        f'\n[[forge_modules]]\n'
        f'name       = "{name}"\n'
        f'package    = "{pip_package}"\n'
        f'config_var = "{config_var}"\n'
    )
    toml_path.write_text(existing + block, encoding="utf-8")

    # Bootstrap datasets
    config, _ = load_config(root)  # reload to pick up the new block
    engine = StorageEngine(root / ".forge")
    bootstrap_module_datasets(config, engine)
    engine.close()

    n_models = len(mc.models)
    n_repos = len(mc.endpoint_repos)
    n_pipelines = len(mc.pipelines)
    n_datasets = len(mc.dataset_ids)
    console.print(
        f"[green]OK[/green] Added module [bold]{name}[/bold] - "
        f"{n_models} model(s), {n_repos} endpoint repo(s), "
        f"{n_pipelines} pipeline(s), {n_datasets} dataset(s) bootstrapped"
    )


# ── forge module remove ───────────────────────────────────────────────────────

@module_group.command("remove")
@click.argument("name")
@click.option(
    "--drop-datasets",
    is_flag=True,
    default=False,
    help="Delete module dataset files from .forge/data/ (destructive, no undo)",
)
def module_remove(name: str, drop_datasets: bool) -> None:
    """Remove a module from this Forge project."""
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    import tomli_w  # type: ignore[import]

    from forge.config import find_project_root

    root = find_project_root()
    toml_path = root / "forge.toml"
    with open(toml_path, "rb") as f:
        raw = tomllib.load(f)

    modules = raw.get("forge_modules", [])
    match = next((m for m in modules if m.get("name") == name), None)
    if match is None:
        console.print(f"[yellow][!][/yellow] Module [bold]{name}[/bold] not found in forge.toml")
        return

    config_var = match.get("config_var", _default_config_var(name))

    # Drop datasets if requested
    if drop_datasets:
        if not click.confirm(
            f"Delete all dataset files for module '{name}'? This cannot be undone.",
            default=False,
        ):
            console.print("Aborted.")
            return
        _drop_module_datasets(root, config_var)

    # Rewrite forge.toml without this module block
    raw["forge_modules"] = [m for m in modules if m.get("name") != name]
    if not raw["forge_modules"]:
        raw.pop("forge_modules")
    with open(toml_path, "wb") as f:
        tomli_w.dump(raw, f)

    console.print(f"[green]OK[/green] Removed module [bold]{name}[/bold] from forge.toml")
    if not drop_datasets:
        console.print(
            "[dim]Tip: run with --drop-datasets to also delete the module's data files.[/dim]"
        )


def _drop_module_datasets(root: Path, config_var: str) -> None:
    from forge.storage.engine import StorageEngine

    module_path, attr = config_var.split(":")
    try:
        m = importlib.import_module(module_path)
        mc = getattr(m, attr)
    except Exception as exc:
        console.print(f"[yellow][!][/yellow] Could not load module config to find datasets: {exc}")
        return

    engine = StorageEngine(root / ".forge")
    try:
        for class_name, dataset_id in mc.dataset_ids.items():
            meta = engine.get_dataset(dataset_id)
            if meta and meta.parquet_path:
                parquet_file = engine.data_dir / meta.parquet_path
                if parquet_file.exists():
                    parquet_file.unlink()
                    console.print(f"  Deleted {parquet_file.name} ({class_name})")
            # Remove the catalog entry
            engine._execute(
                "DELETE FROM datasets WHERE id = ?", [dataset_id]
            )
    finally:
        engine.close()


# ── forge module list ─────────────────────────────────────────────────────────

@module_group.command("list")
def module_list() -> None:
    """List modules configured in this Forge project."""
    from forge.config import find_project_root, load_config

    root = find_project_root()
    config, _ = load_config(root)

    if not config.forge_modules:
        console.print("[dim]No modules configured. Use 'forge module add <name>' to add one.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Package")
    table.add_column("Installed Version")
    table.add_column("Config Var")

    for m in config.forge_modules:
        try:
            version = importlib.metadata.version(m.package)
        except importlib.metadata.PackageNotFoundError:
            version = "[red]not installed[/red]"
        table.add_row(m.name, m.package, version, m.config_var)

    console.print(table)


# ── forge module build ────────────────────────────────────────────────────────

_MODULE_PY_TEMPLATE = '''\
# forge_modules/{snake_name}/module.py — GENERATED by `forge module build`. Do not edit.
from forge.modules import ModuleConfig, ModelEntry, EndpointRepoEntry, PipelineEntry

MODULE_CONFIG = ModuleConfig(
    name={name!r},
    models=[
{model_lines}
    ],
    endpoint_repos=[
{repo_lines}
    ],
    pipelines=[
{pipeline_lines}
    ],
    dataset_ids={{{dataset_id_lines}
    }},
)
'''


@module_group.command("build")
def module_build() -> None:
    """Generate forge_modules/<name>/module.py from this module's source."""
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    root = Path.cwd()
    toml_path = root / "forge.toml"
    if not toml_path.exists():
        console.print("[red]No forge.toml found. Run this command from inside a module directory.[/red]")
        raise SystemExit(1)

    with open(toml_path, "rb") as f:
        raw = tomllib.load(f)

    project_name = raw.get("project", {}).get("name", root.name)
    snake_name = _name_to_underscored(project_name)

    # Add project root to sys.path so model imports resolve
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    # Import each model module to trigger @forge_model decorators
    from forge.model.definition import _MODEL_REGISTRY, _CLASS_REGISTRY

    for model_cfg in raw.get("models", []):
        module_path = model_cfg.get("module", "")
        if module_path:
            try:
                importlib.import_module(module_path)
            except Exception as exc:
                console.print(f"[yellow][!][/yellow] Could not import model module {module_path}: {exc}")

    # Collect model entries from _CLASS_REGISTRY
    model_lines = []
    dataset_id_map: dict[str, str] = {}
    for class_name, cls in _CLASS_REGISTRY.items():
        defn = _MODEL_REGISTRY.get(class_name)
        if defn is None:
            continue
        dataset_id = defn.backing_dataset_id
        mode = defn.mode
        module_import = f"forge_modules.{snake_name}.{defn.module}"
        model_lines.append(
            f"        ModelEntry(class_name={class_name!r}, "
            f"module={module_import!r}, mode={mode!r}),"
        )
        dataset_id_map[class_name] = dataset_id

    # Collect endpoint repos from forge.toml
    repo_lines = []
    for repo_cfg in raw.get("endpoint_repos", []):
        module = repo_cfg.get("module", "")
        namespaced = f"forge_modules.{snake_name}.{module}"
        repo_lines.append(f"        EndpointRepoEntry(module={namespaced!r}),")

    # Collect pipelines from forge.toml
    pipeline_lines = []
    for p in raw.get("pipelines", []):
        pid = p.get("id", "")
        display_name = p.get("display_name") or p.get("name", "")
        module = p.get("module", "")
        namespaced = f"forge_modules.{snake_name}.{module}"
        function = p.get("function", "run")
        schedule = p.get("schedule")
        if schedule:
            pipeline_lines.append(
                f"        PipelineEntry(id={pid!r}, display_name={display_name!r},\n"
                f"                      module={namespaced!r}, function={function!r},"
                f" schedule={schedule!r}),"
            )
        else:
            pipeline_lines.append(
                f"        PipelineEntry(id={pid!r}, display_name={display_name!r},\n"
                f"                      module={namespaced!r}, function={function!r}),"
            )

    dataset_id_lines = "\n".join(
        f"        {cls!r}: {uid!r}," for cls, uid in sorted(dataset_id_map.items())
    )
    if dataset_id_lines:
        dataset_id_lines = "\n" + dataset_id_lines + "\n"

    content = _MODULE_PY_TEMPLATE.format(
        snake_name=snake_name,
        name=project_name,
        model_lines="\n".join(model_lines) if model_lines else "        # no models",
        repo_lines="\n".join(repo_lines) if repo_lines else "        # no endpoint repos",
        pipeline_lines="\n".join(pipeline_lines) if pipeline_lines else "        # no pipelines",
        dataset_id_lines=dataset_id_lines,
    )

    # Warn on UUID drift vs existing module.py
    namespace_dir = root / "forge_modules" / snake_name
    module_py_path = namespace_dir / "module.py"
    if module_py_path.exists():
        _warn_uuid_drift(module_py_path, dataset_id_map)

    namespace_dir.mkdir(parents=True, exist_ok=True)
    init_file = namespace_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("")

    module_py_path.write_text(content, encoding="utf-8")
    console.print(
        f"[green]OK[/green] Generated [bold]forge_modules/{snake_name}/module.py[/bold] - "
        f"{len(model_lines)} model(s), {len(repo_lines)} endpoint repo(s), "
        f"{len(pipeline_lines)} pipeline(s)"
    )


def _warn_uuid_drift(module_py_path: Path, new_ids: dict[str, str]) -> None:
    """Parse existing module.py and warn if any dataset UUID changed."""
    text = module_py_path.read_text(encoding="utf-8")
    for class_name, new_id in new_ids.items():
        pattern = re.compile(rf'["\']({class_name})["\']:\s*["\']([^"\']+)["\']')
        m = pattern.search(text)
        if m and m.group(2) != new_id:
            console.print(
                f"[red][!] UUID drift for {class_name}: "
                f"was {m.group(2)!r}, now {new_id!r}. "
                f"Dataset UUIDs must never change after first publication.[/red]"
            )


# ── forge module adopt ────────────────────────────────────────────────────────

@module_group.command("adopt")
@click.argument("project_path")
@click.option("--name", default=None, help="Module name (default: forge.toml project name)")
@click.option(
    "--in-place",
    is_flag=True,
    help="Add packaging files to the project directory instead of copying",
)
def module_adopt(project_path: str, name: str | None, in_place: bool) -> None:
    """Promote a Forge project into a publishable module package."""
    import shutil
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    src = Path(project_path).resolve()
    src_toml = src / "forge.toml"
    if not src_toml.exists():
        console.print(f"[red]No forge.toml found at {src}[/red]")
        raise SystemExit(1)

    with open(src_toml, "rb") as f:
        src_raw = tomllib.load(f)

    project_name = name or src_raw.get("project", {}).get("name", src.name)
    snake_name = _name_to_underscored(project_name)

    if in_place:
        target = src
    else:
        # Default destination: packages/forge-modules/<name>
        # Walk up to find the monorepo root (contains packages/)
        monorepo_root = _find_monorepo_root()
        if monorepo_root:
            target = monorepo_root / "packages" / "forge-modules" / project_name
        else:
            target = Path.cwd() / "packages" / "forge-modules" / project_name
        console.print(f"[dim]Copying {src} -> {target}...[/dim]")
        _copytree_filtered(src, target)
        console.print(f"[green]OK[/green] Copied to {target}")

    # Generate pyproject.toml
    _write_pyproject_toml(target, project_name)

    # Create forge_modules/<snake>/  namespace dir
    ns_dir = target / "forge_modules" / snake_name
    ns_dir.mkdir(parents=True, exist_ok=True)
    init_file = ns_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("")

    # Ensure there is NO forge_modules/__init__.py (namespace package)
    top_init = target / "forge_modules" / "__init__.py"
    if top_init.exists():
        top_init.unlink()

    # Run forge module build to generate module.py
    result = subprocess.run(
        [sys.executable, "-m", "forge.cli.main", "module", "build"],
        cwd=str(target),
    )
    if result.returncode != 0:
        console.print(
            "[yellow][!][/yellow] 'forge module build' failed — run it manually inside the target dir."
        )

    console.print(f"[green]OK[/green] Module [bold]{project_name}[/bold] adopted at {target}")
    console.print(
        "[dim]Next: pip install -e . then forge module add <name> in your host project[/dim]"
    )


def _find_monorepo_root() -> Path | None:
    """Walk up from cwd to find the forge-framework monorepo root."""
    for candidate in [Path.cwd(), *Path.cwd().parents]:
        if (candidate / "packages").is_dir() and (candidate / "CLAUDE.md").exists():
            return candidate
    return None


def _copytree_filtered(src: Path, dst: Path) -> None:
    import shutil

    _SKIP_DIRS = {".venv", "node_modules", "dist", ".forge-suite"}
    _SKIP_DATA_SUFFIXES = {".parquet", ".duckdb", ".duckdb.wal"}

    def ignore(directory: str, contents: list[str]) -> list[str]:
        d = Path(directory)
        skipped = []
        for name in contents:
            p = d / name
            if p.is_dir() and name in _SKIP_DIRS:
                skipped.append(name)
                continue
            if p.is_dir() and p.name == "data" and (d / "forge.toml").exists():
                skipped.append(name)  # skip project-level data/ dir
                continue
            if any(name.endswith(s) for s in _SKIP_DATA_SUFFIXES):
                skipped.append(name)
        return skipped

    shutil.copytree(str(src), str(dst), ignore=ignore)


def _write_pyproject_toml(target: Path, name: str) -> None:
    from forge.version import __version__

    pyproject_path = target / "pyproject.toml"
    if pyproject_path.exists():
        console.print("[dim]pyproject.toml already exists — skipping generation[/dim]")
        return

    # Detect optional LLM dependencies
    optional_deps: list[str] = []
    for py_file in (target / "endpoint_repos").rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        if "anthropic" in text:
            optional_deps.append("anthropic")
        if "openai" in text:
            optional_deps.append("openai")
        if "boto3" in text:
            optional_deps.append("boto3")

    optional_section = ""
    if optional_deps:
        listed = ", ".join(f'"{d}"' for d in sorted(set(optional_deps)))
        optional_section = f'\n[project.optional-dependencies]\nall = [{listed}]\n'

    content = f'''\
[build-system]
requires      = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name            = "forge-modules-{name}"
version         = "0.1.0"
description     = ""
requires-python = ">=3.11"
license         = {{ text = "MIT" }}
dependencies    = [
    "forge-framework>={__version__}",
]
{optional_section}
[tool.setuptools.packages.find]
where   = ["."]
include = ["forge_modules*"]
'''
    pyproject_path.write_text(content, encoding="utf-8")
    console.print(f"[green]OK[/green] Generated pyproject.toml for forge-modules-{name}")
