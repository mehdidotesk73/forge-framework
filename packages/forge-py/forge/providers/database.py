"""Database provider Protocol — extended by future cloud database integrations."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class DatabaseProvider(Protocol):
    """Minimal interface that any database backend must satisfy."""

    def read_table(self, table_id: str) -> pd.DataFrame:
        """Read a table/dataset by ID and return it as a DataFrame."""
        ...

    def write_table(self, table_id: str, df: pd.DataFrame) -> None:
        """Persist a DataFrame to the given table/dataset ID."""
        ...

    def delete_rows(self, table_id: str, primary_key: str, pk_values: list[Any]) -> None:
        """Delete rows matching pk_values from the given table."""
        ...


class LocalDatabaseProvider:
    """Default local Parquet/DuckDB provider — wraps StorageEngine."""

    def __init__(self, engine: Any) -> None:
        self._engine = engine

    def read_table(self, table_id: str) -> pd.DataFrame:
        return self._engine.read_dataset(table_id)

    def write_table(self, table_id: str, df: pd.DataFrame) -> None:
        self._engine.write_dataset(table_id, df)

    def delete_rows(self, table_id: str, primary_key: str, pk_values: list[Any]) -> None:
        self._engine.delete_rows(table_id, primary_key, pk_values)


def make_database_provider(provider: str, options: dict[str, str], engine: Any) -> DatabaseProvider:
    """Instantiate the correct DatabaseProvider from forge.toml [database] config."""
    if provider == "local":
        return LocalDatabaseProvider(engine)
    raise ValueError(
        f"Unknown database provider '{provider}'. "
        "Only 'local' is supported in this version of Forge."
    )
