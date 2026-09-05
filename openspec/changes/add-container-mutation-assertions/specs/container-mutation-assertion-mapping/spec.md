# Spec: Container Mutation Assertion Mapping

## ADDED Requirements

### Requirement: Paired target result provenance
The test-mapping analyzer SHALL recognize container-state evidence only when the asserted expression is statically traceable to a direct invocation of the paired target in the same test function. The trace SHALL support direct use of the target call and a target call assigned to a simple local name. Unsupported, ambiguous, or unrelated provenance SHALL retain the existing assertion mapping.

#### Scenario: Simple target result binding
- **WHEN** a test assigns a direct call to the paired target to a simple local name and asserts a qualifying projection of that name
- **THEN** the analyzer records internal container-state evidence for the assertion

#### Scenario: Direct target call in assertion
- **WHEN** a qualifying container-state projection contains a direct call to the paired target
- **THEN** the analyzer records internal container-state evidence without requiring an assigned name

#### Scenario: Unrelated container
- **WHEN** an assertion observes a container that is not derived from the paired target call
- **THEN** the analyzer does not record container-state evidence for the paired target

#### Scenario: Unsupported provenance
- **WHEN** a value reaches an assertion through a helper call, attribute assignment, mutable alias chain, tuple unpacking, nested function, control-flow merge, or another unsupported AST form
- **THEN** the analyzer preserves the assertion's existing side-effect mapping rather than inferring target-result provenance

### Requirement: Container-state observation forms
The analyzer SHALL recognize membership against the traced result, `len()` of the traced result, subscripts or slices of the traced result, and iteration or comprehensions over the traced result as container-state observations. Whole-result equality or identity and arbitrary method calls SHALL NOT qualify solely by referencing the traced result.

#### Scenario: Membership observation
- **WHEN** the traced target result is the container operand of a membership assertion
- **THEN** the assertion qualifies as a container-state observation

#### Scenario: Size observation
- **WHEN** an assertion compares `len()` of the traced target result
- **THEN** the assertion qualifies as a container-state observation

#### Scenario: Indexed or sliced observation
- **WHEN** an assertion observes an item or slice of the traced target result
- **THEN** the assertion qualifies as a container-state observation

#### Scenario: Iteration projection observation
- **WHEN** an assertion iterates over the traced target result or compares a comprehension derived from it
- **THEN** the assertion qualifies as a container-state observation

#### Scenario: Whole-result equality
- **WHEN** an assertion compares the traced target result as a whole without a qualifying state projection
- **THEN** the assertion retains ordinary return-value mapping

#### Scenario: Arbitrary result method
- **WHEN** an assertion calls an arbitrary method on the traced target result
- **THEN** the method call alone does not qualify as container-state evidence

### Requirement: Evidence-based effect mapping
For a non-error assertion with qualifying container-state evidence, the analyzer SHALL map the assertion to `ContainerMutation` when the paired target reports at least one `ContainerMutation` effect. The analyzer SHALL emit no more than one mapping row for that assertion and target pair. If either the evidence or target effect is absent, the analyzer SHALL preserve all existing error, value, P0, generator, generic, unknown-type, and fallback precedence behavior.

#### Scenario: Mutation effect and state evidence coexist
- **WHEN** a non-error assertion has qualifying target-result container-state evidence and the paired target reports `ContainerMutation`
- **THEN** the analyzer maps the assertion row to `ContainerMutation`

#### Scenario: Target has no mutation effect
- **WHEN** an assertion has qualifying container-state evidence but the paired target does not report `ContainerMutation`
- **THEN** the analyzer applies the existing mapping precedence for that assertion type

#### Scenario: Mutation effect lacks state evidence
- **WHEN** the paired target reports `ContainerMutation` but the assertion lacks qualifying target-result container-state evidence
- **THEN** the analyzer applies the existing mapping precedence for that assertion type

#### Scenario: Several mutation effects share one type
- **WHEN** the paired target reports more than one `ContainerMutation` effect and one assertion qualifies
- **THEN** the analyzer emits one row with the canonical `ContainerMutation` side-effect type and does not invent effect identifiers

