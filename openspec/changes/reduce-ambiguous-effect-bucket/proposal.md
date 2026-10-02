## Why

`gaze quality` (main-HEAD gaze + snake-eyes `main`) classifies **58.9%** of detected side effects as `Ambiguous` — `classification_counts = {contractual: 557, incidental: 342, ambiguous: 1286}` out of 2185 (issue #33). The ambiguity is not in the already-resolved `ContainerMutation` identities (#28); it is spread across `ReturnValue` (82), `CallbackInvocation` (50), `MapMutation` (37), and others, concentrated in internal helpers — `__init__` (91), `initialize_result` (34), `signals.caller.extract` (29), `_collect_defined_names` (14), `_process_class_statement` (10), `_parse_modules` (8). The common thread is that these functions' *visibility* — the surface that determines whether an effect is caller-visible (`contractual`) or private bookkeeping (`incidental`) — is either missing or under-informative in the signals snake-eyes emits. Resolving this is a Detection Accuracy improvement (Principle II: ambiguity over omission, but the bucket should not be this large when the disposition is knowable).

## What Changes

- Extend the signal adapter's per-file AST context (`_FileContext`) to compute each function's **surface** — `module`, `method`, or `nested` — plus, for methods, the enclosing class's visibility (`public` / `private`; the enum also carries `none` for non-method surfaces).
- Extend the `visibility` extractor to consume that context so that dunder methods (notably `__init__`) and nested helpers emit a *visibility* signal derived from their enclosing surface, **reusing the existing `PUBLIC_WEIGHT`/`PRIVATE_WEIGHT` gate values** rather than dropping to `None` (dunder) or relying on the bare name prefix (nested helpers). The nested branch is effect-type-aware: `ClosureCaptureMutation` on a nested surface keeps `None` (stays `unclaimed`).
- Add a **documented, reviewable disposition table** recording, per (surface × enclosing-class visibility × dunder × name-prefix), which internal-helper mutations are safely `incidental`, which are `contractual`, and which remain `unclaimed` (corresponding to Gaze's `ambiguous` bucket) — satisfying the documented-classification-judgment constraint before any encoding.
- Add conformance and regression tests: surface-computation unit tests, disposition-table conformance tests, a `classify_signals`-boundary integration test, and the existing no-label negative test.
- Re-measure the ambiguous bucket with `gaze quality --analyzer snake-eyes --language python --format json .` and record the post-change counts against a pre-change re-measurement taken with the same pinned gaze commit.

## Capabilities

### New Capabilities

- `visibility-context`: the signal-extraction enrichment that classifies each analyzed function's surface (`module`, `method`, `nested`) and enclosing-class visibility (`none`, `public`, `private`), feeding a precise `visibility` signal so internal-vs-exported mutating helpers are distinguishable in the raw signal stream.
- `effect-disposition`: the documented, reviewable disposition table that records, per (surface × enclosing-class visibility × dunder × name-prefix), whether the analyzer's internal-helper mutations are treated as safely `incidental`, `contractual`, or left `unclaimed`, encoded as reviewed data with a conformance test asserting the table is complete, internally consistent, and agrees with the emitted visibility signal.

### Modified Capabilities

- `signal-extractors` (visibility requirement): the `visibility` extractor's behavior is refined to be surface-aware. Previously it emitted a signal from name/`__all__` alone and returned `None` for dunder methods; now dunder methods of public classes emit `PUBLIC_WEIGHT`, dunder methods of private classes emit `PRIVATE_WEIGHT`, nested helpers emit `PRIVATE_WEIGHT` (except `ClosureCaptureMutation`, which keeps `None`), non-dunder methods of private classes emit `PRIVATE_WEIGHT` regardless of name, and module-level dunder functions keep `None`. See `specs/signal-extractors/spec.md` for the `## MODIFIED Requirements` delta.

### Removed Capabilities

None.

## Impact

- `src/snake_eyes/signals/_types.py` — new `FunctionSurface` and `EnclosingClassVisibility` enums.
- `src/snake_eyes/signals/visibility.py` — `extract` gains surface, enclosing-class-visibility, and effect-type parameters; existing name/`__all__` branches preserved.
- `src/snake_eyes/signals/adapter.py` — `_FileContext` and `_collect_file_context` compute function surface and enclosing-class visibility; `extract_signals` passes them (plus effect type) to `visibility.extract`.
- `tests/test_signals_visibility.py`, `tests/test_signals_adapter.py` — new and updated cases for surface-aware visibility.
- `tests/test_effect_disposition.py` — new conformance test for the disposition table.
- `tests/test_classify_signals_method.py` — `classify_signals`-boundary integration test.
- `tests/test_signals_negative_label.py` — existing no-label negative test (updated coverage only).
- `docs/effect-disposition.md` — new disposition-table artifact.
- `openspec/changes/reduce-ambiguous-effect-bucket/implementation-report.md` — committed; records pre-change and post-change `classification_counts` (same pinned gaze commit) plus the gaze binary source/commit and protocol version.
- `README.md`, `AGENTS.md` — reference `docs/effect-disposition.md`, update the now-stale `visibility.py` (surface-aware; no longer defers dunder behavior to gaze-py), `_types.py` (`SignalResult` + two enums), and `adapter.py` (surface computation) project-structure comments, and document the new per-module coverage post-step in `AGENTS.md` "Shell Commands" and "Protected gates".
- `.github/workflows/ci.yml` — add a `uv run coverage report --include=... --fail-under=95` post-step for `signals.visibility` and `signals.adapter` (user-directed; the `--cov-fail-under=85` floor is unchanged; branch coverage is already enabled via `pyproject.toml` `branch = true`).
- No protocol field changes, no new `source` value, no weight changes (weights remain gate values). Classification itself stays in Gaze's Go core.

## Constitution Alignment

- **Protocol Fidelity — PASS.** No new `source` value, no wire-shape change, deterministic output preserved.
- **Detection Accuracy — PASS.** The change is expected to narrow the ambiguous bucket by emitting more accurate visibility signals; ambiguity (closure-capture on nested surfaces) is never silently asserted.
- **Python-Native Analysis — PASS.** Surface is derived with stdlib `ast` from the existing `parents` walk; no reimplementation of Python semantics, no new dependency.
- **Testability — PASS.** Coverage strategy with per-module targets is specified in `design.md` and `tasks.md`.
- **Analysis Safety — PASS.** Static analysis only; analyzed code is never executed.
