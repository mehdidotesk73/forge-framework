"""@forge_model decorator, field_def, and related declarations."""
from __future__ import annotations

import json
import uuid as _uuid_mod
from dataclasses import dataclass, field
from typing import Any, Callable, TypeVar, get_type_hints

T = TypeVar("T")

# ── Registries ────────────────────────────────────────────────────────────────

_MODEL_REGISTRY: dict[str, "ForgeModelDefinition"] = {}
_CLASS_REGISTRY:  dict[str, type] = {}


# ── Metadata types ────────────────────────────────────────────────────────────

@dataclass
class ModelField:
    name: str
    type: str
    nullable: bool = False
    primary_key: bool = False
    display: str = ""
    display_hint: str = ""


@dataclass
class RelationDefinition:
    name: str
    target_model: str
    via_field: str


@dataclass
class ForgeModelDefinition:
    class_name: str
    mode: str  # "snapshot" | "stream"
    backing_dataset_id: str
    fields: list[ModelField]
    relations: list[RelationDefinition] = field(default_factory=list)
    module: str = ""
    snapshot_dataset_id: str | None = None


# ── Sentinels ─────────────────────────────────────────────────────────────────

class _FieldMeta:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class _RelatedMeta:
    def __init__(self, target_model: str, via: str) -> None:
        self.target_model = target_model
        self.via = via


# ── Typed base classes (for IDE / Pylance support) ───────────────────────────

class ForgeStreamModel:
    """Inherit from this for Pylance/mypy to see query methods on stream models."""
    @classmethod
    def get(cls, pk_value: Any, *, engine: Any = None) -> Any | None: ...  # type: ignore[empty-body]
    @classmethod
    def get_many(cls, pk_values: list, *, engine: Any = None) -> list: ...  # type: ignore[empty-body]
    @classmethod
    def all(cls, *, engine: Any = None) -> list: ...  # type: ignore[empty-body]
    @classmethod
    def filter(cls, *, engine: Any = None, **kwargs: Any) -> list: ...  # type: ignore[empty-body]
    def _to_dict(self) -> dict[str, Any]: ...  # type: ignore[empty-body]


class ForgeSnapshotModel(ForgeStreamModel):
    """Inherit from this for Pylance/mypy to see query + mutation methods on snapshot models."""
    @classmethod
    def create(cls, *, engine: Any = None, **kwargs: Any) -> Any: ...  # type: ignore[empty-body]
    def update(self, *, engine: Any = None, **kwargs: Any) -> None: ...  # type: ignore[empty-body]
    def remove(self, *, engine: Any = None) -> None: ...  # type: ignore[empty-body]


# ── Public declarations ───────────────────────────────────────────────────────

def field_def(
    *,
    primary_key: bool = False,
    display: str = "",
    display_hint: str = "",
    nullable: bool = False,
) -> Any:
    return _FieldMeta(primary_key=primary_key, display=display,
                      display_hint=display_hint, nullable=nullable)


def related(target_model: str, *, via: str) -> Any:
    """
    Declare a one-to-many relationship resolved via a JSON key list field.

        grades = related("Grade", via="grade_keys")

    Generates: student.grades()  →  list[Grade]
    """
    return _RelatedMeta(target_model=target_model, via=via)


# ── Decorator ─────────────────────────────────────────────────────────────────

def forge_model(mode: str, backing_dataset: str) -> Callable:
    """Class decorator that registers a Forge object type and mixes in query methods."""

    def decorator(cls: type) -> type:
        hints = get_type_hints(cls)

        fields: list[ModelField] = []
        for fname, ftype in hints.items():
            if fname.startswith("_"):
                continue
            meta = cls.__dict__.get(fname)
            if isinstance(meta, _FieldMeta):
                fields.append(ModelField(
                    name=fname,
                    type=_python_type_to_forge(ftype),
                    nullable=meta.nullable,
                    primary_key=meta.primary_key,
                    display=meta.display or fname.replace("_", " ").title(),
                    display_hint=meta.display_hint,
                ))
            elif not isinstance(meta, (_RelatedMeta, classmethod, staticmethod)):
                nullable = False
                try:
                    import typing
                    args = getattr(ftype, "__args__", None)
                    origin = getattr(ftype, "__origin__", None)
                    if origin is typing.Union and type(None) in (args or ()):
                        nullable = True
                        ftype = next(a for a in args if a is not type(None))
                except Exception:
                    pass
                fields.append(ModelField(
                    name=fname,
                    type=_python_type_to_forge(ftype),
                    nullable=nullable,
                    primary_key=False,
                    display=fname.replace("_", " ").title(),
                ))

        relations: list[RelationDefinition] = []
        for attr_name, attr_val in cls.__dict__.items():
            if isinstance(attr_val, _RelatedMeta):
                relations.append(RelationDefinition(
                    name=attr_name,
                    target_model=attr_val.target_model,
                    via_field=attr_val.via,
                ))

        defn = ForgeModelDefinition(
            class_name=cls.__name__,
            mode=mode,
            backing_dataset_id=backing_dataset,
            fields=fields,
            relations=relations,
            module=cls.__module__,
        )
        pk_fields = [f for f in fields if f.primary_key]
        if len(pk_fields) == 0:
            raise TypeError(f"@forge_model '{cls.__name__}' must declare exactly one field with primary_key=True")
        if len(pk_fields) > 1:
            raise TypeError(f"@forge_model '{cls.__name__}' has multiple primary_key fields: {[f.name for f in pk_fields]}")

        _MODEL_REGISTRY[cls.__name__] = defn
        _CLASS_REGISTRY[cls.__name__] = cls

        _mix_in_class_methods(cls, defn, mode)
        _mix_in_relation_methods(cls, relations)

        cls._forge_model = defn  # type: ignore[attr-defined]
        return cls

    return decorator


