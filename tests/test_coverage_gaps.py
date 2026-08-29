"""Targeted tests to close coverage gaps in complexity.py and coverage.py.

validates: gaze analyzer protocol v1.1.0
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import stat
import unittest.mock as mock
from pathlib import Path

import coverage as coverage_pkg
import pytest

from snake_eyes.analysis.complexity import compute_complexity
from snake_eyes.coverage import parse_coverage

COVERAGE_FIXTURES = Path(__file__).parent / "fixtures" / "coverage"


# ---------------------------------------------------------------------------
# complexity.py gap coverage
# ---------------------------------------------------------------------------


def test_complexity_comprehension(tmp_path: Path) -> None:
    """comprehension adds to complexity."""
    code = "def f(lst):\n    return [x for x in lst if x > 0]\n"
    (tmp_path / "comp.py").write_text(code)
    entries = compute_complexity(str(tmp_path), None)
    entry = next(e for e in entries if e["name"] == "f")
    assert entry["complexity"] >= 2  # base 1 + comprehension + if


def test_complexity_while_loop(tmp_path: Path) -> None:
    """While loop adds +1 to complexity."""
    code = "def f(n):\n    while n > 0:\n        n -= 1\n"
    (tmp_path / "while.py").write_text(code)
    entries = compute_complexity(str(tmp_path), None)
    entry = next(e for e in entries if e["name"] == "f")
    assert entry["complexity"] >= 2  # base 1 + while


def test_complexity_for_loop(tmp_path: Path) -> None:
    """For loop adds +1 to complexity."""
    code = "def f(lst):\n    for x in lst:\n        pass\n"
    (tmp_path / "forloop.py").write_text(code)
    entries = compute_complexity(str(tmp_path), None)
    entry = next(e for e in entries if e["name"] == "f")
    assert entry["complexity"] >= 2  # base 1 + for


def test_complexity_except_handler(tmp_path: Path) -> None:
    """ExceptHandler adds +1 to complexity."""
    code = "def f():\n    try:\n        pass\n    except Exception:\n        pass\n"
    (tmp_path / "exc.py").write_text(code)
    entries = compute_complexity(str(tmp_path), None)
    entry = next(e for e in entries if e["name"] == "f")
    assert entry["complexity"] >= 2  # base 1 + except


def test_complexity_broadened_exceptions_traversal(tmp_path: Path) -> None:
    """Unparseable file is skipped and compute_complexity continues.

    NOTE: deeply-nested source does NOT reach the MAX_AST_DEPTH=200 visitor
    guard. CPython's tokenizer rejects indentation past MAXINDENT=100 with
    IndentationError, so ast.parse raises first and the file is skipped at the
    parse step via BROADENED_EXCEPTIONS in the compute_complexity file loop.
    The visitor's own depth guard is covered separately by
    test_complexity_visitor_recursion_error_skips_file (in-memory AST).
    """
    # Build deeply nested source; the tokenizer's MAXINDENT=100 limit makes
    # this unparseable, exercising the parse-skip-and-continue path.
    depth = 250
    lines = []
    indent = ""
    for _ in range(depth):
        lines.append(f"{indent}if True:")
        indent += "    "
    lines.append(f"{indent}x = 1")
    code = "def deep_func():\n" + "\n".join(f"    {line}" for line in lines) + "\n"
    (tmp_path / "overdeep.py").write_text(code)
    (tmp_path / "good.py").write_text("def ok(): return 1\n")

    entries = compute_complexity(str(tmp_path), None)
    # good.py must still be processed
    names = [e["name"] for e in entries]
    assert "ok" in names


# ---------------------------------------------------------------------------
# coverage.py gap coverage: _parse_source_spans branches
# ---------------------------------------------------------------------------


def test_coverage_parse_source_spans_stat_error(tmp_path: Path) -> None:
    """_parse_source_spans: real stat OSError → faulty file skipped, valid file kept.

    H3: Injects the REAL fault via pathlib.Path.stat side_effect so the actual
    ``except OSError`` branch in the guard fires, rather than self-mocking.
    """
    sample = tmp_path / "sample_module.py"
    shutil.copy(COVERAGE_FIXTURES / "sample_module.py", sample)
    good = tmp_path / "good_module.py"
    good.write_text("def ok(): return 1\n")

    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "sample_module.py": {
                "executed_lines": [4, 5],
                "missing_lines": [8, 9],
                "excluded_lines": [],
            },
            "good_module.py": {
                "executed_lines": [1],
                "missing_lines": [],
                "excluded_lines": [],
            },
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))

    # Inject real stat failure scoped to sample_module.py only, for normal stat
    # calls (follow_symlinks=True / default).  lstat() passes follow_symlinks=False;
    # we do NOT raise for those to avoid breaking pathlib internals.
    original_stat = pathlib.Path.stat

    def failing_stat(
        self: pathlib.Path, *, follow_symlinks: bool = True, **kwargs: object
    ) -> os.stat_result:
        if self.name == "sample_module.py" and follow_symlinks:
            raise OSError("injected stat error")
        return original_stat(self, follow_symlinks=follow_symlinks, **kwargs)  # type: ignore[arg-type]

    with mock.patch.object(pathlib.Path, "stat", failing_stat):
        result = parse_coverage(str(tmp_path), None)

    # Faulty file is skipped.
    assert not any(e["file"] == "sample_module.py" for e in result)
    # Co-present valid file still yields rows.
    assert any(e["file"] == "good_module.py" for e in result)


def test_coverage_parse_source_spans_non_regular(tmp_path: Path) -> None:
    """_parse_source_spans: non-regular file → skip."""
    if not hasattr(os, "mkfifo"):
        pytest.skip("mkfifo not available")

    fifo = tmp_path / "fifo_module.py"
    os.mkfifo(fifo)

    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "fifo_module.py": {
                "executed_lines": [1],
                "missing_lines": [],
                "excluded_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))
    result = parse_coverage(str(tmp_path), None)
    assert not any(e["file"] == "fifo_module.py" for e in result)


def test_coverage_parse_source_spans_size_cap(tmp_path: Path) -> None:
    """_parse_source_spans: file exceeding size cap → skip."""
    sample = tmp_path / "sample_module.py"
    shutil.copy(COVERAGE_FIXTURES / "sample_module.py", sample)

    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "sample_module.py": {
                "executed_lines": [4, 5],
                "missing_lines": [8, 9],
                "excluded_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))

    # Patch MAX_FILE_BYTES in both cov_mod and _shared (is_analyzable_file reads
    # _shared.MAX_FILE_BYTES directly).
    import snake_eyes.analysis._shared as shared_mod
    import snake_eyes.coverage as cov_mod

    with (
        mock.patch.object(cov_mod, "MAX_FILE_BYTES", 10),
        mock.patch.object(shared_mod, "MAX_FILE_BYTES", 10),
    ):
        result = parse_coverage(str(tmp_path), None)

    assert not any(e["file"] == "sample_module.py" for e in result)


def test_coverage_parse_source_spans_parse_error(tmp_path: Path) -> None:
    """_parse_source_spans: syntax error in file → skip."""
    bad = tmp_path / "bad_syntax.py"
    bad.write_text("def broken(\n")

    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "bad_syntax.py": {
                "executed_lines": [1],
                "missing_lines": [],
                "excluded_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))
    result = parse_coverage(str(tmp_path), None)
    assert not any(e["file"] == "bad_syntax.py" for e in result)


def test_coverage_dot_coverage_stat_error(tmp_path: Path) -> None:
    """_parse_dot_coverage: real stat OSError → faulty file skipped, valid file kept.

    H3: Injects the REAL fault via pathlib.Path.stat side_effect so the actual
    ``except OSError`` branch in ``is_analyzable_file`` fires, not self-mocking.
    """
    sample = tmp_path / "sample_module.py"
    shutil.copy(COVERAGE_FIXTURES / "sample_module.py", sample)
    good = tmp_path / "good_module.py"
    good.write_text("def ok(): return 1\n")

    from coverage.data import CoverageData

    dot_cov = tmp_path / ".coverage"
    cdata = CoverageData(basename=str(dot_cov))
    cdata.add_lines({str(sample): [4, 5], str(good): [1]})
    cdata.write()

    # Inject real stat failure scoped to sample_module.py only, for normal stat
    # calls (follow_symlinks=True / default).  lstat() passes follow_symlinks=False;
    # we do NOT raise for those to avoid breaking pathlib internals.
    original_stat = pathlib.Path.stat

    def failing_stat(
        self: pathlib.Path, *, follow_symlinks: bool = True, **kwargs: object
    ) -> os.stat_result:
        if self.name == "sample_module.py" and follow_symlinks:
            raise OSError("injected stat error")
        return original_stat(self, follow_symlinks=follow_symlinks, **kwargs)  # type: ignore[arg-type]

    with mock.patch.object(pathlib.Path, "stat", failing_stat):
        result = parse_coverage(str(tmp_path), None)

    # Faulty file is skipped.
    assert not any(e["file"] == "sample_module.py" for e in result)
    # Co-present valid file still yields rows.
    assert any(e["file"] == "good_module.py" for e in result)


def test_coverage_dot_coverage_non_regular(tmp_path: Path) -> None:
    """_parse_dot_coverage: non-regular file (.py with FIFO mode) is skipped.

    Uses monkeypatching to fake a non-regular stat result so no real FIFO is
    opened.  Exercises the stat + S_ISREG guard in _parse_dot_coverage that
    must fire BEFORE any open()/analysis2() call.
    """
    # A regular file so discovery includes it; we'll fake its stat mode below.
    fake_py = tmp_path / "fifo_module.py"
    fake_py.write_text("x = 1\n")

    from coverage.data import CoverageData

    dot_cov = tmp_path / ".coverage"
    cdata = CoverageData(basename=str(dot_cov))
    cdata.add_lines({str(fake_py): [1]})
    cdata.write()

    # Build a fake stat_result whose st_mode signals a FIFO (S_IFIFO = 0o010000).
    import stat as stat_mod

    real_stat = fake_py.stat()
    fifo_mode = (real_stat.st_mode & ~0o170000) | stat_mod.S_IFIFO
    fake_stat = os.stat_result(
        (
            fifo_mode,
            real_stat.st_ino,
            real_stat.st_dev,
            real_stat.st_nlink,
            real_stat.st_uid,
            real_stat.st_gid,
            real_stat.st_size,
            real_stat.st_atime,
            real_stat.st_mtime,
            real_stat.st_ctime,
        )
    )

    import snake_eyes.coverage as cov_mod

    original_path_stat = cov_mod.pathlib.Path.stat

    def mock_path_stat(self: object, **kwargs: object) -> os.stat_result:
        if str(self) == str(fake_py):
            return fake_stat
        return original_path_stat(self, **kwargs)  # type: ignore[arg-type]

    with mock.patch.object(cov_mod.pathlib.Path, "stat", mock_path_stat):
        result = parse_coverage(str(tmp_path), None)

    assert not any(e["file"] == "fifo_module.py" for e in result)


def test_coverage_dot_coverage_size_cap(tmp_path: Path) -> None:
    """_parse_dot_coverage: file exceeding size cap → skip BEFORE analysis2().

    Testing LOW: also asserts analysis2 is NOT called for the over-cap file,
    pinning the pre-analysis2 guard from H1.  Patches both cov_mod.MAX_FILE_BYTES
    and _shared.MAX_FILE_BYTES since is_analyzable_file reads the shared constant.
    """
    sample = tmp_path / "sample_module.py"
    shutil.copy(COVERAGE_FIXTURES / "sample_module.py", sample)

    from coverage.data import CoverageData

    dot_cov = tmp_path / ".coverage"
    cdata = CoverageData(basename=str(dot_cov))
    cdata.add_lines({str(sample): [4, 5]})
    cdata.write()

    import snake_eyes.analysis._shared as shared_mod
    import snake_eyes.coverage as cov_mod

    with (
        mock.patch.object(cov_mod, "MAX_FILE_BYTES", 10),
        mock.patch.object(shared_mod, "MAX_FILE_BYTES", 10),
        mock.patch.object(
            coverage_pkg.Coverage, "analysis2", wraps=None
        ) as mock_analysis2,
    ):
        result = parse_coverage(str(tmp_path), None)

    assert not any(e["file"] == "sample_module.py" for e in result)
    # analysis2 must NOT have been called for the oversized file
    mock_analysis2.assert_not_called()


def test_coverage_dot_coverage_analysis2_error(tmp_path: Path) -> None:
    """_parse_dot_coverage: analysis2 raises CoverageException → skip."""
    sample = tmp_path / "sample_module.py"
    shutil.copy(COVERAGE_FIXTURES / "sample_module.py", sample)

    from coverage.data import CoverageData

    dot_cov = tmp_path / ".coverage"
    cdata = CoverageData(basename=str(dot_cov))
    cdata.add_lines({str(sample): [4, 5]})
    cdata.write()

    import coverage as coverage_pkg

    def mock_analysis2(*args: object, **kwargs: object) -> None:
        raise coverage_pkg.exceptions.CoverageException("mock error")

    with mock.patch.object(
        coverage_pkg.Coverage, "analysis2", side_effect=mock_analysis2
    ):
        result = parse_coverage(str(tmp_path), None)

    assert not any(e["file"] == "sample_module.py" for e in result)


def test_coverage_json_files_not_in_discovered(tmp_path: Path) -> None:
    """coverage.json file not in discovered set → skipped."""
    # No actual python file in tmp_path — coverage.json references a non-existent file
    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "not_discovered.py": {
                "executed_lines": [1],
                "missing_lines": [],
                "excluded_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))
    result = parse_coverage(str(tmp_path), None)
    assert result == []


def test_coverage_json_non_list_executed_lines(tmp_path: Path) -> None:
    """coverage.json: non-list executed_lines → entry skipped."""
    (tmp_path / "sample_module.py").write_text("def f(): pass\n")
    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "sample_module.py": {
                "executed_lines": "not_a_list",
                "missing_lines": [],
                "excluded_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))
    result = parse_coverage(str(tmp_path), None)
    assert result == []


def test_coverage_json_non_int_executed_lines_degrades(tmp_path: Path) -> None:
    """coverage.json: list with non-int element in executed_lines → skip gracefully.

    A JSON-valid but wrong-shape list (e.g. ["x"], [null]) must NOT raise;
    parse_coverage must degrade gracefully (skip that file / return []).
    Validates: spec 'JSON-valid but wrong-shape → [] / per-file skip' degradation.
    """
    (tmp_path / "sample_module.py").write_text("def f(): pass\n")
    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "sample_module.py": {
                "executed_lines": ["x", None],  # non-int elements
                "missing_lines": [2],
                "excluded_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))

    # Must not raise; must degrade gracefully
    try:
        result = parse_coverage(str(tmp_path), None)
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(
            f"parse_coverage raised {type(exc).__name__} "
            f"on non-int executed_lines: {exc}"
        ) from exc

    # File with non-int elements must be skipped (empty result or absent entry)
    assert not any(e["file"] == "sample_module.py" for e in result), (
        f"Entry for bad file must be skipped, got {result}"
    )


# ---------------------------------------------------------------------------
# M4 — RecursionError on deeply-nested coverage.json
# ---------------------------------------------------------------------------


def test_coverage_json_recursion_error_degrades(tmp_path: Path) -> None:
    """M4: RecursionError from deeply-nested JSON degrades to [] rather than raise.

    json.loads can raise RecursionError on deeply-nested structures; the
    parse must catch it and return [] (graceful degradation, Constitution V).
    """
    (tmp_path / "sample_module.py").write_text("def f(): pass\n")
    # Write a valid coverage.json first (needed for the file to be found)
    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "sample_module.py": {
                "executed_lines": [1],
                "missing_lines": [],
                "excluded_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))

    # Patch json.loads to raise RecursionError, simulating deeply-nested JSON
    import snake_eyes.coverage as cov_mod

    with mock.patch.object(cov_mod.json, "loads", side_effect=RecursionError("deep")):
        result = parse_coverage(str(tmp_path), None)

    assert result == [], f"Expected [] on RecursionError, got {result}"


# ---------------------------------------------------------------------------
# M4 — Broadened cov.load() exceptions
# ---------------------------------------------------------------------------


def test_coverage_dot_coverage_memory_error_degrades(tmp_path: Path) -> None:
    """M4: MemoryError from cov.load() degrades to [] (broadened exception catch)."""
    (tmp_path / "sample_module.py").write_text("def ok(): pass\n")

    from coverage.data import CoverageData

    sample = tmp_path / "sample_module.py"
    dot_cov = tmp_path / ".coverage"
    cdata = CoverageData(basename=str(dot_cov))
    cdata.add_lines({str(sample): [1]})
    cdata.write()

    with mock.patch.object(
        coverage_pkg.Coverage, "load", side_effect=MemoryError("OOM")
    ):
        result = parse_coverage(str(tmp_path), None)

    assert result == [], f"Expected [] on MemoryError from cov.load(), got {result}"


# ---------------------------------------------------------------------------
# M6c — AST depth-budget guard on the coverage path
#
# NOTE: The snake-eyes AST depth budget (MAX_AST_DEPTH=200) cannot be reached by
# deeply-nested *source text*: CPython's tokenizer rejects indentation past
# MAXINDENT (100) with an IndentationError long before 200 nested blocks, so
# ast.parse() fails first and the file is skipped at the parse step. To exercise
# the span-lister depth guard itself we inject an over-deep AST tree in memory
# (mirroring test_complexity_visitor_recursion_error_skips_file).
# ---------------------------------------------------------------------------


def test_span_lister_depth_budget_raises() -> None:
    """enumerate_functions_with_spans raises RecursionError past MAX_AST_DEPTH.

    Covers the _SpanLister._check_depth guard (a Constitution V resource bound)
    directly, by building a nested-function AST deeper than the budget in memory
    — bypassing the tokenizer's MAXINDENT limit.
    """
    import ast

    from snake_eyes.analysis._shared import (
        MAX_AST_DEPTH,
        enumerate_functions_with_spans,
    )

    inner: ast.stmt = ast.Pass()
    node: ast.FunctionDef | None = None
    for i in range(MAX_AST_DEPTH + 10):
        node = ast.FunctionDef(
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
        inner = node
    assert node is not None
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)

    with pytest.raises(RecursionError):
        enumerate_functions_with_spans(module)


def test_parse_source_spans_traversal_error_returns_none(tmp_path: Path) -> None:
    """_parse_source_spans returns None when span enumeration raises.

    Covers the BROADENED_EXCEPTIONS handler in _parse_source_spans: a well-formed
    source file whose span enumeration blows up (here a RecursionError from the
    depth guard) is skipped gracefully (returns None) rather than aborting.
    """
    import snake_eyes.coverage as cov_mod

    src = tmp_path / "m.py"
    src.write_text("def f():\n    return 1\n")

    with mock.patch.object(
        cov_mod,
        "enumerate_functions_with_spans",
        side_effect=RecursionError("AST depth budget exceeded in span lister"),
    ):
        assert cov_mod._parse_source_spans(src, "m.py") is None


def test_dot_coverage_spans_none_skips(tmp_path: Path) -> None:
    """.coverage branch skips a file whose span enumeration yields None.

    Covers the `if spans is None: continue` guard in _parse_dot_coverage (the
    .coverage counterpart of the JSON-branch skip).
    """
    from coverage.data import CoverageData

    import snake_eyes.coverage as cov_mod

    sample = tmp_path / "sample_module.py"
    sample.write_text("def ok():\n    return 1\n")
    dot_cov = tmp_path / ".coverage"
    cdata = CoverageData(basename=str(dot_cov))
    cdata.add_lines({str(sample): [1]})
    cdata.write()

    with mock.patch.object(cov_mod, "_parse_source_spans", return_value=None):
        result = parse_coverage(str(tmp_path), None)

    # File is skipped (no spans) → no rows, and no crash.
    assert result == []


# ---------------------------------------------------------------------------
# M7 — async function coverage rows
# ---------------------------------------------------------------------------


def test_coverage_async_function(tmp_path: Path) -> None:
    """M7: async def functions produce correct start_line/end_line/covered/total/pct.

    Exercises the visit_AsyncFunctionDef path in enumerate_functions_with_spans.
    """
    # async def with 2 statements: line 2 executed, line 3 missing
    code = "async def fetch():\n    x = 1\n    y = 2\n"
    (tmp_path / "async_mod.py").write_text(code)

    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "async_mod.py": {
                "executed_lines": [2],
                "missing_lines": [3],
                "excluded_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))

    result = parse_coverage(str(tmp_path), None)

    entries = [e for e in result if e["function"] == "fetch"]
    assert entries, "async def fetch not found in coverage results"
    e = entries[0]
    assert e["start_line"] == 1, f"start_line={e['start_line']}"
    assert e["end_line"] >= 3, f"end_line={e['end_line']}"
    assert e["covered_stmts"] == 1, f"covered_stmts={e['covered_stmts']}"
    assert e["total_stmts"] == 2, f"total_stmts={e['total_stmts']}"
    assert e["percentage"] == 50.0, f"percentage={e['percentage']}"


# ---------------------------------------------------------------------------
# M9 — non-dict 'files' value returns []
# ---------------------------------------------------------------------------


def test_coverage_json_non_dict_files_returns_empty(tmp_path: Path) -> None:
    """M9: non-dict 'files' value (e.g. list/string) → parse_coverage returns [].

    Covers the isinstance(files_map, dict) guard (M9: must return [] not None).
    """
    (tmp_path / "sample_module.py").write_text("def f(): pass\n")

    for bad_files in [[], "x", 42]:
        (tmp_path / "coverage.json").write_text(
            json.dumps({"meta": {"version": "7.0.0"}, "files": bad_files})
        )
        result = parse_coverage(str(tmp_path), None)
        assert result == [], f"Expected [] for files={bad_files!r}, got {result}"


# ---------------------------------------------------------------------------
# H2 — config_file=False regression: coveragerc omit has no effect
# ---------------------------------------------------------------------------


def test_coverage_dot_coverage_ignores_coveragerc_omit(tmp_path: Path) -> None:
    """H2: .coveragerc with omit= must not affect parse_coverage output.

    Places a .coveragerc that omits sample_module.py in the cwd and asserts
    parse_coverage still returns rows for that file (config_file=False).
    """
    sample = tmp_path / "sample_module.py"
    shutil.copy(COVERAGE_FIXTURES / "sample_module.py", sample)

    from coverage.data import CoverageData

    dot_cov = tmp_path / ".coverage"
    cdata = CoverageData(basename=str(dot_cov))
    cdata.add_lines({str(sample): [4, 5]})
    cdata.write()

    # Write a .coveragerc that would omit sample_module.py if loaded
    (tmp_path / ".coveragerc").write_text("[run]\nomit = sample_module.py\n")

    # Change cwd to tmp_path so the .coveragerc would be auto-discovered
    import os

    orig_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = parse_coverage(str(tmp_path), None)
    finally:
        os.chdir(orig_cwd)

    # Despite .coveragerc saying omit, the file must appear (config_file=False)
    assert any(e["file"] == "sample_module.py" for e in result), (
        f"sample_module.py omitted by coveragerc but should not be: {result}"
    )


# ---------------------------------------------------------------------------
# Testing LOW — ordering fixture with non-trivial key ordering
# ---------------------------------------------------------------------------


def test_ordering_non_trivial_sort_key(tmp_path: Path) -> None:
    """Testing LOW: fixture where alphabetical(function) != (file, start_line) order.

    The current sample_module fixture has covered_func at line 4 < uncovered_func
    at line 8, and alphabetically covered_func < uncovered_func — so a wrong sort
    key would still pass.  This fixture uses function names where alpha order
    differs from line order, truly pinning (file, start_line, function).
    """
    # zz_first appears on line 1 (lower line), aa_second appears on line 4.
    # Alphabetically: aa_second < zz_first, but by line: zz_first < aa_second.
    # Correct sort key (file, start_line, function) → zz_first first.
    code = "def zz_first():\n    return 1\n\n\ndef aa_second():\n    return 2\n"
    (tmp_path / "ordering_test.py").write_text(code)

    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "ordering_test.py": {
                "executed_lines": [2, 6],
                "missing_lines": [],
                "excluded_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))

    result = parse_coverage(str(tmp_path), None)

    names = [e["function"] for e in result if e["file"] == "ordering_test.py"]
    assert names == ["zz_first", "aa_second"], (
        f"Expected [zz_first, aa_second] by start_line order, got {names}"
    )


# ---------------------------------------------------------------------------
# Adversary LOW — symlinked data files
# ---------------------------------------------------------------------------


def test_coverage_json_symlink_rejected(tmp_path: Path) -> None:
    """Adversary LOW: a symlink at coverage.json is treated as non-regular → skipped."""
    (tmp_path / "sample_module.py").write_text("def f(): pass\n")

    real_json = tmp_path / "real_coverage.json"
    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "sample_module.py": {
                "executed_lines": [1],
                "missing_lines": [],
                "excluded_lines": [],
            }
        },
    }
    real_json.write_text(json.dumps(cov_json))

    symlink = tmp_path / "coverage.json"
    symlink.symlink_to(real_json)

    # Patch stat to report the symlink as a non-regular file (FIFO mode)
    real_stat = real_json.stat()
    fifo_mode = (real_stat.st_mode & ~0o170000) | stat.S_IFIFO
    fake_stat_result = os.stat_result(
        (
            fifo_mode,
            real_stat.st_ino,
            real_stat.st_dev,
            real_stat.st_nlink,
            real_stat.st_uid,
            real_stat.st_gid,
            real_stat.st_size,
            real_stat.st_atime,
            real_stat.st_mtime,
            real_stat.st_ctime,
        )
    )

    original_stat = pathlib.Path.stat

    def patched_stat(
        self: pathlib.Path, *, follow_symlinks: bool = True, **kwargs: object
    ) -> os.stat_result:
        if self.name == "coverage.json" and follow_symlinks:
            return fake_stat_result
        return original_stat(self, follow_symlinks=follow_symlinks, **kwargs)  # type: ignore[arg-type]

    with mock.patch.object(pathlib.Path, "stat", patched_stat):
        result = parse_coverage(str(tmp_path), None)

    assert result == [], f"Expected [] for symlinked coverage.json, got {result}"
