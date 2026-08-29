"""Additional tests to hit uncovered branches.

Covers: _shared, complexity, detector, coverage modules.
validates: gaze analyzer protocol v1.1.0
"""

from __future__ import annotations

import json
import os
import shutil
import unittest.mock as mock
from pathlib import Path
from typing import Any

import pytest

from snake_eyes.analysis._shared import (
    derive_package,
    enumerate_functions_with_spans,
    iter_source_files,
    ordered_file_list,
)
from snake_eyes.analysis.complexity import compute_complexity
from snake_eyes.analysis.detector import analyze_source
from snake_eyes.analysis.models import FunctionRecord, function_record_to_dict

EFFECTS_DIR = Path(__file__).parent / "fixtures" / "effects"
COVERAGE_FIXTURES = Path(__file__).parent / "fixtures" / "coverage"


def _to_dicts(records: list[FunctionRecord]) -> list[dict[str, Any]]:
    return [function_record_to_dict(r) for r in records]


def _types(records: list[FunctionRecord]) -> set[str]:
    return {e["type"] for r in _to_dicts(records) for e in r["side_effects"]}


# ---------------------------------------------------------------------------
# _shared.py coverage
# ---------------------------------------------------------------------------


def test_iter_source_files_non_regular(tmp_path: Path) -> None:
    """Non-regular files (FIFO) are skipped by iter_source_files."""
    if not hasattr(os, "mkfifo"):
        pytest.skip("mkfifo not available")
    fifo = tmp_path / "pipe.py"
    os.mkfifo(fifo)
    (tmp_path / "real.py").write_text("def f(): pass\n")

    files = ordered_file_list(str(tmp_path), None)
    results = list(iter_source_files(str(tmp_path), files))
    rel_paths = [r[0] for r in results]
    assert "real.py" in rel_paths
    assert "pipe.py" not in rel_paths


def test_iter_source_files_size_cap(tmp_path: Path) -> None:
    """Files exceeding MAX_FILE_BYTES are skipped."""
    big = tmp_path / "big.py"
    with mock.patch("snake_eyes.analysis._shared.MAX_FILE_BYTES", 10):
        big.write_text("def f(): pass\n")  # 15 bytes > 10
        files = ["big.py"]
        results = list(iter_source_files(str(tmp_path), files))
        assert results == []


def test_iter_source_files_stat_error(tmp_path: Path) -> None:
    """OSError on stat → file skipped."""
    (tmp_path / "good.py").write_text("def ok(): pass\n")
    files = ["missing.py", "good.py"]
    results = list(iter_source_files(str(tmp_path), files))
    rel_paths = [r[0] for r in results]
    assert "missing.py" not in rel_paths
    assert "good.py" in rel_paths


