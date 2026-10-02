"""Tests for the signal adapter (signals/adapter.py) fan-out and dict shape."""

from __future__ import annotations

import ast
from pathlib import Path

from snake_eyes.signals import adapter, extract_signals
from snake_eyes.signals._types import EnclosingClassVisibility, FunctionSurface

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
_FORBIDDEN_LABELS = {"contractual", "incidental", "ambiguous", "unclaimed"}


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
    assert len([s for s in signals if s["source"] == "visibility"]) == 2


def test_extract_signals_orders_returned_projection(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text(
        "def get_z():\n"
        '    """Return z."""\n'
        "    return 'z'\n\n"
        "def get_a():\n"
        '    """Return a."""\n'
        "    return 'a'\n"
    )

    signals = extract_signals(str(tmp_path), None)

    assert [
        (
            signal["package"],
            signal["function"],
            signal["side_effect_type"],
            signal["source"],
        )
        for signal in signals
    ] == [
        ("m", "get_a", "ReturnValue", "docstring"),
        ("m", "get_a", "ReturnValue", "naming_convention"),
        ("m", "get_a", "ReturnValue", "visibility"),
        ("m", "get_z", "ReturnValue", "docstring"),
        ("m", "get_z", "ReturnValue", "naming_convention"),
        ("m", "get_z", "ReturnValue", "visibility"),
    ]


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
    assert {s["source"] for s in signals} == _ALLOWED_SOURCES


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


def _parents(source: str) -> tuple[ast.Module, dict[ast.AST, ast.AST]]:
    tree = ast.parse(source)
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return tree, parents


def _func(tree: ast.Module, name: str) -> ast.AST:
    return next(
        n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
    )


def _cls(tree: ast.Module, name: str) -> ast.ClassDef:
    return next(
        n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == name
    )


def test_function_surface_module_method_nested() -> None:
    tree, parents = _parents(
        "class C:\n"
        "    def m(self):\n"
        "        return 1\n"
        "def outer():\n"
        "    def inner():\n"
        "        return 2\n"
        "def top():\n"
        "    return 3\n"
    )
    assert (
        adapter._function_surface(_func(tree, "m"), parents) is FunctionSurface.METHOD
    )
    assert (
        adapter._function_surface(_func(tree, "inner"), parents)
        is FunctionSurface.NESTED
    )
    assert (
        adapter._function_surface(_func(tree, "top"), parents) is FunctionSurface.MODULE
    )


def test_method_on_class_inside_function_is_method() -> None:
    tree, parents = _parents(
        "def factory():\n"
        "    class Worker:\n"
        "        def run(self):\n"
        "            return 1\n"
    )
    assert (
        adapter._function_surface(_func(tree, "run"), parents) is FunctionSurface.METHOD
    )


def test_enclosing_class_visibility() -> None:
    tree, parents = _parents(
        "class Worker:\n"
        "    def run(self):\n"
        "        return 1\n"
        "class _Worker:\n"
        "    def run(self):\n"
        "        return 2\n"
        "def factory():\n"
        "    class Local:\n"
        "        def run(self):\n"
        "            return 3\n"
        "class Outer:\n"
        "    class Inner:\n"
        "        def run(self):\n"
        "            return 4\n"
    )
    assert (
        adapter._enclosing_class_visibility(_cls(tree, "Worker"), parents)
        is EnclosingClassVisibility.PUBLIC
    )
    assert (
        adapter._enclosing_class_visibility(_cls(tree, "_Worker"), parents)
        is EnclosingClassVisibility.PRIVATE
    )
    assert (
        adapter._enclosing_class_visibility(_cls(tree, "Local"), parents)
        is EnclosingClassVisibility.PRIVATE
    )
    assert (
        adapter._enclosing_class_visibility(_cls(tree, "Inner"), parents)
        is EnclosingClassVisibility.PUBLIC
    )


def test_enclosing_class_visibility_transitive_and_private_class() -> None:
    tree, parents = _parents(
        "def factory():\n"
        "    class Mid:\n"
        "        class Deep:\n"
        "            def run(self):\n"
        "                return 1\n"
        "class _Outer:\n"
        "    class Pub:\n"
        "        def run(self):\n"
        "            return 2\n"
    )
    # A class transitively nested inside a function is private (an ancestor is a
    # FunctionDef).
    assert (
        adapter._enclosing_class_visibility(_cls(tree, "Deep"), parents)
        is EnclosingClassVisibility.PRIVATE
    )
    # A class nested inside a private class does not inherit private (direct name
    # decides).
    assert (
        adapter._enclosing_class_visibility(_cls(tree, "Pub"), parents)
        is EnclosingClassVisibility.PUBLIC
    )


def test_function_surface_async_defs() -> None:
    tree, parents = _parents(
        "class C:\n"
        "    async def am(self):\n"
        "        return 1\n"
        "async def outer():\n"
        "    async def inner():\n"
        "        return 2\n"
    )
    assert (
        adapter._function_surface(_func(tree, "am"), parents) is FunctionSurface.METHOD
    )
    assert (
        adapter._function_surface(_func(tree, "inner"), parents)
        is FunctionSurface.NESTED
    )


def test_enclosing_class_returns_none_for_nested_and_module() -> None:
    tree, parents = _parents(
        "def top():\n    return 1\ndef outer():\n    def inner():\n        return 2\n"
    )
    # A module-level function walks to the Module and returns None (fallthrough).
    assert adapter._enclosing_class(_func(tree, "top"), parents) is None
    # A nested function hits the enclosing FunctionDef and returns None.
    assert adapter._enclosing_class(_func(tree, "inner"), parents) is None


def test_function_surface_control_flow_and_fallthrough() -> None:
    tree, parents = _parents("if True:\n    def cond():\n        return 1\n")
    # A function inside an if-block walks past the If node to the Module.
    assert (
        adapter._function_surface(_func(tree, "cond"), parents)
        is FunctionSurface.MODULE
    )
    # A node absent from the parents map falls through to MODULE.
    assert adapter._function_surface(_func(tree, "cond"), {}) is FunctionSurface.MODULE


def test_enclosing_class_visibility_fallthrough() -> None:
    tree, _parents_map = _parents("class C:\n    pass\n")
    # A classdef absent from the parents map falls through to PUBLIC.
    assert (
        adapter._enclosing_class_visibility(_cls(tree, "C"), {})
        is EnclosingClassVisibility.PUBLIC
    )
