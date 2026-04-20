"""SUITE app operations — run, stop, ping, and open project apps."""
from __future__ import annotations

import json
from pathlib import Path


def _find_free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _run_ports_path(root: Path) -> Path:
    return root / ".forge" / "run_ports.json"


def _load_run_ports(root: Path) -> dict:
    p = _run_ports_path(root)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def _save_run_ports(root: Path, data: dict) -> None:
    p = _run_ports_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))


def _is_pid_alive(pid: int) -> bool:
    import os
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _get_app(project_id: str, app_name: str):
    from models.models import App
    return next((a for a in App.all() if a.project_id == project_id and a.name == app_name), None)


def _get_project(project_id: str):
    from models.models import ForgeProject
    return ForgeProject.get(project_id)


def _ensure_api_running(root: Path) -> int:
    """Start the project API backend if not alive; return the live port."""
    import shutil
    import subprocess

    run_ports = _load_run_ports(root)
    api_port = run_ports.get("api_port")
    api_pid = run_ports.get("api_pid")

    if api_port and api_pid and _is_pid_alive(api_pid):
        return api_port

    api_port = _find_free_port()
    forge_bin = str(root / ".venv" / "bin" / "forge")
    if not _Path_exists(forge_bin):
        forge_bin = shutil.which("forge") or "forge"
    with open(root / ".forge-api.log", "w") as api_log:
        api_proc = subprocess.Popen(
            [forge_bin, "dev", "serve", "--port", str(api_port)],
            cwd=str(root),
            start_new_session=True,
            stdout=api_log,
            stderr=api_log,
        )
    run_ports["api_port"] = api_port
    run_ports["api_pid"] = api_proc.pid
    _save_run_ports(root, run_ports)
    return api_port


def _Path_exists(p: str) -> bool:
    return Path(p).exists()


def _ensure_suite_root_file(app_dir: Path) -> None:
    """Write .forge/suite_root into the app dir so vite.config.ts can resolve @forge-suite/ts."""
    suite_root_file = app_dir / ".forge" / "suite_root"
    if suite_root_file.exists():
        return
    from forge.operations.projects import resolve_suite_root
    suite_root = resolve_suite_root()
    if suite_root is None:
        try:
            import forge_suite
            candidate = Path(forge_suite.__file__).resolve().parent.parent.parent.parent.parent
            if (candidate / "forge-framework" / "packages" / "forge-ts").exists():
                suite_root = candidate
        except Exception:
            pass
    if suite_root is not None:
        suite_root_file.parent.mkdir(parents=True, exist_ok=True)
        suite_root_file.write_text(str(suite_root))


def run_app(project_id: str, app_name: str) -> dict:
    import os
    import shutil
    import subprocess
    import time

    proj = _get_project(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}

    app_record = _get_app(project_id, app_name)
    if app_record is None:
        return {"error": f"App '{app_name}' not found"}

    root = Path(proj.root_path)
    app_dir = (root / app_record.path).resolve()
    if not app_dir.exists():
        return {"error": f"App directory not found: {app_dir}"}

    npm = shutil.which("npm")
    if npm is None:
        return {"error": "npm not found in PATH"}

    if not (app_dir / "node_modules").exists():
        result = subprocess.run(
            [npm, "install"], cwd=str(app_dir), capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            return {"error": f"npm install failed: {result.stderr[:500]}"}

    _ensure_suite_root_file(app_dir)
    api_port = _ensure_api_running(root)
    run_ports = _load_run_ports(root)

    # Start Vite frontend — pass api_port via env so vite.config.ts proxy targets it
    frontend_port = _find_free_port()
    log_file = app_dir / ".forge-dev.log"
    child_env = {**os.environ, "VITE_API_PORT": str(api_port)}
    with open(log_file, "w") as log:
        proc = subprocess.Popen(
            [npm, "run", "dev", "--", "--port", str(frontend_port)],
            cwd=str(app_dir),
            env=child_env,
            start_new_session=True,
            stdout=log,
            stderr=log,
        )

    time.sleep(0.8)
    if proc.poll() is not None:
        tail = log_file.read_text(encoding="utf-8", errors="replace")[-800:] if log_file.exists() else ""
        return {"error": f"Dev server exited immediately.\n{tail}"}

    run_ports.setdefault("apps", {})[app_name] = {"port": frontend_port, "pid": proc.pid}
    _save_run_ports(root, run_ports)

    return {"ok": True, "url": f"http://localhost:{frontend_port}", "port": frontend_port, "api_port": api_port}


def ping_app(project_id: str, app_name: str) -> dict:
    import urllib.request

    proj = _get_project(project_id)
    if proj is None:
        return {"live": False}

    root = Path(proj.root_path)
    run_ports = _load_run_ports(root)
    app_state = run_ports.get("apps", {}).get(app_name, {})
    port = app_state.get("port")
    if not port:
        return {"live": False}

    try:
        urllib.request.urlopen(f"http://localhost:{int(port)}/", timeout=1)
        return {"live": True, "port": port}
    except Exception:
        return {"live": False, "port": port}


def stop_app(project_id: str, app_name: str) -> dict:
    import subprocess

    proj = _get_project(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}

    root = Path(proj.root_path)
    run_ports = _load_run_ports(root)

    app_state = run_ports.get("apps", {}).get(app_name)
    if not app_state:
        return {"ok": True, "stopped": False, "message": f"App '{app_name}' is not running"}

    killed = []

    # Kill frontend process and any stray process on its port
    frontend_pid = app_state.get("pid")
    frontend_port = app_state.get("port")
    if frontend_pid:
        subprocess.run(["kill", str(frontend_pid)], capture_output=True)
        killed.append(frontend_pid)
    if frontend_port:
        result = subprocess.run(["lsof", "-ti", f"tcp:{frontend_port}"], capture_output=True, text=True)
        for pid in result.stdout.strip().splitlines():
            subprocess.run(["kill", pid.strip()], capture_output=True)

    del run_ports["apps"][app_name]

    # Kill API only when no other apps from this project are still running
    if not run_ports["apps"]:
        api_pid = run_ports.get("api_pid")
        if api_pid:
            subprocess.run(["kill", str(api_pid)], capture_output=True)
            killed.append(api_pid)
        run_ports.pop("api_port", None)
        run_ports.pop("api_pid", None)

    _save_run_ports(root, run_ports)
    return {"ok": True, "stopped": True, "killed_pids": killed}


def open_app(project_id: str, app_name: str) -> dict:
    import subprocess
    import shutil

    proj = _get_project(project_id)
    if proj is None:
        return {"error": f"Project {project_id} not found"}

    root = Path(proj.root_path)
    run_ports = _load_run_ports(root)
    port = run_ports.get("apps", {}).get(app_name, {}).get("port")
    if not port:
        return {"error": f"App '{app_name}' is not running"}

    url = f"http://localhost:{port}"
    opener = shutil.which("open") or shutil.which("xdg-open")
    if opener:
        subprocess.Popen([opener, url])
    return {"ok": True, "url": url}
