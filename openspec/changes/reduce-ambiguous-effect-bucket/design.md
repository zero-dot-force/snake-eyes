## Context

Gaze's universal scoring engine classifies each detected side effect as `contractual`, `incidental`, or `ambiguous` from five raw signals (interface, visibility, caller_count, naming_convention, docstring) that snake-eyes emits. snake-eyes never scores — the formula lives in Gaze's Go core. The only lever snake-eyes has to shrink the 58.9% ambiguous bucket is to emit more *accurate* signals.

Issue #33 shows the ambiguity is concentrated in internal helpers: `__init__` (91 ambiguous effects), `_`-prefixed helpers, and nested helpers. Today the `visibility` extractor (`signals/visibility.py`) receives only `(func_name, in_all)` and has two blind spots:

1. **Dunder methods return `None`.** `__init__` (the single largest ambiguous function) emits *no* visibility signal at all, so Gaze's scorer has one fewer input exactly where the disposition (method on a public class = caller-visible surface) is most knowable.
2. **Nested helpers are judged by bare name.** A nested helper `def helper()` (no underscore) inside another function is misread as public surface, even though it can never be part of any public API. Its mutations are private bookkeeping and should weigh private.

The fix is a *signal-extraction* change, not a scoring change: enrich the visibility input with function *surface* (module / method / nested + enclosing-class visibility), reusing the existing `PUBLIC_WEIGHT=10` / `PRIVATE_WEIGHT=-10` gate values. Because new classification judgment must be documented before it is encoded (Principle II "ambiguity over omission" and the governance rule to document trade-offs, per the `classify-signals` and container-mutation-assertions precedent), the change pairs the encoding with a reviewed disposition table (`docs/`) that records the per-(surface × enclosing-class visibility × dunder × name-prefix × effect-type exception) judgment — a documentation gate, not a runtime input.

## Goals / Non-Goals

**Goals:**

- Compute each function's surface (`module`, `method`, `nested`) and, for methods, the enclosing class's visibility (`public` / `private`), in `signals/adapter.py` `_collect_file_context`.
- Make `visibility.extract` surface-aware so dunder methods (`__init__`) and nested helpers emit a `visibility` signal derived from their surface, using only the existing `PUBLIC_WEIGHT`/`PRIVATE_WEIGHT` values.
- Add a reviewed disposition table under `docs/effect-disposition.md` plus a conformance test asserting it covers every reachable (surface × enclosing-class visibility × dunder × name-prefix × effect-type exception) combination with no conflict, and agrees with the extractor's emitted weights.
- Re-measure the ambiguous bucket with `gaze quality` and record before/after `classification_counts` with a pinned gaze commit.

**Non-Goals:**

- No scoring: no 5-signal sum, no tier boost, no contradiction penalty, no `contractual`/`incidental`/`ambiguous` label emitted by snake-eyes.
- No new `source` value and no sixth extractor — the five protocol sources stay fixed.
- No weight retuning — `PUBLIC_WEIGHT`/`PRIVATE_WEIGHT` remain gate values.
- No change to the detector, `analyze`, `complexity`, `coverage`, or `test_mapping` methods.
- No change to the Gaze Go core or the protocol schema.
- No guarantee of a specific ambiguous-percentage target — the change improves signal accuracy and re-measures; it does not force a number.

## Decisions

### Decision: extend the existing `visibility` source rather than add a signal

The change enriches the existing `visibility` signal with surface context instead of introducing a sixth signal source or a new `surface` field.

*Rationale:* The protocol fixes the five `source` strings (Protocol Fidelity, Principle I). A sixth source would require a protocol change in Gaze and risk violating the classify-signals contract. Surface is, semantically, visibility — so it belongs in the `visibility` extractor.

*Alternatives considered:* (a) new `source == "surface"` — rejected: breaks the five-source protocol contract. (b) emit surface as a new dict field — rejected: changes the wire shape and requires Gaze to consume it. (c) do nothing (data-only sidecar) — rejected by the issue as insufficient.

