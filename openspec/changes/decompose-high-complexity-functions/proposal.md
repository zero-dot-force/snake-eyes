# Proposal: Decompose High-Complexity Functions

## Why

A 2026-09-25 Gaze report (issue #27) flags six functions in `src/snake_eyes/` with McCabe complexity at or above 21, each warranting a `decompose` / `decompose_and_test` fix strategy. These functions have grown into deeply nested `if`/`elif`/`try` dispatchers that are hard to reason about, review, and test in isolation, but they sit on the analyzer's correctness-critical path (side-effect detection, test pairing, provenance). Decomposing them into focused helpers reduces complexity without changing analyzer behavior.

## What Changes

- Decompose six high-complexity functions into focused helper methods/functions, preserving byte-identical analyzer output:
  - `_append_bound_names` (22) in `src/snake_eyes/quality/_provenance.py:116`
  - `_build_call_graph` (26) in `src/snake_eyes/quality/pairing.py:213`
  - `visit_stmt` (28) in `src/snake_eyes/quality/assertions.py:630`
  - `visit_ClassDef` (21) in `src/snake_eyes/analysis/detector.py:1548`
  - `_analyze_func_node` (25) in `src/snake_eyes/analysis/detector.py:1856`
  - `run_test_mapping` (23) in `src/snake_eyes/quality/pipeline.py:158`
- Add focused unit tests for each extracted helper.
- Preserve existing behavioral contracts: JSON-RPC response schema, side-effect taxonomy, effect identity ordering, exception degradation semantics, and `MAX_AST_DEPTH` recursion bounds.
- No protocol changes, no new dependencies, no `SideEffectType` changes.
- Explicitly out of scope: `_handle_call` (complexity 144) is tracked by issue #26 and is not modified here.

## Capabilities

### New Capabilities

- `complexity-decomposition`: The contract that the six flagged functions are decomposed into focused helpers such that cyclomatic complexity per function is reduced below the Gaze decomposition threshold while analyzer output remains byte-identical, and that the existing regression suites continue to pass as the behavioral contract.

### Modified Capabilities

None. This is a behavior-preserving internal refactor; no spec-level requirement changes.

## Impact

- Affected code: `src/snake_eyes/quality/_provenance.py`, `src/snake_eyes/quality/pairing.py`, `src/snake_eyes/quality/assertions.py`, `src/snake_eyes/analysis/detector.py`, `src/snake_eyes/quality/pipeline.py`.
- Affected tests: `tests/test_provenance_regressions.py`, `tests/test_test_mapping_method.py`, `tests/test_detector.py`, `tests/test_detector_extra.py`, `tests/test_analysis_methods.py`, plus new focused tests for each extracted helper.
- Protocol impact: none. No method, request, response-field, assertion-type, or side-effect-taxonomy changes.
- Dependencies: none.
- Validation: unchanged CI workflow gates; per-function McCabe complexity re-measured to confirm each flagged function drops below the decomposition threshold; existing regression suites remain green.

## Constitution Check

- **I. Protocol Fidelity - PASS**: Behavior-preserving refactor; JSON-RPC output remains byte-identical.
- **II. Detection Accuracy - PASS**: No detection logic changes; effects are detected and classified exactly as before.
- **III. Python-Native Analysis - PASS**: No reimplementation of Python semantics; existing `ast`/`astroid` usage is unchanged.
- **IV. Testability - PASS**: The change improves testability by isolating each branch into independently testable helpers; coverage strategy included.
- **V. Analysis Safety - PASS**: Static analysis only; no execution, import, or subprocess behavior introduced.
