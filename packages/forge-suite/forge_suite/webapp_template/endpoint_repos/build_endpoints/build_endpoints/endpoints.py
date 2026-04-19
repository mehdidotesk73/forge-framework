"""
Control Layer — build_endpoints
Shells out to the forge CLI and streams stdout/stderr as SSE events.
"""
from __future__ import annotations

from pathlib import Path

from forge.control import streaming_endpoint, StreamEvent

from models.models import ForgeProject

RUN_PIPELINE_ID       = "cccccccc-0005-0000-0000-000000000000"
RUN_MODEL_BUILD_ID    = "cccccccc-0006-0000-0000-000000000000"
RUN_ENDPOINT_BUILD_ID = "cccccccc-0007-0000-0000-000000000000"


def _get_root(project_id: str) -> Path | None:
    proj = ForgeProject.get(project_id)
    return Path(proj.root_path) if proj else None


def _to_stream_events(gen):
    for event, data in gen:
        yield StreamEvent(data=data, event=event)


@streaming_endpoint(
    name="run_pipeline",
    endpoint_id=RUN_PIPELINE_ID,
    description="Run a named pipeline in the active project and stream its output",
    params=[
        {"name": "project_id", "type": "string", "required": True},
        {"name": "pipeline_name", "type": "string", "required": True},
    ],
)
def run_pipeline(project_id: str, pipeline_name: str):
    from forge.operations.build import stream_pipeline_run
    root = _get_root(project_id)
    if root is None:
        yield StreamEvent(data=f"Project {project_id} not found", event="error")
        return
    yield from _to_stream_events(stream_pipeline_run(root, pipeline_name))


@streaming_endpoint(
    name="run_model_build",
    endpoint_id=RUN_MODEL_BUILD_ID,
    description="Run forge model build and stream detailed schema + data summary per model",
    params=[
        {"name": "project_id", "type": "string", "required": True},
    ],
)
def run_model_build(project_id: str):
    from forge.operations.build import stream_model_build
    root = _get_root(project_id)
    if root is None:
        yield StreamEvent(data=f"Project {project_id} not found", event="error")
        return
    yield from _to_stream_events(stream_model_build(root))


@streaming_endpoint(
    name="run_endpoint_build",
    endpoint_id=RUN_ENDPOINT_BUILD_ID,
    description="Run forge endpoint build and stream output",
    params=[
        {"name": "project_id", "type": "string", "required": True},
    ],
)
def run_endpoint_build(project_id: str):
    from forge.operations.build import stream_endpoint_build
    root = _get_root(project_id)
    if root is None:
        yield StreamEvent(data=f"Project {project_id} not found", event="error")
        return
    yield from _to_stream_events(stream_endpoint_build(root))