# ── Method factories ──────────────────────────────────────────────────────────

def _mix_in_class_methods(cls: type, defn: ForgeModelDefinition, mode: str) -> None:
    field_names = [f.name for f in defn.fields]
    field_names_set = set(field_names)
    pk_name = next((f.name for f in defn.fields if f.primary_key), None)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _resolve(engine_override: Any = None) -> tuple[str, Any]:
        """Returns (dataset_id, engine). Reads engine from context if not overridden."""
        from forge.control.context import get_engine
        eng = get_engine(engine_override)
        d = cls._forge_model
        if not d.snapshot_dataset_id:
            artifact = (
                __import__("pathlib").Path(eng.forge_dir)
                / "artifacts"
                / f"{d.class_name}.schema.json"
            )
            if artifact.exists():
                snap_id = json.loads(artifact.read_text()).get("snapshot_dataset_id")
                if snap_id:
                    d.snapshot_dataset_id = snap_id
        return (d.snapshot_dataset_id or d.backing_dataset_id), eng

    # ── _from_dict — disables dirty tracking during construction ─────────────

    @classmethod  # type: ignore[misc]
    def _from_dict(klass, data: dict[str, Any]) -> Any:
        instance = object.__new__(klass)
        object.__setattr__(instance, "_forge_managed", False)
        for fname in field_names:
            object.__setattr__(instance, fname, data.get(fname))
        object.__setattr__(instance, "_forge_managed", True)
        return instance

    # ── __setattr__ — dirty tracking ─────────────────────────────────────────

    def __setattr__(self, name: str, value: Any) -> None:
        if name in field_names_set:
            try:
                managed = object.__getattribute__(self, "_forge_managed")
            except AttributeError:
                managed = False
            if managed:
                from forge.control.context import get_uow
                uow = get_uow()
                if uow is not None:
                    uow.mark_dirty(self)
        object.__setattr__(self, name, value)

    # ── Class-level queries ───────────────────────────────────────────────────

    @classmethod  # type: ignore[misc]
    def all(klass, *, engine: Any = None) -> list:
        dataset_id, eng = _resolve(engine)
        df = eng.read_dataset(dataset_id)
        return [klass._from_dict(row) for row in df.to_dict(orient="records")]

    @classmethod  # type: ignore[misc]
    def get(klass, pk_value: Any, *, engine: Any = None) -> Any | None:
        if pk_name is None:
            raise ValueError(f"{klass.__name__} has no primary_key field")
        dataset_id, eng = _resolve(engine)
        df = eng.read_dataset(dataset_id)
        matches = df[df[pk_name] == pk_value]
        if matches.empty:
            return None
        return klass._from_dict(matches.iloc[0].to_dict())

    @classmethod  # type: ignore[misc]
    def get_many(klass, pk_values: list, *, engine: Any = None) -> list:
        """Batch fetch by PK — single DB read, order-preserving."""
        if pk_name is None:
            raise ValueError(f"{klass.__name__} has no primary_key field")
        if not pk_values:
            return []
        dataset_id, eng = _resolve(engine)
        df = eng.read_dataset(dataset_id)
        matches = df[df[pk_name].isin([str(pk) for pk in pk_values])]
        by_pk = {
            str(row[pk_name]): klass._from_dict(row)
            for row in matches.to_dict(orient="records")
        }
        return [by_pk[str(pk)] for pk in pk_values if str(pk) in by_pk]

    @classmethod  # type: ignore[misc]
    def filter(klass, *, engine: Any = None, **kwargs: Any) -> list:
        dataset_id, eng = _resolve(engine)
        df = eng.read_dataset(dataset_id)
        for col, val in kwargs.items():
            df = df[df[col] == val]
        return [klass._from_dict(row) for row in df.to_dict(orient="records")]

    # ── Instance helpers ──────────────────────────────────────────────────────

    def _to_dict(self) -> dict[str, Any]:
        return {fname: getattr(self, fname, None) for fname in field_names}

    def __repr__(self) -> str:
        pk_val = getattr(self, pk_name, "?") if pk_name else "?"
        return f"{cls.__name__}({pk_name}={pk_val!r})"

    # ── Snapshot-only mutations ───────────────────────────────────────────────

    if mode == "snapshot":

        @classmethod  # type: ignore[misc]
        def create(klass, *, engine: Any = None, **kwargs: Any) -> Any:
            if pk_name and pk_name not in kwargs:
                kwargs[pk_name] = _uuid_mod.uuid4().hex[:8]
            instance = klass._from_dict(kwargs)
            from forge.control.context import get_uow
            uow = get_uow()
            if uow is not None:
                uow.register_new(instance)
            else:
                # Outside endpoint context — write immediately (CLI / tests)
                _, eng = _resolve(engine)
                eng.upsert_rows(
                    klass._forge_model.snapshot_dataset_id or klass._forge_model.backing_dataset_id,
                    [kwargs], pk_name or list(kwargs.keys())[0]
                )
            return instance

        def update(self, *, engine: Any = None, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)  # goes through __setattr__ → marks dirty
            # If no UoW (CLI), write immediately
            from forge.control.context import get_uow
            if get_uow() is None:
                dataset_id, eng = _resolve(engine)
                eng.upsert_rows(dataset_id, [self._to_dict()], pk_name)

        def remove(self, *, engine: Any = None) -> None:
            from forge.control.context import get_uow
            uow = get_uow()
            if uow is not None:
                uow.mark_deleted(self)
            else:
                if pk_name is None:
                    raise ValueError(f"{cls.__name__} has no primary_key field")
                dataset_id, eng = _resolve(engine)
                eng.delete_rows(dataset_id, pk_name, [getattr(self, pk_name)])

        cls.create = create  # type: ignore[attr-defined]
        cls.update = update  # type: ignore[attr-defined]
        cls.remove = remove  # type: ignore[attr-defined]

    # ── Attach all methods ────────────────────────────────────────────────────

    cls._from_dict   = _from_dict    # type: ignore[attr-defined]
    cls.__setattr__  = __setattr__   # type: ignore[assignment]
    cls.all          = all           # type: ignore[attr-defined]
    cls.get          = get           # type: ignore[attr-defined]
    cls.get_many     = get_many      # type: ignore[attr-defined]
    cls.filter       = filter        # type: ignore[attr-defined]
    cls._to_dict     = _to_dict      # type: ignore[attr-defined]
    cls.__repr__     = __repr__      # type: ignore[assignment]


