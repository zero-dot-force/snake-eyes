## Why

snake-eyes advertises the three required Gaze protocol v1.1.0 methods — `analyze`, `complexity`, and `coverage` — as unimplemented (`-32601`). Until they land, Gaze has no Python side-effect detection, no per-function cyclomatic complexity, and no coverage-to-function mapping to feed its universal scoring engine. Issue #3 (`taxonomy-and-discovery`) already landed the 48-type `SideEffectType` taxonomy, the `Effect`/`FunctionRecord` models, and `discover()`; this change consumes them to make snake-eyes a complete required-method Gaze backend. Implements #4; depends on #3 (taxonomy-and-discovery, merged).

## What Changes

- Add `src/snake_eyes/analysis/complexity.py`: lift the gaze-py McCabe `cyclomatic_complexity` logic and adapt it to pass project gates (full type annotations for mypy --strict, ruff format, import sorting), retaining provenance headers (gaze-py copyright + Apache-2.0 §4(b) change notice). Compute complexity per `FunctionDef`/`AsyncFunctionDef`, including nested functions and methods of nested classes; lambdas are not functions.
- Add `src/snake_eyes/analysis/detector.py`: lift the gaze-py detector core logic and adapt it to pass project gates, retaining provenance headers (gaze-py copyright + Apache-2.0 §4(b) change notice); expose `analyze_path(root_path, patterns)` and `analyze_source(source, filename, package)`; detect the original taxonomy types that have a Python analogue, plus 10 new Python-specific types (`ErrorSignal`, `GeneratorYield`, `ContainerMutation`, `StreamOutput`, `AsyncGeneratorYield`, `MetaprogrammingMutation`, `DescriptorEffect`, `ResourceManagement`, `ImportSideEffect`, `MonkeyPatch`). The `SideEffectType` enum retains all 48 members as vocabulary, but `ChannelClose`, `DeferredReturnMutation`, `AtomicOp`, `CgoCall`, `Panic`, and `UnsafeMutation` have no reliable Python analogue and are not detected. Dual-emit `ErrorSignal` alongside `ErrorReturn` for every `raise`; report ambiguous constructs (`eval`, `exec`, computed `getattr` calls) as a best-effort effect or `CallbackInvocation` with `detail={"confidence": "ambiguous"}` — never silently dropped.
- Add `src/snake_eyes/coverage.py`: `parse_coverage(root_path, patterns)` reading `coverage.json` (stdlib `json`) or `.coverage` (coverage.py API via `Coverage.analysis2()`), mapping executed/missing lines to functions via AST; missing data returns an empty result, not an error; never runs the analyzed project's tests.
- Wire `analyze`, `complexity`, and `coverage` handlers into `DEFAULT_DISPATCH`. All three share `{root_path, patterns}` params; missing `root_path` returns `-32602`; parse-error files (raising `SyntaxError`, `ValueError`, `RecursionError`, `OSError`, or `MemoryError`) are skipped and the request continues. `initialize` capability flags are unchanged.
- Add `coverage>=7.0,<8` as the sole new runtime dependency. No `radon` (the lifted McCabe walk covers complexity); no `astroid`.
- Add fixtures under `tests/fixtures/effects/` and `tests/fixtures/coverage/` plus unit and JSON-RPC end-to-end tests.
- RESOURCE_BOUNDS safeguards (Constitution V) and DETERMINISM guarantees (Constitution I) are part of this change: a per-file byte-size cap and AST depth/recursion budget bound analysis on untrusted input; output ordering is deterministic so the same input tree produces byte-identical JSON-RPC output.

Out of scope: `classify_signals`, `test_mapping`, `analyze/stream` streaming, running the analyzed project's test suite, CRAP/GazeCRAP/quadrant computation, classification labels on effects (Gaze classifies), astroid-based name inference, and effect types with no Python analogue (`ChannelClose`, `DeferredReturnMutation`, `AtomicOp`, `CgoCall`, `Panic`, `UnsafeMutation`).

## Capabilities

### New Capabilities
- `detector`: Python side-effect detection engine — `analyze_path`/`analyze_source`, the per-function AST walk, and the normative detection rules for every `SideEffectType` value with a Python analogue (the original taxonomy types that have a Python analogue, plus the 10 new Python-specific types). The `SideEffectType` enum retains all 48 members as vocabulary; `ChannelClose`, `DeferredReturnMutation`, `AtomicOp`, `CgoCall`, `Panic`, and `UnsafeMutation` are not detected (no reliable Python analogue).
- `complexity`: cyclomatic complexity computation — the lifted McCabe `cyclomatic_complexity` logic and per-function complexity over discovered source and test files.
- `coverage-parser`: coverage.py data parsing — `parse_coverage` with `coverage.json`/`.coverage` lookup order and line-to-function mapping.
- `analyze-method`: the JSON-RPC `analyze` method — shared params, `functions[]` result schema with per-function `side_effects[]`, parse-error skip, and error mapping.
- `complexity-method`: the JSON-RPC `complexity` method — shared params, `functions[]` result schema with `complexity` and dotted `package` derivation.
- `coverage-method`: the JSON-RPC `coverage` method — shared params, `functions[]` result schema using the `function` field, and missing-data behavior.

