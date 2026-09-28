# Spec: Complexity Decomposition

## ADDED Requirements

### Requirement: Flagged functions are decomposed below the threshold
The change SHALL decompose each of the six functions flagged by Gaze in issue #27 — `_append_bound_names`, `_build_call_graph`, `visit_stmt`, `visit_ClassDef`, `_analyze_func_node`, and `run_test_mapping` — into focused helpers such that each original function's McCabe cyclomatic complexity falls below the decomposition threshold that flagged it. `_handle_call` (issue #26) SHALL remain unmodified.

#### Scenario: Each flagged function is decomposed
- **WHEN** the refactor is complete and McCabe complexity is re-measured per function
- **THEN** each of the six flagged functions reports a complexity lower than its pre-refactor value, and no new function introduced by the refactor exceeds the threshold that would flag it for decomposition

#### Scenario: Out-of-scope function untouched
- **WHEN** the diff is reviewed against `src/snake_eyes/analysis/detector.py`
- **THEN** `_handle_call` is not modified by this change

### Requirement: Behavior is preserved byte-for-byte
The change SHALL preserve analyzer behavior exactly: JSON-RPC responses SHALL remain byte-identical for identical inputs, side-effect taxonomy membership SHALL be unchanged, effect ordering SHALL remain deterministic, and all existing public method contracts (`analyze`, `complexity`, `coverage`, `classify_signals`, `test_mapping`) SHALL be unaffected.

#### Scenario: Identical JSON-RPC output
- **WHEN** the same Python source tree is analyzed before and after the refactor
- **THEN** the JSON-RPC responses for every supported method are byte-identical

#### Scenario: Existing regression suites pass unchanged
- **WHEN** the existing test suites under `tests/` are run after the refactor
- **THEN** every previously passing test still passes with no assertion or expectation modification required

### Requirement: Degradation and resource-bound semantics are preserved
The change SHALL preserve every exception-degradation and recursion-bound behavior of the decomposed code, including the `FileNotFoundError` re-raise in `_build_call_graph`, the graceful skip of unparseable files, the `MAX_AST_DEPTH` recursion budget, and the per-file/per-call `Exception` catch-and-degrade paths.

#### Scenario: FileNotFoundError still re-raised
- **WHEN** `_build_call_graph` is invoked on a project whose call-graph file has been deleted
- **THEN** the `FileNotFoundError` propagates to the caller exactly as before the refactor, rather than being swallowed

#### Scenario: Unparseable file still degrades gracefully
- **WHEN** a file in the call-graph project fails to parse
- **THEN** the analyzer skips that file and continues, without aborting the request, as before

### Requirement: Extracted helpers are independently testable
Each helper extracted by the change SHALL be a pure, callable unit that can be exercised in isolation by a focused test, and the change SHALL add at least one focused test per extracted helper in addition to keeping the existing regression suites green.

#### Scenario: Focused test per extracted helper
- **WHEN** the change is complete
- **THEN** each new helper has a dedicated test in the `tests/` tree that exercises its success path and, where applicable, its degradation path

### Requirement: No protected gate is lowered
The change SHALL NOT lower any protected quality or governance gate. The `--cov-fail-under=85` coverage floor, the `ruff format --check` formatting gate, and the `uv sync --locked` lockfile gate SHALL remain unchanged.

#### Scenario: CI parity
- **WHEN** the refactor is complete
- **THEN** `uv sync --locked`, Ruff lint, Ruff format check, strict mypy, and pytest with the protected 85 percent coverage floor all pass without lowering a gate
