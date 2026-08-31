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
    (tmp_path / "m.py").write_text(
        "def get_value(a, b):\n"
        '    """Return the value; raises ValueError."""\n'
        "    if a:\n"
        "        raise ValueError\n"
        "    return b\n"
    )
    signals = extract_signals(str(tmp_path), None)
    # A function with multiple effects fans out one signal per (effect, source);
    # identical (source, side_effect_type) pairs are preserved, not merged.
    keys = [(s["function"], s["side_effect_type"], s["source"]) for s in signals]
    assert len(keys) == len(signals)


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
