"""FastAPI application for forge dev serve."""
from __future__ import annotations

import importlib
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

import fastapi
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from forge.config import ProjectConfig
from forge.control.decorator import (
    ActionEndpointDefinition,
    ComputedAttributeEndpointDefinition,
    StreamingEndpointDefinition,
    get_endpoint_registry,
)
from forge.pipeline.runner import PipelineRunner
from forge.scheduler.scheduler import ForgeScheduler
from forge.storage.engine import StorageEngine

log = logging.getLogger(__name__)


def create_app(
    config: ProjectConfig,
    root: Path,
    engine: StorageEngine,
    runner: PipelineRunner,
    scheduler: ForgeScheduler | None = None,
) -> FastAPI:
    app = FastAPI(title=f"Forge — {config.name}", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Datasets ─────────────────────────────────────────────────────────────

    @app.get("/api/datasets")
    def list_datasets() -> list[dict]:
        return [d.to_dict() for d in engine.list_datasets()]

    @app.get("/api/datasets/{dataset_id}")
    def inspect_dataset(dataset_id: str) -> dict:
        meta = engine.get_dataset(dataset_id)
        if meta is None:
            raise HTTPException(404, f"Dataset {dataset_id} not found")
        df = engine.read_dataset(dataset_id)
        return {
            **meta.to_dict(),
            "preview": df.head(20).to_dict(orient="records"),
        }

    # ── Pipelines ────────────────────────────────────────────────────────────

    @app.post("/api/pipelines/{pipeline_id}/run")
    def trigger_pipeline(pipeline_id: str) -> dict:
        pipeline_cfg = config.pipeline_by_id.get(pipeline_id)
        if pipeline_cfg is None:
            raise HTTPException(404, f"Pipeline '{pipeline_id}' not found")
        try:
            defn = runner.load_pipeline(pipeline_cfg.module, pipeline_cfg.function)
            result = runner.run(defn, config_name=pipeline_cfg.display_name)
            return {**result, "pipeline_name": pipeline_cfg.display_name, "pipeline_id": pipeline_id}
        except Exception as exc:
            raise HTTPException(500, str(exc)) from exc

    @app.get("/api/pipelines/{pipeline_id}/history")
    def pipeline_history(pipeline_id: str) -> list[dict]:
        pipeline_cfg = config.pipeline_by_id.get(pipeline_id)
        if pipeline_cfg is None:
            raise HTTPException(404, f"Pipeline '{pipeline_id}' not found")
        return engine.get_pipeline_history(pipeline_cfg.display_name)

    @app.get("/api/pipelines")
    def list_pipelines() -> list[dict]:
        return [
            {"id": p.id, "name": p.display_name, "schedule": p.schedule}
            for p in config.pipelines
        ]

    # ── Endpoints (control layer) ─────────────────────────────────────────────

    @app.get("/api/endpoints")
    def list_endpoints() -> dict:
        registry_path = root / ".forge" / "artifacts" / "endpoints.json"
        if registry_path.exists():
            return json.loads(registry_path.read_text())
        return {}

    @app.post("/endpoints/{endpoint_id}")
    async def call_endpoint(endpoint_id: str, request: Request) -> Any:
        registry = get_endpoint_registry()
        defn = registry.get(endpoint_id)
        if defn is None:
            # Try loading from disk registry (endpoints may not be imported yet)
            raise HTTPException(404, f"Endpoint {endpoint_id} not found")

        body = await request.json()

        from forge.control.context import init_context
        try:
            if isinstance(defn, ActionEndpointDefinition):
                uow = init_context(engine)
                result = defn.func(**body)
                uow.flush()  # atomic write on success; skipped on exception
                return result

            elif isinstance(defn, ComputedAttributeEndpointDefinition):
                # Computed column calls are read-only — init context for model
                # queries but no UoW flush needed
                init_context(engine)
                extra_params = {k: v for k, v in body.items()
                                if k not in ("objects", "primary_keys")}

                from forge.model.definition import _CLASS_REGISTRY
                cls = _CLASS_REGISTRY.get(defn.object_type)
                if cls is None:
                    raise HTTPException(404, f"Model '{defn.object_type}' not registered")
                if "primary_keys" not in body:
                    raise HTTPException(400, "Computed column requests must include 'primary_keys'")
                objects = cls.get_many(body["primary_keys"])

                result = defn.func(objects, **extra_params)
                return {"columns": result}

        except HTTPException:
            raise
        except SystemExit as exc:
            log.error("SystemExit raised inside endpoint %s: %r", endpoint_id, exc)
            raise HTTPException(500, f"Endpoint raised SystemExit({exc.code})") from exc
        except Exception as exc:
            raise HTTPException(500, str(exc)) from exc

    @app.post("/endpoints/{endpoint_id}/stream")
    async def call_streaming_endpoint(endpoint_id: str, request: Request) -> StreamingResponse:
        registry = get_endpoint_registry()
        defn = registry.get(endpoint_id)
        if defn is None or not isinstance(defn, StreamingEndpointDefinition):
            raise HTTPException(404, f"Streaming endpoint {endpoint_id} not found")

        body = await request.json()

        from forge.control.context import init_context
        init_context(engine)

        async def event_stream():
            try:
                for event in defn.func(**body):
                    yield f"event: {event.event}\ndata: {event.data}\n\n"
            except Exception as exc:
                yield f"event: error\ndata: {exc}\n\n"
            finally:
                yield "event: done\ndata: \n\n"

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── Schema artifacts ──────────────────────────────────────────────────────

    @app.get("/api/schemas")
    def list_schemas() -> list[dict]:
        artifacts_dir = root / ".forge" / "artifacts"
        schemas = []
        for f in artifacts_dir.glob("*.schema.json"):
            schemas.append(json.loads(f.read_text()))
        return schemas

    @app.get("/api/schemas/{name}")
    def get_schema(name: str) -> dict:
        artifact_path = root / ".forge" / "artifacts" / f"{name}.schema.json"
        if not artifact_path.exists():
            raise HTTPException(404, f"Schema for '{name}' not found. Run forge model build.")
        return json.loads(artifact_path.read_text())

    # ── Object set queries ────────────────────────────────────────────────────

    @app.get("/api/objects/{object_type}")
    def get_object_set(object_type: str, limit: int = 1000, offset: int = 0) -> dict:
        artifact_path = root / ".forge" / "artifacts" / f"{object_type}.schema.json"
        if not artifact_path.exists():
            raise HTTPException(404, f"Object type '{object_type}' not built. Run forge model build.")
        artifact = json.loads(artifact_path.read_text())
        dataset_id = artifact.get("snapshot_dataset_id") or artifact["backing_dataset_id"]
        df = engine.read_dataset(dataset_id)
        total = len(df)
        rows = df.iloc[offset : offset + limit].to_dict(orient="records")
        return {"total": total, "rows": rows, "schema": artifact}

    # ── Health ────────────────────────────────────────────────────────────────

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "project": config.name}

    return app


def load_model_modules(config: ProjectConfig, root: Path) -> None:
    """Import model modules so @forge_model decorators populate _CLASS_REGISTRY."""
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    for model_cfg in config.models:
        try:
            importlib.import_module(model_cfg.module)
        except Exception as exc:
            log.debug("Could not import model module %s: %s", model_cfg.module, exc)


def load_endpoint_modules(config: ProjectConfig, root: Path) -> None:
    """Import endpoint repo modules so decorators register their endpoints."""
    # Project root must be on sys.path so endpoints can import model classes
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    for repo_cfg in config.endpoint_repos:
        repo_path = (root / repo_cfg.module.replace(".", "/")).resolve()
        _SKIP = {"setup.py", "conftest.py"}
        for py_file in repo_path.rglob("*.py"):
            if py_file.name.startswith("_") or py_file.name in _SKIP:
                continue
            rel = py_file.relative_to(root)
            module_name = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
            try:
                importlib.import_module(module_name)
            except Exception as exc:
                log.debug("Could not import %s: %s", module_name, exc)
