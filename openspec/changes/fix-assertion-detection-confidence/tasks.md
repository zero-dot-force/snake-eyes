## 1. Pipeline — result type and confidence computation

- [x] 1.1 Add a `TestMappingResult` dataclass (fields `mappings: list[dict[str, Any]]`, `assertion_detection_confidence: int`) to `src/snake_eyes/quality/pipeline.py`
- [x] 1.2 Restructure `run_test_mapping` so that, after test-function collection, it iterates every `(test_function, test_file)` pair, resolves the AST node, and collects assertions once into a `dict[tuple[str, str], list[AssertionInfo]]` (reusing the existing `collect_assertions` guard, which swallows `RecursionError` internally and returns partial results; a test function counts as detected iff its collected list is non-empty)
- [x] 1.3 Compute `assertion_detection_confidence` as `(100 * detected + total // 2) // total` when `total > 0`, else `0`, where `detected` counts test functions with at least one assertion
- [x] 1.4 Remove the `not test_functions or not target_records` and `not pairs` early returns so confidence is still computed when there are no pairs; keep `mappings` empty in those cases
- [x] 1.5 Update the pairing loop to read pre-collected assertions from the map instead of re-invoking `collect_assertions`
- [x] 1.6 Return a `TestMappingResult` from `run_test_mapping`; update its docstring and type annotations

## 2. Server handler

- [x] 2.1 Update `_test_mapping` in `src/snake_eyes/server.py` to unpack the result and return `{"mappings": result.mappings, "assertion_detection_confidence": result.assertion_detection_confidence}`

## 3. Tests

- [x] 3.1 [P] Update `tests/test_test_mapping_method.py` to assert the new two-key envelope and confidence semantics
- [x] 3.2 [P] Add a `test_mapping` response-shape assertion to `tests/test_server.py` (the server handler unit test), asserting the new two-key envelope
- [x] 3.3 [P] Update `tests/test_protocol.py` if it asserts the `test_mapping` envelope
- [x] 3.4 [P] Add pipeline unit tests covering confidence for all-asserted (100), partially-asserted (exact round-half-up values, e.g. 1/3 → 33, 2/3 → 67), no-assertion (0), unpaired-test, no-production-targets, and empty (0) projects; plus a degenerate-assertion-walk case (asserting the function is counted as detected iff ≥1 assertion was collected) and a cross-run byte-identical determinism case for the new return shape

## 4. Verification

- [x] 4.1 Run `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/`
- [x] 4.2 Run `uv run mypy src/`
- [x] 4.3 Run `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85`
- [x] 4.4 Verify constitution alignment (Protocol Fidelity, Detection Accuracy, Python-Native Analysis, Testability, Analysis Safety) as documented in the proposal

<!-- spec-review: passed -->
<!-- code-review: passed -->
