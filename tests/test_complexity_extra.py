"""Extra complexity tests to raise coverage above targets.

validates: gaze analyzer protocol v1.1.0
"""

from __future__ import annotations

import unittest.mock as mock
from pathlib import Path

from snake_eyes.analysis.complexity import compute_complexity


def test_complexity_async_function(tmp_path: Path) -> None:
    """Async functions get a complexity entry."""
    code = "async def fetch(url):\n    return url\n"
    (tmp_path / "async_mod.py").write_text(code)
    entries = compute_complexity(str(tmp_path), None)
    names = [e["name"] for e in entries]
    assert "fetch" in names
    fetch_entry = next(e for e in entries if e["name"] == "fetch")
    assert fetch_entry["complexity"] >= 1


def test_complexity_async_nested(tmp_path: Path) -> None:
    """Nested async functions each get separate entries."""
    code = (
        "async def outer():\n"
        "    async def inner():\n"
        "        return 1\n"
        "    return inner\n"
    )
    (tmp_path / "async_nested.py").write_text(code)
    entries = compute_complexity(str(tmp_path), None)
    names = [e["name"] for e in entries]
    assert "outer" in names
    assert "inner" in names


def test_complexity_async_with(tmp_path: Path) -> None:
    """async with adds +1 to complexity."""
    code = "async def f():\n    async with open('x') as fp:\n        pass\n"
    (tmp_path / "async_with.py").write_text(code)
    entries = compute_complexity(str(tmp_path), None)
    entry = next(e for e in entries if e["name"] == "f")
    assert entry["complexity"] >= 2  # base 1 + async with


def test_complexity_async_for(tmp_path: Path) -> None:
    """async for adds +1 to complexity."""
    code = "async def f(items):\n    async for x in items:\n        pass\n"
    (tmp_path / "async_for.py").write_text(code)
    entries = compute_complexity(str(tmp_path), None)
    entry = next(e for e in entries if e["name"] == "f")
    assert entry["complexity"] >= 2  # base 1 + async for


def test_complexity_depth_exceeded_in_visitor(tmp_path: Path) -> None:
    """_ComplexityVisitor depth exceeded triggers RecursionError → file skipped."""
    # Create a function with very deeply nested defs to exceed visitor depth
    # The visitor depth is incremented per FunctionDef/AsyncFunctionDef call
    # 201+ levels of nesting should exceed the 200-depth limit
    depth = 210
    lines = ["def f0():"]
    for i in range(1, depth):
        indent = "    " * i
        lines.append(f"{indent}def f{i}():")
    # last level
    indent = "    " * depth
    lines.append(f"{indent}pass")
    code = "\n".join(lines) + "\n"
    (tmp_path / "deeply_nested.py").write_text(code)
    (tmp_path / "good.py").write_text("def ok(): pass\n")

    # Should not raise — skip-and-continue
    entries = compute_complexity(str(tmp_path), None)
    names = [e["name"] for e in entries]
    # ok() must still appear
    assert "ok" in names


def test_complexity_many_functions(tmp_path: Path) -> None:
    """Many functions in a single file all get entries."""
    lines = [f"def func_{i}(): pass" for i in range(20)]
    (tmp_path / "many.py").write_text("\n".join(lines) + "\n")
    entries = compute_complexity(str(tmp_path), None)
    names = {e["name"] for e in entries}
    for i in range(20):
        assert f"func_{i}" in names


def test_complexity_class_method(tmp_path: Path) -> None:
    """Class methods get complexity entries."""
    code = (
        "class MyClass:\n"
        "    def method(self, x):\n"
        "        if x:\n"
        "            return x\n"
        "        return None\n"
    )
    (tmp_path / "cls.py").write_text(code)
    entries = compute_complexity(str(tmp_path), None)
    names = [e["name"] for e in entries]
    assert "method" in names
    entry = next(e for e in entries if e["name"] == "method")
    assert entry["complexity"] >= 2  # base 1 + if


def test_complexity_visitor_recursion_error_skips_file(tmp_path: Path) -> None:
    """RecursionError in visitor triggers except BROADENED_EXCEPTIONS skip.

    Targets the except block in compute_complexity and _check_depth raise.
    Uses AST manipulation to create a 210-level nested FunctionDef tree
    that cannot be produced by ast.parse (parser rejects deep indentation).
    """
    import ast

    from snake_eyes.analysis import complexity as cplx_mod

    (tmp_path / "good.py").write_text("def ok(): return 1\n")

    # Build a 210-deep nested FunctionDef tree in memory.
    depth = 210

    def _make_nested(d: int) -> ast.FunctionDef:
        inner: ast.stmt = ast.Pass()
        for i in range(d, 0, -1):
            inner = ast.FunctionDef(
                name=f"f{i}",
                args=ast.arguments(
                    posonlyargs=[],
                    args=[],
                    kwonlyargs=[],
                    kw_defaults=[],
                    defaults=[],
                ),
                body=[inner],
                decorator_list=[],
                lineno=i + 1,
                col_offset=i * 4,
            )
        assert isinstance(inner, ast.FunctionDef)
        return inner

    deep_func = _make_nested(depth)
    ast.fix_missing_locations(deep_func)
    deep_module = ast.Module(body=[deep_func], type_ignores=[])
    ast.fix_missing_locations(deep_module)

    original_iter = cplx_mod.iter_source_files

    yielded: list[int] = [0]

    def mock_iter(root_path: str, rel_paths: list[str]) -> object:
        # Yield the deeply-nested tree first (triggers RecursionError in visitor),
        # then fall through to the real implementation for remaining files.
        if yielded[0] == 0:
            yielded[0] += 1
            yield "deep.py", "", deep_module
        yield from original_iter(root_path, [p for p in rel_paths if p != "deep.py"])

    with mock.patch.object(cplx_mod, "iter_source_files", mock_iter):
        entries = compute_complexity(str(tmp_path), None)

    # deep.py is skipped due to RecursionError; good.py must still appear
    names = [e["name"] for e in entries]
    assert "ok" in names, (
        "good.py must still be processed after the RecursionError skip"
    )
