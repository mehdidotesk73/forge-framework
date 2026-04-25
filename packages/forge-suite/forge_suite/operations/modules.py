"""SUITE module operations — absorb, shed, implant, and list modules."""
from __future__ import annotations

import importlib
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ── helpers ────────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _forge_module_model():
    from models.models import ForgeModule
    return ForgeModule


def _webapp_root() -> Path:
    """Return the forge-suite runtime webapp root (~/.forge-suite/webapp)."""
    return (Path.home() / ".forge-suite" / "webapp").resolve()


def _name_to_snake(name: str) -> str:
    return name.replace("-", "_")


def _default_config_var(name: str) -> str:
    snake = _name_to_snake(name)
    return f"forge_modules.{snake}.module:MODULE_CONFIG"


# ── list ───────────────────────────────────────────────────────────────────────

def list_modules() -> dict:
    """Return all ForgeModule records as a list of dicts."""
    ForgeModule = _forge_module_model()
    rows = [
        {
            "id": m.id,
            "name": m.name,
            "package": m.package,
            "version": m.version,
            "source_path": m.source_path,
            "namespace_path": m.namespace_path,
            "absorbed_at": m.absorbed_at,
            "description": m.description,
            "origin": getattr(m, "origin", "user"),
        }
        for m in ForgeModule.all()
    ]
    return {"modules": rows}


# ── absorb ─────────────────────────────────────────────────────────────────────

def absorb_module(source_path: str, name: str = "", description: str = "", origin: str = "user") -> dict:
    """
    Absorb an existing Forge project as a module into forge-webapp.

    Steps:
    1. Resolve source_path; infer name from forge.toml if not given.
    2. Run forge module build inside source_path (calls CLI logic directly).
    3. Copy forge_modules/<snake>/ into forge-webapp/forge_modules/<snake>/.
    4. Append [[forge_modules]] block to forge-webapp/forge.toml.
    5. Create ForgeModule snapshot row.
    6. Rebuild forge-webapp models + endpoints.
    """
    import subprocess

    ForgeModule = _forge_module_model()
    src = Path(source_path).resolve()
    if not src.exists():
        return {"error": f"Source path does not exist: {source_path}"}

    toml_path = src / "forge.toml"
    if not toml_path.exists():
        return {"error": f"No forge.toml found at {source_path}"}

    # Parse forge.toml to infer name
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib  # type: ignore[no-redef]

    with open(toml_path, "rb") as f:
        raw = tomllib.load(f)

    inferred_name = raw.get("project", {}).get("name", src.name)
    module_name = name.strip() or inferred_name
    snake = _name_to_snake(module_name)

    # Check not already absorbed
    if any(m.name == module_name for m in ForgeModule.all()):
        return {"error": f"Module '{module_name}' is already absorbed"}

    # Run `forge module build` inside source_path using subprocess so it runs
    # in the correct working directory. Use sys.executable to ensure same venv.
    import os
    _utf8_env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, "-m", "forge.cli.main", "module", "build"],
        cwd=str(src),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_utf8_env,
    )
    if result.returncode != 0:
        return {"error": f"forge module build failed:\n{result.stderr}"}

    # Locate the generated namespace dir
    gen_namespace = src / "forge_modules" / snake
    if not gen_namespace.exists():
        return {"error": f"forge module build did not produce forge_modules/{snake}/ in {source_path}"}

    # Copy namespace dir into forge-webapp
    webapp_root = _webapp_root()
    dest_namespace = webapp_root / "forge_modules" / snake
    if dest_namespace.exists():
        shutil.rmtree(dest_namespace)
    shutil.copytree(str(gen_namespace), str(dest_namespace))

    # Determine installed version
    package_name = f"forge-modules-{module_name}"
    try:
        import importlib.metadata as _meta
        version = _meta.version(package_name)
    except Exception:
        version = "dev"

    # Config var
    config_var = _default_config_var(module_name)

    # Append [[forge_modules]] to forge-webapp/forge.toml
    webapp_toml = webapp_root / "forge.toml"
    existing_toml = webapp_toml.read_text(encoding="utf-8")
    block = (
        f'\n[[forge_modules]]\n'
        f'name       = "{module_name}"\n'
        f'package    = "{package_name}"\n'
        f'config_var = "{config_var}"\n'
    )
    webapp_toml.write_text(existing_toml + block, encoding="utf-8")

    # Create ForgeModule record
    mod_id = f"fm-{uuid.uuid4().hex[:12]}"
    ForgeModule.create(
        id=mod_id,
        name=module_name,
        package=package_name,
        version=version,
        source_path=str(src),
        namespace_path=str(dest_namespace),
        absorbed_at=_now(),
        description=description,
        origin=origin,
    )

    # Rebuild forge-webapp models and endpoints so the namespace package is live
    rebuild_result = _rebuild_webapp(webapp_root)

    return {
        "ok": True,
        "id": mod_id,
        "name": module_name,
        "version": version,
        "namespace_path": str(dest_namespace),
        "rebuild": rebuild_result,
        "restart_required": True,
    }