### Decision: model surface and enclosing-class visibility as enums

Introduce a `FunctionSurface` enum (`module` / `method` / `nested`) and an `EnclosingClassVisibility` enum (`none` / `public` / `private`), both defined in `signals/_types.py` (the shared signal value types module). `_collect_file_context` computes them from the existing `parents` map. A function is `method` when its direct enclosing scope is a class body, `nested` when its direct enclosing scope is a function body, else `module`. Enclosing-class visibility is `private` when the enclosing class name has a leading underscore OR the class itself is transitively nested inside a function body (any ancestor scope of the class is a function body — a function-local class is not caller-visible regardless of its name), `public` otherwise, and `none` for `module`/`nested`.

*Rationale:* The `_collect_file_context` walk already builds a `parents: dict[ast.AST, ast.AST]` map. The existing `_enclosing_class` helper distinguishes *method vs non-method* only — it returns the enclosing `ClassDef` or `None`, and returns `None` for **both** nested functions and module-level functions (it bails on any enclosing `FunctionDef`). Distinguishing `nested` from `module`, and deriving the enclosing class's own nesting, requires a small addition to the parent walk. Extending the existing AST-derived data is Python-native (Principle III) and avoids a second parse. The enums live in `_types.py` (not `adapter.py`) so `visibility.py` can type its parameters against them without introducing an import cycle (adapter imports `visibility`, which imports `_types`).

*Alternatives considered:* (a) re-derive surface at extract time per function — rejected: duplicates the walk and risks drift. (b) use astroid for surface — rejected: stdlib `ast` already has the parent links; astroid adds a dependency for no gain. (c) `FunctionSurface` in `adapter.py` — rejected: circular import risk.

### Decision: reuse existing weights; dunder-of-public-class = public, dunder-of-private-class = private

The surface-aware rules emit only `PUBLIC_WEIGHT` (`10`) and `PRIVATE_WEIGHT` (`-10`). A `__init__` on a public class emits public; on a private class emits private; a module-level dunder keeps `None`.

*Rationale:* The weights are the gaze-py gate values fixed by the `classify-signals` precedent. This change must not invent new magnitudes; it only decides *which existing* weight applies to a newly-distinguished surface. The disposition table records the judgment that a public class's `__init__` state setup is caller-visible (contractual) while a private helper's mutation is bookkeeping (incidental).

*Alternatives considered:* (a) introduce a new `DUNDER_WEIGHT` — rejected: invents a gate value. (b) keep dunder as `None` and only fix nested helpers — rejected: `__init__` is the single largest ambiguous contributor (91 effects), so leaving it untouched leaves the core of #33 unresolved.

### Decision: the nested branch is effect-type-aware for closure capture

A `nested` surface emits `PRIVATE_WEIGHT` in general, but `ClosureCaptureMutation` on a `nested` surface returns `None` (no signal). The extractor accepts the effect type of the effect being classified.

*Rationale:* A nested closure can escape its enclosing function (returned/stored and later invoked by an external caller), so its mutations can be caller-visible. Emitting `PRIVATE_WEIGHT` for a closure would silently assert a privacy judgment the change cannot make, violating Principle II (ambiguity over omission). Returning `None` for `ClosureCaptureMutation` keeps that combination `unclaimed` (Gaze may classify it `ambiguous`), which is the honest outcome. All other nested effects are genuinely internal bookkeeping and weigh private.

*Alternatives considered:* (a) unconditional `nested → PRIVATE_WEIGHT` — rejected: asserts a judgment on escaping closures. (b) introduce a `nested-closure` surface — rejected: over-fits; effect-type-awareness is a smaller change that reuses the existing per-effect loop in the adapter.

### Decision: disposition table keyed on the function-visibility decision space (with one effect-type exception)

