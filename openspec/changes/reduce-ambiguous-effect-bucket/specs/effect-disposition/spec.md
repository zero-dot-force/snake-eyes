## ADDED Requirements

### Requirement: disposition table is documented and reviewable

The change SHALL add a documented, reviewable **effect-disposition table** (a Markdown artifact at `docs/effect-disposition.md`) that records, for every reachable function-visibility outcome, a disposition from the closed set `incidental`, `contractual`, or `unclaimed`. The table SHALL be the authoritative record of the classification judgment exercised by the surface-aware visibility signal, satisfying the documented-classification-judgment gate before any signal encoding is authored.

The disposition key SHALL be the tuple `(surface, enclosing-class visibility, dunder, name-prefix, effect-type exception)` where:

- `surface` is one of `module`, `method`, `nested`;
- `enclosing-class visibility` is one of `none`, `public`, `private` (`none` applies to `module` and `nested` surfaces; `public`/`private` apply to `method` surfaces);
- `dunder` is one of `false`, `true`, or `n/a` (a name property: the function name starts and ends with `__`; `n/a` marks an axis that does not decide the disposition);
- `name-prefix` is one of `public`, `private`, or `n/a` (the leading-underscore name prefix; `n/a` for dunder, private-class-method, and nested rows where the name prefix is not the deciding axis). The `name-prefix` axis SHALL collapse `__all__`-exported module-level names into `public` (an `__all__`-exported name is caller-visible regardless of any leading underscore); this collapse applies only to non-dunder names (dunder short-circuits before `__all__`/name-prefix);
- `effect-type exception` is one of `none` or `ClosureCaptureMutation` (the one effect type for which the nested surface asserts no judgment).

The reachable key space SHALL be the ten combinations the visibility signal can actually distinguish: `module`/`none`/`false`/`public`/`none`, `module`/`none`/`false`/`private`/`none`, `module`/`none`/`true`/`n/a`/`none`, `method`/`public`/`false`/`public`/`none`, `method`/`public`/`false`/`private`/`none`, `method`/`public`/`true`/`n/a`/`none`, `method`/`private`/`false`/`n/a`/`none`, `method`/`private`/`true`/`n/a`/`none`, `nested`/`none`/`n/a`/`n/a`/`none`, and `nested`/`none`/`n/a`/`n/a`/`ClosureCaptureMutation`.

Effect types (`SideEffectType` values from `snake_eyes.analysis.effects.SideEffectType`) SHALL be listed in each row's rationale as illustrative examples of the effects that carry that disposition; they are documentation, not a key axis (except the single `effect-type exception` axis above).

The disposition `unclaimed` in the table SHALL correspond to Gaze's `ambiguous` scoring bucket: a combination marked `unclaimed` is one for which snake-eyes asserts no classification judgment, and Gaze may classify it `ambiguous`. The disposition `unclaimed` here denotes "no classification judgment asserted" (Gaze may bucket it `ambiguous`) and is distinct from the container-mutation-assertion coverage domain's `unclaimed`, which denotes a `ContainerMutation` effect no test assertion covers. `unclaimed` is renamed from Gaze's `ambiguous` because it names snake-eyes' own no-claim stance (snake-eyes never asserts a bucket); `contractual` and `incidental` are retained because they name the direction toward Gaze's same-named buckets, not a claimed outcome.

#### Scenario: table exists and enumerates dispositions

- **WHEN** the disposition table artifact is inspected
- **THEN** it contains a header naming the disposition key columns (`surface`, `enclosing-class visibility`, `dunder`, `name-prefix`, `effect-type exception`, `disposition`, `rationale`) and rows covering the ten reachable combinations

### Requirement: disposition table covers every combination

The disposition table SHALL include an explicit disposition for every one of the ten reachable `(surface, enclosing-class visibility, dunder, name-prefix, effect-type exception)` combinations. No reachable combination SHALL be left uncovered; a combination whose disposition is genuinely unknown SHALL be marked `unclaimed`, never omitted.

#### Scenario: no uncovered combination

- **WHEN** the conformance test enumerates the ten reachable key combinations
- **THEN** every combination has a disposition recorded in the table (either `incidental`, `contractual`, or `unclaimed`)

### Requirement: disposition table is internally consistent

