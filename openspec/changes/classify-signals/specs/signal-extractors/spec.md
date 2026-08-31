## ADDED Requirements

### Requirement: signal extractor package and source identifiers
The system SHALL provide a `src/snake_eyes/signals/` package containing five signal extractors reconstructed from gaze-py's documented `src/gaze_py/classify/signals/` behavior: `interface.py`, `visibility.py`, `caller.py`, `naming.py`, and `docstring.py`. Each extractor SHALL emit its signal `source` as exactly one of the five protocol v1.1.0 strings — `interface`, `visibility`, `caller_count`, `naming_convention`, `docstring` — and SHALL NOT introduce any other `source` value (no sixth extractor, no `type_annotation`). Each extractor SHALL return either a single raw signal (carrying `weight` and a short, non-empty `reasoning`) or `None` when no rule applies.

#### Scenario: only the five protocol sources are produced
- **WHEN** any extractor emits a signal
- **THEN** its `source` is one of `interface`, `visibility`, `caller_count`, `naming_convention`, `docstring` and no other value

#### Scenario: extractor returns None when no rule applies
- **WHEN** an extractor is given inputs that match none of its rules
- **THEN** it returns `None` and no signal is produced

### Requirement: interface extractor detects ABC and Protocol bases
The `interface` extractor SHALL emit an `interface` signal for a method defined on a class whose bases include an abstract base class (`abc.ABC`, a metaclass of `abc.ABCMeta`) or `typing.Protocol`. The emitted weight SHALL be the gaze-py interface weight (the documented gaze-py value, expected to be `30`). A method on a class with no interface base SHALL produce no `interface` signal.

#### Scenario: ABC subclass method fires interface signal
- **WHEN** a method is defined on a class that subclasses `abc.ABC`
- **THEN** an `interface` signal is emitted with `source == "interface"` and `weight == 30`

#### Scenario: Protocol subclass method fires interface signal
- **WHEN** a method is defined on a class that subclasses `typing.Protocol`
- **THEN** an `interface` signal is emitted with `source == "interface"`

#### Scenario: plain class method produces no interface signal
- **WHEN** a method is defined on a class with no ABC or Protocol base
- **THEN** the `interface` extractor returns `None` and no `interface` signal is emitted

### Requirement: visibility extractor distinguishes public and private names
The `visibility` extractor SHALL emit a `visibility` signal based on the function's public/private naming convention (leading-underscore private vs. public) and `__all__` membership, using gaze-py's documented weights. A public function and a private (leading-underscore) function SHALL produce distinguishable `visibility` outcomes (different weight, or one emits while the other does not), matching gaze-py's documented behavior. The extractor SHALL NOT redefine the gaze-py weights.

#### Scenario: public and private names differ in visibility signal
- **WHEN** the extractor runs for a public function `def public_fn()` and for a private function `def _private()`
- **THEN** the two `visibility` results differ per gaze-py's documented behavior (either the private function's weight is lower, or one emits a signal while the other returns `None`), without any weight value being changed

### Requirement: caller_count extractor maps inbound counts to gaze-py buckets
The `caller` extractor SHALL accept an inbound caller count and emit a `caller_count` signal whose weight is the gaze-py weight for that count's bucket. The bucket boundaries and their weights SHALL match gaze-py's documented values exactly; this change SHALL NOT retune them. When gaze-py emits no signal for a given count (e.g. a zero-caller count), the extractor SHALL return `None` for that count.

#### Scenario: distinct counts map to their gaze-py bucket weights
- **WHEN** the `caller` extractor is invoked with inbound counts of `0`, `5`, and `20`
- **THEN** each invocation returns the gaze-py `caller_count` weight for that count's bucket (or `None` where gaze-py emits no signal), with the gaze-py bucket boundaries and weights unchanged

### Requirement: naming_convention extractor matches function name against effect type
The `naming` extractor SHALL emit a `naming_convention` signal when the function name's convention agrees with the effect type (e.g. a `get_`/`is_`/`has_` prefix agreeing with `ReturnValue`), and SHALL preserve gaze-py's negative-agreement outcomes (a name gaze-py treats as contradicting the effect stays negative). Weights SHALL match gaze-py's documented values.

#### Scenario: getter name agrees with ReturnValue
- **WHEN** the extractor runs for a function named `get_foo` with effect type `ReturnValue`
- **THEN** a `naming_convention` signal is emitted reflecting positive agreement, per the gaze-py weight

#### Scenario: contradicting name stays negative
- **WHEN** the extractor runs for a function whose name gaze-py treats as contradicting the effect type
- **THEN** the `naming_convention` result remains the negative-agreement outcome defined by gaze-py, unchanged

