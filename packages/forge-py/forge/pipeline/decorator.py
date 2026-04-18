"""@pipeline decorator and associated types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ForgeInput:
    dataset_id: str


@dataclass
class ForgeOutput:
    dataset_id: str


@dataclass
class PipelineDefinition:
    name: str
    func: Callable
    inputs: dict[str, ForgeInput]
    outputs: dict[str, ForgeOutput]
    schedule: str | None = None
    module: str = ""


# Registry populated by @pipeline decorators when modules are imported
_PIPELINE_REGISTRY: dict[str, PipelineDefinition] = {}


def pipeline(
    inputs: dict[str, ForgeInput],
    outputs: dict[str, ForgeOutput],
    schedule: str | None = None,
    name: str | None = None,
) -> Callable:
    """Decorator that registers a function as a Forge pipeline."""

    def decorator(func: Callable) -> Callable:
        pipeline_name = name or func.__name__
        defn = PipelineDefinition(
            name=pipeline_name,
            func=func,
            inputs=inputs,
            outputs=outputs,
            schedule=schedule,
            module=func.__module__,
        )
        _PIPELINE_REGISTRY[pipeline_name] = defn
        func._forge_pipeline = defn  # type: ignore[attr-defined]
        return func

    return decorator


def get_registry() -> dict[str, PipelineDefinition]:
    return _PIPELINE_REGISTRY
