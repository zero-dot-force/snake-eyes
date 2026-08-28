"""Protocol-shaped data models for the analyze payload.

These dataclasses mirror the Gaze protocol v1.1.0 analyze payload shape, not
gaze-py's internal model. Optional fields are omitted from serialization when
unset so that Gaze-side optional fields remain genuinely optional.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Effect:
    """A single observable side effect.

    ``location`` is a ``"file.py:line:col"`` string relative to the analysis
    root; ``target`` names the attribute/parameter/exception involved; and
    ``detail`` carries opaque metadata. All three are optional.
    """

    type: str
    description: str
    location: str | None = None
    target: str | None = None
    detail: dict[str, Any] | None = None


@dataclass(frozen=True)
class FunctionRecord:
    """A function and its observed side effects.

    ``package`` is the dotted module path, ``file`` is the path relative to
    ``root_path`` with POSIX separators, and ``line`` is the 1-based ``def``
    line number.
    """

    name: str
    package: str
    file: str
    line: int
    side_effects: tuple[Effect, ...] = ()


def function_record_to_dict(record: FunctionRecord) -> dict[str, Any]:
    """Serialize a ``FunctionRecord`` to a JSON-ready dict.

    Optional ``Effect`` fields (``location``, ``target``, ``detail``) are
    omitted when ``None``. ``side_effects`` is serialized as a list.
    """
    effects: list[dict[str, Any]] = []
    for effect in record.side_effects:
        serialized: dict[str, Any] = {
            "type": effect.type,
            "description": effect.description,
        }
        if effect.location is not None:
            serialized["location"] = effect.location
        if effect.target is not None:
            serialized["target"] = effect.target
        if effect.detail is not None:
            serialized["detail"] = effect.detail
        effects.append(serialized)
    return {
        "name": record.name,
        "package": record.package,
        "file": record.file,
        "line": record.line,
        "side_effects": effects,
    }
