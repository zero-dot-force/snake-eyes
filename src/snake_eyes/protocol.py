"""JSON-RPC 2.0 protocol types, constants, and serialization for snake-eyes."""

from __future__ import annotations

import dataclasses
import json
import sys
from dataclasses import dataclass
from typing import Any

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

PROTOCOL_VERSION = "1.1.0"
ANALYZER_NAME = "snake-eyes"
LANGUAGE = "python"


@dataclass
class JsonRpcRequest:
    """A JSON-RPC 2.0 request envelope."""

    jsonrpc: str
    id: int | str | None
    method: str
    params: dict[str, Any] | None


@dataclass
class JsonRpcSuccess:
    """A JSON-RPC 2.0 success response envelope."""

    id: int | str | None
    result: dict[str, Any] | None
    jsonrpc: str = "2.0"


@dataclass
class JsonRpcErrorBody:
    """The body of a JSON-RPC 2.0 error response."""

    code: int
    message: str
    data: object | None = None


@dataclass
class JsonRpcError:
    """A JSON-RPC 2.0 error response envelope."""

    id: int | str | None
    error: JsonRpcErrorBody
    jsonrpc: str = "2.0"


def initialize_result() -> dict[str, Any]:
    """Build the ``initialize`` result dict per protocol v1.1.0."""
    major, minor, micro = sys.version_info[:3]
    return {
        "analyzer_name": ANALYZER_NAME,
        "language": LANGUAGE,
        "language_version": f"{major}.{minor}.{micro}",
        "protocol_version": PROTOCOL_VERSION,
        "capabilities": {
            "discover": False,
            "test_mapping": False,
            "classify_signals": False,
            "streaming": False,
        },
    }


def shutdown_result() -> dict[str, Any]:
    """Build the ``shutdown`` result dict (empty object)."""
    return {}


def to_dict(obj: Any) -> Any:
    """Convert a protocol dataclass into a JSON-ready dict.

    The optional ``data`` field of a ``JsonRpcErrorBody`` is omitted when it
    is ``None``; the protocol forbids emitting JSON ``null`` for an omitted
    field.
    """
    if dataclasses.is_dataclass(obj):
        result: dict[str, Any] = {}
        for field in dataclasses.fields(obj):
            value = getattr(obj, field.name)
            if field.name == "data" and value is None:
                continue
            result[field.name] = to_dict(value)
        return result
    if isinstance(obj, dict):
        return {key: to_dict(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [to_dict(item) for item in obj]
    return obj


def to_json(obj: Any) -> str:
    """Serialize a protocol object to a single-line JSON string."""
    return json.dumps(to_dict(obj))
