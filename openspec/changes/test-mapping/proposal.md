## Why

Gaze's universal scoring engine needs Python test-to-assertion mapping data to compute test quality and contract-coverage metrics, but snake-eyes currently advertises `test_mapping: false` and exposes no such method. This change delivers the `test_mapping` JSON-RPC method so Gaze can learn which Python tests exercise which production functions, through which assertions, against which observable side effects.

## What Changes

- Add a new `test_mapping` JSON-RPC method that accepts `{"root_path", "patterns"}` and returns `{"mappings": [...]}` conforming to Gaze analyzer protocol v1.1.0. Empty projects and projects with no test/target pairs return `{"mappings": []}` (a success result, never an error).
- Add a new `src/snake_eyes/quality/` package implementing a three-strategy pairing engine, assertion detection, side-effect-type inference, and an orchestration pipeline.
- Pair tests to production functions with **first-match-wins** priority: (1) name convention (`test_foo`/`testFoo`/`TestFoo`↔`foo`; strip a `test_`/`Test`/`test`/`Test` prefix; confidence 90, case-only match 70), (2) direct AST call (confidence 80), (3) astroid transitive call graph via BFS depth-limit 5 (confidence 75). Unpaired tests emit no rows.
- Emit **one mapping row per assertion**: classify each assertion into exactly one of `equality | error_check | membership | identity | comparison | generic`, and infer a `side_effect_type` from the assertion kind plus the target function's detected effects.
- Flip the `test_mapping` capability flag from `false` to `true` in `initialize`.
- Lift and adapt pairing and assertion-detection logic from gaze-py (permission granted, copyright retained); write the pipeline and effect-type inference fresh against snake-eyes models. `confidence` is emitted as an integer 0–100 (lifted 0.0–1.0 scores are converted, e.g. 0.9 → 90).
- Add a `tests/fixtures/sample_project/` fixture exercising all three pairing strategies and every assertion type.
- No **BREAKING** changes: the method is additive and no existing method, model, or capability behavior changes.

## Capabilities

### New Capabilities

- `test-mapping-method`: The `test_mapping` JSON-RPC method — request/param validation, dispatch registration, `{"mappings": [...]}` response shape, error mapping, and the `initialize` capability-flag flip.
- `test-pairing`: The three-strategy, first-match-wins test-to-target pairing engine (name convention, direct call, astroid transitive call graph) with de-duplication and graceful degradation when astroid is unavailable.
- `assertion-detection`: Per-paired-test assertion collection and classification of each assertion into the six allowed `assertion_type` values across pytest and unittest styles.
- `effect-type-mapping`: Inference of `side_effect_type` for each assertion row from the assertion type plus the target function's detector-reported side effects.
- `test-mapping-pipeline`: The `run_test_mapping(root_path, patterns)` orchestration that composes discovery, analysis, pairing, assertion detection, and effect inference into deterministically ordered protocol dictionaries.

### Modified Capabilities

None. `openspec/specs/` holds no archived capabilities; no existing requirement changes.

### Removed Capabilities

None.

## Impact

- **New files**:
  - `src/snake_eyes/quality/__init__.py`
  - `src/snake_eyes/quality/pairing.py` (lifted from gaze-py `quality/pairing.py`, adapted)
  - `src/snake_eyes/quality/assertions.py` (lifted from gaze-py quality assertion helpers, adapted)
  - `src/snake_eyes/quality/mapping.py` (new — side-effect-type inference)
  - `src/snake_eyes/quality/pipeline.py` (new — `run_test_mapping` orchestration)
  - `tests/fixtures/sample_project/` (fixture: `src/sample/__init__.py`, `src/sample/calculator.py`, `tests/test_calculator.py`)
  - New test modules under `tests/` covering pairing, assertions, effect inference, pipeline, and JSON-RPC end-to-end.
