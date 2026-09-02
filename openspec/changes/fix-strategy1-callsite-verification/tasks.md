## 1. Modify `_name_match` to accept AST context

- [x] 1.1 Add `test_tree: ast.Module` and `test_name: str` parameters to `_name_match` in `src/snake_eyes/quality/pairing.py`
- [x] 1.2 After each name-convention match is found, call `_direct_call_names(test_tree, test_name)` to get the set of callee names in the test body
- [x] 1.3 Only append a match to `results` if `rec.name` is present in the callee name set (exact, case-sensitive check); skip the pairing otherwise
- [x] 1.4 Update the `_name_match` call site in `pair_tests` to pass `tree` and `test_name` as the new arguments
- [x] 1.5 Update existing tests that rely on strategy-1 name matching with test bodies that contain no call to the target (e.g., `assert True` bodies). These tests will be suppressed after the fix and must be updated to include a call to the matched target function, or restructured to test the new behavior. Affected tests include any that construct fixture test functions with exact-name matches but no call-site presence.

## 2. Tests for call-site verification

- [x] 2.1 Add test: name match with direct call present emits pairing at confidence 90
- [x] 2.2 Add test: name match with attribute call (`obj.foo()`) emits pairing at confidence 90
- [x] 2.3 Add test: name match with no call to target does NOT emit pairing (suppressed)
- [x] 2.4 Add test (integration through `pair_tests`): suppressed strategy-1 match falls through to strategy-2 direct-call match. This MUST drive `pair_tests` (not `_name_match` in isolation) to verify end-to-end fallthrough behavior.
- [x] 2.5 Add test: indirect call through helper does NOT count as call-site presence for strategy-1
- [x] 2.6 Add test: case-only name match (confidence 70) with call present emits pairing at confidence 70
- [x] 2.7 Add test: case-only name match (confidence 70) with no call present does NOT emit pairing (suppressed)
- [x] 2.8 Add integration test through `run_test_mapping` pipeline: fixture project where a test name-matches a target but does NOT call it — verify the false pairing is absent from the output. The fixture must ensure strategy-1 is the only strategy that could produce the false pairing.

## 3. Verification

- [x] 3.1 Run full test suite with coverage and confirm 85% gate passes
- [x] 3.2 Run ruff check, ruff format --check, and mypy gates

<!-- spec-review: passed -->
<!-- code-review: passed -->