# ── shed ───────────────────────────────────────────────────────────────────────

def shed_module(module_id: str, drop_datasets: bool = False, confirm: bool = False) -> dict:
    """
    Remove a module from forge-webapp.

    NOTE: This does NOT touch any managed project's forge.toml — project owners
    must remove the [[forge_modules]] entry from their own projects.
    Pass confirm=True when removing a suite-bundled module.
    """
    ForgeModule = _forge_module_model()
    mod = ForgeModule.get(module_id)
    if mod is None:
        return {"error": f"Module {module_id} not found"}

    if getattr(mod, "origin", "user") == "suite" and not confirm:
        return {
            "warning": (
                f"Module '{mod.name}' is bundled with this forge-suite installation. "
                "Removing it is permanent until you reinstall forge-suite. "
                "Pass confirm=True to proceed."
            )
        }

    module_name = mod.name
    snake = _name_to_snake(module_name)
    webapp_root = _webapp_root()

    # Remove [[forge_modules]] block for this module from forge-webapp/forge.toml
    # We use text-based removal to avoid requiring tomli_w and to preserve
    # the rest of the file's formatting exactly.
    import re

    webapp_toml = webapp_root / "forge.toml"
    toml_text = webapp_toml.read_text(encoding="utf-8")

    # Match a [[forge_modules]] block whose name = "module_name" and strip it.
    # A block spans from [[forge_modules]] up to (but not including) the next
    # section header or end-of-file.
    pattern = (
        r'\n\[\[forge_modules\]\]\n'
        r'(?:[^\[]*?)'                         # block body (no new section)
        r'name\s*=\s*"' + re.escape(module_name) + r'"'
        r'[^\[]*'                              # rest of block body
    )
    toml_text = re.sub(pattern, "", toml_text)
    webapp_toml.write_text(toml_text, encoding="utf-8")

    # Delete namespace dir
    namespace_dir = webapp_root / "forge_modules" / snake
    if namespace_dir.exists():
        shutil.rmtree(str(namespace_dir))

    # Optionally drop dataset files
    if drop_datasets:
        _drop_module_datasets(webapp_root, module_name)

    # Remove ForgeModule record
    mod.remove()

    # Rebuild
    rebuild_result = _rebuild_webapp(webapp_root)

    return {
        "ok": True,
        "name": module_name,
        "rebuild": rebuild_result,
        "restart_required": True,
    }


def _drop_module_datasets(webapp_root: Path, module_name: str) -> None:
    """Delete dataset files declared by a module's MODULE_CONFIG."""
    snake = _name_to_snake(module_name)
    config_var = _default_config_var(module_name)
    module_path, attr = config_var.split(":")
    try:
        m = importlib.import_module(module_path)
        mc = getattr(m, attr)
    except Exception:
        return

    from forge.storage.engine import StorageEngine
    engine = StorageEngine(webapp_root / ".forge")
    try:
        for dataset_id in mc.dataset_ids.values():
            meta = engine.get_dataset(dataset_id)
            if meta and meta.parquet_path:
                parquet_file = engine.data_dir / meta.parquet_path
                if parquet_file.exists():
                    parquet_file.unlink()
            try:
                engine._execute("DELETE FROM datasets WHERE id = ?", [dataset_id])
            except Exception:
                pass
    finally:
        engine.close()


# ── implant ────────────────────────────────────────────────────────────────────

