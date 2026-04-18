"""Pipeline execution engine."""
from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path
from typing import Any

from forge.pipeline.decorator import PipelineDefinition, get_registry
from forge.storage.engine import InputHandle, OutputHandle, StorageEngine


class _InputBundle:
    def __init__(self, handles: dict[str, InputHandle]) -> None:
        self._handles = handles

    def __getattr__(self, name: str) -> InputHandle:
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._handles:
            raise AttributeError(f"No input named '{name}'")
        return self._handles[name]


class _OutputBundle:
    def __init__(self, handles: dict[str, OutputHandle]) -> None:
        self._handles = handles

    def __getattr__(self, name: str) -> OutputHandle:
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._handles:
            raise AttributeError(f"No output named '{name}'")
        return self._handles[name]

    def rows_written(self) -> dict[str, int]:
        return {k: v.rows_written for k, v in self._handles.items()}


class PipelineRunner:
    def __init__(self, engine: StorageEngine, project_root: Path) -> None:
        self.engine = engine
        self.project_root = project_root

    def _ensure_sys_path(self) -> None:
        root_str = str(self.project_root)
        if root_str not in sys.path:
            sys.path.insert(0, root_str)

    def load_pipeline(self, module_path: str, func_name: str) -> PipelineDefinition:
        self._ensure_sys_path()
        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name)
        if not hasattr(func, "_forge_pipeline"):
            raise ValueError(
                f"{module_path}.{func_name} is not decorated with @pipeline"
            )
        return func._forge_pipeline

    def run(self, defn: PipelineDefinition, config_name: str | None = None) -> dict[str, Any]:
        run_id = self.engine.record_run_start(config_name or defn.name)
        start = time.monotonic()
        try:
            input_handles = {
                k: InputHandle(v.dataset_id, self.engine)
                for k, v in defn.inputs.items()
            }
            output_handles = {
                k: OutputHandle(k, v.dataset_id, self.engine)
                for k, v in defn.outputs.items()
            }
            inputs_bundle = _InputBundle(input_handles)
            outputs_bundle = _OutputBundle(output_handles)

            defn.func(inputs_bundle, outputs_bundle)

            duration = time.monotonic() - start
            rows_written = outputs_bundle.rows_written()
            self.engine.record_run_finish(run_id, "success", duration, rows_written)
            return {
                "run_id": run_id,
                "status": "success",
                "duration_seconds": duration,
                "rows_written": rows_written,
            }
        except Exception as exc:
            duration = time.monotonic() - start
            self.engine.record_run_finish(run_id, "failed", duration, {}, str(exc))
            raise
