"""Endpoint-layer utility: run a registered pipeline from within an endpoint handler."""
from __future__ import annotations

from typing import Any


def run_pipeline(name: str) -> dict[str, Any]:
    """Run a named pipeline synchronously from within an endpoint handler.

    The pipeline must already be registered (i.e. its module was imported at
    server startup).  Returns the run-summary dict produced by PipelineRunner.

    Example — endpoint that writes a skill file then immediately re-indexes::

        from forge.control import action_endpoint, run_pipeline

        @action_endpoint(name="save_skill", ...)
        def save_skill(skill_name: str, body: str) -> dict:
            write_skill(skill_name, {}, body)
            run_pipeline("index_skills")
            return {"ok": True}

    Raises:
        ValueError: if no pipeline with ``name`` is in the registry.
        RuntimeError: if called outside an active endpoint context (no engine).
    """
    from forge.pipeline.decorator import get_registry
    from forge.pipeline.runner import PipelineRunner
    from forge.control.context import get_engine

    engine = get_engine()
    registry = get_registry()
    if name not in registry:
        raise ValueError(
            f"Pipeline '{name}' not found in registry. "
            "Ensure its module is listed under [[pipelines]] in forge.toml."
        )
    defn = registry[name]
    project_root = engine.forge_dir.parent
    runner = PipelineRunner(engine, project_root)
    return runner.run(defn)
