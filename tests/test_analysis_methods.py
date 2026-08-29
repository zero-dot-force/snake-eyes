"""JSON-RPC e2e tests for analyze/complexity/coverage methods.

validates: gaze analyzer protocol v1.1.0
"""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from conftest import req, responses

from snake_eyes.protocol import INVALID_PARAMS
from snake_eyes.server import Server

# ---------------------------------------------------------------------------
# Fixtures dir
# ---------------------------------------------------------------------------

EFFECTS_DIR = Path(__file__).parent / "fixtures" / "effects"
COVERAGE_FIXTURES = Path(__file__).parent / "fixtures" / "coverage"


# ---------------------------------------------------------------------------
# Harness helpers
# ---------------------------------------------------------------------------


def _run(raw: str) -> str:
    stdin = io.StringIO(raw)
    stdout = io.StringIO()
    server = Server(stdin, stdout, io.StringIO())
    with pytest.raises(SystemExit) as exc:
        server.run()
    assert exc.value.code == 0
    return stdout.getvalue()


def _call(method: str, tmp_path: Path, **extra: Any) -> dict[str, Any]:
    raw = req(method, root_path=str(tmp_path), **extra) + "\n"
    resp = responses(_run(raw))
    return resp[0]


def _copy_fixture(name: str, dest: Path) -> None:
    src = EFFECTS_DIR / name
    shutil.copy(src, dest / name)


# ---------------------------------------------------------------------------
# 7.6 — JSON-RPC e2e parameter validation (missing/wrong root_path, non-array patterns)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method", ["analyze", "complexity", "coverage"])
def test_missing_root_path_returns_32602(method: str, tmp_path: Path) -> None:
    """Missing root_path → -32602."""
    raw = req(method) + "\n"
    resp = responses(_run(raw))[0]
    assert resp["error"]["code"] == INVALID_PARAMS


@pytest.mark.parametrize("method", ["analyze", "complexity", "coverage"])
def test_non_string_root_path_returns_32602(method: str, tmp_path: Path) -> None:
    """Non-string root_path → -32602."""
    raw = req(method, root_path=123) + "\n"
    resp = responses(_run(raw))[0]
    assert resp["error"]["code"] == INVALID_PARAMS


@pytest.mark.parametrize("method", ["analyze", "complexity", "coverage"])
def test_non_array_patterns_returns_32602(method: str, tmp_path: Path) -> None:
    """Non-array patterns → -32602."""
    raw = req(method, root_path=str(tmp_path), patterns="not-a-list") + "\n"
    resp = responses(_run(raw))[0]
    assert resp["error"]["code"] == INVALID_PARAMS


# ---------------------------------------------------------------------------
# Analyze method e2e
# ---------------------------------------------------------------------------


def test_analyze_no_classification_key(tmp_path: Path) -> None:
    """Effects carry no 'classification' key."""
    _copy_fixture("p0.py", tmp_path)
    resp = _call("analyze", tmp_path)
    result = resp["result"]
    for func in result["functions"]:
        for eff in func["side_effects"]:
            assert "classification" not in eff, (
                f"classification must not be set on effect: {eff}"
            )


def test_analyze_returns_functions_list(tmp_path: Path) -> None:
    """Analyze result wraps functions[] list."""
    _copy_fixture("pure.py", tmp_path)
    resp = _call("analyze", tmp_path)
    assert "result" in resp
    assert "functions" in resp["result"]
    assert isinstance(resp["result"]["functions"], list)


def test_analyze_response_id_matches(tmp_path: Path) -> None:
    """JSON-RPC response id matches request id."""
    _copy_fixture("pure.py", tmp_path)
    raw = req("analyze", id=42, root_path=str(tmp_path)) + "\n"
    resp = responses(_run(raw))[0]
    assert resp["id"] == 42


def test_analyze_syntax_error_and_valid_file(tmp_path: Path) -> None:
    """syntax_error.py + valid file in same request → valid file present, no crash."""
    _copy_fixture("syntax_error.py", tmp_path)
    (tmp_path / "valid.py").write_text("def ok(): pass\n")
    resp = _call("analyze", tmp_path)
    funcs = resp["result"]["functions"]
    names = [f["name"] for f in funcs]
    assert "ok" in names


def test_analyze_byte_identical_determinism(tmp_path: Path) -> None:
    """Two analyze calls on the same input produce byte-identical JSON."""
    _copy_fixture("p0.py", tmp_path)
    raw = req("analyze", root_path=str(tmp_path)) + "\n"
    out1 = _run(raw)
    out2 = _run(raw)
    assert out1 == out2, "analyze output must be byte-identical across runs"


