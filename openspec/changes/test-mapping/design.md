## Context

Snake Eyes is a JSON-RPC analyzer that Gaze spawns as a subprocess. Issues #4 (analysis-methods) and #5 (classify-signals) have already landed: the detector (`analyze_path`), discovery (`discover`), the shared helpers (`_shared.derive_package`, `iter_source_files`), the effects taxonomy (`effects.SideEffectType`, `TIER_MAP`), and the astroid-based caller inference (`analysis/inference.py`) all exist in the tree. `astroid>=3.0,<4` is already a shipped runtime dependency.

Today `initialize` advertises `test_mapping: false` and no such method exists. Gaze's universal scoring engine wants Python test-to-assertion mapping data — which tests exercise which production functions, through which assertions, against which observable side effects — so it can compute test-quality and contract-coverage metrics on the Go side. This change implements the analyzer half of that contract.

The behavior is fully specified by issue #6, which states every decision is already made; this document records the technical approach and the rationale behind each choice, and defers CRAP/GazeCRAP/quadrant/contract-coverage computation to Gaze.

## Goals / Non-Goals

**Goals:**

- Deliver a protocol-faithful `test_mapping` JSON-RPC method returning `{"mappings": [...]}` per Gaze analyzer protocol v1.1.0.
- Pair Python tests to production functions using three strategies with first-match-wins priority and integer confidence scores.
- Emit one mapping row per assertion, classified into the six allowed `assertion_type` values, each carrying an inferred `side_effect_type`.
- Reuse existing snake-eyes infrastructure (`discover`, `analyze_path`, `derive_package`, `astroid` inference) rather than reimplementing it.
- Keep output deterministic and independently testable at the per-module coverage targets.

**Non-Goals:**

- Computing CRAP, GazeCRAP, quadrants, fix strategies, or contract-coverage percentages (Gaze owns scoring).
- Lifting gaze-py `quality/pipeline.py` (the pipeline is written fresh against snake-eyes models).
- Running pytest or reading coverage data during `test_mapping`.
- Modifying the signal extractors or the `classify_signals` method (independent of #5).
- Streaming responses (`streaming` stays `false`).

## Decisions

### Decision: New `src/snake_eyes/quality/` package with a lift/write split

Introduce a `quality/` package containing `pairing.py` (lifted), `assertions.py` (lifted), `mapping.py` (new), `pipeline.py` (new), and `__init__.py`. Pairing and assertion detection are lifted from gaze-py and adapted to snake-eyes `ast` usage and models; the pipeline and side-effect-type inference are written fresh.

*Rationale:* The issue grants permission to lift gaze-py's proven pairing and assertion logic (retaining copyright) but explicitly forbids lifting `quality/pipeline.py`, which is coupled to gaze-py's scoring. Splitting concerns per file keeps the lifted code isolated (with provenance headers) and the snake-eyes-specific orchestration clean and separately coverable.

*Alternatives considered:* A single `quality/mapping.py` module — rejected because it would blur lifted-vs-original provenance and make the 95% mapping / 85% pipeline coverage split unenforceable. Placing pairing under `analysis/` — rejected; `quality/` mirrors gaze-py's package boundary and keeps test-mapping concerns cohesive.

### Decision: Three-strategy, first-match-wins pairing with integer confidence

For each (test_function, test_file), evaluate strategies in priority order and stop at the first match, never emitting duplicate pairs for the same `(test_function, test_file, target_package, target_function)` key: (1) name convention — strip `test_`/`Test`/`test`/`Test` prefix, exact match confidence 90, case-only match confidence 70; (2) direct AST `Call` to the target name, confidence 80; (3) astroid transitive call graph via BFS with `depth_limit=5`, confidence 75. When a single strategy matches multiple same-named targets across different packages, each distinct `(target_package, target_function)` is paired, deterministically ordered by `analyze_path` order (sorted by `(file, line, name)`). `target_package` comes from the production file's dotted module path via the shared `_shared.derive_package` helper (same as `analyze`), or equivalently `FunctionRecord.package`.

*Rationale:* First-match-wins yields the highest-confidence relationship deterministically and avoids duplicate rows. Confidence is emitted as an integer 0–100 to match the protocol; lifted gaze-py scores on a 0.0–1.0 scale are converted at the lift boundary (0.9 → 90).

*Alternatives considered:* Emitting all matching strategies per pair (multi-row) — rejected; the protocol expects one relationship per (test, target) and multiplies assertion rows already. Keeping float confidence — rejected; violates protocol fidelity (`confidence` is int 0–100).

### Decision: Reuse shipped astroid for strategy 3 with graceful degradation

Strategy 3 builds a transitive call graph with astroid (already a dependency, reused as `analysis/inference.py` does) and BFS to `depth_limit=5`. The graph is built **lazily, on the first unpaired-test lookup — once per `run_test_mapping` request and then reused** for every subsequent lookup — mirroring `analysis/inference.py`, which builds its caller index once (`build_caller_index`) and reuses it (`CallerIndex.count`) rather than rebuilding per lookup — so a project is not re-parsed once per test, and a fully-paired project (every test paired by strategies 1–2) never triggers the astroid parse at all. Callees are matched by their resolved defining **file path**, not by `derive_package`'s dotted name (under a `src/` layout `derive_package` yields `src.sample.calculator`, which never equals astroid's inferred `sample.calculator`; `analysis/inference.py` established file-path matching for exactly this reason). To stay safe in the long-lived stdio server, strategy 3 clears `astroid.MANAGER` before building the graph (per-request isolation, so one request's tree cannot leak into another's) and again in a `finally` (bounding resident memory), mirroring `analysis/inference.py`. It catches a broadened exception set — astroid errors, `RecursionError`, `MemoryError`, and an unexpected catch-all — so pathological-but-parseable input degrades (strategy 3 skipped, strategies 1–2 still returned) rather than surfacing as `-32603`; the method never fails because of astroid, and each skip/degrade emits a one-line **stderr** diagnostic (stdout stays reserved for the JSON-RPC response), mirroring `analysis/inference.py`. The broadened catch SHALL NOT absorb `FileNotFoundError` — a non-existent root must still propagate to the handler as `-32602` (discovery, not the strategy-3 catch, is the source of that error).

