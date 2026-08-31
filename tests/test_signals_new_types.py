from __future__ import annotations

import pytest

from snake_eyes.analysis.effects import SideEffectType
from snake_eyes.signals import docstring, naming

# The 10 Python-specific SideEffectType values added beyond gaze-py's original
# 38, plus the gaze-py-original ``ClosureCaptureMutation`` -- each paired with
# the closest gaze-py branch it must route to. The naming/docstring extractors
# switch on effect type via ``_routing.effect_category``; a new type must behave
# identically to its closest branch (equivalence), never raise, and never be
# silently dropped when a keyword/prefix applies.
_ROUTING_EQUIVALENCE = [
    (SideEffectType.GeneratorYield, SideEffectType.ReturnValue),
    (SideEffectType.StreamOutput, SideEffectType.ReturnValue),
    (SideEffectType.AsyncGeneratorYield, SideEffectType.ReturnValue),
    (SideEffectType.ErrorSignal, SideEffectType.ErrorReturn),
    (SideEffectType.ContainerMutation, SideEffectType.SliceMutation),
    (SideEffectType.MonkeyPatch, SideEffectType.ReflectionMutation),
    (SideEffectType.DescriptorEffect, SideEffectType.SliceMutation),
    (SideEffectType.ResourceManagement, SideEffectType.SliceMutation),
    (SideEffectType.MetaprogrammingMutation, SideEffectType.SliceMutation),
    (SideEffectType.ImportSideEffect, SideEffectType.SliceMutation),
    (SideEffectType.ClosureCaptureMutation, SideEffectType.ReflectionMutation),
]

_DOC = "Returns, raises, and mutates: appends, updates, yields."


@pytest.mark.parametrize(("new_type", "closest"), _ROUTING_EQUIVALENCE)
def test_naming_routes_new_type_like_closest_branch(
    new_type: SideEffectType, closest: SideEffectType
) -> None:
    assert naming.extract("get_foo", new_type) == naming.extract("get_foo", closest)
    assert naming.extract("set_foo", new_type) == naming.extract("set_foo", closest)


@pytest.mark.parametrize(("new_type", "closest"), _ROUTING_EQUIVALENCE)
def test_docstring_routes_new_type_like_closest_branch(
    new_type: SideEffectType, closest: SideEffectType
) -> None:
    assert docstring.extract(_DOC, new_type) == docstring.extract(_DOC, closest)


def test_unmapped_type_returns_none() -> None:
    # A detector-emitted type with no naming/docstring branch -> no signal
    # (routes to OTHER), never a KeyError.
    assert naming.extract("get_foo", SideEffectType.LogWrite) is None
    assert docstring.extract("writes to the log", SideEffectType.LogWrite) is None