# ---------------------------------------------------------------------------
# Complexity method e2e
# ---------------------------------------------------------------------------


def test_complexity_returns_functions_with_complexity(tmp_path: Path) -> None:
    """Complexity result has functions[] with complexity int."""
    _copy_fixture("complexity_fixture.py", tmp_path)
    resp = _call("complexity", tmp_path)
    assert "result" in resp
    funcs = resp["result"]["functions"]
    assert isinstance(funcs, list)
    for f in funcs:
        assert "complexity" in f
        assert isinstance(f["complexity"], int)


def test_complexity_response_id_matches(tmp_path: Path) -> None:
    """JSON-RPC response id matches request id."""
    _copy_fixture("pure.py", tmp_path)
    raw = req("complexity", id=99, root_path=str(tmp_path)) + "\n"
    resp = responses(_run(raw))[0]
    assert resp["id"] == 99


def test_complexity_byte_identical_determinism(tmp_path: Path) -> None:
    """Two complexity calls produce byte-identical JSON."""
    _copy_fixture("complexity_fixture.py", tmp_path)
    raw = req("complexity", root_path=str(tmp_path)) + "\n"
    out1 = _run(raw)
    out2 = _run(raw)
    assert out1 == out2


def test_complexity_syntax_error_and_valid(tmp_path: Path) -> None:
    """syntax_error.py + valid file → valid file present, no crash."""
    _copy_fixture("syntax_error.py", tmp_path)
    (tmp_path / "valid.py").write_text("def ok(): pass\n")
    resp = _call("complexity", tmp_path)
    names = [f["name"] for f in resp["result"]["functions"]]
    assert "ok" in names


# ---------------------------------------------------------------------------
# Coverage method e2e
# ---------------------------------------------------------------------------


def test_coverage_returns_functions_with_function_field(tmp_path: Path) -> None:
    """Coverage result uses 'function' field."""
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

    resp = _call("coverage", tmp_path)
    assert "result" in resp
    funcs = resp["result"]["functions"]
    for f in funcs:
        assert "function" in f, f"Must have 'function' field: {f}"


def test_coverage_empty_when_no_data(tmp_path: Path) -> None:
    """No coverage data → {\"functions\": []}."""
    (tmp_path / "mod.py").write_text("def f(): pass\n")
    resp = _call("coverage", tmp_path)
    assert resp["result"] == {"functions": []}


def test_coverage_response_id_matches(tmp_path: Path) -> None:
    """JSON-RPC response id matches request id."""
    (tmp_path / "mod.py").write_text("def f(): pass\n")
    raw = req("coverage", id=7, root_path=str(tmp_path)) + "\n"
    resp = responses(_run(raw))[0]
    assert resp["id"] == 7


def test_coverage_byte_identical_determinism(tmp_path: Path) -> None:
    """Two coverage calls produce byte-identical JSON."""
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
    raw = req("coverage", root_path=str(tmp_path)) + "\n"
    out1 = _run(raw)
    out2 = _run(raw)
    assert out1 == out2


# ---------------------------------------------------------------------------
# 7.8 — schema-conformance canned request/response pair tests
# ---------------------------------------------------------------------------
# Hand-authored expected shapes. Protocol: gaze analyzer protocol v1.1.0.


def test_analyze_schema_conformance(tmp_path: Path) -> None:
    """analyze response schema conformance.

    validates: gaze analyzer protocol v1.1.0
    fields: jsonrpc, id, result.functions[].{name,package,file,line,side_effects[]}
    """
    _copy_fixture("pure.py", tmp_path)
    raw = req("analyze", id=1, root_path=str(tmp_path)) + "\n"
    resp = responses(_run(raw))[0]

    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    result = resp["result"]
    assert "functions" in result
    for func in result["functions"]:
        assert "name" in func
        assert "package" in func
        assert "file" in func
        assert "line" in func
        assert "side_effects" in func
        assert isinstance(func["side_effects"], list)
        for e in func["side_effects"]:
            assert "type" in e
            assert "description" in e
            assert "location" in e
            assert "classification" not in e


def test_complexity_schema_conformance(tmp_path: Path) -> None:
    """complexity response schema conformance.

    validates: gaze analyzer protocol v1.1.0
    fields: jsonrpc, id, result.functions[].{name,package,file,line,complexity}
    """
    _copy_fixture("pure.py", tmp_path)
    raw = req("complexity", id=2, root_path=str(tmp_path)) + "\n"
    resp = responses(_run(raw))[0]

    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 2
    result = resp["result"]
    assert "functions" in result
    for func in result["functions"]:
        assert "name" in func
        assert "package" in func
        assert "file" in func
        assert "line" in func
        assert "complexity" in func
        assert isinstance(func["complexity"], int)


