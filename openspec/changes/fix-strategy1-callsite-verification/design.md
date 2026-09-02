## Context

Strategy-1 in `quality/pairing.py` (`_name_match`) pairs tests to targets using prefix stripping only. It strips `test_`/`Test`/`test`/`Test` prefixes and matches the remainder against target function names. This produces false pairings when a test name happens to contain a target function name as a substring but never actually calls that function.

Strategy-2 (`_direct_call_match`) already implements call-site extraction via `_direct_call_names`, which walks a test function's AST body for `ast.Call` nodes and collects callee names. This helper is well-tested and handles both `Name` (bare calls) and `Attribute` (method calls) nodes.

The `pair_tests` function uses first-match-wins: if strategy-1 returns results, strategies 2 and 3 are skipped. This means false positives from strategy-1 prevent correct matches from being found by later strategies.

## Goals / Non-Goals

**Goals:**
- Eliminate false strategy-1 pairings where the test never calls the matched target
- Reuse the existing `_direct_call_names` helper to avoid code duplication
- Maintain strategy-1 priority (name-convention matches with verified call sites remain highest confidence)

**Non-Goals:**
- Changing strategy-2 or strategy-3 behavior
- Modifying confidence scores for verified strategy-1 matches (they remain 90/70)
- Adding transitive call resolution to strategy-1 (if the test calls a helper that calls the target, that is handled by strategy-3)
- Handling dynamic dispatch (`getattr`, `__call__`, etc.) -- consistent with existing `_direct_call_names` limitations

## Decisions

### Decision 1: Skip unverified pairings entirely (not reduce confidence)

**Choice**: If a strategy-1 name match has no call-site confirmation, the pairing is not emitted at all.

**Alternatives considered**:
- *Reduce confidence to 30*: Issue #14 listed this as an option. Rejected because a pairing where the test does not call the target is definitionally wrong -- emitting it at any confidence produces a false positive in Gaze's metrics.

**Rationale**: Suppressing the false pairing allows the test to fall through to strategy-2 or strategy-3, which may find the correct target. A low-confidence false pairing would still appear in results and prevent fallthrough.

### Decision 2: Reuse `_direct_call_names` for call-site extraction

**Choice**: Pass the test AST tree and test function name through the existing `_direct_call_names` helper rather than writing a new AST walker.

**Rationale**: `_direct_call_names` already handles the exact logic needed -- finding `ast.Call` nodes inside a specific function and extracting callee names from `ast.Name.id` and `ast.Attribute.attr`. Duplication would violate DRY and diverge over time.

### Decision 3: Modify `_name_match` signature to accept AST context

**Choice**: Add `test_tree: ast.Module` and `test_name: str` parameters to `_name_match` so it can perform call-site verification internally. Note: `test_name` is already the first parameter of `_name_match`; the new `test_name` parameter here refers to passing the qualified test function name (e.g., `TestFoo.test_bar`) needed by `_direct_call_names` to locate the correct function node in the AST tree.

**Rationale**: Keeps the verification co-located with the matching logic. The caller (`pair_tests`) already has the test tree available. The alternative of doing verification in `pair_tests` after `_name_match` returns would split the strategy-1 logic across two locations.

## Risks / Trade-offs

- **[Performance]** Adding an AST walk per strategy-1 match adds overhead. **Mitigation**: `_direct_call_names` is already called for strategy-2 on every test that doesn't match strategy-1. Tests that now pass through strategy-1 verification and fail will call `_direct_call_names` twice (once in strategy-1, once in strategy-2). The cost is negligible -- it's a single-pass `ast.walk` over a test function body, typically a few dozen nodes. No caching needed.

- **[False negatives]** A test that exercises a target through indirect calls (via helper functions, fixtures, or parametrize) will not have the target name in its direct call set and will be skipped by strategy-1. **Mitigation**: This is correct behavior -- indirect calls are the domain of strategy-3 (transitive call graph). The test falls through and may be caught there.

- **[Exact-match only]** `_direct_call_names` collects bare names (`fn.id`) and attribute names (`fn.attr`). A call like `module.function()` produces `function` in the set, which matches. A call like `obj.method()` where `method != target_name` does not match. **Mitigation**: This is the same behavior strategy-2 already uses. Consistent treatment across strategies.
