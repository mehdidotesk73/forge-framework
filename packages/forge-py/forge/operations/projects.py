"""CORE project operations — work on a project root Path, no model-layer imports."""
from __future__ import annotations

import ast
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# ── Helpers ────────────────────────────────────────────────────────────────────

def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_toml(path: Path) -> dict:
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    with open(path, "rb") as f:
        return tomllib.load(f)


def resolve_suite_root() -> Path | None:
    """Read FORGE_SUITE_ROOT from ~/.forge/env."""
    env_file = Path.home() / ".forge" / "env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("FORGE_SUITE_ROOT="):
                val = line.split("=", 1)[1].strip()
                if val:
                    return Path(val)
    return None


def parse_pipeline_io_from_source(filepath: Path) -> tuple[list[str], list[str]]:
    """Extract ForgeInput/ForgeOutput dataset IDs from a pipeline source file via AST."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return [], []

    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                    constants[target.id] = str(node.value.value)

    def resolve_arg(node: ast.expr) -> str:
        if isinstance(node, ast.Constant):
            return str(node.value)
        if isinstance(node, ast.Name):
            return constants.get(node.id, "")
        return ""

    input_ids: list[str] = []
    output_ids: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg in ("inputs", "outputs"):
            if isinstance(node.value, ast.Dict):
                for val in node.value.values:
                    if isinstance(val, ast.Call) and isinstance(val.func, ast.Name):
                        if val.func.id == "ForgeInput" and val.args:
                            uid = resolve_arg(val.args[0])
                            if uid:
                                input_ids.append(uid)
                        elif val.func.id == "ForgeOutput" and val.args:
                            uid = resolve_arg(val.args[0])
                            if uid:
                                output_ids.append(uid)
    return input_ids, output_ids


def try_load_pipeline_io(root: Path, module: str, function: str) -> tuple[list[str], list[str]]:
    """Import a pipeline module and read its input/output dataset IDs.

    Falls back to AST parsing when the import fails (e.g. missing project
    dependencies not present in the forge-suite venv).
    """
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    try:
        import importlib
        if module in sys.modules:
            mod = importlib.reload(sys.modules[module])
        else:
            mod = importlib.import_module(module)
        func = getattr(mod, function, None)
        if func is None:
            return [], []
        defn = getattr(func, "_forge_pipeline", None)
        if defn is None:
            return [], []
        inputs = list(defn.inputs.values()) if defn.inputs else []
        outputs = list(defn.outputs.values()) if defn.outputs else []
        input_ids = [getattr(i, "dataset_id", "") for i in inputs]
        output_ids = [getattr(o, "dataset_id", "") for o in outputs]
        return input_ids, output_ids
    except Exception:
        module_file = root / module.replace(".", "/")
        for candidate in (module_file.with_suffix(".py"), module_file / "__init__.py"):
            if candidate.exists():
                return parse_pipeline_io_from_source(candidate)
        return [], []


# ── IDE config ──────────────────────────────────────────────────────────────────

def write_ide_config(root: Path, suite_root: Path | None = None) -> None:
    """Write VS Code and Pyright config into a project root (and its pipelines/ subdir).

    VS Code's Pylance only reads pyrightconfig.json from the workspace root — it
    does not walk up past it. Writing the config to pipelines/ as well means
    import resolution works whether the user opens the full project or just the
    pipelines subfolder.

    suite_root defaults to the value of FORGE_SUITE_ROOT in ~/.forge/env, then
    falls back to detecting forge-framework from this file's own location.
    """
    if suite_root is None:
        suite_root = resolve_suite_root()

    if suite_root is not None:
        # forge-suite layout: suite_root/.venv and suite_root/forge-framework/
        venv_parent = suite_root
        forge_py_path = suite_root / "forge-framework" / "packages" / "forge-py"
    else:
        # Standalone forge-framework checkout: .venv and packages/forge-py next to each other
        forge_framework_root = Path(__file__).resolve().parents[4]
        venv_parent = forge_framework_root
        forge_py_path = forge_framework_root / "packages" / "forge-py"

    import sys as _sys
    venv_python = (
        venv_parent / ".venv" / "Scripts" / "python.exe"
        if _sys.platform == "win32"
        else venv_parent / ".venv" / "bin" / "python"
    )
    pyright_cfg = json.dumps({
        "venvPath": str(venv_parent),
        "venv": ".venv",
        "extraPaths": [str(forge_py_path)],
    }, indent=2)

    vscode_dir = root / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    (vscode_dir / "settings.json").write_text(
        json.dumps({"python.defaultInterpreterPath": str(venv_python)}, indent=2)
    )
    (root / "pyrightconfig.json").write_text(pyright_cfg)

    pipelines_dir = root / "pipelines"
    if pipelines_dir.exists():
        (pipelines_dir / "pyrightconfig.json").write_text(pyright_cfg)


# ── Project scaffolding ────────────────────────────────────────────────────────

_FORGE_TOML_TEMPLATE = """\
[project]
name = "{name}"
forge_version = "{forge_version}"
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

