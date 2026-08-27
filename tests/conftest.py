"""Shared helpers for the snake-eyes test suite."""

from __future__ import annotations

import json
from typing import Any


def req(method: str, id: int | str = 1, **params: Any) -> str:
    """Serialize a JSON-RPC 2.0 request object to a single-line string."""
    obj: dict[str, Any] = {"jsonrpc": "2.0", "id": id, "method": method}
    if params:
        obj["params"] = params
    return json.dumps(obj)


def responses(output: str) -> list[dict[str, Any]]:
    """Parse each non-empty line of server output as a JSON object."""
    return [json.loads(line) for line in output.splitlines() if line]
