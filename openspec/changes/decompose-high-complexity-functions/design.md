# Design: Decompose High-Complexity Functions

## Context

Issue #27 is a Gaze-driven refactor. Six functions in `src/snake_eyes/` score at or above complexity 21 and were assigned `decompose` / `decompose_and_test` strategies. They share a common shape: a single method has accreted a long sequence of mutually-exclusive branches (`if`/`elif` dispatch over `ast` node types, or a multi-step procedural pipeline with nested loops and `try`/`except`). The functions are correctness-critical — they implement side-effect detection, test-to-target pairing, provenance tracing, and test-mapping orchestration — so the refactor must be strictly behavior-preserving. The existing regression suites (`test_provenance_regressions.py`, `test_test_mapping_method.py`, `test_detector.py`, `test_detector_extra.py`, `test_analysis_methods.py`) are the behavioral contract that proves preservation.

## Goals / Non-Goals

**Goals:**

- Reduce each of the six flagged functions' McCabe complexity below its flagging threshold by extracting focused helpers.
- Preserve byte-identical analyzer output and every degradation/recursion-bound semantic.
- Improve testability by making each extracted helper independently exercisable, and add focused tests.
- Pass the unchanged CI gates without lowering any protected gate.

**Non-Goals:**

- Modifying `_handle_call` (issue #26), whose complexity of 144 is a separate work item.
- Changing the Gaze protocol, JSON-RPC schema, `SideEffectType` taxonomy, or effect identity ordering.
- Adding new dependencies or new analyzer capabilities.
- Rewriting the algorithms themselves (e.g., replacing AST dispatch with a different mechanism); this is a structural extraction only.

## Decisions

### 1. Extract helpers, do not rewrite dispatch mechanisms
Each function is decomposed by extracting its branches and pipeline stages into private helpers on the same class/module, keeping the original function as a thin orchestrator. This is the lowest-risk way to reduce McCabe complexity because it preserves control-flow order and side effects by construction.

**Alternative considered:** Replace `if`/`elif` chains with dict dispatch or a visitor-pattern table. Rejected: it would change control-flow structure more than necessary, is harder to audit for behavior preservation, and risks subtle ordering changes in effect collection.

### 2. Decompose in ascending-risk order
Implementation proceeds from the smallest, most self-contained function to the largest orchestration: `_append_bound_names` → `_build_call_graph` → `visit_stmt` → `visit_ClassDef` → `_analyze_func_node` → `run_test_mapping`. Each step lands green before the next begins, so a regression is always attributable to a single function.

**Alternative considered:** Batch all six in one commit. Rejected: a single diff spanning five files makes regression bisection and review disproportionately hard, and violates the task-completion bookkeeping convention (one checkbox marked at a time).

### 3. Preserve degradation semantics explicitly
`_build_call_graph` re-raises `FileNotFoundError` for a missing call-graph file while swallowing per-file and per-call exceptions. The extracted `_parse_modules`, `_collect_defined_names`, and `_resolve_call_edges` helpers keep these exception boundaries intact — the `FileNotFoundError` re-raise stays in the orchestrator, and per-candidate/per-call `except Exception` stays inside the resolver helper where it operates per-node.

**Alternative considered:** Unify all errors into a single degrade-and-return-None path. Rejected: it would change the observable `FileNotFoundError` contract that existing tests in `test_test_mapping_method.py` assert.

### 4. Keep recursion bounds in the helper that recurses
`_append_bound_names` enforces `MAX_AST_DEPTH`. The extracted `_append_funcdef_bound_names` / `_append_classdef_bound_names` helpers receive the depth and bound as parameters and recurse through the same generic path, so the depth budget semantics are unchanged. The orchestrator no longer recomputes the bound per branch.

**Alternative considered:** Move depth accounting into a decorator or wrapper. Rejected: unnecessary indirection that would complicate stack traces and mypy strict typing for no behavior gain.

### 5. Focused tests target helpers via the public surface where possible
Where a helper is private and tightly coupled to visitor state, the focused test exercises it through the nearest public entry point (e.g., `collect_assertions`, `_build_call_graph` via the public test-mapping path, or a directly-constructed visitor). This keeps tests meaningful without widening the public API, honoring the Zero-Waste Mandate.

**Alternative considered:** Export every helper as a public function solely for testability. Rejected: it would expand the public surface and risk accidental external use; tests can reach private helpers through the established module import path used by existing suites.

## Risks / Trade-offs

- **[Risk] Behavior drift from a subtly reordered branch** → Extract branches verbatim, preserving order; run the full regression suite plus a before/after byte-identity comparison of `analyze`/`test_mapping` output on a fixture project.
- **[Risk] Recursion / `MAX_AST_DEPTH` semantics change** → Thread depth and bound through extracted helpers unchanged; add a focused test that exercises the depth ceiling.
- **[Risk] `FileNotFoundError` re-raise lost** → Keep the re-raise in the orchestrator and add an explicit test asserting propagation (already present; must remain green).
- **[Risk] A helper's name collides with an existing method** → Prefix all extracted helpers with `_` and scope them to the owning class/module; grep for collisions before committing.
- **[Trade-off] Complexity is moved, not eliminated** → Total complexity is unchanged, but per-function complexity — the metric Gaze flags — drops below threshold, which is the issue's stated goal. No new function is allowed to exceed the flagging threshold.

## Migration Plan

1. Implement each decomposition in ascending-risk order, running the relevant test file in isolation after each function before the full suite.
2. After all six land, run the exact CI workflow commands (`uv sync --locked`, `ruff check`, `ruff format --check`, `mypy`, `pytest --cov-fail-under=85`).
3. Re-measure per-function McCabe complexity to confirm each flagged function dropped below its threshold.

Rollback is a `git revert` of the change; there is no persisted data, dependency, or wire-format migration.

## Open Questions

None. The decomposition boundaries are clear from the source, and `_handle_call` is explicitly out of scope per issue #26.
