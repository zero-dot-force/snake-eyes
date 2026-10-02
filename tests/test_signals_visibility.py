from __future__ import annotations

from snake_eyes.signals import visibility
from snake_eyes.signals._types import EnclosingClassVisibility, FunctionSurface


def _extract(
    name: str,
    in_all: bool = False,
    surface: FunctionSurface = FunctionSurface.MODULE,
    enclosing: EnclosingClassVisibility = EnclosingClassVisibility.NONE,
    effect: str = "ReturnValue",
):
    return visibility.extract(name, in_all, surface, enclosing, effect)


def test_public_name_positive_weight() -> None:
    result = _extract("public_fn")
    assert result is not None
    assert result.weight == visibility.PUBLIC_WEIGHT
    assert result.reasoning


def test_private_name_negative_weight() -> None:
    result = _extract("_private")
    assert result is not None
    assert result.weight == visibility.PRIVATE_WEIGHT


def test_public_and_private_weights_differ() -> None:
    pub = _extract("public_fn")
    priv = _extract("_private")
    assert pub is not None
    assert priv is not None
    assert pub.weight != priv.weight


def test_all_membership_marks_public() -> None:
    result = _extract("_exported", in_all=True)
    assert result is not None
    assert result.weight == visibility.PUBLIC_WEIGHT


def test_module_level_dunder_no_signal() -> None:
    assert _extract("__init__") is None


def test_public_class_dunder_method_public() -> None:
    result = _extract(
        "__init__",
        surface=FunctionSurface.METHOD,
        enclosing=EnclosingClassVisibility.PUBLIC,
    )
    assert result is not None
    assert result.weight == visibility.PUBLIC_WEIGHT


def test_private_class_dunder_method_private() -> None:
    result = _extract(
        "__init__",
        surface=FunctionSurface.METHOD,
        enclosing=EnclosingClassVisibility.PRIVATE,
    )
    assert result is not None
    assert result.weight == visibility.PRIVATE_WEIGHT


def test_private_class_method_private_regardless_of_name() -> None:
    result = _extract(
        "run",
        surface=FunctionSurface.METHOD,
        enclosing=EnclosingClassVisibility.PRIVATE,
    )
    assert result is not None
    assert result.weight == visibility.PRIVATE_WEIGHT


def test_public_class_method_public() -> None:
    result = _extract(
        "run",
        surface=FunctionSurface.METHOD,
        enclosing=EnclosingClassVisibility.PUBLIC,
    )
    assert result is not None
    assert result.weight == visibility.PUBLIC_WEIGHT


def test_public_class_private_named_method_private() -> None:
    result = _extract(
        "_helper",
        surface=FunctionSurface.METHOD,
        enclosing=EnclosingClassVisibility.PUBLIC,
    )
    assert result is not None
    assert result.weight == visibility.PRIVATE_WEIGHT


def test_nested_helper_private() -> None:
    result = _extract("helper", surface=FunctionSurface.NESTED)
    assert result is not None
    assert result.weight == visibility.PRIVATE_WEIGHT


def test_nested_closure_capture_no_signal() -> None:
    assert (
        _extract(
            "helper", surface=FunctionSurface.NESTED, effect="ClosureCaptureMutation"
        )
        is None
    )


def test_nested_dunder_private() -> None:
    result = _extract("__x__", surface=FunctionSurface.NESTED)
    assert result is not None
    assert result.weight == visibility.PRIVATE_WEIGHT


def test_gate_values_preserved() -> None:
    assert visibility.PUBLIC_WEIGHT == 10
    assert visibility.PRIVATE_WEIGHT == -10