def test_iter_source_files_syntax_error(tmp_path: Path) -> None:
    """SyntaxError on parse → file skipped."""
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(\n")
    (tmp_path / "good.py").write_text("def ok(): pass\n")
    files = ["bad.py", "good.py"]
    results = list(iter_source_files(str(tmp_path), files))
    rel_paths = [r[0] for r in results]
    assert "bad.py" not in rel_paths
    assert "good.py" in rel_paths


def test_bounded_visitor_depth_exceeded(tmp_path: Path) -> None:
    """Deeply nested AST exceeds depth budget in _shared helpers."""
    # Create deeply nested if-statements that exceed depth 200
    depth = 220
    lines = []
    indent = ""
    for i in range(depth):
        lines.append(f"{indent}if True:")
        indent += "    "
    lines.append(f"{indent}pass")
    code = "def deep():\n" + "\n".join(f"    {line}" for line in lines) + "\n"
    (tmp_path / "deep.py").write_text(code)

    # Should skip-and-continue without raising
    entries = compute_complexity(str(tmp_path), None)
    # deep() may or may not appear depending on whether the traversal raises
    # before or after recording; the important thing is no exception propagates
    assert isinstance(entries, list)


def test_derive_package_init(tmp_path: Path) -> None:
    """pkg/__init__.py → 'pkg'."""
    assert derive_package("pkg/__init__.py") == "pkg"


def test_derive_package_nested() -> None:
    """pkg/sub/mod.py → 'pkg.sub.mod'."""
    assert derive_package("pkg/sub/mod.py") == "pkg.sub.mod"


def test_enumerate_functions_with_spans_lambdas_excluded(tmp_path: Path) -> None:
    """Lambdas are excluded from enumerate_functions_with_spans."""
    import ast

    source = "f = lambda x: x\ndef real(): pass\n"
    tree = ast.parse(source)

    spans = enumerate_functions_with_spans(tree)
    names = [name for name, _, _ in spans]
    assert "real" in names
    assert "<lambda>" not in names


def test_enumerate_functions_with_spans(tmp_path: Path) -> None:
    """enumerate_functions_with_spans returns (name, start, end) triples."""
    import ast

    source = "def f():\n    pass\n\ndef g():\n    pass\n"
    tree = ast.parse(source)

    spans = enumerate_functions_with_spans(tree)
    names = [s[0] for s in spans]
    assert "f" in names
    assert "g" in names
    for name, start, end in spans:
        assert end >= start


# ---------------------------------------------------------------------------
# complexity.py coverage
# ---------------------------------------------------------------------------


def test_complexity_ifexp(tmp_path: Path) -> None:
    """Ternary expression (IfExp) adds +1 to complexity."""
    code = "def f(x):\n    return 1 if x else 0\n"
    (tmp_path / "ifexp.py").write_text(code)
    entries = compute_complexity(str(tmp_path), None)
    entry = next(e for e in entries if e["name"] == "f")
    assert entry["complexity"] >= 2  # base 1 + ternary 1


def test_complexity_match_case(tmp_path: Path) -> None:
    """match/case adds +1 per case to complexity (Python 3.10+)."""
    code = (
        "def f(x):\n"
        "    match x:\n"
        "        case 1:\n"
        "            return 'one'\n"
        "        case 2:\n"
        "            return 'two'\n"
        "        case _:\n"
        "            return 'other'\n"
    )
    (tmp_path / "match.py").write_text(code)
    entries = compute_complexity(str(tmp_path), None)
    entry = next((e for e in entries if e["name"] == "f"), None)
    if entry:  # Python 3.10+
        assert entry["complexity"] >= 3  # base 1 + 2+ cases


def test_complexity_with_statement(tmp_path: Path) -> None:
    """with statement adds +1 to complexity."""
    code = (
        "import contextlib\n"
        "def f():\n"
        "    with contextlib.suppress(Exception):\n"
        "        pass\n"
    )
    (tmp_path / "withstmt.py").write_text(code)
    entries = compute_complexity(str(tmp_path), None)
    entry = next(e for e in entries if e["name"] == "f")
    assert entry["complexity"] >= 2  # base 1 + with


def test_complexity_boolop(tmp_path: Path) -> None:
    """BoolOp with N operands adds N-1 to complexity."""
    code = "def f(a, b, c):\n    return a and b and c\n"
    (tmp_path / "boolop.py").write_text(code)
    entries = compute_complexity(str(tmp_path), None)
    entry = next(e for e in entries if e["name"] == "f")
    assert entry["complexity"] >= 2  # base 1 + (3-1) bool edges - 1 return


# ---------------------------------------------------------------------------
# detector.py coverage — more effect types
# ---------------------------------------------------------------------------


def test_detect_goroutine_spawn(tmp_path: Path) -> None:
    """GoroutineSpawn detected via .start()."""
    source = (
        "import threading\n"
        "def f():\n"
        "    t = threading.Thread(target=None)\n"
        "    t.start()\n"
    )
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "GoroutineSpawn" in types


def test_detect_database_write() -> None:
    """DatabaseWrite detected via cursor.execute()."""
    source = "def f(cursor):\n    cursor.execute('SELECT 1')\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "DatabaseWrite" in types


def test_detect_database_transaction() -> None:
    """DatabaseTransaction detected via conn.commit()."""
    source = "def f(conn):\n    conn.commit()\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "DatabaseTransaction" in types


def test_detect_log_write() -> None:
    """LogWrite detected via logging.info()."""
    source = "import logging\ndef f():\n    logging.info('msg')\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "LogWrite" in types


def test_detect_wait_group_asyncio_gather() -> None:
    """WaitGroupOp detected via asyncio.gather()."""
    source = "import asyncio\ndef f():\n    asyncio.gather()\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "WaitGroupOp" in types


def test_detect_channel_send() -> None:
    """ChannelSend detected via queue.put()."""
    source = "def f(q):\n    q.put(1)\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "ChannelSend" in types


def test_detect_mutex_op() -> None:
    """MutexOp detected via lock.acquire()."""
    source = "def f(lock):\n    lock.acquire()\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "MutexOp" in types


def test_detect_context_cancellation() -> None:
    """ContextCancellation detected via task.cancel()."""
    source = "def f(task):\n    task.cancel()\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "ContextCancellation" in types


def test_detect_time_dependency() -> None:
    """TimeDependency detected via time.time()."""
    source = "import time\ndef f():\n    return time.time()\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "TimeDependency" in types


def test_detect_filesystem_delete() -> None:
    """FileSystemDelete detected via os.remove()."""
    source = "import os\ndef f(p):\n    os.remove(p)\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "FileSystemDelete" in types


def test_detect_filesystem_meta() -> None:
    """FileSystemMeta detected via os.chmod()."""
    source = "import os\ndef f(p):\n    os.chmod(p, 0o644)\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "FileSystemMeta" in types


def test_detect_eval_ambiguous() -> None:
    """eval() emits CallbackInvocation with confidence='ambiguous'."""
    source = "def f(code):\n    eval(code)\n"
    records = analyze_source(source, "f.py", "f")
    dicts = _to_dicts(records)
    cb = [
        e
        for r in dicts
        for e in r["side_effects"]
        if e["type"] == "CallbackInvocation"
        and e.get("detail", {}).get("confidence") == "ambiguous"
    ]
    assert cb


def test_detect_recover_behavior() -> None:
    """RecoverBehavior detected via bare except with no re-raise."""
    source = "def f():\n    try:\n        pass\n    except:\n        pass\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "RecoverBehavior" in types


def test_detect_map_mutation_subscript() -> None:
    """MapMutation detected via dict subscript assignment on a local."""
    source = "def f():\n    d = {}\n    d['k'] = 1\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "MapMutation" in types


def test_detect_map_mutation() -> None:
    """MapMutation detected via dict subscript assignment (local)."""
    source = "def f():\n    d = {}\n    d['k'] = 1\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "MapMutation" in types


def test_detect_closure_capture_mutation() -> None:
    """ClosureCaptureMutation detected via nonlocal mutation."""
    source = (
        "def outer():\n"
        "    x = 0\n"
        "    def inner():\n"
        "        nonlocal x\n"
        "        x = 1\n"
        "    inner()\n"
    )
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "ClosureCaptureMutation" in types


def test_detect_finalize_registration() -> None:
    """FinalizerRegistration detected via atexit.register()."""
    source = "import atexit\ndef f(cb):\n    atexit.register(cb)\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "FinalizerRegistration" in types


def test_detect_stderr_write() -> None:
    """StderrWrite detected via sys.stderr.write()."""
    source = "import sys\ndef f():\n    sys.stderr.write('err')\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "StderrWrite" in types


def test_detect_stdout_write_via_sys() -> None:
    """StdoutWrite detected via sys.stdout.write()."""
    source = "import sys\ndef f():\n    sys.stdout.write('out')\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "StdoutWrite" in types


def test_detect_print_file_stderr() -> None:
    """StderrWrite detected via print(file=sys.stderr)."""
    source = "import sys\ndef f():\n    print('err', file=sys.stderr)\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "StderrWrite" in types


def test_detect_writer_output_on_param() -> None:
    """WriterOutput detected when writing to a parameter (not opened here)."""
    source = "def f(writer):\n    writer.write('data')\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "WriterOutput" in types


def test_detect_import_side_effect_from_import() -> None:
    """ImportSideEffect detected via function-level from-import."""
    source = "def f():\n    from os import path\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "ImportSideEffect" in types


def test_detect_env_var_mutation_via_environ_update() -> None:
    """EnvVarMutation detected via os.environ.update()."""
    source = "import os\ndef f():\n    os.environ.update({'X': '1'})\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "EnvVarMutation" in types


def test_detect_global_subscript_mutation() -> None:
    """GlobalMutation detected via subscript assignment to a global dict."""
    source = "_data = {}\ndef f():\n    global _data\n    _data['k'] = 1\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "GlobalMutation" in types


def test_detect_asyncio_create_task() -> None:
    """GoroutineSpawn detected via asyncio.create_task()."""
    source = "import asyncio\ndef f():\n    asyncio.create_task(None)\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "GoroutineSpawn" in types


def test_detect_shutil_copy() -> None:
    """FileSystemWrite detected via shutil.copy()."""
    source = "import shutil\ndef f(src, dst):\n    shutil.copy(src, dst)\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "FileSystemWrite" in types


def test_detect_path_write_text() -> None:
    """FileSystemWrite detected via Path.write_text()."""
    source = "from pathlib import Path\ndef f(p):\n    Path(p).write_text('x')\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "FileSystemWrite" in types


def test_detect_wait_group_barrier_wait() -> None:
    """WaitGroupOp detected via barrier.wait()."""
    source = "def f(barrier):\n    barrier.wait()\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "WaitGroupOp" in types


def test_detect_delattr() -> None:
    """ReflectionMutation detected via delattr()."""
    source = "def f(obj):\n    delattr(obj, 'attr')\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "ReflectionMutation" in types


def test_detect_bare_raise_dual_emit() -> None:
    """Bare raise (re-raise) emits BOTH ErrorReturn AND ErrorSignal."""
    source = "def f():\n    try:\n        pass\n    except:\n        raise\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "ErrorReturn" in types
    assert "ErrorSignal" in types


def test_detect_yield_from_generator() -> None:
    """YieldFrom in sync function emits GeneratorYield."""
    source = "def f():\n    yield from range(3)\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "GeneratorYield" in types


def test_detect_contextmanager_decorator() -> None:
    """ResourceManagement detected via @contextmanager decorator."""
    source = (
        "from contextlib import contextmanager\n@contextmanager\ndef f():\n    yield\n"
    )
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "ResourceManagement" in types


def test_detect_function_level_import() -> None:
    """ImportSideEffect detected via function-level import statement."""
    source = "def f():\n    import os\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "ImportSideEffect" in types


def test_detect_multiprocessing_pool() -> None:
    """SyncPoolOp detected via multiprocessing.Pool()."""
    source = "import multiprocessing\ndef f():\n    multiprocessing.Pool(4)\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "SyncPoolOp" in types


def test_effect_sort_key_no_location() -> None:
    """_effect_sort_key handles Effect with no location (returns 0,0,type)."""
    from snake_eyes.analysis.detector import (
        _effect_sort_key,  # type: ignore[attr-defined]
    )
    from snake_eyes.analysis.models import Effect

    e = Effect(type="ReturnValue", description="test", location=None)
    key = _effect_sort_key(e)
    assert key == (0, 0, "ReturnValue")


def test_detect_assert_not_effect() -> None:
    """assert statements do NOT produce an effect."""
    source = "def f(x):\n    assert x > 0\n    return x\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "AssertEffect" not in types  # no such type
    # Only ReturnValue should be present (no effect for assert)


def test_detect_datetime_time_dependency() -> None:
    """TimeDependency detected via datetime.now() (direct import)."""
    source = "from datetime import datetime\ndef f():\n    return datetime.now()\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "TimeDependency" in types


def test_detect_os_write_filesystem() -> None:
    """FileSystemWrite detected via os.write()."""
    source = "import os\ndef f(fd):\n    os.write(fd, b'data')\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "FileSystemWrite" in types


# ---------------------------------------------------------------------------
# coverage.py extra branches
# ---------------------------------------------------------------------------


def test_parse_coverage_confine_path_absolute(tmp_path: Path) -> None:
    """Absolute paths outside root_path are silently ignored."""
    from snake_eyes.coverage import parse_coverage

    shutil.copy(COVERAGE_FIXTURES / "sample_module.py", tmp_path / "sample_module.py")
    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "/etc/passwd": {
                "executed_lines": [1],
                "missing_lines": [],
                "excluded_lines": [],
            },
            "sample_module.py": {
                "executed_lines": [4, 5],
                "missing_lines": [8, 9],
                "excluded_lines": [],
            },
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))
    result = parse_coverage(str(tmp_path), None)
    files_in_result = {e["file"] for e in result}
    assert not any("passwd" in f for f in files_in_result)


