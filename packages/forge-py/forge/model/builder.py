"""forge model build — generates schema artifacts and SDKs."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any

from forge.config import ModelConfig, ProjectConfig
from forge.model.definition import ForgeModelDefinition, get_model_registry
from forge.model.codegen_python import generate_python_sdk
from forge.model.codegen_typescript import generate_typescript_sdk
from forge.storage.engine import StorageEngine


class ModelBuilder:
    def __init__(
        self,
        config: ProjectConfig,
        root: Path,
        engine: StorageEngine,
    ) -> None:
        self.config = config
        self.root = root
        self.engine = engine
        self.artifacts_dir = root / ".forge" / "artifacts"
        self.generated_dir = root / ".forge" / "generated"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        (self.generated_dir / "python").mkdir(parents=True, exist_ok=True)
        (self.generated_dir / "typescript").mkdir(parents=True, exist_ok=True)

    def build_all(self) -> list[dict[str, Any]]:
        results = []
        for model_cfg in self.config.models:
            result = self.build_one(model_cfg)
            results.append(result)
        return results

    def build_one(self, model_cfg: ModelConfig) -> dict[str, Any]:
        defn = self._load_definition(model_cfg)

        # For snapshot models: ensure snapshot dataset exists
        snapshot_dataset_id = None
        if defn.mode == "snapshot":
            existing_snapshot = self._find_snapshot(defn.backing_dataset_id)
            if existing_snapshot is None:
                snap = self.engine.snapshot_dataset(defn.backing_dataset_id)
                snapshot_dataset_id = snap.id
            else:
                snapshot_dataset_id = existing_snapshot
            defn.snapshot_dataset_id = snapshot_dataset_id

        # Build schema artifact from live dataset
        dataset_id = snapshot_dataset_id or defn.backing_dataset_id
        dataset_meta = self.engine.get_dataset(dataset_id)
        if dataset_meta is None:
            # Fall back to declared fields only
            schema_fields = {f.name: {"type": f.type, "nullable": f.nullable} for f in defn.fields}
        else:
            schema_fields = dataset_meta.schema.get("fields", {})
            # Merge with declared field metadata
            for f in defn.fields:
                if f.name in schema_fields:
                    schema_fields[f.name].update({
                        "primary_key": f.primary_key,
                        "display": f.display,
                        "display_hint": f.display_hint,
                    })

        artifact = {
            "name": defn.class_name,
            "mode": defn.mode,
            "backing_dataset_id": defn.backing_dataset_id,
            "snapshot_dataset_id": snapshot_dataset_id,
            "fields": schema_fields,
            "primary_key": next(
                (f.name for f in defn.fields if f.primary_key), None
            ),
        }

        # Write schema artifact
        artifact_path = self.artifacts_dir / f"{defn.class_name}.schema.json"
        artifact_path.write_text(json.dumps(artifact, indent=2))

        # Generate Python SDK
        py_sdk_path = self.generated_dir / "python" / f"{defn.class_name.lower()}.py"
        py_sdk_path.write_text(generate_python_sdk(artifact))

        # Generate TypeScript SDK
        ts_sdk_path = self.generated_dir / "typescript" / f"{defn.class_name}.ts"
        ts_sdk_path.write_text(generate_typescript_sdk(artifact))

        # Write/update index files
        self._write_python_index()
        self._write_typescript_index()

        return {
            "name": defn.class_name,
            "mode": defn.mode,
            "artifact": str(artifact_path),
            "python_sdk": str(py_sdk_path),
            "typescript_sdk": str(ts_sdk_path),
        }

    def reinitialize(self, class_name: str) -> dict[str, Any]:
        """Drop snapshot and recreate from source dataset."""
        model_cfg = self.config.model_by_name.get(class_name)
        if model_cfg is None:
            raise ValueError(f"No model named '{class_name}'")
        defn = self._load_definition(model_cfg)
        if defn.mode != "snapshot":
            raise ValueError(f"Model '{class_name}' is not a snapshot model")
        snap = self.engine.snapshot_dataset(defn.backing_dataset_id)
        return {"name": class_name, "new_snapshot_id": snap.id}

    def _load_definition(self, model_cfg: ModelConfig) -> ForgeModelDefinition:
        root_str = str(self.root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)
        mod = importlib.import_module(model_cfg.module)
        cls = getattr(mod, model_cfg.class_name)
        if not hasattr(cls, "_forge_model"):
            raise ValueError(
                f"{model_cfg.module}.{model_cfg.class_name} is not decorated with @forge_model"
            )
        return cls._forge_model

    def _find_snapshot(self, source_dataset_id: str) -> str | None:
        for ds in self.engine.list_datasets():
            if ds.is_snapshot and ds.source_dataset_id == source_dataset_id:
                return ds.id
        return None

    def _write_python_index(self) -> None:
        py_dir = self.generated_dir / "python"
        modules = [f.stem for f in py_dir.glob("*.py") if f.name != "__init__.py"]
        lines = ["# Auto-generated by forge model build — do not edit\n"]
        for mod in sorted(modules):
            lines.append(f"from .{mod} import *  # noqa: F401,F403\n")
        (py_dir / "__init__.py").write_text("".join(lines))

    def _write_typescript_index(self) -> None:
        ts_dir = self.generated_dir / "typescript"
        modules = [f.stem for f in ts_dir.glob("*.ts") if f.name != "index.ts"]
        lines = ["// Auto-generated by forge model build — do not edit\n"]
        for mod in sorted(modules):
            lines.append(f'export * from "./{mod}";\n')
        (ts_dir / "index.ts").write_text("".join(lines))
