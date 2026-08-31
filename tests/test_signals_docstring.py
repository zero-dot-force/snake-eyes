from __future__ import annotations

from snake_eyes.analysis.effects import SideEffectType
from snake_eyes.signals import docstring


def test_return_keyword_with_return_effect() -> None:
    result = docstring.extract("Returns the answer.", SideEffectType.ReturnValue)
    assert result is not None
    assert result.weight == 15
    assert result.reasoning


def test_error_keyword_with_error_effect() -> None:
    result = docstring.extract(
        "Raises ValueError on bad input.", SideEffectType.ErrorReturn
    )
    assert result is not None
    assert result.weight == 15


def test_no_docstring_no_signal() -> None:
    assert docstring.extract(None, SideEffectType.ReturnValue) is None
    assert docstring.extract("", SideEffectType.ReturnValue) is None


def test_mismatched_docstring_no_signal() -> None:
    assert docstring.extract("A short summary.", SideEffectType.ReturnValue) is None