*Rationale:* Constitution V (Analysis Safety) and issue #6 both require graceful degradation: ambiguity/omission of one strategy must not fail the whole method. Reusing the existing dependency adds no new supply-chain surface.

*Alternatives considered:* Adding a new call-graph library or bumping astroid to `<5` — rejected; astroid `>=3.0,<4` already ships and suffices. Making strategy 3 mandatory — rejected; it would make CI depend on astroid successfully importing an arbitrary fixture.

### Decision: Bounded, guarded parsing for untrusted input (Constitution V)

The pipeline treats analyzed source as untrusted. Test files are read only through the shared guarded reader (`_shared.iter_source_files` / `is_analyzable_file`), which enforces the 16 MiB `MAX_FILE_BYTES` byte cap and skips (rather than aborts on) files that exceed it — the same reader `analyze` uses. The `MAX_AST_DEPTH` recursion budget is **not** enforced by the reader (it yields the raw tree); it is a visitor-level guard, so the pipeline's own traversals must apply it: test-function collection reuses the depth-guarded `_shared.enumerate_functions_with_spans`, and the assertion walk is depth-guarded (or catches `RecursionError`). An over-deep-but-parseable test file is therefore skipped (no rows) rather than surfacing as `-32603`, matching `analyze`'s behavior. The astroid cache lifecycle and broadened exception handling from the strategy-3 decision are implemented **inline in `quality/pairing.py`**, leaving `analysis/inference.py` untouched (issue #6 forbids `classify_signals` changes); factoring them into a shared astroid-manager lifecycle helper is an optional, behavior-preserving follow-up that must re-run the classify_signals conformance tests.

*Rationale:* Constitution V (Analysis Safety) is non-negotiable and treats analyzed source as untrusted input; the new test-file parse path and the second astroid entry point must restate the byte-cap/AST-depth and cache-isolation/memory guards or they silently regress. The guarded reader bounds the direct test-file parse, but astroid's transitive inference can still parse imported modules that exceed the 16 MiB per-file cap (as `analysis/inference.py` documents); the `MemoryError`/`RecursionError` degrade path — not the reader — is what bounds that worst case.

*Alternatives considered:* Bare `ast.parse` on test files — rejected; bypasses the byte-cap guard and the depth-guarded traversal and reintroduces a DoS vector. Extracting a shared astroid-manager lifecycle helper reused by `analysis/inference.py` — deferred; it would modify a `classify_signals` (#5) file, which issue #6 places out of scope, so the inline-in-`pairing.py` discipline is primary and the shared helper is an optional behavior-preserving refactor.

### Decision: One mapping row per assertion, classified into six types

For each paired test function, collect every assertion and emit one mapping row per assertion (a test with three asserts → three rows, same target, differing `assertion_location`). Each assertion is classified into exactly one of `equality | error_check | membership | identity | comparison | generic`, covering both pytest bare `assert` and unittest `assert*` methods. `assertion_location` is formatted `path:line` (no column), path relative to `root_path`.

*Rationale:* Gaze needs assertion-granular data to reason about what each test verifies. The six-value closed set is the protocol contract; a `generic` fallback guarantees every assertion is representable (Detection Accuracy — ambiguity over omission).

*Alternatives considered:* One row per test (aggregating assertions) — rejected; loses the assertion-level signal Gaze consumes. Adding assertion subtypes beyond the six — rejected; violates protocol fidelity.

### Decision: Infer `side_effect_type` from assertion kind plus target effects

`mapping.py` infers each row's `side_effect_type` from the assertion type and the target function's detector-reported `side_effects` (never re-parsing ad hoc): `error_check` → `ErrorReturn` if the target has it, else `ErrorSignal` if present, else `ErrorReturn`; `equality`/`comparison`/`identity`/`membership` → `ReturnValue` if present, else the target's first P0 effect, else `ReturnValue`; `generic` → the target's first effect if any, else `ReturnValue`. "First P0 effect" iterates the target's effects in detector order and selects the first whose `TIER_MAP[type]` is `Tier.P0`.

*Rationale:* Consuming detector output keeps a single source of truth for effects and honors Python-Native Analysis. The fallback chains guarantee a valid, non-empty `side_effect_type` even when the target has no detected effects, so no row is dropped for lack of a perfect match.

*Alternatives considered:* Re-parsing the target inside `mapping.py` — rejected; duplicates detector logic and risks divergence. Emitting a null/empty effect type — rejected; violates protocol (every row carries a `side_effect_type`).

### Decision: Fresh `run_test_mapping` pipeline orchestrating existing components

`pipeline.py` exposes `run_test_mapping(root_path, patterns) -> list[dict]`: (1) `discover()`; (2) `analyze_path()` on the same root/patterns to get target effects; (3) parse test files and collect `FunctionDef`/`AsyncFunctionDef` whose names start with `test_`, plus methods named `test*` of classes subclassing `unittest.TestCase`; (4) pair; (5) detect assertions; (6) infer effect types; (7) serialize protocol dicts. It never runs pytest and never reads coverage. Pairing targets are restricted to production functions defined in `discover().source_files`: because `analyze_path` enumerates both source and test files, the pipeline filters analyzed records to those whose `file` is a discovered source file, so a test function is never emitted as a pairing target.

*Rationale:* Reuses the analyzer's proven discovery and detection paths, keeping the pipeline thin and safe (static analysis only). Returning `list[dict]` (single-valued) keeps the wrapping responsibility in one place — see the next decision.

*Alternatives considered:* Lifting gaze-py `quality/pipeline.py` — explicitly forbidden by the issue. Re-discovering/re-reading files independently — rejected; duplicates `_shared`/`discovery` behavior and risks inconsistency.

### Decision: Deterministic ordering with an explicit ordering assertion

`run_test_mapping` sorts `mappings` by a stable composite key `(test_file, test_function, assertion_line, assertion_col, target_package, target_function)`, where `assertion_line` is the **integer** source line compared numerically (so line 2 sorts before line 10 — a `path:line` string key would order `:10` before `:2`) and `assertion_col` is the integer column offset (or an equivalent stable collection index) that breaks ties when several assertions share one source line, making the key a total order. Tests assert byte-identical repeat runs, byte-identical output across two separate processes launched with `PYTHONHASHSEED=0` vs `1` (the pipeline's set-based de-dup and astroid BFS make iteration order hash-seed-sensitive; a same-process repeat cannot catch this), the concrete order of rows on a fixture whose assertions span single- and double-digit lines, and a two-assertions-on-one-line case that exercises the `assertion_col` tiebreaker.

*Rationale:* Protocol Fidelity requires deterministic output. A prior analysis-methods review learning is that a byte-identical determinism test cannot catch a wrong-but-stable sort key (e.g., a copy-pasted sort key referencing the wrong field name); an explicit ordering-value assertion on a known fixture is required in addition.

*Alternatives considered:* Relying on discovery/AST order only — rejected; not guaranteed stable across platforms. Byte-identical determinism test alone — rejected per the learning above.

### Decision: Single-wrap response and standard handler error mapping

`run_test_mapping` returns `list[dict]`; only the `_test_mapping` server handler wraps it into `{"mappings": [...]}`. The handler mirrors existing handlers: it calls `_validate_analysis_params`, runs the pipeline in a try/except, and maps `FileNotFoundError` → `RpcError(INVALID_PARAMS, ...)` (-32602). `"test_mapping"` is registered in `DEFAULT_DISPATCH`, and `protocol.initialize_result()` flips `test_mapping` to `True` (updating its docstring; discover/classify_signals stay True, streaming stays False).

*Rationale:* Matches the established handler pattern for consistency and testability, and avoids the double-wrapping defect called out in prior learnings (parse/return contracts stay single-valued; the handler is the sole wrapper).

*Alternatives considered:* Wrapping inside the pipeline — rejected; couples orchestration to the RPC envelope and risks double-wrapping. A bespoke validation path — rejected; `_validate_analysis_params` already enforces the param contract uniformly.

## Risks / Trade-offs

- **Astroid cannot import/parse an arbitrary target project** → Strategy 3 is optional and wrapped in broad exception handling; strategies 1–2 still return. CI does not require strategy 3 to fire on the fixture; the BFS helper is unit-tested with a mocked graph or a tiny on-disk package astroid can parse.
- **Name-convention pairing produces false positives** → First-match-wins priority orders exact name match (90) above weaker signals; case-only matches are demoted to 70; direct-call (80) and transitive (75) provide corroboration where names differ.
- **Confidence scale confusion (0.0–1.0 vs 0–100)** → Conversion happens once at the lift boundary; tests assert `confidence` is an `int` in [0, 100] and check specific values (90/80/75/70).
- **Wrong-but-stable sort key** → Explicit ordering-value assertion on a fixture in addition to a byte-identical determinism test.
- **Target function has no detected side effects** → Effect-type inference falls back to `ReturnValue` (or `ErrorReturn` for `error_check`), guaranteeing a valid row rather than a dropped one.
- **Duplicate mapping rows** → Pairing de-duplicates by (test_function, test_file, target_package, target_function); assertion rows are intentionally distinct by `assertion_location`.
- **Scope creep toward scoring** → Non-Goals and the constitution check explicitly exclude CRAP/quadrant/coverage math; the pipeline reads no coverage and runs no pytest.
- **Astroid cache contamination / unbounded memory in the long-lived server** → Strategy 3 builds the graph once per request, clears `astroid.MANAGER` before building and in a `finally` (per-request isolation + memory bounding), implemented inline in `quality/pairing.py` (leaving `analysis/inference.py` untouched); an isolation test asserts no cross-request contamination across two requests over different trees in one process.
- **Divergence between the two inline astroid-lifecycle copies** → The clear-before/`finally`-clear + broadened-catch + stderr-diagnostic discipline is duplicated inline in `quality/pairing.py` and `analysis/inference.py` (issue #6 forbids modifying the latter). Extracting a shared astroid-manager lifecycle helper is a **tracked, deferred follow-up** (behavior-preserving, must re-run the classify_signals conformance tests); it is recorded here so the divergence risk survives archival.
- **Hash-seed-dependent iteration order** → The composite sort key uses the integer assertion line, and a cross-subprocess `PYTHONHASHSEED=0` vs `1` test asserts byte-identical output (a same-process repeat cannot detect hash-seed sensitivity).
- **Fixture test file auto-collected by the host pytest run** → `tests/fixtures/sample_project/tests/test_calculator.py` matches pytest's default collection and would `ImportError` on the fixture's package; `tests/` excludes `tests/fixtures/` from collection (`collect_ignore_glob`/`--ignore`/`norecursedirs`), and a test asserts the fixture file is not collected.
- **Unguarded parsing of untrusted test files** → Test-file reading reuses the guarded reader (`iter_source_files`/`is_analyzable_file`) for the 16 MiB byte cap; the `MAX_AST_DEPTH` budget is applied by the pipeline's own depth-guarded traversals (`enumerate_functions_with_spans` + a guarded assertion walk, or a `RecursionError` catch), so oversized and over-deep files are skipped rather than exhausting resources or surfacing as `-32603`.

## Migration Plan

Purely additive; no rollback data migration is required.

1. Commit the spec artifacts (proposal, design, specs, tasks) **before** any implementation. Implementation commits MUST NOT be combined with spec-artifact commits.
2. Implement in dependency order: `quality/pairing.py` and `quality/assertions.py` (with provenance headers) → `quality/mapping.py` → `quality/pipeline.py` → `server.py` handler + dispatch → `protocol.py` capability flip → fixtures and tests.
3. Run the CI-parity gate (uv sync --locked; ruff check; ruff format --check; mypy src/; pytest --cov --cov-fail-under=85) plus a manual stdio smoke test before marking tasks complete.
4. **Rollback:** revert the change set. The only externally observable behavior change is the `test_mapping` capability flag and the new method; reverting restores `test_mapping: false` and removes the method with no residual state.

## Open Questions

None. Issue #6 states "Do not ask clarifying questions. Every decision is already made below," and all defaults (protocol field names, lift boundaries, no scoring math, optional strategy 3) are fixed by the issue.