#### Scenario: Error assertion remains unchanged
- **WHEN** an error assertion is paired with a target that reports `ContainerMutation`
- **THEN** the analyzer preserves the existing error-effect precedence and fallback behavior

### Requirement: Protocol and determinism preservation
The analyzer MUST preserve the Gaze analyzer protocol v1.1.0 `test_mapping` request and response contract. Every serialized mapping row SHALL retain exactly the established eight fields and one of the six established assertion types. Identical input SHALL produce byte-identical output across repeated runs and hash seeds.

#### Scenario: Mapping row serialization
- **WHEN** internal container-state evidence changes an assertion's selected side-effect type
- **THEN** the serialized row contains only `test_function`, `test_file`, `assertion_location`, `assertion_type`, `target_function`, `target_package`, `side_effect_type`, and `confidence`

#### Scenario: Assertion type remains stable
- **WHEN** an assertion maps to `ContainerMutation`
- **THEN** its serialized assertion type remains its existing `equality`, `comparison`, `identity`, `membership`, `error_check`, or `generic` classification

#### Scenario: Hash-seed determinism
- **WHEN** the same project is analyzed in separate processes with different `PYTHONHASHSEED` values
- **THEN** the complete JSON-RPC responses are byte-identical and equal an explicit expected response, including row values and established row order

### Requirement: Static and bounded analysis
Container-state provenance and observation analysis MUST use the parsed Python AST without importing or executing analyzed source or tests. The analysis SHALL remain within the existing function-scope and AST-depth boundaries and SHALL degrade to existing mapping behavior when those boundaries prevent a confident trace.

#### Scenario: Untrusted test source
- **WHEN** test source contains import-time code, subprocess calls, file writes, `exec`, or `eval`
- **THEN** the analyzer inspects syntax without executing any of those operations

#### Scenario: AST depth boundary
- **WHEN** a synthetic in-memory AST or targeted traversal failure drives candidate provenance or state observation beyond the configured AST depth limit
- **THEN** the analyzer completes safely and preserves existing mapping behavior for that assertion

#### Scenario: Unsupported AST form
- **WHEN** provenance or observation analysis encounters a syntactically valid AST form outside the supported direct-call and simple-name model
- **THEN** the analyzer preserves existing mapping behavior for that assertion without propagating an analysis failure

### Requirement: Observable container contract coverage
Repository tests added or refined by this change SHALL assert caller-observable container outcomes rather than internal mutator calls. They SHALL cover representative ordering, membership, size, indexed placement, or removal outcomes exposed by affected return values, and SHALL leave inaccessible local bookkeeping unclaimed.

#### Scenario: Returned mutation-built sequence
- **WHEN** a production function returns a sequence whose ordering or contents are part of its caller-visible behavior
- **THEN** its focused test asserts that observable ordering or content through a qualifying container-state projection against an explicit expected value derived from known inputs, not by re-invoking the target or checking only a self-derived property

#### Scenario: Internal mutation is inaccessible
- **WHEN** a detected container mutation changes only local bookkeeping that is not exposed through the target result
- **THEN** the test suite does not add an implementation-coupled assertion merely to mark the effect covered

### Requirement: Conformance and quality regression verification
The implementation SHALL include isolated assertion-analysis, mapping, pipeline, JSON-RPC, determinism, depth, and static-safety tests. Validation MUST run the repository's unchanged CI commands and SHALL evaluate the workspace-local Gaze quality report by unique `ContainerMutation` effect identity or source location rather than repeated test-pair rows.

#### Scenario: CI parity validation
- **WHEN** implementation is complete
- **THEN** `uv sync --locked`, Ruff lint, Ruff format check, strict mypy, and pytest with the protected 85 percent coverage floor all pass without lowering a quality gate

#### Scenario: Quality report comparison
- **WHEN** the before and after workspace-local Gaze quality reports are compared
- **THEN** each qualifying `(owning target, ContainerMutation)` group is credited by a provenance-qualified mapping at protocol type-level granularity, same-target/same-type effect identities are attributed only to the canonical type the row schema exposes, and unrelated or inaccessible mutation effects remain visible
