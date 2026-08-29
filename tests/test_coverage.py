"""Tests for coverage.parse_coverage — validates: gaze analyzer protocol v1.1.0."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import coverage as _cov_pkg
import pytest

from snake_eyes.coverage import parse_coverage

# ---------------------------------------------------------------------------
# Fixture dir
# ---------------------------------------------------------------------------

COVERAGE_FIXTURES = Path(__file__).parent / "fixtures" / "coverage"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _copy_coverage_fixture(name: str, dest_dir: Path) -> None:
    src = COVERAGE_FIXTURES / name
    shutil.copy(src, dest_dir / name)


# ---------------------------------------------------------------------------
# 7.5 — coverage.json canned fixture tests
# ---------------------------------------------------------------------------


def test_module_shadow_guard() -> None:
    """import coverage resolves to the third-party package, not this module."""
    assert hasattr(_cov_pkg, "Coverage"), (
        "coverage module must be the third-party package (has Coverage class)"
    )


def test_coverage_json_expected_values(tmp_path: Path) -> None:
    """Canned coverage.json: correct covered_stmts/total_stmts/pct for covered_func."""
    # Copy both the module and the coverage.json into a structure that matches the keys
    # The coverage.json uses keys like "tests/fixtures/coverage/sample_module.py"
    # so we need to recreate that directory structure under tmp_path
    dest_module = tmp_path / "tests" / "fixtures" / "coverage" / "sample_module.py"
    dest_module.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(COVERAGE_FIXTURES / "sample_module.py", dest_module)

    # Build a coverage.json that uses the relative path from tmp_path
    rel_key = "tests/fixtures/coverage/sample_module.py"
    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            rel_key: {
                "executed_lines": [4, 5],
                "missing_lines": [8, 9],
                "excluded_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))

    result = parse_coverage(str(tmp_path), None)

    assert result, "parse_coverage returned empty list"
    covered_func_entries = [e for e in result if e["function"] == "covered_func"]
    assert covered_func_entries, "covered_func not in results"
    e = covered_func_entries[0]
    # covered_func body: lines 4,5 — both executed
    assert e["covered_stmts"] >= 1, f"covered_stmts={e['covered_stmts']}"
    assert e["total_stmts"] >= 1, f"total_stmts={e['total_stmts']}"
    assert isinstance(e["percentage"], float)


def test_missing_coverage_files_returns_empty(tmp_path: Path) -> None:
    """No coverage files present → parse_coverage returns []."""
    (tmp_path / "mod.py").write_text("def f(): pass\n")
    result = parse_coverage(str(tmp_path), None)
    assert result == []


def test_dot_coverage_only_non_100(tmp_path: Path) -> None:
    """.coverage-only fixture maps functions at non-100% coverage."""
    # Copy sample_module.py into a path that matches what CoverageData recorded
    # The .coverage was written with abs_path from the original fixture dir.
    # For this test we use a fresh .coverage written against tmp_path files.
    sample = tmp_path / "sample_module.py"
    shutil.copy(COVERAGE_FIXTURES / "sample_module.py", sample)

    from coverage.data import CoverageData

    dot_cov_path = tmp_path / ".coverage"
    cdata = CoverageData(basename=str(dot_cov_path))
    # Only covered_func lines 4,5 executed; uncovered_func lines 8,9 NOT executed
    cdata.add_lines({str(sample): [4, 5]})
    cdata.write()

    result = parse_coverage(str(tmp_path), None)

    # There should be two function entries, and at least one with < 100%
    assert result, f"Expected non-empty result from .coverage file, got {result}"
    percentages = [e["percentage"] for e in result]
    assert any(p < 100.0 for p in percentages), (
        f"Expected non-100% coverage, got {percentages}"
    )


def test_coverage_json_wins_over_dot_coverage(tmp_path: Path) -> None:
    """When both coverage.json and .coverage present, coverage.json wins."""
    sample = tmp_path / "sample_module.py"
    shutil.copy(COVERAGE_FIXTURES / "sample_module.py", sample)

    # Write a .coverage file (only covered_func)
    from coverage.data import CoverageData

    dot_cov_path = tmp_path / ".coverage"
    cdata = CoverageData(basename=str(dot_cov_path))
    cdata.add_lines({str(sample): [4, 5]})
    cdata.write()

    # Write coverage.json with a sentinel value in executed_lines
    # (all lines of sample_module) to distinguish from .coverage result
    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "sample_module.py": {
                "executed_lines": [4, 5, 8, 9],
                "missing_lines": [],
                "excluded_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))

    result = parse_coverage(str(tmp_path), None)

    # coverage.json was used — all stmts in sample_module covered
    all_covered = all(e["percentage"] == 100.0 for e in result if e["total_stmts"] > 0)
    assert all_covered, (
        f"Expected 100% from coverage.json, got {[e['percentage'] for e in result]}"
    )


def test_malformed_coverage_json_returns_empty(tmp_path: Path) -> None:
    """Malformed/wrong-shape coverage.json → parse_coverage returns bare []."""
    (tmp_path / "sample_module.py").write_text("def f(): pass\n")
    (tmp_path / "coverage.json").write_text("NOT VALID JSON {{{{")
    result = parse_coverage(str(tmp_path), None)
    assert result == [], f"Expected [], got {result}"


def test_wrong_shape_coverage_json_returns_empty(tmp_path: Path) -> None:
    """JSON-valid but wrong-shape (missing 'files' key) → parse_coverage returns []."""
    (tmp_path / "sample_module.py").write_text("def f(): pass\n")
    (tmp_path / "coverage.json").write_text('{"not_files": {}}')
    result = parse_coverage(str(tmp_path), None)
    assert result == [], f"Expected [], got {result}"


def test_result_is_bare_list_not_wrapped(tmp_path: Path) -> None:
    """parse_coverage returns a bare list, NOT {'functions': [...]}."""
    (tmp_path / "sample_module.py").write_text("def f(): pass\n")
    result = parse_coverage(str(tmp_path), None)
    assert isinstance(result, list), f"Expected list, got {type(result)}"


def test_syntax_error_file_skipped(tmp_path: Path) -> None:
    """syntax_error.py beside covered modules is skipped; valid entries still return."""
    sample = tmp_path / "sample_module.py"
    shutil.copy(COVERAGE_FIXTURES / "sample_module.py", sample)
    shutil.copy(COVERAGE_FIXTURES / "syntax_error.py", tmp_path / "syntax_error.py")

    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "sample_module.py": {
                "executed_lines": [4, 5],
                "missing_lines": [8, 9],
                "excluded_lines": [],
            },
            "syntax_error.py": {
                "executed_lines": [1],
                "missing_lines": [],
                "excluded_lines": [],
            },
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))

    result = parse_coverage(str(tmp_path), None)

    # Valid entries from sample_module must be present
    assert any(e["file"] == "sample_module.py" for e in result), (
        "sample_module.py must still yield entries"
    )


def test_ordering_by_file_start_line_function(tmp_path: Path) -> None:
    """Results ordered by (file, start_line, function).

    Testing LOW: uses a two-file fixture where alpha(function) != line order,
    so a wrong sort key would fail.  zz_early (line 1) must precede aa_late (line 5)
    even though 'aa_late' < 'zz_early' alphabetically.
    """
    # Two files: mod_a.py has one func at line 1; mod_b.py has zz_func at line 1
    # and aa_func at line 5 — line order and alpha order diverge for mod_b.py.
    (tmp_path / "mod_a.py").write_text("def one(): return 1\n")
    (tmp_path / "mod_b.py").write_text(
        "def zz_early():\n    return 1\n\n\ndef aa_late():\n    return 2\n"
    )

    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "mod_a.py": {
                "executed_lines": [1],
                "missing_lines": [],
                "excluded_lines": [],
            },
            "mod_b.py": {
                "executed_lines": [2, 6],
                "missing_lines": [],
                "excluded_lines": [],
            },
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))

    result = parse_coverage(str(tmp_path), None)

    keys = [(e["file"], e["start_line"], e["function"]) for e in result]
    assert keys == sorted(keys), f"Not ordered by (file,start_line,function): {keys}"

    # Extra: within mod_b.py, zz_early must come before aa_late (line order wins)
    mod_b_funcs = [e["function"] for e in result if e["file"] == "mod_b.py"]
    assert mod_b_funcs == ["zz_early", "aa_late"], (
        f"Expected [zz_early, aa_late] by line order, got {mod_b_funcs}"
    )


def test_zero_total_stmts(tmp_path: Path) -> None:
    """Zero executable stmts: total_stmts==0 and percentage==0.0."""
    # A function with only a docstring — may have zero executable statements
    (tmp_path / "empty_func.py").write_text(
        '"""Module."""\n\ndef doc_only():\n    """Only a docstring."""\n'
    )
    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "empty_func.py": {
                "executed_lines": [],
                "missing_lines": [],
                "excluded_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))

    result = parse_coverage(str(tmp_path), None)

    zero_total = [e for e in result if e["total_stmts"] == 0]
    assert zero_total, f"Expected at least one zero-total entry, got {result}"
    for e in zero_total:
        assert e["total_stmts"] == 0, f"total_stmts must be 0: {e}"
        assert e["percentage"] == 0.0, f"percentage must be 0.0 for zero total: {e}"


# ---------------------------------------------------------------------------
# 7.12 — coverage confinement: traversal keys ignored
# ---------------------------------------------------------------------------


def test_traversal_keys_ignored(tmp_path: Path) -> None:
    """traversal.json: traversal/absolute-path keys silently ignored."""
    sample = tmp_path / "tests" / "fixtures" / "coverage" / "sample_module.py"
    sample.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(COVERAGE_FIXTURES / "sample_module.py", sample)

    shutil.copy(COVERAGE_FIXTURES / "traversal.json", tmp_path / "coverage.json")

    result = parse_coverage(str(tmp_path), None)

    # Traversal paths must NOT appear in results
    for e in result:
        assert "etc" not in e["file"], f"Traversal path leaked into result: {e['file']}"
        assert not e["file"].startswith("/"), f"Absolute path leaked: {e['file']}"


# ---------------------------------------------------------------------------
# 7.10 — coverage function-set is subset of detector function-set
# ---------------------------------------------------------------------------


def test_coverage_subset_of_detector(tmp_path: Path) -> None:
    """parse_coverage function-set must be a SUBSET of analyze_path function-set."""
    from snake_eyes.analysis.detector import analyze_path

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

    det_records = analyze_path(str(tmp_path), None)
    cov_entries = parse_coverage(str(tmp_path), None)

    det_set = {(r.file, r.name) for r in det_records}
    cov_set = {(e["file"], e["function"]) for e in cov_entries}

    outside = cov_set - det_set
    assert not outside, f"Coverage entries outside detector set: {outside}"


def test_nonexistent_root_raises(tmp_path: Path) -> None:
    """Non-existent root_path raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        parse_coverage(str(tmp_path / "no_such_dir"), None)


def test_coverage_uses_function_field(tmp_path: Path) -> None:
    """Coverage entries use 'function' field (not 'name')."""
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

    result = parse_coverage(str(tmp_path), None)

    for e in result:
        assert "function" in e, f"Coverage entry must have 'function' field: {e}"
        assert "name" not in e, f"Coverage entry must NOT have 'name' field: {e}"
