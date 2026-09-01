## MODIFIED Requirements

### Requirement: Value-assertion effect inference

For an `equality`, `comparison`, `identity`, or `membership` assertion, `side_effect_type` SHALL be `ReturnValue` if the target has a `ReturnValue` effect; otherwise the target's first P0 effect; otherwise `GeneratorYield` if the target has a `GeneratorYield` effect; otherwise `AsyncGeneratorYield` if the target has an `AsyncGeneratorYield` effect; otherwise `ReturnValue` as a fallback.

#### Scenario: Target returns a value
- **WHEN** the assertion type is `equality` and the target's effects include `ReturnValue`
- **THEN** `side_effect_type` is `ReturnValue`

#### Scenario: Target has no ReturnValue but has a P0 effect
- **WHEN** the assertion type is `comparison`, the target has no `ReturnValue`, but has at least one P0 effect
- **THEN** `side_effect_type` is the target's first P0 effect

#### Scenario: Target is a generator with no ReturnValue or P0 effect
- **WHEN** the assertion type is `equality` and the target has no `ReturnValue` and no P0 effect, but has a `GeneratorYield` effect
- **THEN** `side_effect_type` is `GeneratorYield`

#### Scenario: Target is an async generator with no ReturnValue or P0 effect
- **WHEN** the assertion type is `membership` and the target has no `ReturnValue`, no P0 effect, and no `GeneratorYield`, but has an `AsyncGeneratorYield` effect
- **THEN** `side_effect_type` is `AsyncGeneratorYield`

#### Scenario: Target has no usable effect
- **WHEN** the assertion type is `membership` and the target has no `ReturnValue`, no P0 effect, no `GeneratorYield`, and no `AsyncGeneratorYield`
- **THEN** `side_effect_type` falls back to `ReturnValue`

#### Scenario: Target has both ReturnValue and GeneratorYield
- **WHEN** the assertion type is `identity` and the target's effects include both `ReturnValue` and `GeneratorYield`
- **THEN** `side_effect_type` is `ReturnValue` (ReturnValue takes precedence)
