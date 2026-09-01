## ADDED Requirements

### Requirement: Effect-type inference consumes detector output

For each assertion row, the mapping module SHALL infer `side_effect_type` from the assertion type together with the target function's side effects as reported by the detector (`FunctionRecord.side_effects`). It SHALL NOT re-parse the target function ad hoc. "First P0 effect" means the target's first side effect, in detector order, whose tier in `TIER_MAP` is `P0`.

#### Scenario: Inference reads detected effects, not a fresh parse
- **WHEN** inferring `side_effect_type` for a row whose target function was analyzed
- **THEN** the inference uses that target's `side_effects` from the detector output rather than re-parsing the source

### Requirement: Error-check effect inference

For an `error_check` assertion, `side_effect_type` SHALL be `ErrorReturn` if the target has an `ErrorReturn` effect; otherwise `ErrorSignal` if the target has an `ErrorSignal` effect; otherwise `ErrorReturn` as a fallback.

#### Scenario: Target has ErrorReturn
- **WHEN** the assertion type is `error_check` and the target's effects include `ErrorReturn`
- **THEN** `side_effect_type` is `ErrorReturn`

#### Scenario: Target has ErrorSignal but not ErrorReturn
- **WHEN** the assertion type is `error_check`, the target has no `ErrorReturn`, but has `ErrorSignal`
- **THEN** `side_effect_type` is `ErrorSignal`

#### Scenario: Target has neither error effect
- **WHEN** the assertion type is `error_check` and the target has neither `ErrorReturn` nor `ErrorSignal`
- **THEN** `side_effect_type` falls back to `ErrorReturn`

### Requirement: Value-assertion effect inference

For an `equality`, `comparison`, `identity`, or `membership` assertion, `side_effect_type` SHALL be `ReturnValue` if the target has a `ReturnValue` effect; otherwise the target's first P0 effect; otherwise `ReturnValue` as a fallback.

#### Scenario: Target returns a value
- **WHEN** the assertion type is `equality` and the target's effects include `ReturnValue`
- **THEN** `side_effect_type` is `ReturnValue`

#### Scenario: Target has no ReturnValue but has a P0 effect
- **WHEN** the assertion type is `comparison`, the target has no `ReturnValue`, but has at least one P0 effect
- **THEN** `side_effect_type` is the target's first P0 effect

#### Scenario: Target has no usable effect
- **WHEN** the assertion type is `membership` and the target has no `ReturnValue` and no P0 effect
- **THEN** `side_effect_type` falls back to `ReturnValue`

### Requirement: Generic effect inference

For a `generic` assertion, `side_effect_type` SHALL be the target's first side effect if the target has any; otherwise `ReturnValue`.

#### Scenario: Target has at least one effect
- **WHEN** the assertion type is `generic` and the target has one or more side effects
- **THEN** `side_effect_type` is the target's first side effect

#### Scenario: Target has no effects
- **WHEN** the assertion type is `generic` and the target has no side effects
- **THEN** `side_effect_type` falls back to `ReturnValue`