def test_coverage_schema_conformance(tmp_path: Path) -> None:
    """coverage response schema conformance.

    validates: gaze analyzer protocol v1.1.0
    fields: jsonrpc, id, result.functions[].{file,function,start_line,end_line,...}
    """
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

    raw = req("coverage", id=3, root_path=str(tmp_path)) + "\n"
    resp = responses(_run(raw))[0]

    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 3
    result = resp["result"]
    assert "functions" in result
    for func in result["functions"]:
        assert "file" in func
        assert "function" in func
        assert "start_line" in func
        assert "end_line" in func
        assert "covered_stmts" in func
        assert "total_stmts" in func
        assert "percentage" in func


# ---------------------------------------------------------------------------
# 7.9 — resource bounds via JSON-RPC
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not hasattr(__import__("os"), "mkfifo"),
    reason="mkfifo not available on this platform",
)
@pytest.mark.parametrize("method", ["analyze", "complexity"])
def test_fifo_skipped_via_jsonrpc(method: str, tmp_path: Path) -> None:
    """FIFO with .py extension skipped; valid files still returned."""
    import os

    fifo = tmp_path / "pipe.py"
    os.mkfifo(fifo)
    (tmp_path / "good.py").write_text("def good(): pass\n")
    resp = _call(method, tmp_path)
    names = [f["name"] for f in resp["result"]["functions"]]
    assert "good" in names


# ---------------------------------------------------------------------------
# 7.8 — canned exact-equality response tests (hand-authored expected objects)
# ---------------------------------------------------------------------------


def test_analyze_canned_exact_equality(tmp_path: Path) -> None:
    """analyze: hand-authored expected result, compared for full dict equality.

    validates: gaze analyzer protocol v1.1.0
    fixture: noop function with no side effects
    """
    (tmp_path / "noop_only.py").write_text("def noop() -> None:\n    pass\n")
    raw = req("analyze", id=100, root_path=str(tmp_path)) + "\n"
    resp = responses(_run(raw))[0]

    expected: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 100,
        "result": {
            "functions": [
                {
                    "name": "noop",
                    "package": "noop_only",
                    "file": "noop_only.py",
                    "line": 1,
                    "side_effects": [],
                }
            ]
        },
    }
    assert resp == expected, (
        f"analyze canned response mismatch.\nExpected: {expected}\nGot: {resp}"
    )


def test_complexity_canned_exact_equality(tmp_path: Path) -> None:
    """complexity: hand-authored expected result, compared for full dict equality.

    validates: gaze analyzer protocol v1.1.0
    fixture: single function with no branches (complexity == 1)
    """
    (tmp_path / "simple.py").write_text("def simple() -> None:\n    pass\n")
    raw = req("complexity", id=101, root_path=str(tmp_path)) + "\n"
    resp = responses(_run(raw))[0]

    expected: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 101,
        "result": {
            "functions": [
                {
                    "name": "simple",
                    "package": "simple",
                    "file": "simple.py",
                    "line": 1,
                    "complexity": 1,
                }
            ]
        },
    }
    assert resp == expected, (
        f"complexity canned response mismatch.\nExpected: {expected}\nGot: {resp}"
    )


def test_coverage_canned_exact_equality(tmp_path: Path) -> None:
    """coverage: hand-authored expected result, compared for full dict equality.

    validates: gaze analyzer protocol v1.1.0
    fixture: one function with no executable statements (zero-statement body yields
    covered_stmts=0, total_stmts=0, percentage=0.0)
    """
    (tmp_path / "covered.py").write_text("def covered() -> None:\n    pass\n")
    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "covered.py": {
                "executed_lines": [],
                "missing_lines": [],
                "excluded_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))

    raw = req("coverage", id=102, root_path=str(tmp_path)) + "\n"
    resp = responses(_run(raw))[0]

    expected: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 102,
        "result": {
            "functions": [
                {
                    "file": "covered.py",
                    "function": "covered",
                    "start_line": 1,
                    "end_line": 2,
                    "covered_stmts": 0,
                    "total_stmts": 0,
                    "percentage": 0.0,
                }
            ]
        },
    }
    assert resp == expected, (
        f"coverage canned response mismatch.\nExpected: {expected}\nGot: {resp}"
    )
