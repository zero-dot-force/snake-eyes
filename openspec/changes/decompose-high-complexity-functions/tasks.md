# Tasks: Decompose High-Complexity Functions

## 1. Decompose `_append_bound_names`

- [x] 1.1 Extract `_append_funcdef_bound_names` (decorators/defaults/returns expression list) and `_append_classdef_bound_names` (decorators/bases/keywords) from `_append_bound_names` in `src/snake_eyes/quality/_provenance.py`, threading `MAX_AST_DEPTH` through unchanged.
- [x] 1.2 Keep the original `_append_bound_names` as a thin dispatch over the two helpers, preserving all remaining branch types (Lambda, Name Store/Del, Import/ImportFrom, ExceptHandler, MatchAs/MatchStar, MatchMapping, generic recurse).
- [x] 1.3 Add focused tests in `tests/test_provenance_regressions.py` (or a new adjacent test file) for each extracted helper, including a `MAX_AST_DEPTH` ceiling case.
- [x] 1.4 Run `uv run pytest tests/test_provenance_regressions.py` in isolation.

## 2. Decompose `_build_call_graph`

- [x] 2.1 Extract `_parse_modules`, `_collect_defined_names`, and `_resolve_call_edges` (plus a `_callee_file` helper) from `_build_call_graph` in `src/snake_eyes/quality/pairing.py`, keeping the `FileNotFoundError` re-raise in the orchestrator and per-call/per-candidate `except Exception` in the resolver helper.
- [x] 2.2 Keep the astroid manager cache-clear step at the top of the orchestrator unchanged.
- [x] 2.3 Add focused tests in `tests/test_test_mapping_method.py` for each extracted helper, preserving the existing `FileNotFoundError` re-raise and graceful-skip tests.
- [x] 2.4 Run `uv run pytest tests/test_test_mapping_method.py` in isolation.

## 3. Decompose `visit_stmt`

- [x] 3.1 Extract `_visit_assert`, `_visit_call_expr`, `_visit_with`, `_visit_for`, `_visit_while`, `_visit_if`, `_visit_try`, and `_visit_match` helpers from `visit_stmt` in `src/snake_eyes/quality/assertions.py`.
- [x] 3.2 Reduce `visit_stmt` to a thin dispatch over the helpers, preserving the final `_invalidate_iteration_bindings` fallback branch.
- [x] 3.3 Add focused tests for each extracted helper through `collect_assertions` (the public entry point), keeping existing assertion-detection tests green.
- [x] 3.4 Run the assertion-detection test suite in isolation.

## 4. Decompose `visit_ClassDef`

- [x] 4.1 Extract `_process_class_statement` (the Delete / binding-assignment / AnnAssign-with-value sub-branches) from `visit_ClassDef` in `src/snake_eyes/analysis/detector.py`, preserving the decorator/bases/keywords/type_params visitation order.
- [x] 4.2 Add focused tests for the extracted helper via the existing detector test files, covering all four sub-branches.
- [x] 4.3 Run `uv run pytest tests/test_detector.py tests/test_detector_extra.py` in isolation.

## 5. Decompose `_analyze_func_node`

- [x] 5.1 Extract `_resolve_local_names`, `_collect_env_mutation_nodes`, `_append_env_effects`, `_append_descriptor_effect`, and `_append_resource_effects` from `_analyze_func_node` in `src/snake_eyes/analysis/detector.py`, preserving the `_EffectVisitor` run and the final effect sort.
- [x] 5.2 Add focused tests for each extracted helper in the detector test suite.
- [x] 5.3 Run `uv run pytest tests/test_detector.py tests/test_detector_extra.py tests/test_analysis_methods.py` in isolation.

## 6. Decompose `run_test_mapping`

- [x] 6.1 Extract `_collect_test_evidence`, `_build_target_indexes`, and `_build_mapping_rows` from `run_test_mapping` in `src/snake_eyes/quality/pipeline.py`, keeping the numbered pipeline order and the final sort + tiebreaker strip intact.
- [x] 6.2 Add focused tests for each extracted helper through the existing test-mapping test files.
- [x] 6.3 Run the test-mapping test suite in isolation.

## 7. Verification

- [x] 7.1 Run a before/after byte-identity comparison of `analyze` and `test_mapping` JSON-RPC output on a fixture project to confirm behavior preservation.
- [x] 7.2 Re-measure per-function McCabe complexity to confirm all six flagged functions dropped below their flagging threshold and no new helper exceeds it.

## 8. CI Parity

- [x] 8.1 Run `uv sync --locked`.
- [x] 8.2 Run `uv run ruff check src/ tests/`.
- [x] 8.3 Run `uv run ruff format --check src/ tests/`.
- [x] 8.4 Run `uv run mypy src/`.
- [x] 8.5 Run `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85`.
- [x] 8.6 Confirm no protocol schema, dependency constraint, or protected quality/governance gate was modified.