def implant_module(project_id: str, module_name: str) -> dict:
    """
    Fully implant an absorbed module into a managed Forge project.

    Steps:
    1. Verify the module is absorbed.
    2. Find the target project.
    3. Check module not already in project forge.toml.
    4. Locate the project's Python interpreter (.venv).
    5. Pip-install the module package into the project venv
       (editable install if source_path is a live dev directory, else pinned release).
    6. Append [[forge_modules]] block to project forge.toml.
    7. Run forge model build in the project.
    8. Run forge endpoint build in the project.
    9. Sync project metadata in the Suite.
    10. Return result.
    Rolls back forge.toml write if model/endpoint build fails.
    """
    import os
    import subprocess

    ForgeModule = _forge_module_model()

    mod = next((m for m in ForgeModule.all() if m.name == module_name), None)
    if mod is None:
        return {"error": f"Module '{module_name}' is not absorbed"}

    from models.models import ForgeProject
    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}

    root = Path(proj.root_path)
    toml_path = root / "forge.toml"
    if not toml_path.exists():
        return {"error": f"forge.toml not found at {proj.root_path}"}

    # Locate project venv Python interpreter
    project_python = _find_project_python(root)
    if project_python is None:
        return {
            "error": (
                f"No .venv found in {proj.root_path}. "
                "Run 'forge dev serve' once inside the project to bootstrap its venv, "
                "or use 'bash setup.sh' if the project has one."
            )
        }

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib  # type: ignore[no-redef]

    with open(toml_path, "rb") as f:
        raw = tomllib.load(f)

    if any(m.get("name") == module_name for m in raw.get("forge_modules", [])):
        return {"error": f"Module '{module_name}' is already in this project's forge.toml"}

    # ── Step 5: pip install into project venv ──────────────────────────────────
    pip_spec = _resolve_pip_spec(mod)
    _utf8_env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    pip_result = subprocess.run(
        [str(project_python), "-m", "pip", "install"] + pip_spec,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_utf8_env,
    )
    if pip_result.returncode != 0:
        return {
            "error": f"pip install failed:\n{pip_result.stderr.strip()}",
            "pip_spec": pip_spec,
        }

    # ── Step 6: append [[forge_modules]] to project forge.toml ────────────────
    existing_toml = toml_path.read_text(encoding="utf-8")
    block = (
        f'\n[[forge_modules]]\n'
        f'name       = "{mod.name}"\n'
        f'package    = "{mod.package}"\n'
        f'config_var = "{_default_config_var(mod.name)}"\n'
    )
    toml_path.write_text(existing_toml + block, encoding="utf-8")

    # ── Step 7: run module init pipelines to seed datasets with proper schema ──
    init_pipelines_run: list[str] = []
    init_pipeline_errors: list[str] = []
    mc = _load_module_config(module_name)
    if mc and mc.pipelines:
        for pl in mc.pipelines:
            pl_name = pl.display_name
            if "init" in pl_name.lower():
                r = subprocess.run(
                    [str(project_python), "-m", "forge.cli.main", "pipeline", "run", pl_name],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env=_utf8_env,
                )
                if r.returncode == 0:
                    init_pipelines_run.append(pl_name)
                else:
                    init_pipeline_errors.append(
                        f"pipeline run {pl_name}: {(r.stderr or r.stdout or '')[-300:].strip()}"
                    )

    # ── Steps 8–9: forge model build + forge endpoint build in project ─────────
    build_errors = []
    for cmd in (["model", "build"], ["endpoint", "build"]):
        r = subprocess.run(
            [str(project_python), "-m", "forge.cli.main"] + cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_utf8_env,
        )
        if r.returncode != 0:
            build_errors.append(f"forge {' '.join(cmd)}: {r.stderr.strip()}")

    if build_errors:
        # Roll back forge.toml write to leave the project in a consistent state
        toml_path.write_text(existing_toml, encoding="utf-8")
        return {
            "error": "Build failed after pip install; forge.toml has been restored.",
            "details": build_errors,
        }

    # ── Step 10: sync Suite project metadata ──────────────────────────────────
    from forge_suite.operations.projects import sync_project
    sync_project(project_id)

    return {
        "ok": True,
        "module": module_name,
        "project": proj.name,
        "pip_spec": pip_spec,
        "init_pipelines": init_pipelines_run,
        "init_pipeline_errors": init_pipeline_errors,
    }


def _find_project_python(root: Path) -> Path | None:
    """Return the Python interpreter inside the project's .venv, or None."""
    candidates = [
        root / ".venv" / "bin" / "python",
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "python",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_module_config(module_name: str):
    """Load MODULE_CONFIG from the absorbed module copy in forge-webapp."""
    webapp_root = _webapp_root()
    webapp_str = str(webapp_root)
    if webapp_str not in sys.path:
        sys.path.insert(0, webapp_str)
    snake = _name_to_snake(module_name)
    module_path = f"forge_modules.{snake}.module"
    try:
        # Force re-import in case the module was just written to disk
        if module_path in sys.modules:
            del sys.modules[module_path]
        m = importlib.import_module(module_path)
        return getattr(m, "MODULE_CONFIG", None)
    except Exception:
        return None


def _resolve_pip_spec(mod) -> list[str]:
    """
    Return the pip install argument list for a module.

    Uses editable install when source_path is a live dev directory (contains
    forge.toml), otherwise uses a pinned release install.
    """
    src = Path(mod.source_path) if mod.source_path else None
    if src and src.is_dir() and (src / "forge.toml").exists():
        return ["-e", str(src)]
    version = getattr(mod, "version", "dev")
    if version and version != "dev":
        return [f"{mod.package}=={version}"]
    return [mod.package]


# ── internal rebuild ───────────────────────────────────────────────────────────

def _rebuild_webapp(webapp_root: Path) -> dict:
    """Run forge model build + forge endpoint build in forge-webapp."""
    import os
    import subprocess

    _utf8_env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    errors = []
    for cmd in (["model", "build"], ["endpoint", "build"]):
        r = subprocess.run(
            [sys.executable, "-m", "forge.cli.main"] + cmd,
            cwd=str(webapp_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_utf8_env,
        )
        if r.returncode != 0:
            errors.append(f"forge {' '.join(cmd)}: {r.stderr.strip()}")

    return {"ok": len(errors) == 0, "errors": errors}
