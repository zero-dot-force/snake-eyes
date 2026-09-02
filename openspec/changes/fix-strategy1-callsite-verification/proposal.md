## Why

Strategy-1 (name-convention) pairing in `quality/pairing.py` matches tests to target functions based on prefix stripping and exact name comparison (e.g., `test_add` strips to `add`, which exactly matches a target function `add`). It does not verify that the test body actually calls the matched target, producing false pairings at confidence 90. For example, after a refactoring where a test function is renamed but its body still tests something else, `test_add` could match target `add` at confidence 90 despite never calling `add()`. These false pairings degrade Gaze's test quality metrics and — because strategy-1 uses first-match-wins — prevent correct matches from being found by strategy-2 or strategy-3.

## What Changes

- Add call-site verification to strategy-1: after a name-convention match is found, walk the test function's AST body for `ast.Call` nodes and check whether any call resolves to the matched target function name.
- If no matching call is found, skip the pairing entirely (do not emit the result).
- The existing `_direct_call_names` helper (strategy-2) already extracts callee names from a test function AST. Strategy-1 will reuse this function to avoid duplication.
- Strategy-2 and strategy-3 behavior is unchanged.

## Capabilities

### New Capabilities

- `callsite-verification`: Call-site presence verification for strategy-1 name-convention pairings. Ensures a name-matched test actually calls its purported target before emitting a pairing result.

### Modified Capabilities

<!-- No existing specs to modify -->

### Removed Capabilities

None.

## Impact

- **Code**: `src/snake_eyes/quality/pairing.py` -- `_name_match` function signature changes to accept a test AST tree and test function name; internal logic adds a call-site check using `_direct_call_names`.
- **Behavior**: Some strategy-1 pairings that were previously emitted at confidence 90/70 will now be suppressed. These are false pairings by definition (the test never calls the target). Some tests may fall through to strategy-2 or strategy-3, which is correct behavior.
- **Protocol**: No protocol changes. `PairedResult` schema is unchanged.
- **Dependencies**: No new dependencies. Uses existing `ast` stdlib infrastructure already in use.

## Constitution Alignment

| Principle | Verdict | Notes |
|---|---|---|
| I. Protocol Fidelity | PASS | No protocol changes. `PairedResult` schema unchanged. Determinism preserved. |
| II. Detection Accuracy | PASS | Eliminates false positives (false pairings where test never calls target). False negatives for indirect calls correctly deferred to strategy-3. |
| III. Python-Native Analysis | PASS | Reuses `ast` module infrastructure already in use via `_direct_call_names`. |
| IV. Testability | PASS | Coverage strategy: unit tests for each scenario + integration test through `pair_tests` for fallthrough + project-wide 85% gate. |
| V. Analysis Safety | PASS | No new dependencies. No code execution. Uses existing `ast.walk` (parse-level only). |
