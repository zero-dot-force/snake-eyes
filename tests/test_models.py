"""Tests for the protocol-shaped data models."""

from __future__ import annotations

import dataclasses

import pytest

from snake_eyes.analysis.effects import SideEffectType
from snake_eyes.analysis.models import Effect, FunctionRecord, function_record_to_dict


def test_function_record_to_dict_omits_none_optionals() -> None:
    effect = Effect(type="StdoutWrite", description="prints")
    record = FunctionRecord(
        name="f", package="pkg.mod", file="pkg/mod.py", line=3, side_effects=(effect,)
    )
    result = function_record_to_dict(record)
    assert result == {
        "name": "f",
        "package": "pkg.mod",
        "file": "pkg/mod.py",
        "line": 3,
        "side_effects": [{"type": "StdoutWrite", "description": "prints"}],
    }
    serialized_effect = result["side_effects"][0]
    assert "location" not in serialized_effect
    assert "target" not in serialized_effect
    assert "detail" not in serialized_effect


def test_function_record_to_dict_includes_optionals_when_set() -> None:
    effect = Effect(
        type="FileSystemWrite",
        description="writes",
        location="mod.py:10:1",
        target="path",
        detail={"mode": "w"},
    )
    record = FunctionRecord("f", "pkg", "pkg/mod.py", 10, (effect,))
    result = function_record_to_dict(record)
    assert result["side_effects"] == [
        {
            "type": "FileSystemWrite",
            "description": "writes",
            "location": "mod.py:10:1",
            "target": "path",
            "detail": {"mode": "w"},
        }
    ]


def test_type_field_is_canonical_string() -> None:
    effect = Effect(type=SideEffectType.StdoutWrite.value, description="x")
    assert effect.type == "StdoutWrite"


def test_effect_is_frozen() -> None:
    effect = Effect(type="StdoutWrite", description="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        effect.description = "changed"


def test_function_record_is_frozen() -> None:
    record = FunctionRecord("f", "pkg", "pkg/mod.py", 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.name = "g"


def test_empty_side_effects_serialize_as_empty_list() -> None:
    record = FunctionRecord("f", "pkg", "pkg/mod.py", 1)
    assert function_record_to_dict(record)["side_effects"] == []
