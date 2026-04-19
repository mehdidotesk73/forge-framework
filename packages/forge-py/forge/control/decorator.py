"""Endpoint decorators for the control layer."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Generator

_ENDPOINT_REGISTRY: dict[str, "ActionEndpointDefinition | ComputedColumnEndpointDefinition | StreamingEndpointDefinition"] = {}


@dataclass
class StreamEvent:
    data: str
    event: str = "message"  # stdout | stderr | status | done | error


@dataclass
class ParamSchema:
    name: str
    type: str
    required: bool = True
    description: str = ""
    default: Any = None


@dataclass
class ActionEndpointDefinition:
    id: str
    name: str
    func: Callable
    params: list[ParamSchema]
    description: str = ""
    module: str = ""
    repo: str = ""

    @property
    def kind(self) -> str:
        return "action"


@dataclass
class ComputedColumnEndpointDefinition:
    id: str
    name: str
    func: Callable
    object_type: str
    columns: list[str]
    params: list[ParamSchema]
    description: str = ""
    module: str = ""
    repo: str = ""

    @property
    def kind(self) -> str:
        return "computed_column"


@dataclass
class StreamingEndpointDefinition:
    id: str
    name: str
    func: Callable[..., Generator[StreamEvent, None, None]]
    params: list[ParamSchema]
    description: str = ""
    module: str = ""
    repo: str = ""

    @property
    def kind(self) -> str:
        return "streaming"


def streaming_endpoint(
    name: str | None = None,
    params: list[dict[str, Any]] | None = None,
    description: str = "",
    endpoint_id: str | None = None,
) -> Callable:
    """Decorator: registers a generator function as a streaming (SSE) endpoint."""

    def decorator(func: Callable) -> Callable:
        ep_name = name or func.__name__
        ep_id = endpoint_id or str(uuid.uuid4())
        parsed_params = _parse_params(params or [])

        defn = StreamingEndpointDefinition(
            id=ep_id,
            name=ep_name,
            func=func,
            params=parsed_params,
            description=description or (func.__doc__ or "").strip(),
            module=func.__module__,
        )
        _ENDPOINT_REGISTRY[ep_id] = defn
        func._forge_endpoint = defn  # type: ignore[attr-defined]
        return func

    return decorator


def action_endpoint(
    name: str | None = None,
    params: list[dict[str, Any]] | None = None,
    description: str = "",
    endpoint_id: str | None = None,
) -> Callable:
    """Decorator: registers a function as an action endpoint."""

    def decorator(func: Callable) -> Callable:
        ep_name = name or func.__name__
        ep_id = endpoint_id or str(uuid.uuid4())
        parsed_params = _parse_params(params or [])

        defn = ActionEndpointDefinition(
            id=ep_id,
            name=ep_name,
            func=func,
            params=parsed_params,
            description=description or (func.__doc__ or "").strip(),
            module=func.__module__,
        )
        _ENDPOINT_REGISTRY[ep_id] = defn
        func._forge_endpoint = defn  # type: ignore[attr-defined]
        return func

    return decorator


def computed_column_endpoint(
    object_type: str,
    columns: list[str],
    params: list[dict[str, Any]] | None = None,
    name: str | None = None,
    description: str = "",
    endpoint_id: str | None = None,
) -> Callable:
    """Decorator: registers a computed column endpoint."""

    def decorator(func: Callable) -> Callable:
        ep_name = name or func.__name__
        ep_id = endpoint_id or str(uuid.uuid4())
        parsed_params = _parse_params(params or [])

        defn = ComputedColumnEndpointDefinition(
            id=ep_id,
            name=ep_name,
            func=func,
            object_type=object_type,
            columns=columns,
            params=parsed_params,
            description=description or (func.__doc__ or "").strip(),
            module=func.__module__,
        )
        _ENDPOINT_REGISTRY[ep_id] = defn
        func._forge_endpoint = defn  # type: ignore[attr-defined]
        return func

    return decorator


def get_endpoint_registry() -> dict[str, Any]:
    return _ENDPOINT_REGISTRY


def _parse_params(raw: list[dict[str, Any]]) -> list[ParamSchema]:
    result = []
    for p in raw:
        if isinstance(p, dict):
            result.append(ParamSchema(
                name=p["name"],
                type=p.get("type", "string"),
                required=p.get("required", True),
                description=p.get("description", ""),
                default=p.get("default"),
            ))
        elif isinstance(p, ParamSchema):
            result.append(p)
    return result
