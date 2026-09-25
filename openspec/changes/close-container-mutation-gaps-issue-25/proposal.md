# Proposal: Explicit ContainerMutation Assertions

## Why

Issue #25 asks for explicit assertions for the remaining `ContainerMutation` side effects after #18 and gaze #246 landed. A fresh workspace `gaze quality` run shows the analyzer's line coverage is 93.9%, but the targeted functions still report `ContainerMutation` gaps because their returned containers are exercised but the mutation contracts (in-place extension and sorting) are not explicitly asserted. This change closes those observable gaps by writing focused, deterministic container-state assertions in the existing test suite.

## What Changes

- **Add explicit `.extend()` and `.sort()` assertions for `compute_complexity`** in `tests/test_complexity.py`. Split the existing whole-list equality check into two container-state observations: one verifying the number and identity of entries (covers `.extend()`), and one verifying deterministic ordering by `(file, line, name)` (covers `.sort()`).
- **Add explicit `.sort()` assertion for `parse_coverage`** in `tests/test_coverage.py` / `tests/test_coverage_extra.py`. Ensure the canonical value test asserts the returned entries are ordered by `(file, start_line, function)`.
- **Confirm `.append()` coverage for `function_record_to_dict`** in `tests/test_models.py`. The existing serialization tests already map to the `.append()` effect; no new assertions are required unless a targeted regression test is missing.
- **Exclude `.pop()` criteria**. No target function in scope calls `.pop()` on an observable contract boundary; the only `.pop()` sites are internal constructor bookkeeping in `detector.py:__init__` and are intentionally left unasserted per Design Decision 4.
- **Re-run `gaze quality`** after test additions and capture before/after unique `(effect_type, source_file, source_line)` identities to verify the intended gaps close.
- **Document a contract-coverage floor** for the three target functions based on the fresh baseline.

## Capabilities

### New Capabilities

- `explicit-container-mutation-assertions`: Adds deterministic container-state assertions (length, membership, ordering) to the existing test suite so that the remaining observable `ContainerMutation` effects in `compute_complexity` and `parse_coverage` are truthfully mapped by the analyzer.

### Modified Capabilities

- None. This change only adds tests; the mapping logic added by #19 is unchanged.

## Impact

- **Affected tests**: `tests/test_complexity.py`, `tests/test_coverage.py`, `tests/test_coverage_extra.py`, and optionally `tests/test_models.py` for a focused `.append()` regression.
- **Affected production code**: none. This is a test-only change.
- **Dependencies**: none.
- **Protocol impact**: none. The Gaze analyzer protocol row schema remains unchanged.
- **Validation**: CI gates (ruff, mypy, pytest with 85% coverage floor) plus a workspace-local `gaze quality` before/after comparison.
