"""CORE dataset operations — list and preview datasets and models in a project."""
from __future__ import annotations

import json
from pathlib import Path


def list_project_datasets(root: Path) -> dict:
    from forge.storage.engine import StorageEngine
    with StorageEngine(root / ".forge") as engine:
        datasets = engine.list_datasets()
        return {
            "datasets": [
                {
                    "id": d.id,
                    "name": d.name,
                    "row_count": d.row_count,
                    "created_at": d.created_at,
                    "is_snapshot": d.is_snapshot,
                }
                for d in datasets
            ]
        }


def _df_to_table(df, limit: int) -> dict:
    df = df.head(int(limit))
    columns = list(df.columns)
    rows = [
        [None if (v != v) else (v.isoformat() if hasattr(v, "isoformat") else v)
         for v in row]
        for row in df.itertuples(index=False, name=None)
    ]
    return {"columns": columns, "rows": rows}


def preview_dataset(root: Path, dataset_id: str, limit: int = 100) -> dict:
    from forge.storage.engine import StorageEngine
    try:
        with StorageEngine(root / ".forge") as engine:
            return _df_to_table(engine.read_dataset(dataset_id), limit)
    except Exception as exc:
        return {"error": str(exc)}


def preview_model(root: Path, model_name: str, limit: int = 200) -> dict:
    from forge.storage.engine import StorageEngine

    forge_dir = root / ".forge"
    artifact = forge_dir / "artifacts" / f"{model_name}.schema.json"
    if not artifact.exists():
        return {"error": f"No artifact found for model '{model_name}' — run forge model build first"}

    schema = json.loads(artifact.read_text())
    dataset_id = schema.get("snapshot_dataset_id") or schema.get("backing_dataset_id")
    if not dataset_id:
        return {"error": f"Model '{model_name}' artifact has no backing dataset ID"}

    try:
        with StorageEngine(forge_dir) as engine:
            return _df_to_table(engine.read_dataset(dataset_id), limit)
    except Exception as exc:
        return {"error": str(exc)}
