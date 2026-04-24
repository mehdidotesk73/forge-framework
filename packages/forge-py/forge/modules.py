"""Forge module system — types used by module.py artifacts and config merging."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelEntry:
    class_name: str
    module: str
    mode: str  # "snapshot" | "stream"
    display_name: str | None = None


@dataclass
class EndpointRepoEntry:
    module: str


@dataclass
class PipelineEntry:
    id: str
    display_name: str
    module: str
    function: str = "run"
    schedule: str | None = None


@dataclass
class ModuleConfig:
    name: str
    models: list[ModelEntry] = field(default_factory=list)
    endpoint_repos: list[EndpointRepoEntry] = field(default_factory=list)
    pipelines: list[PipelineEntry] = field(default_factory=list)
    dataset_ids: dict[str, str] = field(default_factory=dict)
