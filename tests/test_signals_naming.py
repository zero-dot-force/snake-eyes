from __future__ import annotations

from snake_eyes.analysis.effects import SideEffectType
from snake_eyes.signals import naming


def test_accessor_name_with_return_is_positive() -> None:
    result = naming.extract("get_foo", SideEffectType.ReturnValue)
    assert result is not None
    assert result.weight == 15
    assert result.reasoning


def test_accessor_name_with_mutation_is_negative() -> None:
    result = naming.extract("get_foo", SideEffectType.SliceMutation)
    assert result is not None
    assert result.weight == -10


def test_mutator_name_with_mutation_is_positive() -> None:
    result = naming.extract("set_foo", SideEffectType.SliceMutation)
    assert result is not None
    assert result.weight == 15


def test_mutator_name_with_return_is_negative() -> None:
    result = naming.extract("set_foo", SideEffectType.ReturnValue)
    assert result is not None
    assert result.weight == -10


def test_no_prefix_no_signal() -> None:
    assert naming.extract("frobnicate", SideEffectType.ReturnValue) is None
