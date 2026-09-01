## 1. Package scaffold & dependencies

- [x] 1.1 Create the `src/snake_eyes/quality/` package with an `__init__.py` (re-export `run_test_mapping` for ergonomic imports, matching the `analysis/`/`signals/` convention)
- [x] 1.2 Confirm `astroid>=3.0,<4` is already present in `pyproject.toml` (shipped by classify-signals) and add NO new dependency; do NOT bump the astroid pin to `<5`
- [x] 1.3 Confirm `NOTICE` already attributes gaze-py; no NOTICE change required unless a new lifted file needs a distinct attribution line

## 2. Pairing engine (capability: test-pairing)

- [x] 2.1 Lift gaze-py `quality/pairing.py` to `src/snake_eyes/quality/pairing.py`, retaining the gaze-py copyright header and adding the Apache-2.0 §4(b) change notice; annotate to satisfy `mypy --strict` and mark the astroid import `# type: ignore[import-untyped]` as `analysis/inference.py` does
- [x] 2.2 Adapt the lifted code to snake-eyes stdlib `ast` usage and models; convert lifted 0.0–1.0 confidence scores to integer 0–100 (e.g. 0.9 → 90)
- [x] 2.3 Implement Priority 1 name-convention pairing: strip a leading `test_`/`Test`/`test`/`Test` (snake or camel) prefix, exact match confidence 90, case-only match confidence 70; define the case-only tie-break as the first candidate in `analyze_path` order
- [x] 2.4 Implement Priority 2 direct-call pairing: target name appears as a `Call` in the test AST, confidence 80
- [x] 2.5 Implement Priority 3 transitive pairing: astroid call-graph BFS with `depth_limit=5`, confidence 75, reusing the astroid approach from `analysis/inference.py`; build the call graph ONCE per `run_test_mapping` — lazily, on the first unpaired-test lookup — and reuse it for all subsequent lookups (mirror `build_caller_index` built once + `CallerIndex.count` reuse; no per-test rebuild; a fully-paired project never triggers the astroid parse); match callees by resolved defining file path (not `derive_package`'s dotted name); clear `astroid.MANAGER` before that single build and again in a `finally` (per-request isolation + memory bounding); catch a broadened exception set (astroid errors, `RecursionError`, `MemoryError`, catch-all) so it skips gracefully with no method failure, WITHOUT absorbing `FileNotFoundError`; emit a one-line stderr diagnostic on skip/degrade (stdout stays clean for JSON-RPC)
- [x] 2.6 Enforce first-match-wins ordering and de-duplicate pairs by `(test_function, test_file, target_package, target_function)`; when one strategy matches multiple same-named targets across packages, pair each distinct `(target_package, target_function)` deterministically in `analyze_path` order; emit no rows for unpaired tests
- [x] 2.7 Derive `target_package` via `_shared.derive_package` (same helper as `analyze`), or equivalently read `FunctionRecord.package`
- [x] 2.8 Implement the astroid manager lifecycle (clear-cache on entry + `finally`) INLINE in `quality/pairing.py`, leaving `analysis/inference.py` UNTOUCHED (issue #6 scope: no classify_signals changes). A shared helper is OPTIONAL only; if extracted it MUST be behavior-preserving and the classify_signals conformance tests MUST be re-run

## 3. Assertion detection (capability: assertion-detection)

- [x] 3.1 Lift the gaze-py assertion helpers to `src/snake_eyes/quality/assertions.py`, retaining copyright header and adding the Apache-2.0 §4(b) change notice; annotate for `mypy --strict`
- [x] 3.2 Define the assertion node set (`ast.Assert`; `Call`s whose callee ∈ the `assert*`/`raises`/`warns` set; `with pytest.raises(...)`/`raises(...)`/`self.assertRaises(...)`) and traversal scope (test body incl. nested `with`/`for`/`if`/`try`, excluding nested def/class bodies); a `raises`/`warns`/`assertRaises` call used as a `with`-item context expression is counted ONCE (as the with-item), never additionally as a bare call
- [x] 3.3 Implement the exhaustive classification table mapping pytest bare `assert` and every recognized unittest `assert*` form to exactly one of `equality | error_check | membership | identity | comparison | generic` (incl. `assertIsNot`/`assertIsNotNone` → identity, `assertRaisesRegex`/`pytest.warns` → error_check, `assert*Equal` family → equality, `assertNotIn`/`not in` → membership); anything unlisted → `generic`; classify by an explicit name-keyed map (NOT an `endswith("Equal")` heuristic) so `assertNotEqual`/`assertNotAlmostEqual` resolve to `comparison`, not the equality family
- [x] 3.4 Collect every assertion in a paired test and emit one row per assertion with `assertion_location` formatted `path:line` relative to `root_path`

## 4. Effect-type inference (capability: effect-type-mapping)

- [x] 4.1 Create `src/snake_eyes/quality/mapping.py` that consumes the target's `FunctionRecord.side_effects` from the detector (no ad hoc re-parsing); look up tiers via `TIER_MAP.get(...)` with a safe fallback (no `KeyError` on an unexpected type string)
- [x] 4.2 Implement the `error_check` chain: `ErrorReturn` if present, else `ErrorSignal` if present, else `ErrorReturn`
- [x] 4.3 Implement the value-assertion chain (`equality`/`comparison`/`identity`/`membership`): `ReturnValue` if present, else first P0 effect (via `effects.TIER_MAP`), else `ReturnValue`
- [x] 4.4 Implement the `generic` chain: first detected effect if any, else `ReturnValue`

## 5. Pipeline (capability: test-mapping-pipeline)

- [x] 5.1 Create `src/snake_eyes/quality/pipeline.py` exposing `run_test_mapping(root_path, patterns) -> list[dict]`
- [x] 5.2 Compose the stages: `discover()`, `analyze_path()` for target effects, then test-function collection
- [x] 5.3 Restrict pairing targets to production functions defined in `discover().source_files` (filter `analyze_path` records by `file ∈ source_files`); test functions are never targets
- [x] 5.4 Collect test functions: `FunctionDef`/`AsyncFunctionDef` named `test_*`, plus `test*` methods of `unittest.TestCase` subclasses (detected by a shallow scan of each top-level `ClassDef`'s base names for `TestCase`/`unittest.TestCase`, mirroring the detector's Exception-base matching — a step that complements `enumerate_functions_with_spans`, which yields only name/span and no class context; transitive/aliased subclasses are a documented known limitation, i.e. an acknowledged false negative); reuse the depth-guarded `enumerate_functions_with_spans` for function enumeration
- [x] 5.5 Parse test files through the shared guarded reader (`iter_source_files`/`is_analyzable_file`), which provides the `MAX_FILE_BYTES` byte cap only; enforce the `MAX_AST_DEPTH` budget in the pipeline's OWN traversals (the reader does not — depth is a visitor-level guard): use the depth-guarded `enumerate_functions_with_spans` for collection and guard the assertion walk (or catch `RecursionError`) so an over-deep-but-parseable test file is SKIPPED without failing the request or surfacing as -32603
- [x] 5.6 Run pairing → assertion detection → effect-type inference → serialize to protocol dicts
- [x] 5.7 Sort `mappings` by the composite key `(test_file, test_function, assertion_line, assertion_col, target_package, target_function)` comparing the line numerically (line 2 before line 10), where `assertion_col` is the integer column offset (or an equivalent stable collection index) that breaks ties when multiple assertions share one source line to the same target, making the key a total order; emit `test_file` and all path-valued fields root-relative POSIX; return `[]` when empty
- [x] 5.8 Ensure the pipeline runs no pytest, executes no analyzed code, and reads no coverage data

## 6. Server & protocol wiring (capability: test-mapping-method)

- [x] 6.1 Add a `_test_mapping` handler in `server.py` that calls `_validate_analysis_params`, runs `run_test_mapping`, and wraps the list into `{"mappings": [...]}`
- [x] 6.2 Map `FileNotFoundError` from the pipeline to `RpcError(INVALID_PARAMS, ...)` (-32602), mirroring existing handlers
- [x] 6.3 Register `"test_mapping"` in `DEFAULT_DISPATCH`
- [x] 6.4 Flip `test_mapping` to `True` in `protocol.initialize_result()` and update its docstring (discover, classify_signals, test_mapping True; streaming False)
- [x] 6.5 Update existing capability assertions to `test_mapping: True`: `tests/test_classify_signals_method.py` (`caps["test_mapping"]`), `tests/test_discover_method.py`, and the exact-dict assertion in `tests/test_protocol.py`; and remove `test_mapping` from the `test_reserved_methods_not_implemented` parametrize list in `tests/test_server.py` (once registered it returns -32602, not the asserted -32601 METHOD_NOT_FOUND, mirroring the analyze/complexity/coverage/classify_signals precedent)

## 7. Fixtures

- [x] 7.1 Create `tests/fixtures/sample_project/src/sample/__init__.py` and `calculator.py` (`add(a, b)`, `divide(a, b)` raising `ZeroDivisionError`, `Counter.inc` mutating `self`)
- [x] 7.2 Create `tests/fixtures/sample_project/tests/test_calculator.py` exercising: the name strategy (`test_add`), a case-only name match (`test_Add`↔`add`), a direct-call test on `divide` without a name match, a `pytest.raises` error check, a `unittest.TestCase` subclass whose `test_*` method PAIRS to a production target (e.g. `test_inc`↔`Counter.inc`) so a row is emitted, a multi-assertion test whose assertions span single- and double-digit lines (e.g. 2 and 10); add `pyproject.toml` only if needed for imports (the two-assertions-on-one-source-line tiebreaker case is NOT placed in this on-disk fixture — `ruff format` would reflow it onto separate lines — but is constructed in-test via `tmp_path`; see 8.5)
- [x] 7.3 Exclude `tests/fixtures/` from host pytest collection (`collect_ignore_glob = ["fixtures/*"]` in `tests/conftest.py`, or `--ignore=tests/fixtures`/`norecursedirs` in `[tool.pytest.ini_options]`) so the fixture test file is analyzed as input, not executed; prefer the `conftest.py` `collect_ignore_glob` option so the protected `--cov-fail-under` flags already in `addopts` are not disturbed; ensure all fixture sources are ruff-format-clean (the `ruff format --check` gate covers `tests/`)

## 8. Tests

- [x] 8.1 Pairing: `test_add`↔`add` conf 90; `test_Add`↔`add` conf 70; `test_it_works` calling `divide`↔`divide` conf 80; a no-match test yields no row; a test that both name-matches AND calls the same target yields a single row at conf 90 (first-match-wins); a same-named helper in a test module is never a target; assert every emitted row's `confidence` satisfies `isinstance(confidence, int)` and `0 <= confidence <= 100` (guarding against a protocol-illegal float such as `90.0`)
- [x] 8.2 Strategy-3 BFS helper (mocked call graph or tiny on-disk package astroid can parse): target reachable in ≤5 hops pairs at conf 75; target at 6 hops does NOT pair via strategy 3; do NOT require strategy 3 to fire on the fixture in CI
- [x] 8.3 Assertions: a parametrized table asserting each of the six `assertion_type` values against representative pytest AND unittest forms (incl. `assertIsNot`/`assertIsNotNone`, `assertRaisesRegex`, `assert*Equal` family, `assertNotIn`/`not in`); plus node-identification count/scope assertions: a `with pytest.raises(...)` block yields EXACTLY one row (never double-counted as with-item + bare call), an N-assertion test yields EXACTLY N rows, an assertion nested in `with`/`for`/`if`/`while`/`try` IS collected, and an assertion nested in a `def`/`class` body is EXCLUDED
- [x] 8.4 Effect-type: exercise each branch with hand-built `FunctionRecord.side_effects` (`error_check` → `ErrorReturn`/`ErrorSignal`/fallback; value → `ReturnValue`/first-P0/fallback; `generic` → first-effect/fallback), asserting the exact `side_effect_type`
- [x] 8.5 Pipeline: `sample_project` → ≥2 rows with all required keys; the unittest-style test method is collected; determinism via byte-identical repeat run PLUS an explicit ordering-value assertion on the fixture whose assertions span lines 2 and 10 (proving numeric, not lexicographic, ordering); construct a two-assertions-on-one-line case via `tmp_path` and assert the two rows order deterministically by the `col_offset`/collection-index tiebreaker; assert a fixture row's `target_package` equals `derive_package(file)` (guarding the `src/`-layout dotted-name path)
- [x] 8.6 JSON-RPC end-to-end: `initialize` reports `test_mapping: true`; `test_mapping` returns a `{"mappings": [...]}` result; every returned row's `confidence` is an `int` in [0,100]; missing/invalid `root_path` → -32602
- [x] 8.7 Cross-subprocess determinism: spawn `python -m snake_eyes --stdio` twice with `PYTHONHASHSEED=0` and `=1` over `sample_project` and assert byte-identical stdout (mirroring `tests/test_classify_signals_method.py`)
- [x] 8.8 Empty-result contracts: pipeline returns `[]` on a project with test files but zero pairs; e2e `test_mapping` returns a `{"mappings": []}` result object (assert `result` present, `error` absent) for a no-test-files project
- [x] 8.9 Safety: an oversized/over-deep test file is skipped (byte-cap/AST-depth) without an internal error; strategy-3 pathological input degrades to strategies 1–2 with no -32603; a non-existent `root_path` propagates `FileNotFoundError` → -32602 and is NOT absorbed by strategy-3's broad catch
- [x] 8.10 Fixture isolation: assert `tests/fixtures/sample_project/tests/test_calculator.py` is not collected by the host pytest run (host collection count unaffected)
- [x] 8.11 Meet per-file coverage targets: `pairing.py` ≥90%, `assertions.py` ≥90%, `mapping.py` ≥95%, `pipeline.py` ≥85%, project gate ≥85%
- [x] 8.12 Astroid cache isolation: two `test_mapping` requests over different trees in one process do not contaminate each other (`astroid.MANAGER` cleared before + after each strategy-3 build)
- [x] 8.13 Static-only sentinel: a behavioral test proving `run_test_mapping` runs no pytest, executes no analyzed code, and reads no coverage (mirroring the classify-signals sentinel test — behavioral, not a comment)
- [x] 8.14 Same-named multi-package disambiguation: two packages each defining `add` yield exactly one row per `(target_package, target_function)` (build the two-package tree inline via `tmp_path`; the single-package `sample_project` does not provision this)
- [x] 8.15 Assert emitted `test_file` (and path-valued fields) are root-relative POSIX, not absolute

## 9. Documentation

- [x] 9.1 Update `README.md`: add a `test_mapping | Implemented` status-table row, flip the capability sentence (`streaming` is `false`; `test_mapping` now `true`), update the implemented-features prose line to include test-to-assertion mapping, add `src/snake_eyes/quality/` to the project-structure tree enumerating its four modules (`pairing.py`, `assertions.py`, `mapping.py`, `pipeline.py`), and add a "Delivered in issue #6" note
- [x] 9.2 Update `AGENTS.md` Project Structure to list `src/snake_eyes/quality/` (enumerating `pairing.py`, `assertions.py`, `mapping.py`, `pipeline.py`) and note issue #6 delivery; broaden the Architecture "Test-to-assertion mapping (pytest)" line to "(pytest and unittest)"
- [x] 9.3 Extend the `README.md` License section to enumerate the newly-lifted `pairing.py` and `assertions.py` among the files lifted from gaze-py (Matt Peter, Apache 2.0), mirroring the classify-signals precedent
- [x] 9.4 Verify lifted `pairing.py` and `assertions.py` carry both the gaze-py copyright header and the Apache-2.0 §4(b) change notice
- [x] 9.5 Update the astroid-purpose docs to reflect its second consumer: the `README.md` astroid dependency line and the `AGENTS.md` Technology Stack "Inference" bullet must note astroid also backs strategy-3 transitive-call pairing in `quality/pairing.py` (mirroring the classify-signals precedent that updated the Technology Stack when astroid's scope changed)

## 10. Verification (CI parity gate)

- [x] 10.1 `uv sync --locked`
- [x] 10.2 `uv run ruff check src/ tests/`
- [x] 10.3 `uv run ruff format --check src/ tests/`
- [x] 10.4 `uv run mypy src/`
- [x] 10.5 `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85`
- [x] 10.6 Manual stdio smoke test: `initialize` shows `test_mapping: true`; `test_mapping` on `sample_project` returns mapping rows
- [x] 10.7 `openspec validate test-mapping --strict`
- [x] 10.8 Constitution check — confirm PASS for all five principles (Protocol Fidelity, Detection Accuracy, Python-Native Analysis, Testability, Analysis Safety)

<!-- spec-review: passed -->
<!-- code-review: passed -->
