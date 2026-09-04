"""Tests for analysis.detector — validates: gaze analyzer protocol v1.1.0."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from snake_eyes.analysis.detector import _resolve_alias, analyze_path, analyze_source
from snake_eyes.analysis.models import FunctionRecord, function_record_to_dict

# ---------------------------------------------------------------------------
# Fixtures dir
# ---------------------------------------------------------------------------

EFFECTS_DIR = Path(__file__).parent / "fixtures" / "effects"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NO_ANALOGUE_TYPES = {
    "ChannelClose",
    "DeferredReturnMutation",
    "AtomicOp",
    "CgoCall",
    "Panic",
    "UnsafeMutation",
}


def _to_dicts(records: list[FunctionRecord]) -> list[dict[str, Any]]:
    return [function_record_to_dict(r) for r in records]


def _types(records: list[FunctionRecord]) -> set[str]:
    return {e["type"] for r in _to_dicts(records) for e in r["side_effects"]}


def _all_effects(records: list[FunctionRecord]) -> list[dict[str, Any]]:
    return [e for r in _to_dicts(records) for e in r["side_effects"]]


def _has_type(records: list[FunctionRecord], typ: str) -> bool:
    return typ in _types(records)


def _copy_fixture(name: str, tmp_path: Path) -> Path:
    src = EFFECTS_DIR / name
    dest = tmp_path / name
    shutil.copy(src, dest)
    return tmp_path


# ---------------------------------------------------------------------------
# 7.2 — one positive test per each of the 10 new Python-specific types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture,effect_type,fixture_file",
    [
        ("p1.py", "GeneratorYield", "p1.py"),
        ("p1.py", "AsyncGeneratorYield", "p1.py"),
        ("container_local.py", "ContainerMutation", "container_local.py"),
        ("p1.py", "StreamOutput", "p1.py"),
        ("p2.py", "MetaprogrammingMutation", "p2.py"),
        ("p2.py", "ResourceManagement", "p2.py"),
        ("p2.py", "DescriptorEffect", "p2.py"),
        ("p2.py", "ImportSideEffect", "p2.py"),
        ("p2.py", "MonkeyPatch", "p2.py"),
        ("p0.py", "ErrorSignal", "p0.py"),
    ],
)
def test_new_type_detected(
    tmp_path: Path, fixture: str, effect_type: str, fixture_file: str
) -> None:
    """Each new Python-specific type must be detected with correct location."""
    _copy_fixture(fixture, tmp_path)
    records = analyze_path(str(tmp_path), None)
    assert _has_type(records, effect_type), f"{effect_type!r} not found in {fixture}"
    # location must contain the fixture filename
    matching = [
        e
        for r in _to_dicts(records)
        for e in r["side_effects"]
        if e["type"] == effect_type and fixture_file in e.get("location", "")
    ]
    assert matching, f"No {effect_type!r} with location containing {fixture_file!r}"


# ---------------------------------------------------------------------------
# 7.3 — P0 detector tests
# ---------------------------------------------------------------------------


def test_p0_return_value(tmp_path: Path) -> None:
    _copy_fixture("p0.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    assert _has_type(records, "ReturnValue")


def test_p0_error_return(tmp_path: Path) -> None:
    _copy_fixture("p0.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    assert _has_type(records, "ErrorReturn")


def test_p0_error_signal(tmp_path: Path) -> None:
    _copy_fixture("p0.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    assert _has_type(records, "ErrorSignal")


def test_p0_sentinel_error(tmp_path: Path) -> None:
    _copy_fixture("p0.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    assert _has_type(records, "SentinelError")


def test_p0_receiver_mutation(tmp_path: Path) -> None:
    _copy_fixture("p0.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    assert _has_type(records, "ReceiverMutation")


def test_p0_pointer_arg_mutation(tmp_path: Path) -> None:
    _copy_fixture("p0.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    assert _has_type(records, "PointerArgMutation")


def test_raise_dual_emits(tmp_path: Path) -> None:
    """A non-SystemExit raise emits BOTH ErrorReturn AND ErrorSignal."""
    _copy_fixture("p0.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    assert _has_type(records, "ErrorReturn")
    assert _has_type(records, "ErrorSignal")


def test_noop_zero_effects() -> None:
    records = analyze_source("def noop(): pass\n", "noop.py", "noop")
    assert records, "noop function should produce a FunctionRecord"
    effects = _all_effects(records)
    assert effects == [], f"noop() must have zero effects, got {effects}"


def test_location_contains_filename_and_line(tmp_path: Path) -> None:
    """At least one P0 effect must have location with filename + line number."""
    _copy_fixture("p0.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    all_effects = _all_effects(records)
    # location format: "filename.py:line:col"
    locs_with_file = [e for e in all_effects if "p0.py" in e.get("location", "")]
    assert locs_with_file, "At least one effect must have location with p0.py"
    # check that a numeric line number appears in the location
    for e in locs_with_file:
        parts = e["location"].split(":")
        assert len(parts) >= 2, f"Location {e['location']!r} must have line"
        assert parts[1].isdigit(), (
            f"Line in location must be numeric: {e['location']!r}"
        )


def test_full_effect_shape(tmp_path: Path) -> None:
    """At least one effect must have non-empty description; no classification key."""
    _copy_fixture("p0.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    all_effects = _all_effects(records)
    for e in all_effects:
        assert "description" in e and e["description"], "description must be non-empty"
        assert "classification" not in e, "classification must NOT be set"


def test_add_yields_exactly_one_return_value() -> None:
    """add(a, b) -> exactly ONE ReturnValue and NO PointerArgMutation."""
    records = analyze_source(
        "def add(a: int, b: int) -> int:\n    return a + b\n",
        "pure.py",
        "pure",
    )
    assert records
    effects = _all_effects(records)
    rv = [e for e in effects if e["type"] == "ReturnValue"]
    pam = [e for e in effects if e["type"] == "PointerArgMutation"]
    assert len(rv) == 1, f"Expected exactly 1 ReturnValue, got {rv}"
    assert pam == [], f"Expected no PointerArgMutation on add(), got {pam}"


def test_return_value_no_target_key() -> None:
    """A ReturnValue effect dict must NOT contain a 'target' key (omit-when-None)."""
    records = analyze_source("def f(): return 1\n", "f.py", "f")
    assert records
    rv_effects = [e for e in _all_effects(records) if e["type"] == "ReturnValue"]
    assert rv_effects, "ReturnValue must be emitted"
    for e in rv_effects:
        assert "target" not in e, f"ReturnValue must NOT have 'target' key: {e}"


def test_systemexit_raise_no_arg() -> None:
    """raise SystemExit => ProcessExit + ErrorSignal; NO ErrorReturn."""
    records = analyze_source("def f():\n    raise SystemExit\n", "f.py", "f")
    types = _types(records)
    assert "ProcessExit" in types
    assert "ErrorSignal" in types
    assert "ErrorReturn" not in types, "ErrorReturn must be absent for SystemExit"


def test_sys_exit_no_error_return() -> None:
    """sys.exit(0) => ProcessExit + ErrorSignal; NO ErrorReturn."""
    records = analyze_source("import sys\ndef f():\n    sys.exit(0)\n", "f.py", "f")
    types = _types(records)
    assert "ProcessExit" in types
    assert "ErrorSignal" in types
    assert "ErrorReturn" not in types, "ErrorReturn must be absent for sys.exit"


def test_os_exit_no_error_return() -> None:
    """os._exit(1) => ProcessExit + ErrorSignal; NO ErrorReturn."""
    records = analyze_source("import os\ndef f():\n    os._exit(1)\n", "f.py", "f")
    types = _types(records)
    assert "ProcessExit" in types
    assert "ErrorSignal" in types
    assert "ErrorReturn" not in types, "ErrorReturn must be absent for os._exit"


def test_no_analogue_types_never_emitted(tmp_path: Path) -> None:
    """None of the 6 no-analogue type strings must appear in any effect."""
    for name in ("p0.py", "p1.py", "p2.py", "p3.py", "pure.py", "container_local.py"):
        _copy_fixture(name, tmp_path)
    records = analyze_path(str(tmp_path), None)
    found = _types(records) & NO_ANALOGUE_TYPES
    assert not found, f"No-analogue types emitted: {found}"


# ---------------------------------------------------------------------------
# 7.4 — syntax_error.py skipped, valid file still returns
# ---------------------------------------------------------------------------


def test_syntax_error_skipped_valid_file_returned(tmp_path: Path) -> None:
    """syntax_error.py is skipped; valid file functions are still returned."""
    _copy_fixture("syntax_error.py", tmp_path)
    (tmp_path / "valid.py").write_text("def ok(): pass\n")
    records = analyze_path(str(tmp_path), None)
    names = [r.name for r in records]
    assert "ok" in names


# ---------------------------------------------------------------------------
# 7.14 — double-emit NEGATIVE assertions
# ---------------------------------------------------------------------------


def test_file_write_is_stream_output_not_writer_output(tmp_path: Path) -> None:
    """f = open(...,'w'); f.write(...) => StreamOutput NOT WriterOutput."""
    _copy_fixture("p1.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    assert _has_type(records, "StreamOutput"), "StreamOutput must be present"
    assert not _has_type(records, "WriterOutput"), "WriterOutput must be ABSENT"


def test_self_append_is_receiver_not_container(tmp_path: Path) -> None:
    """self.items.append(...) => ReceiverMutation NOT ContainerMutation."""
    source = "class C:\n    def m(self):\n        self.items.append(1)\n"
    records = analyze_source(source, "c.py", "c")
    types = _types(records)
    assert "ReceiverMutation" in types
    assert "ContainerMutation" not in types


def test_param_append_is_pointer_not_container(tmp_path: Path) -> None:
    """param.append(...) => PointerArgMutation NOT ContainerMutation."""
    source = "def f(items):\n    items.append(1)\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "PointerArgMutation" in types
    assert "ContainerMutation" not in types


def test_print_is_stdout_not_stream_output() -> None:
    """print(...) => StdoutWrite NOT StreamOutput."""
    records = analyze_source("def f():\n    print('hi')\n", "f.py", "f")
    types = _types(records)
    assert "StdoutWrite" in types
    assert "StreamOutput" not in types


# ---------------------------------------------------------------------------
# 7.11 — ambiguity tests
# ---------------------------------------------------------------------------


def test_getattr_call_is_callback_ambiguous(tmp_path: Path) -> None:
    """getattr(obj, name)() => CallbackInvocation with confidence='ambiguous'."""
    _copy_fixture("ambiguous.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    all_effects = _all_effects(records)
    cb_ambig = [
        e
        for e in all_effects
        if e["type"] == "CallbackInvocation"
        and e.get("detail", {}).get("confidence") == "ambiguous"
    ]
    assert cb_ambig, "CallbackInvocation(ambiguous) not found"
    # location must contain filename and line number
    for e in cb_ambig:
        assert "ambiguous.py" in e.get("location", "")
        parts = e["location"].split(":")
        assert len(parts) >= 2 and parts[1].isdigit()


def test_unknown_external_call_is_ambiguous(tmp_path: Path) -> None:
    """unknown_external_call() => CallbackInvocation with confidence='ambiguous'."""
    _copy_fixture("ambiguous.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    target = [record for record in records if record.name == "unknown_external_call"]
    assert _all_effects(target) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'some_unknown_function'",
            "location": "ambiguous.py:18:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_pure_local_call_no_effect() -> None:
    """A statically-resolvable pure local call is NOT an effect."""
    source = "def helper(): return 1\ndef caller():\n    helper()\n"
    records = analyze_source(source, "mod.py", "mod")
    caller_records = [r for r in records if r.name == "caller"]
    assert caller_records
    effects = _all_effects(caller_records)
    # helper is defined locally at module scope — per spec NEVER_DROP carve-out:
    # a statically-resolvable pure local call is NOT an effect.
    assert effects == [], (
        "caller() must have NO side effects (helper is a pure local call),"
        f" got {effects}"
    )


def test_pure_local_call_explicit() -> None:
    """A call to a pure builtin (len) produces NO effect."""
    source = "def f(items):\n    return len(items)\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "CallbackInvocation" not in types


# ---------------------------------------------------------------------------
# 7.13 — ordering assertions
# ---------------------------------------------------------------------------


def test_functions_ordered_by_file_line_name(tmp_path: Path) -> None:
    """functions[] ordered by (file, line, name)."""
    for name in ("p0.py", "p1.py"):
        _copy_fixture(name, tmp_path)
    records = analyze_path(str(tmp_path), None)
    dicts = _to_dicts(records)
    keys = [(r["file"], r["line"], r["name"]) for r in dicts]
    assert keys == sorted(keys), f"Not ordered by (file,line,name): {keys}"


def test_side_effects_ordered_by_line_col_type(tmp_path: Path) -> None:
    """side_effects[] within each function ordered by (line, col, type)."""
    _copy_fixture("p0.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    for r_dict in _to_dicts(records):
        effects = list(r_dict["side_effects"])

        def _sort_key(e: dict[str, Any]) -> tuple[int, int, str]:
            loc = e.get("location", "")
            parts = loc.split(":")
            line = int(parts[1]) if len(parts) > 1 else 0
            col = int(parts[2]) if len(parts) > 2 else 0
            return (line, col, e["type"])

        assert effects == sorted(effects, key=_sort_key), (
            f"side_effects not ordered for {r_dict['name']}: {effects}"
        )


# ---------------------------------------------------------------------------
# 7.9 — resource bounds: unreadable file + non-regular file
# ---------------------------------------------------------------------------


def test_unreadable_file_skipped_valid_returned(tmp_path: Path) -> None:
    """Unreadable file (chmod 000) is skipped; valid files still return."""
    bad = tmp_path / "bad.py"
    bad.write_text("def bad(): pass\n")
    os.chmod(bad, 0o000)
    (tmp_path / "good.py").write_text("def good(): pass\n")
    try:
        records = analyze_path(str(tmp_path), None)
        names = [r.name for r in records]
        assert "good" in names
    finally:
        os.chmod(bad, 0o644)


@pytest.mark.skipif(
    not hasattr(os, "mkfifo"), reason="mkfifo not available on this platform"
)
def test_fifo_skipped_valid_returned(tmp_path: Path) -> None:
    """FIFO with .py extension is skipped; valid files still return."""
    fifo = tmp_path / "pipe.py"
    os.mkfifo(fifo)
    (tmp_path / "good.py").write_text("def good(): pass\n")
    records = analyze_path(str(tmp_path), None)
    names = [r.name for r in records]
    assert "good" in names


# ---------------------------------------------------------------------------
# 7.10 — detector vs complexity function-set consistency
# ---------------------------------------------------------------------------


def test_detector_complexity_function_set_match(tmp_path: Path) -> None:
    """(file, name, line) tuples from analyze_path must match compute_complexity."""
    from snake_eyes.analysis.complexity import compute_complexity

    for name in ("p0.py", "pure.py"):
        _copy_fixture(name, tmp_path)

    det_records = analyze_path(str(tmp_path), None)
    cplx_entries = compute_complexity(str(tmp_path), None)

    det_set = {(r.file, r.name, r.line) for r in det_records}
    cplx_set = {(e["file"], e["name"], e["line"]) for e in cplx_entries}

    only_det = det_set - cplx_set
    only_cplx = cplx_set - det_set
    assert det_set == cplx_set, (
        f"Mismatch:\n  detector only: {only_det}\n  complexity only: {only_cplx}"
    )


# ---------------------------------------------------------------------------
# H4 — full-equality golden test for p0.py
# ---------------------------------------------------------------------------


def test_p0_golden_full_equality(tmp_path: Path) -> None:
    """Full-equality golden test: every function in p0.py must match expected
    side_effects exactly (type, location, target, detail).

    This test locks against false positives, wrong per-function attribution,
    and wrong location/target/detail values.  Pin the real, correct detector
    output — do NOT invent values.
    """
    _copy_fixture("p0.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    dicts = {r["name"]: r["side_effects"] for r in _to_dicts(records)}

    # --- returns_value ---
    assert dicts["returns_value"] == [
        {
            "type": "SentinelError",
            "description": "Module defines sentinel exception class 'MyError'",
            "location": "p0.py:5:0",
            "target": "MyError",
        },
        {
            "type": "ReturnValue",
            "description": "Function returns a value",
            "location": "p0.py:10:4",
        },
    ], f"returns_value mismatch: {dicts['returns_value']}"

    # --- raises_error ---
    # NOTE: MyError is a module-level ClassDef — its constructor call is now
    # resolved as a known class constructor, not an opaque callback.  The
    # CallbackInvocation entry that was here before issue #18 was a false positive.
    assert dicts["raises_error"] == [
        {
            "type": "ErrorReturn",
            "description": "Function signals error via raise",
            "location": "p0.py:14:4",
            "target": "MyError",
        },
        {
            "type": "ErrorSignal",
            "description": "Exception signal via raise",
            "location": "p0.py:14:4",
        },
    ], f"raises_error mismatch: {dicts['raises_error']}"

    # --- mutate_self ---
    assert dicts["mutate_self"] == [
        {
            "type": "ReceiverMutation",
            "description": "Mutates receiver attribute 'x'",
            "location": "p0.py:19:8",
            "target": "self.x",
        },
    ], f"mutate_self mismatch: {dicts['mutate_self']}"

    # --- mutate_param ---
    assert dicts["mutate_param"] == [
        {
            "type": "PointerArgMutation",
            "description": "Mutates parameter 'items' via .append()",
            "location": "p0.py:22:8",
            "target": "items",
        },
    ], f"mutate_param mismatch: {dicts['mutate_param']}"


# ---------------------------------------------------------------------------
# H4 — p3.py positive assertion (intended effects detected)
# ---------------------------------------------------------------------------


def test_p3_positive_effects(tmp_path: Path) -> None:
    """p3.py must emit StdoutWrite, EnvVarMutation, ProcessExit and ErrorSignal."""
    _copy_fixture("p3.py", tmp_path)
    records = analyze_path(str(tmp_path), None)
    dicts_by_name = {r["name"]: r["side_effects"] for r in _to_dicts(records)}

    # say_hello: print("hello") => StdoutWrite
    assert any(e["type"] == "StdoutWrite" for e in dicts_by_name["say_hello"]), (
        f"say_hello must emit StdoutWrite: {dicts_by_name['say_hello']}"
    )

    # set_env: os.environ["X"] = "1" => EnvVarMutation
    assert any(e["type"] == "EnvVarMutation" for e in dicts_by_name["set_env"]), (
        f"set_env must emit EnvVarMutation: {dicts_by_name['set_env']}"
    )

    # exit_process: sys.exit(0) => ProcessExit + ErrorSignal
    exit_types = {e["type"] for e in dicts_by_name["exit_process"]}
    assert "ProcessExit" in exit_types, (
        f"exit_process must emit ProcessExit: {dicts_by_name['exit_process']}"
    )
    assert "ErrorSignal" in exit_types, (
        f"exit_process must emit ErrorSignal: {dicts_by_name['exit_process']}"
    )


# ---------------------------------------------------------------------------
# Guard LOW — input() is not pure; yields an effect
# ---------------------------------------------------------------------------


def test_input_call_yields_effect() -> None:
    """input() must NOT be silently dropped — it is an stdin I/O effect.

    After removing input from _PURE_BUILTINS, the detector falls through to
    CallbackInvocation(ambiguous) since input has real I/O semantics.
    """
    source = "def f():\n    x = input('prompt: ')\n    return x\n"
    records = analyze_source(source, "f.py", "f")
    all_effects = _all_effects(records)
    effect_types = {e["type"] for e in all_effects}
    assert effect_types - {"ReturnValue"}, (
        f"input() must produce at least one non-ReturnValue effect, got {all_effects}"
    )
    # Specifically, it must be CallbackInvocation(ambiguous) — not dropped silently
    cb = [
        e
        for e in all_effects
        if e["type"] == "CallbackInvocation"
        and e.get("detail", {}).get("confidence") == "ambiguous"
    ]
    assert cb, f"input() must produce CallbackInvocation(ambiguous), got {all_effects}"


# ---------------------------------------------------------------------------
# Guard LOW — FileSystemWrite gated on open mode
# ---------------------------------------------------------------------------


def test_write_mode_open_co_emits_filesystem_write() -> None:
    """open(p, 'w') + .write() => StreamOutput AND FileSystemWrite."""
    source = "def f(p):\n    fh = open(p, 'w')\n    fh.write('data')\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "StreamOutput" in types, "write-mode open must emit StreamOutput"
    assert "FileSystemWrite" in types, "write-mode open must co-emit FileSystemWrite"


def test_read_mode_open_no_filesystem_write() -> None:
    """open(p, 'r') + .write() => StreamOutput ONLY; NO FileSystemWrite co-emit.

    Chosen approach: mode tracking (dict[var, is_write_mode]) on open_vars.
    A read-mode open that has a .write() call on it still emits StreamOutput
    (because the file object has a .write method), but must NOT co-emit
    FileSystemWrite — contradicting a write operation on a read-mode handle.
    """
    source = "def f(p):\n    fh = open(p, 'r')\n    fh.write('x')\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "StreamOutput" in types, "open-var .write() must still emit StreamOutput"
    assert "FileSystemWrite" not in types, (
        "read-mode open must NOT co-emit FileSystemWrite"
    )


def test_unknown_mode_open_no_filesystem_write() -> None:
    """open(p) with no mode arg => mode unknown; no FileSystemWrite co-emit."""
    source = "def f(p):\n    fh = open(p)\n    fh.write('x')\n"
    records = analyze_source(source, "f.py", "f")
    types = _types(records)
    assert "StreamOutput" in types, "no-mode open .write() must emit StreamOutput"
    assert "FileSystemWrite" not in types, (
        "unknown-mode open must NOT co-emit FileSystemWrite"
    )


# ---------------------------------------------------------------------------
# M6d — depth-budget guard: an over-deep AST is skipped gracefully; a
#        co-present valid file still yields effects.
#
# NOTE: MAX_AST_DEPTH (200) is unreachable via nested *source text* — CPython's
# tokenizer rejects indentation past MAXINDENT (100) with IndentationError
# before the budget is hit, so ast.parse() would fail first. We therefore inject
# an over-deep AST tree in memory (a deep expression inside one function body)
# through a mocked iter_source_files, mirroring the complexity-path guard test.
# ---------------------------------------------------------------------------


def test_depth_budget_skip_valid_file_unaffected(tmp_path: Path) -> None:
    """An over-deep function body trips the effect-visitor depth guard and is
    skipped without crashing; a co-present valid file still yields its effects.

    Covers _EffectVisitor._check_depth (detector.py) — a Constitution V resource
    bound — by injecting a deep expression AST that bypasses the tokenizer's
    MAXINDENT limit (source-text nesting cannot reach MAX_AST_DEPTH).
    """
    import ast
    from unittest import mock

    import snake_eyes.analysis.detector as det_mod
    from snake_eyes.analysis._shared import MAX_AST_DEPTH

    # One function whose body is a single very deep expression: 1 + 1 + 1 + ...
    # (BinOp nesting deeper than MAX_AST_DEPTH).
    expr: ast.expr = ast.Constant(value=1)
    for _ in range(MAX_AST_DEPTH + 10):
        expr = ast.BinOp(left=expr, op=ast.Add(), right=ast.Constant(value=1))
    deep_func = ast.FunctionDef(
        name="deep",
        args=ast.arguments(
            posonlyargs=[],
            args=[],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[ast.Expr(value=expr)],
        decorator_list=[],
        lineno=1,
        col_offset=0,
    )
    deep_module = ast.Module(body=[deep_func], type_ignores=[])
    ast.fix_missing_locations(deep_module)

    # Co-present valid file with a known effect.
    (tmp_path / "good.py").write_text("def ok():\n    return 42\n")

    original_iter = det_mod.iter_source_files

    def mock_iter(root_path, rel_paths):
        yield ("deep.py", "", deep_module)
        yield from original_iter(root_path, [p for p in rel_paths if p != "deep.py"])

    with mock.patch.object(det_mod, "iter_source_files", mock_iter):
        records = analyze_path(str(tmp_path), None)

    names = [r.name for r in records]
    # deep.py tripped the depth guard and was skipped (no crash); the valid
    # file's effects are still present.
    assert "ok" in names, f"valid function 'ok' must be present; got {names}"
    ok_records = [r for r in records if r.name == "ok"]
    ok_types = {e["type"] for r in _to_dicts(ok_records) for e in r["side_effects"]}
    assert "ReturnValue" in ok_types, f"ok() must emit ReturnValue; got {ok_types}"


# ---------------------------------------------------------------------------
# Issue #18 — CallbackInvocation false positives for same-module class
#              constructors, without suppressing unresolved calls.
# ---------------------------------------------------------------------------


def test_module_level_class_no_callback() -> None:
    """3.2 — module-level ClassDef call: no CallbackInvocation."""
    source = "class MyModel:\n    pass\ndef f():\n    MyModel()\n"
    records = analyze_source(source, "mod.py", "mod")
    assert len(records) == 1
    assert _all_effects(records) == []


def test_nested_class_no_callback() -> None:
    """3.3 — calling a nested class must NOT produce CallbackInvocation."""
    source = "def f():\n    class Inner:\n        pass\n    Inner()\n"
    records = analyze_source(source, "mod.py", "mod")
    assert len([r for r in records if r.name == "f"]) == 1
    assert _all_effects([r for r in records if r.name == "f"]) == []


def test_imported_name_still_callback() -> None:
    """Imported callables remain ambiguous without effect-specific resolution."""
    source = "from pathlib import Path\ndef f():\n    Path('.')\n"
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects(records) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Path'",
            "location": "mod.py:3:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_imported_side_effectful_name_still_callback() -> None:
    """A direct import must not hide an effect-specific call from later analysis."""
    source = "from shutil import rmtree\ndef f(path):\n    rmtree(path)\n"
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects(records) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'rmtree'",
            "location": "mod.py:3:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_pascalcase_name_still_callback() -> None:
    """Naming alone cannot establish that a callback is effect-free."""
    source = "def f():\n    UnknownWidget()\n"
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects(records) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'UnknownWidget'",
            "location": "mod.py:2:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_parameter_shadowing_class_still_callback() -> None:
    """A parameter binding takes precedence over a module-level class name."""
    source = "class Handler:\n    pass\ndef f(Handler):\n    Handler()\n"
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:4:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_rebinding_class_name_still_callback() -> None:
    """A function-local assignment shadows a same-named module class."""
    source = (
        "class Handler:\n    pass\ndef f(factory):\n"
        "    Handler = factory\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:5:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_effectful_class_constructor_still_callback() -> None:
    """Class names are suppressed only when construction cannot run user code."""
    source = (
        "class Handler:\n    def __init__(self):\n        pass\n"
        "def f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:5:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_module_rebinding_class_name_still_callback() -> None:
    """A module assignment supersedes an otherwise safe class binding."""
    source = "class Handler:\n    pass\nHandler = factory\ndef f():\n    Handler()\n"
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:5:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_shadowed_exception_base_still_callback() -> None:
    """An exception base name must be proven to be the builtin."""
    source = (
        "class Exception:\n    def __init__(self):\n        pass\n"
        "class Handler(Exception):\n    pass\ndef f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:7:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_pattern_capture_class_name_still_callback() -> None:
    """A capture pattern creates a local binding that shadows a class name."""
    source = (
        "class Handler:\n    pass\ndef f(value):\n"
        "    match value:\n        case Handler:\n            pass\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:7:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


@pytest.mark.parametrize(
    ("source", "function_name", "location"),
    [
        (
            "class Handler:\n    pass\ndef f():\n"
            "    class Handler:\n        def __init__(self):\n            pass\n"
            "    Handler()\n",
            "f",
            "mod.py:7:4",
        ),
        (
            "class Handler:\n    pass\ndef outer(Handler):\n"
            "    def inner():\n        Handler()\n",
            "inner",
            "mod.py:5:8",
        ),
        (
            "class Handler:\n    pass\nif enabled:\n    Handler = factory\n"
            "def f():\n    Handler()\n",
            "f",
            "mod.py:6:4",
        ),
        (
            "class Handler:\n    pass\nmatch value:\n"
            "    case {**Handler}:\n        pass\n"
            "def f():\n    Handler()\n",
            "f",
            "mod.py:7:4",
        ),
        (
            "class Exception:\n    pass\ndef outer():\n"
            "    class Handler(Exception):\n        pass\n    Handler()\n",
            "outer",
            "mod.py:6:4",
        ),
        (
            "class Handler:\n    pass\ndef f():\n"
            "    class Handler:\n        pass\n    class Handler:\n        pass\n"
            "    Handler()\n",
            "f",
            "mod.py:8:4",
        ),
    ],
)
def test_shadowed_class_boundaries_still_callback(
    source: str, function_name: str, location: str
) -> None:
    """Competing bindings prevent a class call from being proven safe."""
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == function_name]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": location,
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_nested_scope_binding_does_not_shadow_module_class() -> None:
    """A child function's binding does not belong to its enclosing scope."""
    source = (
        "class Handler:\n    pass\ndef outer():\n"
        "    def inner():\n        Handler = factory\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "outer"]) == []


@pytest.mark.parametrize(
    ("binding", "call_line"),
    [
        ("for Handler in factories:\n    pass", 6),
        ("with manager as Handler:\n    pass", 6),
        ("try:\n    pass\nexcept Error as Handler:\n    pass", 8),
        ("import package as Handler", 5),
        ("def configure(value=(Handler := factory)):\n    pass", 6),
        ("configure = lambda value=(Handler := factory): None", 5),
    ],
)
def test_module_binding_forms_keep_class_call_ambiguous(
    binding: str, call_line: int
) -> None:
    """Every enclosing-scope binder competes with a safe class definition."""
    source = f"class Handler:\n    pass\n{binding}\ndef f():\n    Handler()\n"
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": f"mod.py:{call_line}:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_binding_after_call_is_conservatively_ambiguous() -> None:
    """Resolution is scope-wide rather than source-order-sensitive."""
    source = (
        "class Handler:\n    pass\ndef f():\n    Handler()\n    Handler = factory\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:4:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_global_declaration_uses_safe_module_class() -> None:
    """A global declaration does not itself replace the module binding."""
    source = "class Handler:\n    pass\ndef f():\n    global Handler\n    Handler()\n"
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == []


@pytest.mark.parametrize(
    ("source", "function_name", "location"),
    [
        (
            "class Handler:\n    pass\nfrom package import *\n"
            "def f():\n    Handler()\n",
            "f",
            "mod.py:5:4",
        ),
        (
            "if enabled:\n    class Handler:\n        pass\ndef f():\n    Handler()\n",
            "f",
            "mod.py:5:4",
        ),
        (
            "class Handler:\n    pass\nHandler.__init__ = callback\n"
            "def f():\n    Handler()\n",
            "f",
            "mod.py:5:4",
        ),
        (
            "class Handler:\n    pass\ndef replace(factory):\n"
            "    global Handler\n    Handler = factory\ndef f():\n    Handler()\n",
            "f",
            "mod.py:7:4",
        ),
    ],
)
def test_module_class_invalidations_stay_ambiguous(
    source: str, function_name: str, location: str
) -> None:
    """Potential module replacement invalidates safe-class resolution."""
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == function_name]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": location,
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_nested_global_declaration_bypasses_enclosing_binding() -> None:
    """A nested global declaration resolves against the module, not its closure."""
    source = (
        "class Handler:\n    pass\ndef outer(Handler):\n"
        "    def inner():\n        global Handler\n        Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "inner"]) == []


def test_control_flow_global_write_invalidates_module_class() -> None:
    """A global write is function-wide even when declared under control flow."""
    source = (
        "class Handler:\n    pass\ndef replace(factory, enabled):\n"
        "    if enabled:\n        global Handler\n        Handler = factory\n"
        "def f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:8:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_control_flow_global_bypasses_enclosing_binding() -> None:
    """A nested global declaration bypasses closures regardless of placement."""
    source = (
        "class Handler:\n    pass\ndef outer(Handler, enabled):\n"
        "    def inner():\n        if enabled:\n            global Handler\n"
        "        Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "inner"]) == []


@pytest.mark.parametrize("operation", ["setattr", "delattr"])
def test_module_constructor_call_mutation_stays_ambiguous(operation: str) -> None:
    """Reflective constructor mutation invalidates safe module classes."""
    arguments = (
        'Handler, "__init__", callback'
        if operation == "setattr"
        else 'Handler, "__init__"'
    )
    source = (
        f"class Handler:\n    pass\n{operation}({arguments})\ndef f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:5:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_local_constructor_mutation_stays_ambiguous() -> None:
    """A mutated local class is not treated as a safe constructor."""
    source = (
        "def f(callback):\n    class Handler:\n        pass\n"
        "    Handler.__init__ = callback\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:5:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_unrelated_class_attribute_mutation_keeps_constructor_safe() -> None:
    """Non-constructor attributes do not invalidate a trivial class."""
    source = (
        "class Handler:\n    pass\nHandler.label = value\ndef f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == []


def test_local_attribute_mutation_does_not_invalidate_module_class() -> None:
    """Mutation through a local shadow does not replace the module class."""
    source = (
        "class Handler:\n    pass\ndef mutate(Handler):\n"
        "    Handler.__init__ = callback\ndef f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == []


def test_global_constructor_mutation_invalidates_module_class() -> None:
    """Constructor mutation through an explicit global invalidates the class."""
    source = (
        "class Handler:\n    pass\ndef mutate(callback):\n    global Handler\n"
        '    setattr(Handler, "__init__", callback)\ndef f():\n    Handler()\n'
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:7:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


@pytest.mark.parametrize(
    "mutation",
    [
        "Handler.__init__ = callback",
        'setattr(Handler, "__init__", callback)',
        'delattr(Handler, "__init__")',
    ],
)
def test_implicit_global_constructor_mutation_invalidates_module_class(
    mutation: str,
) -> None:
    """An unbound constructor-mutation target resolves to module scope."""
    source = (
        f"class Handler:\n    pass\ndef mutate(callback):\n    {mutation}\n"
        "def f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:6:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_enclosing_constructor_mutation_does_not_invalidate_module_class() -> None:
    """A closure mutation targets the enclosing value, not the module class."""
    source = (
        "class Handler:\n    pass\ndef outer(Handler, callback):\n"
        "    def mutate():\n        Handler.__init__ = callback\n"
        "def f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == []


def test_global_exception_base_bypasses_enclosing_binding() -> None:
    """A global exception base does not resolve through an enclosing parameter."""
    source = (
        "def outer(Exception):\n    def inner():\n        global Exception\n"
        "        class Handler(Exception):\n            pass\n        Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "inner"]) == []


@pytest.mark.parametrize(
    "mutation",
    [
        "Handler.__init__ = callback",
        "del Handler.__init__",
        "Handler.__new__ = callback",
        "del Handler.__new__",
        'setattr(Handler, "__init__", callback)',
        'delattr(Handler, "__init__")',
        'setattr(Handler, "__new__", callback)',
        'delattr(Handler, "__new__")',
    ],
)
def test_constructor_mutation_matrix_stays_ambiguous(mutation: str) -> None:
    """Every statically identifiable constructor mutation invalidates safety."""
    source = f"class Handler:\n    pass\n{mutation}\ndef f():\n    Handler()\n"
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:5:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


@pytest.mark.parametrize(
    "class_source",
    [
        "@decorator\nclass Handler:\n    pass",
        "class Handler(metaclass=Meta):\n    pass",
        "class Handler(CustomBase):\n    pass",
        'class Handler:\n    "docstring"',
    ],
)
def test_unsafe_class_forms_stay_ambiguous(class_source: str) -> None:
    """Executable class forms never enter the safe-constructor set."""
    source = f"{class_source}\ndef f():\n    Handler()\n"
    records = analyze_source(source, "mod.py", "mod")
    call_line = len(class_source.splitlines()) + 2
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": f"mod.py:{call_line}:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_class_body_constructor_mutation_invalidates_module_class() -> None:
    """A class body can mutate a module class through ordinary name lookup."""
    source = (
        "class Handler:\n    pass\nclass Mutator:\n"
        "    Handler.__init__ = callback\ndef f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:6:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_class_body_enclosing_mutation_invalidates_local_class() -> None:
    """A nested class body can mutate a class in its enclosing function."""
    source = (
        "def outer(callback):\n    class Handler:\n        pass\n"
        "    class Mutator:\n        Handler.__init__ = callback\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "outer"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:6:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_class_body_enclosing_mutation_does_not_invalidate_module_class() -> None:
    """A nested class body resolves an enclosing parameter before the module."""
    source = (
        "class Handler:\n    pass\ndef outer(Handler, callback):\n"
        "    class Mutator:\n        Handler.__init__ = callback\n"
        "def f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == []


def test_class_body_mutation_uses_source_order() -> None:
    """A later class-namespace binding cannot hide an earlier module mutation."""
    source = (
        "class Handler:\n    pass\nclass Mutator:\n"
        "    Handler.__init__ = callback\n    Handler = replacement\n"
        "def f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:7:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_lambda_constructor_mutation_invalidates_module_class() -> None:
    """A lambda body resolves an unbound mutation target at module scope."""
    source = (
        "class Handler:\n    pass\nmutate = lambda callback: "
        'setattr(Handler, "__init__", callback)\ndef f():\n    Handler()\n'
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:5:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_conditional_class_binding_does_not_hide_module_mutation() -> None:
    """A conditional class binding is not definitely established afterward."""
    source = (
        "class Handler:\n    pass\nclass Mutator:\n    if enabled:\n"
        "        Handler = replacement\n    Handler.__init__ = callback\n"
        "def f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:8:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_constructor_attribute_on_function_does_not_change_call_safety() -> None:
    """Constructor-hook mutation invalidation applies only to classes."""
    source = (
        "def Handler():\n    pass\nHandler.__init__ = callback\n"
        "def f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == []


def test_class_global_rebinding_invalidates_module_class() -> None:
    """A class-scope global assignment replaces the module binding."""
    source = (
        "class Handler:\n    pass\nclass Mutator:\n    global Handler\n"
        "    Handler = callback\ndef f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:7:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_annotation_only_class_name_does_not_hide_module_mutation() -> None:
    """An annotation without a value does not establish a class binding."""
    source = (
        "class Handler:\n    pass\nclass Mutator:\n    Handler: object\n"
        "    Handler.__init__ = callback\ndef f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:7:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_lambda_walrus_binding_does_not_invalidate_module_class() -> None:
    """A lambda-local walrus target owns its subsequent constructor mutation."""
    source = (
        "class Handler:\n    pass\ndef build(factory, callback):\n"
        "    return lambda: ((Handler := factory), "
        'setattr(Handler, "__init__", callback))\ndef f():\n    Handler()\n'
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == []


def test_deleted_class_binding_exposes_module_constructor_mutation() -> None:
    """Deleting a class-local name restores lookup of the module class."""
    source = (
        "class Handler:\n    pass\nclass Mutator:\n    Handler = replacement\n"
        "    del Handler\n    Handler.__init__ = callback\ndef f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:8:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


@pytest.mark.parametrize(
    "body",
    [
        "Alias = Handler\nAlias.__init__ = callback",
        "def mutate(callback):\n    Alias = Handler\n    Alias.__init__ = callback",
    ],
)
def test_constructor_mutation_through_direct_alias_invalidates_class(body: str) -> None:
    """A direct alias names the same class object for constructor mutation."""
    source = f"class Handler:\n    pass\n{body}\ndef f():\n    Handler()\n"
    records = analyze_source(source, "mod.py", "mod")
    call_line = len(source.splitlines())
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": f"mod.py:{call_line}:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


@pytest.mark.parametrize(
    "body",
    [
        "Alias = Handler\nAlias2 = Alias\nAlias2.__init__ = callback",
        "class Mutator:\n    Alias = Handler\n    Alias2 = Alias\n"
        "    Alias2.__init__ = callback",
    ],
)
def test_constructor_mutation_through_alias_chain_invalidates_class(body: str) -> None:
    """Constructor mutations propagate through transitive direct-name aliases."""
    source = f"class Handler:\n    pass\n{body}\ndef f():\n    Handler()\n"
    records = analyze_source(source, "mod.py", "mod")
    call_line = len(source.splitlines())
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": f"mod.py:{call_line}:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


@pytest.mark.parametrize(
    "alias_change",
    [
        "del Alias",
        "Alias = replacement",
    ],
)
def test_changed_class_alias_does_not_mutate_original_class(alias_change: str) -> None:
    """Deleted or rebound aliases no longer identify the original class."""
    source = (
        "class Handler:\n    pass\nclass Mutator:\n    Alias = Handler\n"
        f"    {alias_change}\n    Alias.__init__ = callback\ndef f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == []


@pytest.mark.parametrize(
    "body",
    [
        "Alias = Handler\nAlias2 = Alias\nAlias = replacement\n"
        "Alias2.__init__ = callback",
        "class Mutator:\n    Alias = Handler\n    Alias2 = Alias\n"
        "    Alias = replacement\n    Alias2.__init__ = callback",
        "class Mutator:\n    Alias: object = Handler\n    Alias.__init__ = callback",
        "Alias = Handler\nAlias2 = Alias\nAlias = Alias2\nAlias.__init__ = callback",
    ],
)
def test_alias_snapshot_preserves_constructor_identity(body: str) -> None:
    """Aliases retain the object resolved when their assignment executes."""
    source = f"class Handler:\n    pass\n{body}\ndef f():\n    Handler()\n"
    records = analyze_source(source, "mod.py", "mod")
    call_line = len(source.splitlines())
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": f"mod.py:{call_line}:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_conditional_alias_rebinding_preserves_possible_constructor() -> None:
    """A conditional rebind cannot discard the alias's prior class identity."""
    source = (
        "class Handler:\n    pass\nAlias = Handler\nif enabled:\n"
        "    Alias = replacement\nAlias.__init__ = callback\ndef f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:8:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_enclosing_alias_resolves_class_body_constructor_mutation() -> None:
    """A class-body alias can retain a class from its enclosing function."""
    source = (
        "def outer(callback):\n    class Handler:\n        pass\n"
        "    Alias = Handler\n    class Mutator:\n        Retained = Alias\n"
        "        Retained.__init__ = callback\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "outer"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:8:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]


def test_unresolved_alias_cycle_terminates_without_invalidating_class() -> None:
    """An unresolved alias cycle terminates and does not name a safe class."""
    source = (
        "class Handler:\n    pass\nA = B\nB = A\nA.__init__ = callback\n"
        "def f():\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == []


def test_conditional_enclosing_alias_reaches_class_body_mutation() -> None:
    """All conditional enclosing identities propagate through a class alias."""
    source = (
        "class Handler:\n    pass\nclass Other:\n    pass\nAlias = Other\n"
        "if enabled:\n    Alias = Handler\nclass Mutator:\n    Retained = Alias\n"
        "    Retained.__init__ = callback\ndef f():\n    Handler()\n    Other()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": "mod.py:12:4",
            "detail": {"confidence": "ambiguous"},
        },
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Other'",
            "location": "mod.py:13:4",
            "detail": {"confidence": "ambiguous"},
        },
    ]


def test_resolve_alias_terminates_on_real_cycle() -> None:
    """Cycle protection applies to an actual cyclic alias map."""
    assert _resolve_alias("A", {"A": "B", "B": "A"}) == "A"


def test_alias_target_overflow_keeps_local_class_ambiguous() -> None:
    """Alias fan-out overflow fails closed for function-local classes."""
    branches = "\n".join(
        f"    if condition_{index}:\n        Alias = Target{index}"
        for index in range(63)
    )
    source = (
        "def f(callback):\n    class Handler:\n        pass\n    Alias = Initial\n"
        f"{branches}\n    if final_condition:\n        Alias = Handler\n"
        "    Alias.__init__ = callback\n    Handler()\n"
    )
    records = analyze_source(source, "mod.py", "mod")
    call_line = len(source.splitlines())
    assert _all_effects([r for r in records if r.name == "f"]) == [
        {
            "type": "CallbackInvocation",
            "description": "Ambiguous call to 'Handler'",
            "location": f"mod.py:{call_line}:4",
            "detail": {"confidence": "ambiguous"},
        }
    ]