The disposition table SHALL NOT record conflicting dispositions for the same key. Each cell's `disposition` SHALL be exactly one of `incidental`, `contractual`, or `unclaimed`. Every cell asserting `incidental` or `contractual` SHALL carry a non-empty rationale that names at least one illustrative effect type. A conformance test SHALL fail if the table contains a duplicate key with differing dispositions, a disposition value outside the closed set, a non-`unclaimed` cell with an empty rationale or one that names no effect type, or a key outside the ten reachable combinations.

#### Scenario: conflicting dispositions rejected

- **WHEN** the conformance test parses the disposition table and finds the same key with two different dispositions
- **THEN** the test fails

#### Scenario: invalid disposition value rejected

- **WHEN** the conformance test parses the disposition table and finds a cell whose `disposition` is not exactly `incidental`, `contractual`, or `unclaimed`
- **THEN** the test fails

#### Scenario: non-unclaimed cell without rationale rejected

- **WHEN** the conformance test parses the disposition table and finds an `incidental` or `contractual` cell with an empty rationale, or a rationale that names no effect type
- **THEN** the test fails

### Requirement: disposition table agrees with the emitted visibility signal

The disposition recorded for each key SHALL agree with the `visibility` signal the extractor emits for that key: `contractual` SHALL correspond to `PUBLIC_WEIGHT` (`10`), `incidental` SHALL correspond to `PRIVATE_WEIGHT` (`-10`), and `unclaimed` SHALL correspond to the absence of a signal (`None`). A conformance test SHALL cross-check the table against `visibility.extract`: for each reachable key it SHALL feed a representative `(func_name, in_all, surface, enclosing_class_visibility, effect_type)` to the extractor — where the representative `func_name` and `in_all` exhibit the row's `dunder` and `name-prefix` values (`in_all` SHALL be `false` for `name-prefix: private` rows) — and assert the emitted weight (or `None`) matches the row's disposition.

#### Scenario: disposition matches emitted weight

- **WHEN** the conformance test feeds each reachable key's representative inputs to `visibility.extract`
- **THEN** a `contractual` row emits `PUBLIC_WEIGHT` (`10`), an `incidental` row emits `PRIVATE_WEIGHT` (`-10`), and an `unclaimed` row emits `None`

### Requirement: dispositions remain documentation, not snake-eyes scoring

The disposition table SHALL NOT be consumed by snake-eyes at analysis time to assign labels. snake-eyes SHALL continue to emit raw signals only; the table documents the judgment behind the visibility signal and is verified by tests, not by the JSON-RPC server. The strings `contractual`, `incidental`, `unclaimed`, and `ambiguous` SHALL NOT appear as assigned output values or in emitted `reasoning` strings in `src/snake_eyes/signals/`; they MAY appear in comments and docstrings (prose), but SHALL NOT be emitted as output values. The table's own third disposition is `unclaimed`; `ambiguous` is reserved for Gaze's scoring output and SHALL NOT be used as a disposition value. The table SHALL carry a banner stating that the dispositions record the visibility signal's intended direction (public → toward `contractual`, private → toward `incidental`), not a guaranteed final Gaze bucket, and that `contractual`/`incidental` are documentation terms, not snake-eyes scoring labels. A conformance test SHALL assert the banner is present and contains "not a guaranteed final Gaze bucket".

#### Scenario: no scoring path reads the table

- **WHEN** snake-eyes serves a `classify_signals` request
- **THEN** the response contains raw signal dicts only and does not read or reference the disposition table

### Requirement: re-measurement is recorded

The change SHALL record the post-change `classification_counts` (contractual / incidental / ambiguous) produced by `gaze quality --analyzer snake-eyes --language python --format json .` against the snake-eyes checkout, together with the gaze binary source/commit (and protocol version). The pre-change `classification_counts` SHALL be re-measured with the SAME pinned gaze commit, against the snake-eyes checkout at the pre-change commit, so the before/after delta is self-consistent and reproducible. Both counts and the pinned gaze commit SHALL be recorded in a committed artifact at `openspec/changes/reduce-ambiguous-effect-bucket/implementation-report.md`.

#### Scenario: baseline and outcome both captured

- **WHEN** the change is complete
- **THEN** an artifact records the pre-change and post-change `classification_counts` (both measured with the same pinned gaze commit), the gaze binary source/commit and protocol version, and compares the post-change ambiguous count against the pre-change count
