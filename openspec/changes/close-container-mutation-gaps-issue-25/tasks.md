## 1. Baseline capture

- [x] 1.1 Run `gaze quality --analyzer snake-eyes --language python --format json .` and save the before report.
- [x] 1.2 Extract the current per-target contract coverage and targeted `ContainerMutation` effect IDs (`se-65715d40`, `se-48443a2b`, `se-2ede1f21`) from the report.

## 2. `compute_complexity` assertions

- [x] 2.1 Refactor or extend `tests/test_complexity.py::test_ordering_by_file_line_name` (or add a new focused test) to assert both length/membership of `entries` and deterministic ordering by `(file, line, name)`.
- [x] 2.2 Ensure the length/membership assertion is attributable to `.extend()` at `complexity.py:159` and the ordering assertion is attributable to `.sort()` at `complexity.py:161`.
  - **Outcome**: `len(entries)` maps to `.extend()` (se-2ede1f21). `.sort()` (se-65715d40) cannot be covered by test-only changes because gaze attributes any container-state assertion on the returned list to the first `ContainerMutation` effect in source order (`.extend()`). This is a structural per-pair single-attribution ceiling.

## 3. `parse_coverage` assertions

- [x] 3.1 Add an explicit ordering assertion to `tests/test_coverage.py::test_coverage_json_expected_values` (or an equivalent canonical value test) verifying entries are ordered by `(file, start_line, function)`.
- [x] 3.2 Confirm the ordering assertion maps to `.sort()` at `coverage.py:359`.

## 4. `function_record_to_dict` coverage preservation

- [x] 4.1 Verify existing serialization tests in `tests/test_models.py` still cover `.append()` at `models.py:64`.
- [x] 4.2 Add a focused regression test only if an existing coverage hole is found. (No hole found; no new test added.)

## 5. Validation and quality regression

- [x] 5.1 Run `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85` and ensure all tests pass with coverage above the protected floor. (799 passed, 93.90% coverage)
- [x] 5.2 Run `uv run ruff check src/ tests/` and `uv run ruff format --check src/ tests/`. (Both clean)
- [x] 5.3 Run `uv run mypy src/`. (Clean)
- [x] 5.4 Re-run `gaze quality --analyzer snake-eyes --language python --format json .` and compare unique `(effect_type, source_file, source_line)` identities before and after.
- [x] 5.5 Confirm `se-65715d40` (`complexity.py:161`) and `se-48443a2b` (`coverage.py:359`) are no longer gaps in the focused tests, and no new unique gaps appear for unchanged targets.
  - **Outcome**: `se-48443a2b` is closed in `test_coverage_json_expected_values`. `se-65715d40` remains a gap due to the structural ceiling described in 2.2.

## 6. Documentation and handoff

- [x] 6.1 Record the achieved per-function contract-coverage maxima and the target floor in the change summary.
- [x] 6.2 Update the issue #25 comment with the before/after identity comparison and the final floor.

## 7. Achieved contract-coverage maxima and target floor

| Function | Baseline max | After max | Target floor |
|---|---|---|---|
| `parse_coverage` | 50.0% | 75.0% | >= 75.0% (ordering assertion covers `.sort()`) |
| `compute_complexity` | 28.6% | 28.6% | >= 28.6% (structural ceiling; `.sort()` uncovered) |
| `function_record_to_dict` | 20.0% | 20.0% | >= 20.0% (`.append()` covered; MapMutation out of scope) |

- Global average contract coverage: 27.35% -> 27.41%.
- Closed identity: `ContainerMutation` `.sort()` (`se-48443a2b`) at `src/snake_eyes/coverage.py:359` in `test_coverage_json_expected_values`.
- Open identity due to structural ceiling: `ContainerMutation` `.sort()` (`se-65715d40`) at `src/snake_eyes/analysis/complexity.py:161`; cannot be covered by test-only changes because gaze attributes every container-state assertion on the returned list to the first `ContainerMutation` effect (`.extend()` at line 159).
- Out of scope: `MapMutation` x3 in `function_record_to_dict` require a mapper change in `mapping.py`.
