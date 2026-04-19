"""Project config loader — reads forge.toml from the project root."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from pydantic import BaseModel, Field


class DatasetConfig(BaseModel):
    id: str
    name: str
    path: str  # relative path to parquet file inside .forge/data/


class PipelineConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(__import__("uuid").uuid4()))
    name: str
    module: str
    function: str = "run"
    schedule: str | None = None


class ModelConfig(BaseModel):
    name: str
    mode: str  # "snapshot" | "stream"
    module: str
    class_name: str = Field(alias="class")

    model_config = {"populate_by_name": True}


class EndpointRepoConfig(BaseModel):
    name: str
    path: str


class AppConfig(BaseModel):
    name: str
    path: str
    port: int | None = None


class AuthConfig(BaseModel):
    provider: str = "none"  # "none" | future: "clerk", "supabase", ...
    options: dict[str, str] = Field(default_factory=dict)


class DatabaseConfig(BaseModel):
    provider: str = "local"  # "local" | future: "supabase", "postgres", ...
    options: dict[str, str] = Field(default_factory=dict)


class ProjectConfig(BaseModel):
    name: str
    forge_version: str = "0.0.0"
    api_port: int | None = None
    datasets: list[DatasetConfig] = Field(default_factory=list)
    pipelines: list[PipelineConfig] = Field(default_factory=list)
    models: list[ModelConfig] = Field(default_factory=list)
    endpoint_repos: list[EndpointRepoConfig] = Field(default_factory=list)
    apps: list[AppConfig] = Field(default_factory=list)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    @property
    def pipeline_by_name(self) -> dict[str, PipelineConfig]:
        return {p.name: p for p in self.pipelines}

    @property
    def pipeline_by_id(self) -> dict[str, PipelineConfig]:
        return {p.id: p for p in self.pipelines}

    @property
    def model_by_name(self) -> dict[str, ModelConfig]:
        return {m.name: m for m in self.models}


def find_project_root(start: Path | None = None) -> Path:
    """Walk up from start until forge.toml is found."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "forge.toml").exists():
            return candidate
    raise FileNotFoundError(
        "No forge.toml found. Run 'forge init <project-name>' to create a project."
    )


def load_config(project_root: Path | None = None) -> tuple[ProjectConfig, Path]:
    root = project_root or find_project_root()
    config_path = root / "forge.toml"
    with open(config_path, "rb") as f:
        raw: dict[str, Any] = tomllib.load(f)

    project_section = raw.get("project", {})
    config = ProjectConfig(
        name=project_section.get("name", root.name),
        forge_version=project_section.get("forge_version", "0.0.0"),
        api_port=project_section.get("api_port"),
        datasets=[DatasetConfig(**d) for d in raw.get("datasets", [])],
        pipelines=[PipelineConfig(**p) for p in raw.get("pipelines", [])],
        models=[ModelConfig(**m) for m in raw.get("models", [])],
        endpoint_repos=[EndpointRepoConfig(**r) for r in raw.get("endpoint_repos", [])],
        apps=[AppConfig(**a) for a in raw.get("apps", [])],
        auth=AuthConfig(**raw.get("auth", {})),
        database=DatabaseConfig(**raw.get("database", {})),
    )
    return config, root


def save_config(config: ProjectConfig, root: Path) -> None:
    import tomli_w  # type: ignore[import]

    data: dict[str, Any] = {
        "project": {
            "name": config.name,
            "forge_version": config.forge_version,
        }
    }
    if config.datasets:
        data["datasets"] = [d.model_dump() for d in config.datasets]
    if config.pipelines:
        data["pipelines"] = [p.model_dump() for p in config.pipelines]
    if config.models:
        data["models"] = [
            {**m.model_dump(by_alias=True)} for m in config.models
        ]
    if config.endpoint_repos:
        data["endpoint_repos"] = [r.model_dump() for r in config.endpoint_repos]
    if config.apps:
        data["apps"] = [a.model_dump() for a in config.apps]

    with open(root / "forge.toml", "wb") as f:
        import tomli_w
        tomli_w.dump(data, f)