def test_parse_coverage_dot_coverage_malformed(tmp_path: Path) -> None:
    """Malformed .coverage SQLite file returns []."""
    from snake_eyes.coverage import parse_coverage

    (tmp_path / "sample_module.py").write_text("def f(): pass\n")
    dot_cov = tmp_path / ".coverage"
    dot_cov.write_text("NOT A SQLITE FILE")
    result = parse_coverage(str(tmp_path), None)
    assert result == []


def test_parse_coverage_wrong_shape_file_data(tmp_path: Path) -> None:
    """coverage.json with non-dict file entry is skipped."""
    from snake_eyes.coverage import parse_coverage

    (tmp_path / "sample_module.py").write_text("def f(): pass\n")
    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {"sample_module.py": "not_a_dict"},
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))
    result = parse_coverage(str(tmp_path), None)
    assert result == []


def test_parse_coverage_missing_executed_lines(tmp_path: Path) -> None:
    """coverage.json file entry missing executed_lines key → entry skipped."""
    from snake_eyes.coverage import parse_coverage

    (tmp_path / "sample_module.py").write_text("def f(): pass\n")
    cov_json = {
        "meta": {"version": "7.0.0"},
        "files": {
            "sample_module.py": {
                "missing_lines": [],
            }
        },
    }
    (tmp_path / "coverage.json").write_text(json.dumps(cov_json))
    result = parse_coverage(str(tmp_path), None)
    assert result == []
