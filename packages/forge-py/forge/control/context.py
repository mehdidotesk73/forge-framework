"""
Forge request context — engine access and Unit of Work for endpoint functions.

The server initialises a ForgeContext at the start of each endpoint call.
Model methods read the engine and UoW from the context; endpoint developers
never interact with this module directly.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any


# ── Context variables (one value per coroutine/request) ───────────────────────

_engine_var: ContextVar[Any] = ContextVar("forge_engine")
_uow_var: ContextVar["UnitOfWork | None"] = ContextVar("forge_uow", default=None)


# ── Public accessors ──────────────────────────────────────────────────────────

def get_engine(override: Any = None) -> Any:
    """Return the active engine. Pass override= to use a specific engine instead."""
    if override is not None:
        return override
    try:
        return _engine_var.get()
    except LookupError:
        raise RuntimeError(
            "No Forge engine in context. "
            "Call from within an endpoint, or pass engine= explicitly."
        )


def get_uow() -> "UnitOfWork | None":
    return _uow_var.get()


def init_context(engine: Any) -> "UnitOfWork":
    """Called by the server at the start of each endpoint invocation."""
    _engine_var.set(engine)
    uow = UnitOfWork(engine)
    _uow_var.set(uow)
    return uow


# ── Unit of Work ──────────────────────────────────────────────────────────────

class UnitOfWork:
    """
    Tracks all model mutations within one endpoint call and flushes them
    atomically when the call succeeds. Changes are discarded on exception.

    Grouping strategy: one dataset write per class, not per instance.
    """

    def __init__(self, engine: Any) -> None:
        self.engine = engine
        self._new: list[object] = []
        self._dirty_set: set[int] = set()       # id(instance) → dedup
        self._dirty: list[object] = []
        self._deleted_set: set[int] = set()
        self._deleted: list[object] = []

    def register_new(self, instance: object) -> None:
        self._new.append(instance)

    def mark_dirty(self, instance: object) -> None:
        iid = id(instance)
        if iid not in self._dirty_set and iid not in self._deleted_set:
            self._dirty_set.add(iid)
            self._dirty.append(instance)

    def mark_deleted(self, instance: object) -> None:
        iid = id(instance)
        if iid not in self._deleted_set:
            self._deleted_set.add(iid)
            self._deleted.append(instance)

    def flush(self) -> None:
        """Write all pending changes. Called by server on successful endpoint return."""
        # Group by class to minimise dataset writes
        to_upsert: dict[type, list[object]] = {}
        to_delete: dict[type, list[object]] = {}

        for inst in self._deleted:
            to_delete.setdefault(type(inst), []).append(inst)

        deleted_ids = self._deleted_set
        for inst in self._new + self._dirty:
            if id(inst) not in deleted_ids:
                to_upsert.setdefault(type(inst), []).append(inst)

        for cls, instances in to_delete.items():
            _flush_deletes(cls, instances, self.engine)

        for cls, instances in to_upsert.items():
            _flush_upserts(cls, instances, self.engine)


def _flush_upserts(cls: type, instances: list, engine: Any) -> None:
    defn = cls._forge_model
    dataset_id = _resolve_dataset_id(defn, engine)
    pk = next((f.name for f in defn.fields if f.primary_key), None)
    if pk is None:
        return
    rows = [inst._to_dict() for inst in instances]
    engine.upsert_rows(dataset_id, rows, pk)


def _flush_deletes(cls: type, instances: list, engine: Any) -> None:
    defn = cls._forge_model
    dataset_id = _resolve_dataset_id(defn, engine)
    pk = next((f.name for f in defn.fields if f.primary_key), None)
    if pk is None:
        return
    pk_vals = [getattr(inst, pk) for inst in instances]
    engine.delete_rows(dataset_id, pk, pk_vals)


def _resolve_dataset_id(defn: Any, engine: Any) -> str:
    if defn.snapshot_dataset_id:
        return defn.snapshot_dataset_id
    import json
    from pathlib import Path
    artifact = Path(engine.forge_dir) / "artifacts" / f"{defn.class_name}.schema.json"
    if artifact.exists():
        snap_id = json.loads(artifact.read_text()).get("snapshot_dataset_id")
        if snap_id:
            defn.snapshot_dataset_id = snap_id
            return snap_id
    return defn.backing_dataset_id
