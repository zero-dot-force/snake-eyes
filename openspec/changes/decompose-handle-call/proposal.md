## Why

`_handle_call` at `src/snake_eyes/analysis/detector.py:657` is a ~610-line
`if/elif` waterfall with cyclomatic complexity **144** and GazeCRAP
**20880** at 98.5% line coverage — genuine structural complexity, not a
coverage artifact. A fresh `gaze` report (2026-09-25) flags it as the
single largest structural risk in the codebase and recommends the
`decompose_and_test` strategy: split the call-handling dispatch into
per-node/per-effect helpers, then add tests for each.

Ref: [GitHub Issue #26](https://github.com/zero-dot-force/snake-eyes/issues/26)

## What Changes

Decompose the single monolithic call-dispatch method into small,
single-responsibility per-effect handler methods behind an ordered handler
chain, with a focused unit test per handler. This is a **purely structural
refactor** — no behavior change, no protocol change, no new effects.

1. **Introduce an ordered handler chain** — replace the `if/elif`
   waterfall with a list of `_handle_*` methods tried in order; the first
   handler that consumes the call short-circuits the rest.

2. **Extract top-level call clusters** — `sys.exit`/`os._exit`, `print`,
   `eval`/`exec`, `setattr`/`delattr`, `type`/`types.new_class`,
   `__import__`/`importlib`, `atexit`/`weakref`, time/datetime/date,
   logging, asyncio/thread/spawn, `open(...,'w')`, and `getattr(...)()`
   each become their own method.

3. **Split the large `ast.Attribute` method-call block** into per-concern
   handlers: std-stream writes, env mutations, os filesystem ops,
   shutil/Path ops, writer methods, container methods, map methods, and
   misc methods (mutex/queue/db/http).

4. **Remove the `# noqa: C901 (complex)` suppression** once no single
   method exceeds the complexity threshold.

5. **Add per-handler tests** plus negative/ordering regressions while
   keeping every existing golden test passing unchanged.

## Capabilities

### New Capabilities

- `call-effect-handlers`: decomposed, per-effect call-dispatch handlers
  that preserve the exact existing detector output (effect set, order,
  and content) while making each dispatch rule independently testable.

### Modified Capabilities

None — this refactor changes implementation structure only; no emitted
effect or requirement changes.

### Removed Capabilities

None.

## Constitution Alignment

| Principle | Verdict | Notes |
|-----------|---------|-------|
| I. Protocol Fidelity | PASS | No JSON-RPC schema changes. Output is byte-for-byte deterministic and unchanged. |
| II. Detection Accuracy | PASS | Behavior-preserving refactor; existing golden tests lock effect set/order/content. |
| III. Python-Native Analysis | PASS | Still uses `ast` only; no new dependencies or reimplemented semantics. |
| IV. Testability | PASS | Each handler becomes an isolated unit; per-handler tests added. Coverage gate maintained. |
| V. Analysis Safety | PASS | No code execution; static analysis unchanged. |

## Impact

- **Code**: `src/snake_eyes/analysis/detector.py` — `_handle_call`
  (lines 657-1267) collapses to a thin dispatcher; ~13 top-level and ~8
  method-call sub-concern handler methods are added.
- **Tests**: new `tests/test_detector_call_handlers.py` (or equivalent)
  with one positive test per handler plus negative/ordering regressions.
- **No API/dependency/protocol change**: `analyze_source` /
  `analyze_path` signatures and output unchanged; no new deps.
- **Downstream**: lower GazeCRAP for the module's largest function; the
  related moderate-complexity decompositions are deferred to issue #27.