- **Modified files**:
  - `src/snake_eyes/server.py` — add `_test_mapping` handler; register `"test_mapping"` in `DEFAULT_DISPATCH`; reuse `_validate_analysis_params`; map `FileNotFoundError` → `INVALID_PARAMS` (-32602).
  - `src/snake_eyes/protocol.py` — flip `test_mapping` to `True` in `initialize_result()` and update its docstring (discover, classify_signals, test_mapping True; streaming False).
  - `tests/conftest.py` (or `[tool.pytest.ini_options]`) — exclude `tests/fixtures/` from host pytest collection so the `sample_project` test file is analyzed as fixture input, not run by the host test suite.
  - `README.md` — add a `test_mapping | Implemented` status-table row; flip the capability sentence so only `streaming` is `false`; update the implemented-features prose line to include test-to-assertion mapping; add `src/snake_eyes/quality/` (with its four modules `pairing.py`, `assertions.py`, `mapping.py`, `pipeline.py`) to the project-structure tree; enumerate `pairing.py` and `assertions.py` in the License section as lifted from gaze-py; update the astroid dependency line so it credits strategy-3 transitive-call pairing in addition to caller-count inference; add a "Delivered in issue #6" note.
  - `AGENTS.md` — add `src/snake_eyes/quality/` (with its four modules `pairing.py`, `assertions.py`, `mapping.py`, `pipeline.py`) to the Project Structure section; update the Technology Stack "Inference" bullet so astroid is credited for strategy-3 transitive-call pairing in `quality/pairing.py` in addition to caller-count inference; broaden the Architecture "Test-to-assertion mapping (pytest)" line to "(pytest and unittest)"; note delivery in issue #6.
- **Dependencies**: None added. `astroid>=3.0,<4` is already a runtime dependency (shipped by the classify-signals change) and is reused for strategy-3 transitive pairing exactly as `analysis/inference.py` uses it. `coverage.py` is untouched — this change does not run pytest or read coverage data.
- **Provenance**: `pairing.py` and `assertions.py` retain the gaze-py copyright header (`# Copyright Matt Peter (gaze-py, https://github.com/mpeter/gaze-py). Apache 2.0.`) plus an Apache-2.0 §4(b) change notice. gaze-py `quality/pipeline.py` is explicitly **not** lifted. `NOTICE` already attributes gaze-py.
- **Protocol contract**: Consumes detector output (`analyze_path` → `FunctionRecord.side_effects`) and `discover()`; produces `{"mappings": [...]}`. snake-eyes still computes no CRAP/GazeCRAP/quadrants/contract-coverage percentages — scoring remains Gaze's responsibility.

## Constitution Alignment

- **I. Protocol Fidelity — PASS**: Field names, the six `assertion_type` values, integer `confidence` (0–100), `assertion_location` `path:line` format, and the `{"mappings": [...]}` envelope match Gaze analyzer protocol v1.1.0 exactly. Output is deterministically ordered by a stable key. Empty results return a success `{"mappings": []}`, never an error.
- **II. Detection Accuracy — PASS**: Three pairing strategies maximize true pairs; ambiguity is preferred over omission via a `generic` assertion fallback and an effect-type fallback chain, so uncertain-but-real relationships are still reported rather than silently dropped.
- **III. Python-Native Analysis — PASS**: Pairing and assertion detection use the stdlib `ast`; transitive pairing reuses `astroid` (already shipped) as `analysis/inference.py` does. No Python semantics are reimplemented.
- **IV. Testability — PASS**: Each module is independently testable; per-file coverage targets are pairing 90%+, assertions 90%+, mapping 95%+, pipeline 85%+, with the project gate held at 85%. A protocol-conformance end-to-end test asserts `test_mapping: true` and the response shape.
- **V. Analysis Safety — PASS**: Analyzed source is parsed statically only — the pipeline never executes analyzed code and never runs pytest. Test files are parsed through the shared guarded reader (`iter_source_files`/`is_analyzable_file`), which enforces the 16 MiB byte cap; because `MAX_AST_DEPTH` is a visitor-level guard rather than reader-enforced, the pipeline's own traversals enforce it (reusing the depth-guarded `enumerate_functions_with_spans` for test-function collection and a depth-guarded assertion walk, or catching `RecursionError`); oversized or over-deep files are skipped. Strategy-3 astroid clears `astroid.MANAGER` before building and in a `finally` (per-request isolation + memory bounding) and catches a broadened exception set (astroid errors, `RecursionError`, `MemoryError`, and an unexpected catch-all) so pathological input degrades to strategies 1–2 rather than surfacing as an internal error (-32603); `FileNotFoundError` is not absorbed and propagates to -32602. These guards are encoded as requirements, scenarios, and tasks, not asserted in prose alone.