def _mix_in_relation_methods(cls: type, relations: list[RelationDefinition]) -> None:
    for rel in relations:
        setattr(cls, rel.name, _make_relation_method(rel))


def _make_relation_method(rel: RelationDefinition) -> Callable:
    target_name = rel.target_model
    via_field   = rel.via_field

    def relation_method(self, *, engine: Any = None) -> list:
        target_defn = _MODEL_REGISTRY.get(target_name)
        if target_defn is None:
            raise ValueError(
                f"Model '{target_name}' not registered. Import it before calling this method."
            )
        raw = getattr(self, via_field, None) or "[]"
        ids: list[str] = json.loads(raw) if isinstance(raw, str) else []
        if not ids:
            return []

        from forge.control.context import get_engine
        eng = get_engine(engine)

        dataset_id = target_defn.snapshot_dataset_id or target_defn.backing_dataset_id
        if not target_defn.snapshot_dataset_id:
            from pathlib import Path
            artifact = Path(eng.forge_dir) / "artifacts" / f"{target_name}.schema.json"
            if artifact.exists():
                snap_id = json.loads(artifact.read_text()).get("snapshot_dataset_id")
                if snap_id:
                    target_defn.snapshot_dataset_id = snap_id
                    dataset_id = snap_id

        df = eng.read_dataset(dataset_id)
        pk = next((f.name for f in target_defn.fields if f.primary_key), "id")
        filtered = df[df[pk].isin(ids)]

        TargetClass = _CLASS_REGISTRY.get(target_name)
        if TargetClass is None:
            raise ValueError(f"Class '{target_name}' not in registry.")
        return [TargetClass._from_dict(row) for row in filtered.to_dict(orient="records")]

    relation_method.__name__ = target_name.lower() + "s"
    return relation_method


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_model_registry() -> dict[str, ForgeModelDefinition]:
    return _MODEL_REGISTRY


def _python_type_to_forge(t: Any) -> str:
    mapping = {str: "string", int: "integer", float: "float", bool: "boolean"}
    if t in mapping:
        return mapping[t]
    name = getattr(t, "__name__", str(t))
    if "int"   in name.lower(): return "integer"
    if "float" in name.lower(): return "float"
    if "bool"  in name.lower(): return "boolean"
    if "date"  in name.lower() or "time" in name.lower(): return "datetime"
    return "string"