_REQUIREMENTS_TXT = """\
# Core framework — required for forge dev serve, endpoint code, and model code.
# Add your project-specific dependencies below.
forge-framework=={version}
"""

_SETUP_SH = """\
#!/usr/bin/env bash
# setup.sh — Create the project venv and install dependencies.
# Run this once after cloning, or after adding new packages to requirements.txt.
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
# shellcheck disable=SC1091
if [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate   # Windows / Git Bash
else
    source .venv/bin/activate
fi
pip install -q -r requirements.txt
echo "Setup complete. Activate the venv with:"
echo "  source .venv/bin/activate     (Mac/Linux)"
echo "  .venv\\\\Scripts\\\\activate       (Windows)"
"""

_FORGE_DIR_README = """\
# .forge/

Managed by the Forge framework. Contains build outputs and runtime data for this project.

| Path | What it is | Commit? |
|------|-----------|---------|
| `artifacts/` | Schema JSON + endpoints.json — generated by `forge model build` / `forge endpoint build`. Read at runtime. | Yes |
| `generated/python/` | Python SDKs generated from your models — imported by endpoint code. | Yes |
| `generated/typescript/` | TypeScript SDKs — imported by your React app. | Yes |
| `migration_state.json` | Records which Forge framework upgrades have been applied. | Yes |
| `data/` | Parquet dataset files. Gitignored — regenerated by running your pipelines. | No |
| `forge.duckdb` | DuckDB catalog index. Gitignored — rebuilt from Parquet files automatically. | No |

## If you delete this directory

Run `forge model build` and `forge endpoint build` to regenerate artifacts and SDKs.
Data (Parquet files) will be empty until you run your pipelines again.
"""

_FORGE_SUITE_DIR_README = """\
# .forge-suite/

Created and managed by Forge Suite. Contains machine-local runtime state only.

This directory is gitignored. It is safe to delete — Forge Suite will recreate it
the next time you open or run this project.

| File | What it is |
|------|-----------|
| `run_ports.json` | Ports and PIDs of the running project backend and app servers. |
| `suite_root` | Absolute path to the Forge Suite installation on this machine. Used by vite.config.ts to resolve @forge-suite/ts during development. |

## If you delete this directory

Forge Suite will recreate it the next time you start the project. No data is lost.
You may need to restart the project backend and apps from the Forge Suite UI.
"""


_WINDOWS_ONLY_PACKAGES = {"pywin32", "pywin32-ctypes", "pywinpty", "pypiwin32"}


