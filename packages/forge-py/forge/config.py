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
    display_name: str
    module: str
    function: str = "run"
    schedule: str | None = None


class ModelConfig(BaseModel):
    class_name: str
    module: str
    mode: str  # "snapshot" | "stream"
    display_name: str | None = None

    @property
    def name(self) -> str:
        """Display name, falling back to class name."""
        return self.display_name or self.class_name


class EndpointRepoConfig(BaseModel):
    module: str  # dotted module path, e.g. "endpoint_repos.student_endpoints"


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
        return {p.display_name: p for p in self.pipelines}

    @property
    def pipeline_by_id(self) -> dict[str, PipelineConfig]:
        return {p.id: p for p in self.pipelines}

    @property
    def model_by_class_name(self) -> dict[str, ModelConfig]:
        return {m.class_name: m for m in self.models}

    @property
    def model_by_name(self) -> dict[str, ModelConfig]:
        """Alias for model_by_class_name."""
        return {m.class_name: m for m in self.models}


# ── normalizers: accept both old and new field names ────────────────────────

def _normalize_pipeline(p: dict) -> dict:
    out = dict(p)
    if "display_name" not in out and "name" in out:
        out["display_name"] = out.pop("name")
    return out


def _normalize_model(m: dict) -> dict:
    out = dict(m)
    # Old schema had both name and class (alias); new schema has class_name only
    if "class_name" not in out:
        if "class" in out:
            out["class_name"] = out.pop("class")
        elif "name" in out:
            out["class_name"] = out["name"]
    out.pop("name", None)   # was always redundant with class/class_name
    out.pop("class", None)  # already consumed above
    return out


def _normalize_endpoint_repo(r: dict) -> dict:
    out = dict(r)
    if "module" not in out:
        # Old schema: name + path — derive module from path
        path = out.pop("path", "").lstrip("./").rstrip("/")
        out["module"] = path.replace("/", ".") if path else out.get("name", "")
    out.pop("name", None)
    out.pop("path", None)
    return out


def _normalize_app(a: dict) -> dict:
    out = dict(a)
    out.pop("id", None)  # was redundant with name
    return out


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
        pipelines=[PipelineConfig(**_normalize_pipeline(p)) for p in raw.get("pipelines", [])],
        models=[ModelConfig(**_normalize_model(m)) for m in raw.get("models", [])],
        endpoint_repos=[EndpointRepoConfig(**_normalize_endpoint_repo(r)) for r in raw.get("endpoint_repos", [])],
        apps=[AppConfig(**_normalize_app(a)) for a in raw.get("apps", [])],
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
        data["pipelines"] = [
            {k: v for k, v in p.model_dump().items() if v is not None}
            for p in config.pipelines
        ]
    if config.models:
        data["models"] = [
            {k: v for k, v in m.model_dump().items() if v is not None}
            for m in config.models
        ]
    if config.endpoint_repos:
        data["endpoint_repos"] = [{"module": r.module} for r in config.endpoint_repos]
    if config.apps:
        data["apps"] = [
            {k: v for k, v in a.model_dump().items() if v is not None}
            for a in config.apps
        ]

    with open(root / "forge.toml", "wb") as f:
        tomli_w.dump(data, f)
