## ADDED Requirements

### Requirement: extract_signals public API
The system SHALL provide `src/snake_eyes/signals/adapter.py` exposing `extract_signals(root_path: str, patterns: list[str]) -> list[dict]`. This adapter is original snake-eyes code; gaze-py `classify/engine.py` SHALL NOT be lifted. `extract_signals` SHALL obtain functions via the #4 detector `analyze_path(root_path, patterns)`, thereby inheriting its discovery ordering, parse-error skipping, and resource bounds.

#### Scenario: adapter returns a list of signal dicts
- **WHEN** `extract_signals` runs over a tree containing functions with observable effects
- **THEN** it returns a list whose entries are signal dicts

#### Scenario: engine is not lifted
- **WHEN** the `src/snake_eyes/signals/` package is inspected
- **THEN** there is no lifted copy of gaze-py `classify/engine.py` and no local scoring formula

### Requirement: per-effect extractor fan-out
For each `FunctionRecord` returned by `analyze_path`, and for each `Effect` on that record, `extract_signals` SHALL run all five extractors. Because `FunctionRecord` does not carry the AST inputs the extractors need, `extract_signals` SHALL re-parse the project's ASTs by enumerating files via `_shared.ordered_file_list(root_path, patterns)` and reading each through `_shared.iter_source_files` to derive class bases, function name, docstring, and `__all__` membership, and SHALL build the per-request caller index with a single `build_caller_index(root_path, patterns)` call. The same `(root_path, patterns)` SHALL be threaded to every consumer — the detector's `analyze_path`, the adapter's own AST re-parse, and `build_caller_index` — so that all of them enumerate the identical deterministic, pattern-consistent file set (each performs its own walk over that set; this triple-parse is an accepted trade-off). Each `FunctionRecord` SHALL be mapped to its enclosing class (needed for class bases) by locating the function `def` at `FunctionRecord.line` within the re-parsed AST and taking its enclosing `ClassDef`, if any. The inbound caller count SHALL be obtained via `CallerIndex.count(package, func_name)` (never the per-call `count_callers` test wrapper). Each extractor receives the data it needs from this set: class bases, function name, docstring, and `__all__` membership (from the re-parsed AST); the effect's `SideEffectType`; and the caller count. For every non-`None` extractor result it SHALL append exactly one signal dict, using that effect's type as `side_effect_type`.

#### Scenario: multiple sources for one effect all emitted
- **WHEN** a function-effect pair matches both the `naming_convention` and `docstring` extractors
- **THEN** two signal dicts are appended, one per source, both carrying that effect's `side_effect_type`

#### Scenario: function with zero effects yields zero signals
- **WHEN** a function has an empty `side_effects` list
- **THEN** `extract_signals` appends no signals for that function

### Requirement: raw signals only, no aggregation and no labels
`extract_signals` SHALL NOT sum weights, clamp weights, de-duplicate signals across extractors, or assign any classification label. Multiple signals for the same function-effect pair from different extractors are expected and SHALL all be retained. The strings `contractual`, `incidental`, and `ambiguous` SHALL NOT appear as assigned output values in `adapter.py`.

#### Scenario: duplicate-source signals are not deduped or summed
- **WHEN** two extractors both fire for the same function-effect pair
- **THEN** both signals appear in the output with their individual weights, and no combined or summed weight is produced

#### Scenario: no classification label on adapter output
- **WHEN** any signal dict is produced by `extract_signals`
- **THEN** it contains no `contractual`/`incidental`/`ambiguous` label

### Requirement: signal dict shape
Each signal dict produced by `extract_signals` SHALL carry the protocol v1.1.0 field names: `function` (the unqualified function name), `package` (the dotted package from the shared derivation), `side_effect_type` (the effect's `SideEffectType` value), `source` (one of the five allowed strings), and `weight` (an integer). A short, non-empty `reasoning` string SHALL be included. No other classification fields SHALL be present.

#### Scenario: signal carries protocol field names
- **WHEN** `extract_signals` emits a signal for the function `divide` in package `math_utils`
- **THEN** the dict contains `function == "divide"`, `package == "math_utils"`, `side_effect_type`, `source`, an integer `weight`, and a short, non-empty `reasoning`, and uses `function`/`package` (not `name`)

### Requirement: adapter integrates a raise with a documented exception
Given a function that raises an exception and whose docstring mentions that exception, `extract_signals` SHALL produce at least one signal whose `side_effect_type` is `ErrorReturn` or `ErrorSignal` (from the `docstring` and/or other extractors matching the error effect).

#### Scenario: documented raise yields an error-typed signal
- **WHEN** `extract_signals` runs over a function that contains a `raise` and whose docstring mentions the raised exception
- **THEN** at least one emitted signal has `side_effect_type` equal to `ErrorReturn` or `ErrorSignal`
