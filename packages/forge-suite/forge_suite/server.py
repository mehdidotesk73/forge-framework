"""Forge Suite combined server — management API + pre-built webapp frontend."""
from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent          # forge_suite/
_WEBAPP_DIR = _PACKAGE_DIR.parent / "forge-webapp"      # packages/forge-suite/forge-webapp/
_WEBAPP_DIST = _PACKAGE_DIR / "webapp_dist"             # forge_suite/webapp_dist/

_scheduler = None  # module-level so stop_scheduler() can reach it


def create_app():
    """Create the Forge Suite FastAPI app: management API + pre-built static frontend."""
    global _scheduler

    from fastapi.staticfiles import StaticFiles
    from forge.config import load_config
    from forge.storage.engine import StorageEngine
    from forge.pipeline.runner import PipelineRunner
    from forge.scheduler.scheduler import ForgeScheduler
    from forge.server.app import (
        create_app as forge_create_app,
        load_endpoint_modules,
        load_model_modules,
    )

    webapp_str = str(_WEBAPP_DIR)
    if webapp_str not in sys.path:
        sys.path.insert(0, webapp_str)

    config, _ = load_config(_WEBAPP_DIR)
    engine = StorageEngine(_WEBAPP_DIR / ".forge")
    runner = PipelineRunner(engine, _WEBAPP_DIR)

    load_model_modules(config, _WEBAPP_DIR)
    load_endpoint_modules(config, _WEBAPP_DIR)

    _scheduler = ForgeScheduler(config, runner, engine)
    api = forge_create_app(config, _WEBAPP_DIR, engine, runner, _scheduler)
    _scheduler.start()

    if _WEBAPP_DIST.exists():
        api.mount("/", StaticFiles(directory=str(_WEBAPP_DIST), html=True), name="webapp")

    return api


def stop_scheduler() -> None:
    if _scheduler is not None:
        _scheduler.stop()
