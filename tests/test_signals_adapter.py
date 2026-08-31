"""Tests for the signal adapter (signals/adapter.py) fan-out and dict shape."""

from __future__ import annotations

from pathlib import Path

from snake_eyes.signals import extract_signals

_ALLOWED_SOURCES = {
    "interface",
    "visibility",
    "caller_count",
    "naming_convention",
    "docstring",
}
_SIGNAL_KEYS = {
    "function",
    "package",
    "side_effect_type",
    "source",
    "weight",
    "reasoning",
}
_FORBIDDEN_LABELS = {"contractual", "incidental", "ambiguous"}


def test_extract_signals_shape_and_error_effect(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text(
        "def get_value(a, b):\n"
        '    """Return the value; raises ValueError on bad input."""\n'
        "    if a:\n"
        "        raise ValueError\n"
        "    return b\n"
    )
    signals = extract_signals(str(tmp_path), None)
    assert signals, "expected at least one signal"
    for signal in signals:
        assert set(signal) == _SIGNAL_KEYS
        assert "name" not in signal
        assert signal["source"] in _ALLOWED_SOURCES
        assert isinstance(signal["weight"], int)
        assert isinstance(signal["reasoning"], str)
        assert signal["reasoning"]
        assert signal["function"] == "get_value"
        assert "classification" not in signal
        assert signal["side_effect_type"] not in _FORBIDDEN_LABELS
    assert any(s["side_effect_type"] in {"ErrorReturn", "ErrorSignal"} for s in signals)


def test_extract_signals_empty_project(tmp_path: Path) -> None:
    assert extract_signals(str(tmp_path), None) == []


def test_extract_signals_not_deduplicated(tmp_path: Path) -> None:
    # pick() has two return statements -> two ReturnValue effects, so each
    # function-level source (visibility, docstring, ...) emits the same
    # (function, side_effect_type, source) twice. Raw output must NOT merge them.
    (tmp_path / "m.py").write_text(
        "def pick(x):\n"
        '    """Return a chosen value."""\n'
        "    if x:\n"
        "        return 1\n"
        "    return 2\n"
    )
    signals = extract_signals(str(tmp_path), None)
    keys = [(s["function"], s["side_effect_type"], s["source"]) for s in signals]
    assert keys.count(("pick", "ReturnValue", "visibility")) == 2


def test_extract_signals_covers_all_sources(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text(
        '__all__ = ["Repo", "get_record"]\n'
        "import abc\n"
        "\n"
        "\n"
        "class Repo(abc.ABC):\n"
        "    def get_record(self):\n"
        '        """Return the record."""\n'
        "        return self._record\n"
        "\n"
        "\n"
        "def get_record(a):\n"
        '    """Return the value."""\n'
        "    return a\n"
        "\n"
        "\n"
        "def use_a():\n"
        "    return get_record(1)\n"
        "\n"
        "\n"
        "def use_b():\n"
        "    return get_record(2)\n"
    )
    signals = extract_signals(str(tmp_path), None)
    sources = {s["source"] for s in signals}
    assert sources == _ALLOWED_SOURCES


def test_extract_signals_handles_metaclass_annassign_and_nested(
    tmp_path: Path,
) -> None:
    # Exercises the adapter's defensive branches: an annotated __all__ with a
    # non-string element, a metaclass= keyword base, and a nested function.
    (tmp_path / "m.py").write_text(
        "import abc\n"
        "\n"
        '__all__: list[str] = ["Meta", 123]\n'
        "\n"
        "\n"
        "class Meta(metaclass=abc.ABCMeta):\n"
        "    def get_meta(self):\n"
        '        """Return meta."""\n'
        "        return self._m\n"
        "\n"
        "\n"
        "def outer():\n"
        "    def inner():\n"
        "        return 1\n"
        "\n"
        "    return inner()\n"
    )
    signals = extract_signals(str(tmp_path), None)
    # metaclass=abc.ABCMeta -> interface fires on get_meta's ReturnValue effect.
    assert "interface" in {s["source"] for s in signals}


def test_extract_signals_covers_expr_name_and_non_all_assign(
    tmp_path: Path,
) -> None:
    # Exercises _expr_name's bare-Name branch, its non-Name/non-Attribute
    # (Subscript) branch, and _extract_all's module-level non-__all__ assignment
    # branch. Static AST only -- the module is never imported, so Base[int]
    # being non-subscriptable at runtime is irrelevant.
    (tmp_path / "m.py").write_text(
        "from abc import ABC\n"
        "\n"
        "VERSION = 1\n"
        "\n"
        "\n"
        "class Base(ABC):\n"
        "    def get_a(self):\n"
        '        """Return a."""\n'
        "        return self._a\n"
        "\n"
        "\n"
        "class Weird(Base[int]):\n"
        "    def get_b(self):\n"
        '        """Return b."""\n'
        "        return self._b\n"
    )
    signals = extract_signals(str(tmp_path), None)
    # Bare-Name base ``ABC`` resolves via _expr_name -> interface fires.
    assert "interface" in {s["source"] for s in signals}