The `effect-disposition` table keys on `(surface × enclosing-class visibility × dunder × name-prefix × effect-type exception)` — ten reachable rows — with effect types listed as illustrative examples in each row's rationale, not as a key axis (the `effect-type exception` axis is `none` everywhere except `ClosureCaptureMutation` on the `nested` surface). Its schema is pinned: header columns `surface`, `enclosing-class visibility`, `dunder`, `name-prefix`, `effect-type exception`, `disposition`, `rationale`. `dunder` and `name-prefix` use an `n/a` sentinel for axes that do not decide the disposition. The `name-prefix` axis collapses `__all__`-exported module-level names into `public`. The `nested` surface has two rows: `nested/none/n/a/n/a/none → incidental` (most nested effects) and `nested/none/n/a/n/a/ClosureCaptureMutation → unclaimed` (a closure can escape and be caller-visible). A conformance test (in `tests/`, test-only) parses the table and asserts completeness (all ten rows), consistency (no duplicate-key conflicts; valid disposition values; every non-`unclaimed` cell has a non-empty rationale naming at least one effect type), and agreement with `visibility.extract` (contractual ⇔ `PUBLIC_WEIGHT`, incidental ⇔ `PRIVATE_WEIGHT`, unclaimed ⇔ no signal). snake-eyes does not read the table at runtime.

*Rationale:* The `visibility` extractor emits a *per-function* signal with no effect-type dimension (beyond the closure-capture exception), so keying the table on the 48 `SideEffectType` values would repeat the same surface judgment 48 times and couple the analyzer to future taxonomy changes (Zero-Waste Mandate). Keying on the function-visibility decision space yields ten rows that exactly match what the signal can distinguish, with effect types as documentation. Keeping it out of the runtime path preserves the classify-signals contract that snake-eyes emits raw signals only. The table uses the disposition `unclaimed`; Gaze's scoring bucket for those combinations is `ambiguous` — the two terms name the same "no judgment asserted" state from the documentation side vs. the scoring side. The table carries a banner stating the dispositions record the visibility signal's intended direction (public → toward `contractual`, private → toward `incidental`), not a guaranteed final Gaze bucket, and that `contractual`/`incidental` are documentation terms, not snake-eyes scoring labels.

*Alternatives considered:* (a) key on `SideEffectType` — rejected: redundant 48× repetition and a taxonomy-sync maintenance burden with no runtime consumer. (b) a Python `enum`/dict consumed by `visibility.py` to gate signals — rejected: would smuggle scoring/classification judgment into the analyzer, violating the Gaze-owns-scoring boundary. (c) prose-only doc with no test — rejected: unenforceable; the constitution requires a coverage strategy. (d) a production parser module under `src/` — rejected: snake-eyes must not consume the table at analysis time, and a test-only parser is not measurable under `--cov=snake_eyes`.

### Decision: verify with the real gaze binary

Re-measurement uses the dev `gaze` binary (`gaze quality --analyzer snake-eyes --language python --format json .`) against the snake-eyes checkout. The pre-change `classification_counts` are re-measured with the SAME pinned gaze commit against the snake-eyes checkout at the pre-change commit, and the post-change counts with the same pinned gaze commit, so the before/after delta is self-consistent and reproducible (source/commit and protocol version recorded). This is a manual/recorded step (snake-eyes cannot score), captured in the committed `openspec/changes/reduce-ambiguous-effect-bucket/implementation-report.md`.

*Rationale:* Only Gaze's Go core can produce the classification counts; snake-eyes has no scorer. Re-measuring both sides with the same pinned gaze commit avoids the incomparability of an unpinned "main-HEAD" historical figure.

## Test Strategy

Coverage strategy (unit vs. integration, with targets):