### Modified Capabilities
None — `initialize` capability flags stay `{discover: true, test_mapping: false, classify_signals: false, streaming: false}`. `analyze`/`complexity`/`coverage` are required protocol methods, not advertised optional capability flags, so registering handlers changes no capability flag. `openspec/specs/` holds no archived capabilities yet, so there are no existing requirements to modify.

### Removed Capabilities
None.

## Impact

- New files: `src/snake_eyes/analysis/complexity.py`, `src/snake_eyes/analysis/detector.py`, `src/snake_eyes/coverage.py`; fixtures under `tests/fixtures/effects/` and `tests/fixtures/coverage/`; new test modules for detector, complexity, coverage, and the three JSON-RPC methods.
- Modified files: `src/snake_eyes/server.py` (register three handlers in `DEFAULT_DISPATCH`); `pyproject.toml` and `uv.lock` (add `coverage>=7.0,<8`); possibly `src/snake_eyes/analysis/__init__.py` (re-exports); `README.md` (status table row for analyze/complexity/coverage now implemented; coverage.py now a runtime dep; 'planned later' note updated); `AGENTS.md` (Technology Stack: radon→lifted gaze-py McCabe; Project Structure: complexity.py/coverage.py delivered here + add detector.py).
- Dependencies: one new runtime dependency, `coverage>=7.0,<8` (floor and ceiling), justified because reading `.coverage` SQLite data via the coverage.py API is safer and more forward-compatible than hand-rolling SQLite access; the `coverage.json` path uses only the stdlib. No `radon`, no `astroid`. SC-005 note: coverage.py is actively maintained; no known applicable CVE at this range.
- Provenance: `NOTICE` already attributes gaze-py (Matt Peter, Apache 2.0); the lifted `complexity.py` and `detector.py` retain their gaze-py copyright headers AND add an Apache-2.0 §4(b) change notice (e.g. `# Modified 2026 by zero-dot-force: extended with Python-specific detection; Go-only pattern lists removed.`).
- Protocol contract: three methods stop returning `-32601` and each returns protocol-shaped JSON; `initialize` output is unchanged, so existing clients see no capability change.

## Constitution Alignment

- **I. Protocol Fidelity** — The three methods conform to Gaze protocol v1.1.0: shared `{root_path, patterns}` params; `analyze`/`complexity` results use `functions[]` with `name`/`package`/`file`/`line`; `coverage` uses the `function` field with `start_line`/`end_line`/`covered_stmts`/`total_stmts`/`percentage`; effects carry no `classification` (Gaze classifies); missing `root_path` maps to `-32602`; output is deterministic. `initialize` capabilities are unchanged. — PASS
- **II. Detection Accuracy** — Every taxonomy type with a Python analogue is detected via normative AST rules; `ErrorSignal` is dual-emitted with `ErrorReturn`; ambiguous constructs are reported (best-effort effect or `CallbackInvocation` with `confidence: ambiguous`) rather than omitted. P0 false negatives in fixtures are release-blocking. Types with no Python analogue are not faked. — PASS
- **III. Python-Native Analysis** — Detection uses the `ast` and `symtable` stdlib modules; complexity uses the lifted McCabe walk over the `ast`; coverage uses the coverage.py API and stdlib `json`. No Python semantics are reimplemented, and no astroid is introduced in this change. — PASS
- **IV. Testability** — Coverage strategy: `complexity.py` 100%, `detector.py` 90%+, `coverage.py` 90%+, project gate held at 85%. `analyze_source` enables fixture-level unit tests without a full tree; JSON-RPC end-to-end tests exercise all three methods. One positive test per new type (10) and per P0 type (6); unused Go-only pattern lists are deleted rather than left uncovered. — PASS
- **V. Analysis Safety** — Static analysis only: `ast.parse` never executes analyzed code; coverage parsing reads data files but never invokes `coverage run` or pytest; parse-error files are skipped so the request continues. A per-file byte-size cap and AST depth/recursion budget (RESOURCE_BOUNDS) bound analysis on untrusted input; a file exceeding a bound is skipped-and-continued, never aborting the whole request. The single new dependency (coverage.py) is justified and used only to read data. — PASS
