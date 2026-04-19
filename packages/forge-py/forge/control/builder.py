"""forge endpoint build — walks endpoint repos, emits call form descriptor registry."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

from forge.config import EndpointRepoConfig, ProjectConfig
from forge.control.decorator import (
    ActionEndpointDefinition,
    ComputedColumnEndpointDefinition,
    StreamingEndpointDefinition,
    ParamSchema,
    get_endpoint_registry,
)


class EndpointBuilder:
    def __init__(self, config: ProjectConfig, root: Path) -> None:
        self.config = config
        self.root = root
        self.artifacts_dir = root / ".forge" / "artifacts"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def build_all(self) -> dict[str, Any]:
        registry: dict[str, Any] = {}
        for repo_cfg in self.config.endpoint_repos:
            repo_descriptors = self.build_repo(repo_cfg)
            registry.update(repo_descriptors)
        self._write_registry(registry)
        return registry

    def build_repo(self, repo_cfg: EndpointRepoConfig) -> dict[str, Any]:
        repo_path = (self.root / repo_cfg.path).resolve()
        # Project root must be on path so endpoint modules can import model classes
        if str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))
        if str(repo_path) not in sys.path:
            sys.path.insert(0, str(repo_path))

        # Import all Python modules in the repo to trigger decorator registration
        self._import_repo_modules(repo_path)

        descriptors: dict[str, Any] = {}
        registry = get_endpoint_registry()
        for ep_id, defn in registry.items():
            if defn.module.startswith(repo_cfg.name) or self._module_in_repo(defn.module, repo_path):
                descriptor = self._build_descriptor(defn, repo_cfg.name)
                descriptors[ep_id] = descriptor

        return descriptors

    def _import_repo_modules(self, repo_path: Path) -> None:
        _SKIP = {"setup.py", "conftest.py"}
        for py_file in repo_path.rglob("*.py"):
            if py_file.name.startswith("_") or py_file.name in _SKIP:
                continue
            rel = py_file.relative_to(repo_path)
            module_name = str(rel.with_suffix("")).replace("/", ".").replace("\\", ".")
            try:
                importlib.import_module(module_name)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).debug("Could not import %s: %s", module_name, exc)

    def _module_in_repo(self, module: str, repo_path: Path) -> bool:
        # Check if the module file lives under repo_path
        mod_file = module.replace(".", "/") + ".py"
        return (repo_path / mod_file).exists()

    def _build_descriptor(
        self,
        defn: ActionEndpointDefinition | ComputedColumnEndpointDefinition | StreamingEndpointDefinition,
        repo_name: str,
    ) -> dict[str, Any]:
        is_streaming = isinstance(defn, StreamingEndpointDefinition)
        base = {
            "id": defn.id,
            "name": defn.name,
            "kind": defn.kind,
            "description": defn.description,
            "repo": repo_name,
            "params": [self._serialize_param(p) for p in defn.params],
            "path": f"/endpoints/{defn.id}" + ("/stream" if is_streaming else ""),
        }
        if isinstance(defn, ComputedColumnEndpointDefinition):
            base["object_type"] = defn.object_type
            base["columns"] = defn.columns
        return base

    def _serialize_param(self, p: ParamSchema) -> dict[str, Any]:
        return {
            "name": p.name,
            "type": p.type,
            "required": p.required,
            "description": p.description,
            "default": p.default,
        }

    def _write_registry(self, registry: dict[str, Any]) -> None:
        path = self.artifacts_dir / "endpoints.json"
        path.write_text(json.dumps(registry, indent=2))

    def load_registry(self) -> dict[str, Any]:
        path = self.artifacts_dir / "endpoints.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text())