def _read_requirements(req_file: Path) -> str:
    """Read requirements.txt handling UTF-8 and UTF-16 encodings."""
    raw = req_file.read_bytes()
    for enc in ("utf-8-sig", "utf-16", "utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, Exception):
            continue
    return raw.decode("utf-8", errors="replace")


def _filter_requirements(text: str, platform: str) -> str:
    """Strip platform-incompatible packages from requirements text."""
    if platform == "win32":
        return text
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            lines.append(line)
            continue
        # Extract package name (before any version specifier or extras)
        pkg_name = stripped.split(";")[0].split("==")[0].split(">=")[0].split("<=")[0]
        pkg_name = pkg_name.split("[")[0].strip().lower().replace("_", "-")
        if pkg_name in _WINDOWS_ONLY_PACKAGES:
            lines.append(f"# skipped (Windows-only): {line}")
            continue
        lines.append(line)
    return "\n".join(lines)


def bootstrap_project_venv(root: Path) -> dict:
    """Create .venv and install requirements.txt into it. Returns status dict."""
    import subprocess
    import sys as _sys
    import tempfile

    venv_dir = root / ".venv"
    if not venv_dir.exists():
        try:
            subprocess.run(
                [_sys.executable, "-m", "venv", str(venv_dir)],
                check=True, capture_output=True, timeout=60,
            )
        except Exception as exc:
            return {"venv": False, "installed": False, "error": str(exc)}

    pip_bin = venv_dir / ("Scripts/pip.exe" if _sys.platform == "win32" else "bin/pip")
    req_file = root / "requirements.txt"
    if not req_file.exists():
        return {"venv": True, "installed": False, "error": "requirements.txt not found"}

    req_text = _filter_requirements(_read_requirements(req_file), _sys.platform)

    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tmp:
            tmp.write(req_text)
            tmp_path = tmp.name
        subprocess.run(
            [str(pip_bin), "install", "-q", "-r", tmp_path],
            check=True, capture_output=True, timeout=300,
        )
    except Exception as exc:
        return {"venv": True, "installed": False, "error": str(exc)}
    finally:
        import os as _os
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass

    return {"venv": True, "installed": True}


def bootstrap_project_runtime(root: Path) -> dict:
    """Bootstrap a freshly cloned project: create venv, install deps, run init pipelines, build artifacts.

    Safe to call on any project — each step is skipped if already done.
    Returns a status dict with keys: venv, installed, init_pipelines, model_build, endpoint_build, errors.
    """
    import subprocess
    import sys as _sys

    errors: list[str] = []

    # Step 1: venv + pip install
    venv_result = bootstrap_project_venv(root)
    if not venv_result.get("venv"):
        return {**venv_result, "init_pipelines": [], "model_build": False, "endpoint_build": False, "errors": errors}
    if venv_result.get("error"):
        errors.append(f"pip install: {venv_result['error']}")

    # Resolve forge binary inside project venv
    if _sys.platform == "win32":
        forge_bin = root / ".venv" / "Scripts" / "forge.exe"
    else:
        forge_bin = root / ".venv" / "bin" / "forge"
    if not forge_bin.exists():
        import shutil
        fallback = shutil.which("forge")
        forge_bin_str = fallback or "forge"
    else:
        forge_bin_str = str(forge_bin)

    _run_env = {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    import os as _os
    _env = {**_os.environ, **_run_env}

    def _run(args: list[str], timeout: int = 120) -> tuple[bool, str]:
        try:
            r = subprocess.run(
                [forge_bin_str, *args], cwd=str(root), env=_env,
                capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
            )
            if r.returncode != 0:
                return False, (r.stderr or r.stdout or "")[-500:]
            return True, ""
        except Exception as exc:
            return False, str(exc)

    # Step 2: run init pipelines (any pipeline whose display_name contains "init")
    ran_pipelines: list[str] = []
    try:
        cfg = read_toml(root / "forge.toml")
        for p in cfg.get("pipelines", []):
            name = p.get("display_name") or p.get("name", "")
            if "init" in name.lower():
                ok, err = _run(["pipeline", "run", name], timeout=120)
                if ok:
                    ran_pipelines.append(name)
                else:
                    errors.append(f"pipeline run {name}: {err}")
    except Exception as exc:
        errors.append(f"init pipelines: {exc}")

    # Step 3: forge model build
    model_ok, model_err = _run(["model", "build"], timeout=180)
    if not model_ok:
        errors.append(f"model build: {model_err}")

    # Step 4: forge endpoint build
    endpoint_ok, endpoint_err = _run(["endpoint", "build"], timeout=60)
    if not endpoint_ok:
        errors.append(f"endpoint build: {endpoint_err}")

    return {
        "venv": venv_result.get("venv", False),
        "installed": venv_result.get("installed", False),
        "init_pipelines": ran_pipelines,
        "model_build": model_ok,
        "endpoint_build": endpoint_ok,
        "errors": errors,
    }


def create_project(root: Path, suite_root: Path | None = None) -> None:
    """Scaffold a new Forge project directory structure."""
    from forge.version import __version__

    dirs = [
        root,
        root / ".forge" / "data",
        root / ".forge" / "artifacts",
        root / ".forge" / "generated" / "python",
        root / ".forge" / "generated" / "typescript",
        root / ".forge-suite",
        root / "pipelines",
        root / "models",
        root / "endpoint_repos",
        root / "apps",
        root / "data",
        root / "files",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    (root / "forge.toml").write_text(_FORGE_TOML_TEMPLATE.format(name=root.name, forge_version=__version__))
    (root / ".gitignore").write_text(_GITIGNORE)
    (root / "requirements.txt").write_text(_REQUIREMENTS_TXT.format(version=__version__))
    (root / "setup.sh").write_text(_SETUP_SH)
    (root / ".forge" / "README.md").write_text(_FORGE_DIR_README)
    (root / ".forge-suite" / "README.md").write_text(_FORGE_SUITE_DIR_README)
    (root / "pipelines" / "__init__.py").write_text("")
    (root / "models" / "__init__.py").write_text("")
    (root / ".forge" / "migration_state.json").write_text(
        json.dumps({"forge_version": __version__})
    )
    write_ide_config(root, suite_root=suite_root)


# ── Toml → structured data (no model writes) ──────────────────────────────────

def sync_from_toml_raw(root: Path, cfg: dict | None = None) -> dict:
    """Parse forge.toml and disk artifacts; return structured project data.

    Returns a dict with keys: pipelines, models, endpoint_repos, apps.
    Does NOT write any model records — callers decide what to persist.
    """
    if cfg is None:
        cfg = read_toml(root / "forge.toml")

    artifacts_dir = root / ".forge" / "artifacts"

    # Pipelines
    pipelines = []
    for p in cfg.get("pipelines", []):
        module = p.get("module", "")
        func = p.get("function", "run")
        module_file = root / module.replace(".", "/")
        if not (module_file.with_suffix(".py").exists() or (module_file / "__init__.py").exists()):
            continue
        input_ids, output_ids = try_load_pipeline_io(root, module, func)
        pipelines.append({
            "id": p.get("id", ""),
            "name": p.get("display_name") or p.get("name", ""),
            "module": module,
            "function": func,
            "schedule": p.get("schedule", ""),
            "input_ids": input_ids,
            "output_ids": output_ids,
        })

    # Models
    models = []
    for m in cfg.get("models", []):
        obj_name = m.get("class_name") or m.get("name", "")
        schema_path = artifacts_dir / f"{obj_name}.schema.json"
        field_count = ""
        built_at = ""
        backing_dataset_id = ""
        backing_dataset_name = ""
        snapshot_dataset_id = ""
        if schema_path.exists():
            schema = json.loads(schema_path.read_text())
            field_count = str(len(schema.get("fields", {})))
            built_at = schema.get("built_at", "")
            backing_dataset_id = schema.get("backing_dataset_id", "")
            backing_dataset_name = schema.get("backing_dataset_name", "")
            snapshot_dataset_id = schema.get("snapshot_dataset_id", "")
        models.append({
            "name": obj_name,
            "mode": m.get("mode", "snapshot"),
            "module": m.get("module", ""),
            "backing_dataset_id": backing_dataset_id,
            "backing_dataset_name": backing_dataset_name,
            "snapshot_dataset_id": snapshot_dataset_id,
            "field_count": field_count,
            "built_at": built_at,
        })

    # Endpoint repos + endpoints from artifacts
    endpoints_registry: dict = {}
    endpoints_json = artifacts_dir / "endpoints.json"
    if endpoints_json.exists():
        endpoints_registry = json.loads(endpoints_json.read_text())

    endpoint_repos = []
    for repo in cfg.get("endpoint_repos", []):
        repo_module = repo.get("module", "")
        # Derive display name: last segment of module, or fall back to old "name" field
        repo_name = repo_module.split(".")[-1] if repo_module else repo.get("name", "")
        eps_in_repo = [
            e for e in endpoints_registry.values()
            if e.get("repo") == repo_module or e.get("repo") == repo_name
        ]
        endpoint_repos.append({
            "name": repo_name,
            "module": repo_module,
            "path": repo_module.replace(".", "/") if repo_module else "",
            "endpoints": eps_in_repo,
        })

    # Apps
    apps = []
    for app in cfg.get("apps", []):
        apps.append({
            "name": app.get("name", ""),
            "app_id": app.get("name", ""),
            "path": app.get("path", ""),
            "port": app.get("port", ""),
        })

    return {
        "pipelines": pipelines,
        "models": models,
        "endpoint_repos": endpoint_repos,
        "apps": apps,
    }