### Requirement: docstring extractor matches docstring keywords against effect type
The `docstring` extractor SHALL emit a `docstring` signal when the function docstring contains keywords that agree with the effect type (e.g. a docstring mentioning "returns" agreeing with `ReturnValue`, or naming an exception agreeing with `ErrorReturn`/`ErrorSignal`), using gaze-py's documented weights. A function with no docstring, or a docstring with no matching keyword, SHALL produce no `docstring` signal.

#### Scenario: docstring mentioning returns agrees with ReturnValue
- **WHEN** the extractor runs for a function whose docstring contains "returns" with effect type `ReturnValue`
- **THEN** a `docstring` signal is emitted with `source == "docstring"`

#### Scenario: absent docstring produces no signal
- **WHEN** the extractor runs for a function with no docstring
- **THEN** the `docstring` extractor returns `None`

### Requirement: gaze-py signal weights preserved exactly
The extractors SHALL preserve the gaze-py signal weights exactly as documented. These weights are governance-gate values consumed by Gaze's classification formula; this change SHALL NOT retune, clamp, or otherwise modify them, and tests SHALL assert the gaze-py weights rather than redefine them.

#### Scenario: interface weight is the gaze-py value
- **WHEN** the `interface` extractor emits a signal
- **THEN** its `weight` is `30`, the gaze-py interface weight, and no test alters that value

### Requirement: new Python effect types mapped to closest branch, never KeyError
For extractors that switch on effect type (`naming`, `docstring`), the system SHALL handle the 10 Python-specific `SideEffectType` values added beyond gaze-py's original 38 (`ErrorSignal`, `GeneratorYield`, `StreamOutput`, `AsyncGeneratorYield`, `MetaprogrammingMutation`, `DescriptorEffect`, `ResourceManagement`, `ImportSideEffect`, `MonkeyPatch`, `ContainerMutation`) plus the gaze-py-original `ClosureCaptureMutation`, by routing each to the closest existing gaze-py branch (`GeneratorYield`/`StreamOutput`/`AsyncGeneratorYield` like `ReturnValue`; `MonkeyPatch` like `ReflectionMutation`; `ContainerMutation` like the P1 `SliceMutation`/`MapMutation` branch; `DescriptorEffect`/`ResourceManagement`/`MetaprogrammingMutation`/`ImportSideEffect` like the closest P2/mutation branch; `ClosureCaptureMutation` like the P4 `ReflectionMutation` branch; `ErrorSignal` like the error branch). An effect type that matches no keyword or prefix SHALL cause the extractor to return `None`. The extractors SHALL NOT raise `KeyError` (or any exception) on an unrecognized effect type.

#### Scenario: new effect type routes to closest branch
- **WHEN** an extractor that switches on effect type is given `GeneratorYield`
- **THEN** it returns the same signal structure (equal `weight` and semantically equivalent `reasoning`) as it does for `ReturnValue`, its closest branch, and does not raise

#### Scenario: unmatched effect type returns None not KeyError
- **WHEN** an extractor is given an effect type for which no keyword or prefix applies
- **THEN** it returns `None` and raises no exception

### Requirement: extractors assign no classification label
The extractor modules SHALL NOT compute or assign any classification label. The strings `contractual`, `incidental`, and `ambiguous` SHALL NOT appear as assigned output values anywhere in `src/snake_eyes/signals/`; they MAY appear only in comments that document the prohibition.

#### Scenario: no classification label emitted by extractors
- **WHEN** any extractor emits a signal
- **THEN** the signal carries `weight`, `source`, and `reasoning` but no `contractual`/`incidental`/`ambiguous` label

#### Scenario: production code contains no assigned classification labels
- **WHEN** `src/snake_eyes/signals/` production code is scanned for `contractual`, `incidental`, or `ambiguous` used as assigned values
- **THEN** none is found (occurrences, if any, are only in comments forbidding them)

### Requirement: gaze-py provenance retained on reconstructed extractors
Each reconstructed `signals/*.py` extractor SHALL retain a gaze-py copyright header (Matt Peter, Apache 2.0) AND SHALL add an Apache-2.0 §4(b) change notice identifying zero-dot-force as the modifier (e.g. `# Modified 2026 by zero-dot-force: reconstructed from documented gaze-py behavior; adapted to snake_eyes SideEffectType; new Python effect types mapped.`).

#### Scenario: provenance header present on a reconstructed extractor
- **WHEN** `src/snake_eyes/signals/interface.py` is inspected
- **THEN** it contains the gaze-py Apache 2.0 provenance header and an Apache-2.0 §4(b) change notice identifying zero-dot-force
