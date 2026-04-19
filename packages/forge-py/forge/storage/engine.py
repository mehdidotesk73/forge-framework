"""DuckDB + Parquet storage engine."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from forge.providers.database import DatabaseProvider

import threading

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


class DatasetMeta:
    def __init__(self, data: dict[str, Any]) -> None:
        self.id: str = data["id"]
        self.name: str = data["name"]
        self.parquet_path: str = data["parquet_path"]
        self.schema: dict[str, Any] = data.get("schema", {})
        self.row_count: int = data.get("row_count", 0)
        self.created_at: str = data.get("created_at", "")
        self.version: int = data.get("version", 1)
        self.is_snapshot: bool = data.get("is_snapshot", False)
        self.source_dataset_id: str | None = data.get("source_dataset_id")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "parquet_path": self.parquet_path,
            "schema": self.schema,
            "row_count": self.row_count,
            "created_at": self.created_at,
            "version": self.version,
            "is_snapshot": self.is_snapshot,
            "source_dataset_id": self.source_dataset_id,
        }


class OutputHandle:
    """Write handle given to pipeline functions for a named output."""

    def __init__(self, name: str, dataset_id: str, engine: "StorageEngine") -> None:
        self._name = name
        self._dataset_id = dataset_id
        self._engine = engine
        self._rows_written = 0

    def write(self, data: Any) -> None:
        """Write a DuckDB relation, pandas DataFrame, or PyArrow Table."""
        if isinstance(data, duckdb.DuckDBPyRelation):
            df = data.df()
        elif isinstance(data, pd.DataFrame):
            df = data
        elif isinstance(data, pa.Table):
            df = data.to_pandas()
        else:
            raise TypeError(f"Unsupported type for output.write(): {type(data)}")

        self._rows_written = len(df)
        self._engine.write_dataset(self._dataset_id, df)

    @property
    def rows_written(self) -> int:
        return self._rows_written


class InputHandle:
    """Read handle given to pipeline functions for a named input."""

    def __init__(self, dataset_id: str, engine: "StorageEngine") -> None:
        self._dataset_id = dataset_id
        self._engine = engine
        self._conn: duckdb.DuckDBPyConnection | None = None

    def _get_conn(self) -> duckdb.DuckDBPyConnection:
        if self._conn is None:
            self._conn = duckdb.connect()  # in-memory; parquet reads don't need the catalog lock
        return self._conn

    def relation(self) -> duckdb.DuckDBPyRelation:
        meta = self._engine.get_dataset(self._dataset_id)
        if meta is None:
            raise ValueError(f"Dataset {self._dataset_id} not found")
        conn = self._get_conn()
        return conn.read_parquet(str(self._engine.data_dir / meta.parquet_path))

    def df(self) -> pd.DataFrame:
        return self.relation().df()

    def __repr__(self) -> str:
        return f"InputHandle(dataset_id={self._dataset_id!r})"


class StorageEngine:
    """Manages all datasets stored as Parquet files with a DuckDB catalog."""

    def __init__(self, forge_dir: Path, db_provider: "DatabaseProvider | None" = None) -> None:
        self.forge_dir = forge_dir
        self.data_dir = forge_dir / "data"
        self.db_path = forge_dir / "forge.duckdb"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db_provider = db_provider  # None → local Parquet/DuckDB (default)
        self._ensure_schema()

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Open a fresh catalog connection. Caller is responsible for closing it."""
        return duckdb.connect(str(self.db_path))

    def close(self) -> None:
        self._conn = None

    def __enter__(self) -> "StorageEngine":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _execute(self, sql: str, params: list | None = None) -> None:
        with self._lock:
            conn = duckdb.connect(str(self.db_path))
            try:
                conn.execute(sql, params or [])
            finally:
                conn.close()

    def _fetchone(self, sql: str, params: list | None = None) -> tuple | None:
        with self._lock:
            conn = duckdb.connect(str(self.db_path))
            try:
                return conn.execute(sql, params or []).fetchone()
            finally:
                conn.close()

    def _fetchall(self, sql: str, params: list | None = None) -> list[tuple]:
        with self._lock:
            conn = duckdb.connect(str(self.db_path))
            try:
                return conn.execute(sql, params or []).fetchall()
            finally:
                conn.close()

    def _ensure_schema(self) -> None:
        self._execute("""
            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                parquet_path TEXT NOT NULL,
                schema_json TEXT NOT NULL DEFAULT '{}',
                row_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                is_snapshot BOOLEAN NOT NULL DEFAULT FALSE,
                source_dataset_id TEXT
            )
        """)
        self._execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id TEXT PRIMARY KEY,
                pipeline_name TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
                rows_written_json TEXT NOT NULL DEFAULT '{}',
                error TEXT
            )
        """)

    def get_dataset(self, dataset_id: str) -> DatasetMeta | None:
        row = self._fetchone("SELECT * FROM datasets WHERE id = ?", [dataset_id])
        if row is None:
            return None
        cols = ["id", "name", "parquet_path", "schema_json", "row_count",
                "created_at", "version", "is_snapshot", "source_dataset_id"]
        d = dict(zip(cols, row))
        d["schema"] = json.loads(d.pop("schema_json"))
        return DatasetMeta(d)

    def find_dataset_by_name(self, name: str) -> DatasetMeta | None:
        row = self._fetchone(
            "SELECT * FROM datasets WHERE name = ? ORDER BY version DESC LIMIT 1",
            [name]
        )
        if row is None:
            return None
        cols = ["id", "name", "parquet_path", "schema_json", "row_count",
                "created_at", "version", "is_snapshot", "source_dataset_id"]
        d = dict(zip(cols, row))
        d["schema"] = json.loads(d.pop("schema_json"))
        return DatasetMeta(d)

    def list_datasets(self) -> list[DatasetMeta]:
        rows = self._fetchall("SELECT * FROM datasets ORDER BY created_at DESC")
        cols = ["id", "name", "parquet_path", "schema_json", "row_count",
                "created_at", "version", "is_snapshot", "source_dataset_id"]
        results = []
        for row in rows:
            d = dict(zip(cols, row))
            d["schema"] = json.loads(d.pop("schema_json"))
            results.append(DatasetMeta(d))
        return results

    def register_dataset(self, meta: DatasetMeta) -> None:
        self._execute("""
            INSERT OR REPLACE INTO datasets
            (id, name, parquet_path, schema_json, row_count, created_at,
             version, is_snapshot, source_dataset_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            meta.id, meta.name, meta.parquet_path,
            json.dumps(meta.schema), meta.row_count,
            meta.created_at, meta.version,
            meta.is_snapshot, meta.source_dataset_id,
        ])

    def write_dataset(self, dataset_id: str, df: pd.DataFrame) -> DatasetMeta:
        existing = self.get_dataset(dataset_id)
        if existing and existing.is_snapshot:
            # Mutable snapshot: overwrite in place
            parquet_path = existing.parquet_path
            full_path = self.data_dir / parquet_path
            table = pa.Table.from_pandas(df, preserve_index=False)
            pq.write_table(table, str(full_path))
            schema = _infer_schema(df)
            meta = DatasetMeta({
                **existing.to_dict(),
                "schema": schema,
                "row_count": len(df),
            })
        else:
            # Immutable: write new versioned file
            version = (existing.version + 1) if existing else 1
            name = existing.name if existing else dataset_id
            parquet_path = f"{dataset_id}_v{version}.parquet"
            full_path = self.data_dir / parquet_path
            table = pa.Table.from_pandas(df, preserve_index=False)
            pq.write_table(table, str(full_path))
            schema = _infer_schema(df)
            meta = DatasetMeta({
                "id": dataset_id,
                "name": name,
                "parquet_path": parquet_path,
                "schema": schema,
                "row_count": len(df),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "version": version,
                "is_snapshot": False,
                "source_dataset_id": None,
            })
        self.register_dataset(meta)
        return meta

    def load_file(self, file_path: Path, name: str) -> DatasetMeta:
        """Load a CSV or Parquet file as a new dataset."""
        dataset_id = str(uuid.uuid4())
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(file_path)
        elif suffix in (".parquet", ".pq"):
            df = pd.read_parquet(file_path)
        elif suffix in (".json", ".jsonl"):
            df = pd.read_json(file_path, lines=(suffix == ".jsonl"))
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

        parquet_path = f"{dataset_id}_v1.parquet"
        full_path = self.data_dir / parquet_path
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(table, str(full_path))

        meta = DatasetMeta({
            "id": dataset_id,
            "name": name,
            "parquet_path": parquet_path,
            "schema": _infer_schema(df),
            "row_count": len(df),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": 1,
            "is_snapshot": False,
            "source_dataset_id": None,
        })
        self.register_dataset(meta)
        return meta

    def snapshot_dataset(self, source_id: str) -> DatasetMeta:
        """Create a mutable snapshot copy of a dataset."""
        source = self.get_dataset(source_id)
        if source is None:
            raise ValueError(f"Source dataset {source_id} not found")

        snapshot_id = str(uuid.uuid4())
        src_path = self.data_dir / source.parquet_path
        dst_path = f"{snapshot_id}_snapshot.parquet"
        import shutil
        shutil.copy2(str(src_path), str(self.data_dir / dst_path))

        meta = DatasetMeta({
            "id": snapshot_id,
            "name": f"{source.name}_snapshot",
            "parquet_path": dst_path,
            "schema": source.schema,
            "row_count": source.row_count,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": 1,
            "is_snapshot": True,
            "source_dataset_id": source_id,
        })
        self.register_dataset(meta)
        return meta

    def read_dataset(self, dataset_id: str) -> pd.DataFrame:
        meta = self.get_dataset(dataset_id)
        if meta is None:
            raise ValueError(f"Dataset {dataset_id} not found")
        return pd.read_parquet(str(self.data_dir / meta.parquet_path))

    def read_dataset_relation(self, dataset_id: str) -> duckdb.DuckDBPyRelation:
        meta = self.get_dataset(dataset_id)
        if meta is None:
            raise ValueError(f"Dataset {dataset_id} not found")
        # Use an in-memory DuckDB — parquet reads don't need the catalog lock
        conn = duckdb.connect()
        return conn.read_parquet(str(self.data_dir / meta.parquet_path))

    # ── Run history ──────────────────────────────────────────────────────────

    def record_run_start(self, pipeline_name: str) -> str:
        run_id = str(uuid.uuid4())
        self._execute("""
            INSERT INTO pipeline_runs
            (id, pipeline_name, status, started_at, rows_written_json)
            VALUES (?, ?, 'running', ?, '{}')
        """, [run_id, pipeline_name, datetime.now(timezone.utc).isoformat()])
        return run_id

    def record_run_finish(
        self,
        run_id: str,
        status: str,
        duration: float,
        rows_written: dict[str, int],
        error: str | None = None,
    ) -> None:
        self._execute("""
            UPDATE pipeline_runs
            SET status = ?, finished_at = ?, duration_seconds = ?,
                rows_written_json = ?, error = ?
            WHERE id = ?
        """, [
            status,
            datetime.now(timezone.utc).isoformat(),
            duration,
            json.dumps(rows_written),
            error,
            run_id,
        ])

    def get_pipeline_history(self, pipeline_name: str) -> list[dict[str, Any]]:
        rows = self._fetchall("""
            SELECT id, pipeline_name, status, started_at, finished_at,
                   duration_seconds, rows_written_json, error
            FROM pipeline_runs
            WHERE pipeline_name = ?
            ORDER BY started_at DESC
            LIMIT 50
        """, [pipeline_name])
        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "pipeline_name": row[1],
                "status": row[2],
                "started_at": row[3],
                "finished_at": row[4],
                "duration_seconds": row[5],
                "rows_written": json.loads(row[6]),
                "error": row[7],
            })
        return result

    # ── Snapshot CRUD helpers ─────────────────────────────────────────────────

    def upsert_rows(self, dataset_id: str, rows: list[dict], primary_key: str) -> None:
        df = self.read_dataset(dataset_id)
        new_df = pd.DataFrame(rows)
        # Remove existing rows with same primary key
        if primary_key in df.columns:
            pks = new_df[primary_key].tolist()
            df = df[~df[primary_key].isin(pks)]
        df = pd.concat([df, new_df], ignore_index=True)
        self.write_dataset(dataset_id, df)

    def delete_rows(self, dataset_id: str, primary_key: str, pk_values: list) -> None:
        df = self.read_dataset(dataset_id)
        df = df[~df[primary_key].isin(pk_values)]
        self.write_dataset(dataset_id, df)


def _infer_schema(df: pd.DataFrame) -> dict[str, Any]:
    fields = {}
    for col in df.columns:
        dtype = df[col].dtype
        if pd.api.types.is_integer_dtype(dtype):
            ftype = "integer"
        elif pd.api.types.is_float_dtype(dtype):
            ftype = "float"
        elif pd.api.types.is_bool_dtype(dtype):
            ftype = "boolean"
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            ftype = "datetime"
        else:
            ftype = "string"
        nullable = bool(df[col].isnull().any())
        fields[col] = {"type": ftype, "nullable": nullable}
    return {"fields": fields}