- **Unit tests** — `visibility.py` and `adapter.py` combined statement+branch coverage ≥95% (enforced by a `uv run coverage report --include='src/snake_eyes/signals/visibility.py,src/snake_eyes/signals/adapter.py' --fail-under=95` post-step in `ci.yml`; branch coverage is already enabled via `pyproject.toml` `branch = true`; see tasks 5.1).
- **Conformance test** — `tests/test_effect_disposition.py` (test-only parser) enumerates the ten reachable (surface × enclosing-class visibility × dunder × name-prefix × effect-type exception) combinations and asserts completeness + consistency (no duplicate-key conflicts; valid disposition values; non-`unclaimed` cells have non-empty rationale naming at least one effect type) + agreement with `visibility.extract`'s emitted weights (contractual ⇔ `10`, incidental ⇔ `-10`, unclaimed ⇔ no signal). No coverage percentage applies to test-only code.
- **Integration test** — a `classify_signals`-boundary test asserting a public-class `__init__` yields a `visibility` weight of `10` and a nested helper yields `-10` in the emitted signals.
- **Regression** — `tests/test_signals_negative_label.py` still passes and covers the updated `visibility.py`.
- **Project floor** — `--cov-fail-under=85` remains the protected gate.

## Risks / Trade-offs

- **Changing `visibility` output reshapes Gaze's inputs for *all* analyzed Python** → the change can move effects among all three buckets, not just out of ambiguous. Mitigation: disposition table reviewed per surface combination; re-measurement captures net movement; rollback is a revert.
- **Surface model may misclassify exotic nesting** (e.g. a method defined via decorators) → mitigation: restrict `nested` to "function inside a function body"; treat class-inside-function members as `method` of a private-enclosing class; unit tests cover the edge cases the detector already tolerates.
- **Dunder-of-public-class = public is a judgment call** (some `__init__` bookkeeping is genuinely internal) → mitigation: the disposition table records this as a documented lean toward `contractual`, acknowledging that some genuinely-internal `__init__` bookkeeping will lean contractual.
- **Closure-capture escape** → mitigation: the nested branch returns `None` for `ClosureCaptureMutation`, keeping it `unclaimed` rather than silently asserting private.
- **Re-measurement depends on an external gaze binary** → mitigation: the change records the binary source/commit and treats re-measurement as evidence, not a CI gate; the unit/conformance tests are the protected gates.
- **Weight drift via "fixing" a test** → mitigation: tests assert `PUBLIC_WEIGHT == 10` and `PRIVATE_WEIGHT == -10` as constants; the gate-value protection forbids editing them to pass.

## Migration Plan

Additive, no persisted-data migration.

1. Land the surface computation in `adapter.py` (enums in `_types.py`) and the surface-aware `visibility.extract`, with unit tests meeting the per-module targets in Test Strategy (green under the 85% project gate).
2. Land `docs/effect-disposition.md` disposition table + conformance test (completeness, consistency, and agreement cross-checks).
3. Add a `uv run coverage report --include='src/snake_eyes/signals/visibility.py,src/snake_eyes/signals/adapter.py' --fail-under=95` post-step to `ci.yml` (without lowering the `--cov-fail-under=85` floor; branch coverage is already enabled via `pyproject.toml` `branch = true`).
4. Re-measure with the dev `gaze` binary (pinned source/commit) and record pre-change and post-change counts in `openspec/changes/reduce-ambiguous-effect-bucket/implementation-report.md`.
5. Reference `docs/effect-disposition.md` from the `README.md`/`AGENTS.md` project-structure sections, and update the now-stale `visibility.py` (surface-aware; no longer defers dunder behavior to gaze-py), `_types.py`, and `adapter.py` descriptions there.

Rollback: revert the change; `visibility` returns to the name/`__all__`-only behavior. No protocol client is affected (the five sources and the signal dict shape are unchanged).

## Open Questions

- None outstanding. (The prior "nested-helper vs nested-closure" question is resolved by the effect-type-aware nested branch; the disposition-table format question is resolved by pinning the key space to the ten reachable combinations.)
