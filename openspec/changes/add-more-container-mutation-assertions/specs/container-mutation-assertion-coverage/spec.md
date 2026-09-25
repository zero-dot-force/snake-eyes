# Spec: Container Mutation Assertion Coverage

## ADDED Requirements

### Requirement: Observable target enumeration
The change SHALL enumerate the observable `ContainerMutation` call sites remaining after the prior change by re-running the workspace-local Gaze quality command and grouping the repeated test-pair gaps by owning target function and source location. The enumeration SHALL distinguish observable mutations (the returned value exposes the mutated container) from inaccessible mutations (local bookkeeping not exposed through the result).

#### Scenario: Post-baseline survey
- **WHEN** the workspace-local Gaze quality command is run against the current tree
- **THEN** the report's contractual `ContainerMutation` gaps are grouped into an explicit table keyed by owning target and source location, each classified observable or inaccessible

#### Scenario: Observable targets identified
- **WHEN** a gap belongs to a target whose returned value exposes the mutated container
- **THEN** the gap is classified observable and assigned to a specific test call site that exercises the target

#### Scenario: Inaccessible targets excluded
- **WHEN** a gap belongs to a target whose mutation updates only internal bookkeeping or invalidation state
- **THEN** the gap is classified inaccessible and excluded from assertion additions

### Requirement: Caller-observable assertion additions
Tests added or refined by this change SHALL assert caller-observable container outcomes through a qualifying container-state projection (membership, `len()`, subscript, slice, iteration, or comprehension) against an explicit expected value derived from known inputs. A whole-result equality assertion SHALL NOT be added or counted as container-state coverage when a qualifying projection is required to close the gap.

#### Scenario: Ordering assertion
- **WHEN** a target returns a sorted container and its test observes only an unsorted whole-result equality
- **THEN** the test gains an ordering assertion derived from known inputs, such as asserting the projected sequence of keys or names

#### Scenario: Membership or size assertion
- **WHEN** a target returns a deduplicated or aggregated container and its test observes only whole-result equality
- **THEN** the test gains a membership, `len()`, or indexed-content assertion against an explicit expected value

#### Scenario: Serialized content assertion
- **WHEN** a target returns a serialized list of records and its test does not yet observe the container state
- **THEN** the test gains a projection or indexed-content assertion that verifies a caller-visible contract

### Requirement: Inaccessible and ambiguous effects remain unclaimed
The change SHALL NOT add an implementation-coupled assertion merely to mark an inaccessible mutation covered. For ambiguous `ContainerMutation` identities, the change SHALL add an assertion only when the mutated container is genuinely caller-observable through the target result; otherwise the effect SHALL remain visible in the Gaze quality report.

#### Scenario: Inaccessible bookkeeping left unclaimed
- **WHEN** a detected container mutation updates only internal detector, alias-tracking, or constructor-invalidation state
- **THEN** no test references that internal state and no assertion is added for the effect

#### Scenario: Ambiguous identity without observable result
- **WHEN** an ambiguous `ContainerMutation` identity cannot be traced to a caller-observable container through the target result
- **THEN** the effect remains reported as a gap and receives no fabricated coverage

### Requirement: Quality regression verification
The implementation SHALL verify closure by comparing before and after workspace-local Gaze quality reports by unique `(effect_type, source_file, source_line)` identity rather than repeated test-pair rows. It SHALL also run the repository's unchanged CI commands and SHALL NOT lower any protected quality or governance gate.

#### Scenario: Repeated-row reduction
- **WHEN** container-state assertions are added to additional call sites of observable targets
- **THEN** the count of repeated contractual `ContainerMutation` test-pair gap rows decreases without removing any unique effect identity

#### Scenario: Unique identity stability
- **WHEN** the before and after reports are compared by unique effect identity
- **THEN** no inaccessible identity disappears and no new unique contractual identity appears

#### Scenario: CI parity
- **WHEN** the test changes are complete
- **THEN** `uv sync --locked`, Ruff lint, Ruff format check, strict mypy, and pytest with the protected 85 percent coverage floor all pass without lowering a quality gate
