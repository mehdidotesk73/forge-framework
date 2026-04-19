"""SUITE visualization operations — DAG, layer lineage, project health."""
from __future__ import annotations

import json
from pathlib import Path


def _active_project():
    from models.models import ForgeProject
    for p in ForgeProject.all():
        if p.is_active == "true":
            return p
    return None


def pipeline_dag(project_id: str = "") -> dict:
    from models.models import Pipeline

    if not project_id:
        proj = _active_project()
        if proj is None:
            return {"nodes": [], "edges": []}
        project_id = proj.id

    pipelines = [p for p in Pipeline.all() if p.project_id == project_id]

    nodes: list[dict] = []
    edges: list[dict] = []
    seen_datasets: set[str] = set()

    for pl in pipelines:
        pl_node_id = f"pipeline:{pl.name}"
        nodes.append({"id": pl_node_id, "kind": "pipeline", "label": pl.name, "schedule": pl.schedule})

        input_ids = json.loads(pl.input_datasets or "[]")
        output_ids = json.loads(pl.output_datasets or "[]")

        for ds_id in input_ids:
            if ds_id not in seen_datasets:
                nodes.append({"id": f"dataset:{ds_id}", "kind": "dataset", "label": ds_id[:8]})
                seen_datasets.add(ds_id)
            edges.append({"source": f"dataset:{ds_id}", "target": pl_node_id})

        for ds_id in output_ids:
            if ds_id not in seen_datasets:
                nodes.append({"id": f"dataset:{ds_id}", "kind": "dataset", "label": ds_id[:8]})
                seen_datasets.add(ds_id)
            edges.append({"source": pl_node_id, "target": f"dataset:{ds_id}"})

    return {"nodes": nodes, "edges": edges}


def layer_lineage(project_id: str = "") -> dict:
    from models.models import Endpoint, EndpointRepo, ObjectType, Pipeline

    if not project_id:
        proj = _active_project()
        if proj is None:
            return {"layers": []}
        project_id = proj.id

    pipelines = [p for p in Pipeline.all() if p.project_id == project_id]
    obj_types = [o for o in ObjectType.all() if o.project_id == project_id]
    repos = [r for r in EndpointRepo.all() if r.project_id == project_id]
    endpoints = [e for e in Endpoint.all() if e.project_id == project_id]

    layers = [
        {
            "name": "Pipeline",
            "color": "#5ba3d9",
            "items": [{"label": p.name, "detail": p.module} for p in pipelines],
        },
        {
            "name": "Model",
            "color": "#8b6cc1",
            "items": [{"label": o.name, "detail": o.mode} for o in obj_types],
        },
        {
            "name": "Control",
            "color": "#e8833a",
            "items": [{"label": e.name, "detail": e.kind} for e in endpoints],
        },
        {
            "name": "View",
            "color": "#4caf7c",
            "items": [{"label": r.name, "detail": f"{r.endpoint_count} endpoints"} for r in repos],
        },
    ]

    return {"layers": layers, "project_id": project_id}


def project_health(project_id: str = "") -> dict:
    from models.models import Endpoint, EndpointRepo, ForgeProject, ObjectType, Pipeline, PipelineRun

    if not project_id:
        proj = _active_project()
        if proj is None:
            return {"status": "no_project"}
        project_id = proj.id

    proj = ForgeProject.get(project_id)
    if proj is None:
        return {"status": "not_found"}

    root = Path(proj.root_path)
    artifacts_dir = root / ".forge" / "artifacts"

    pipelines = [p for p in Pipeline.all() if p.project_id == project_id]
    obj_types = [o for o in ObjectType.all() if o.project_id == project_id]
    repos = [r for r in EndpointRepo.all() if r.project_id == project_id]
    endpoints = [e for e in Endpoint.all() if e.project_id == project_id]
    runs = [r for r in PipelineRun.all() if r.project_id == project_id]

    built_models = [o for o in obj_types if o.built_at]
    endpoints_built = artifacts_dir.joinpath("endpoints.json").exists()
    last_run = max((r.started_at for r in runs), default="") if runs else ""
    failed_runs = [r for r in runs if r.status == "error"]

    status = "ok"
    if len(built_models) < len(obj_types):
        status = "warn"
    if failed_runs:
        status = "warn"

    return {
        "status": status,
        "project_id": project_id,
        "project_name": proj.name,
        "pipeline_count": len(pipelines),
        "model_count": len(obj_types),
        "models_built": len(built_models),
        "repo_count": len(repos),
        "endpoint_count": len(endpoints),
        "endpoints_built": endpoints_built,
        "run_count": len(runs),
        "last_run": last_run,
        "failed_runs": len(failed_runs),
    }
