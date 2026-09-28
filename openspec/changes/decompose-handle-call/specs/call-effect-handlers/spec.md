## Relationship to Prior Spec

This spec does not change any detector requirement. It adds a structural
requirement over the existing detector spec
([detector spec](../../../analysis-methods/specs/detector/spec.md)):
`_handle_call` SHALL be decomposed into single-responsibility per-effect
handlers while preserving the exact effect output that the detector spec
mandates. The behavioral requirements — effect detection, ordering,
determinism, and ambiguity reporting — are unchanged.

## Coverage Strategy

Tests are unit-level, exercising the decomposed handlers through the
detector's public `analyze_source` entry point with inline source strings,
asserting the complete effect list (type, description, location, target,
detail) rather than mere membership. One positive test per handler, plus
negative and ordering regressions for the order-sensitive co-emit rules.
The existing golden tests (`test_p0_golden_full_equality`,
`test_p3_positive_effects`, and the issue-#18 ambiguity suite) serve as the
behavior-preservation regression harness and MUST pass unchanged. The
existing 85% coverage gate applies.

## ADDED Requirements

### Requirement: Call dispatch is decomposed into per-effect handlers

The `_EffectVisitor` SHALL resolve call expressions through an ordered
sequence of single-responsibility handler methods rather than a single
monolithic `if/elif` waterfall. Each handler SHALL have a well-defined
concern (e.g. exit calls, print, reflection, metaprogramming, logging,
filesystem, container mutation) and SHALL return whether it consumed the
call. `_handle_call` SHALL iterate the handlers in a fixed, deterministic
order and stop at the first handler that consumes the call.

#### Scenario: A handler consumes its call

- **WHEN** a call expression matches a specific effect rule (e.g.
  `sys.exit(0)`)
- **THEN** exactly the handler responsible for that rule SHALL emit its
  effects and consume the call, and no subsequent handler SHALL execute
  for that call

#### Scenario: No handler matches a call

- **WHEN** a call expression matches no effect-specific handler
- **THEN** the name-call fallback SHALL execute (pure-builtin, local, and
  module resolution, then `CallbackInvocation` ambiguous)

### Requirement: Decomposition preserves effect output

Decomposing `_handle_call` SHALL NOT change the set, order, description,
target, location, or detail of any emitted effect. Every emitted
`SideEffectType`, its ordering within a function record, and its
`(description, location, target, detail)` content SHALL remain identical
to the pre-refactor output.

#### Scenario: Golden output is unchanged

- **GIVEN** the existing detector fixtures (`p0.py`, `p1.py`, `p2.py`,
  `p3.py`, `pure.py`, `container_local.py`, `ambiguous.py`)
- **WHEN** the detector analyzes them after decomposition
- **THEN** the emitted effect lists SHALL match the pre-refactor golden
  expectations exactly

#### Scenario: Order-sensitive co-emit is preserved

- **GIVEN** a write-mode `open()` whose handle is later `.write()`-called
- **WHEN** the detector analyzes the function after decomposition
- **THEN** `StreamOutput` SHALL be emitted and `FileSystemWrite` SHALL be
  co-emitted only for write-mode opens, in the same order as before

#### Scenario: Container mutation precedence is preserved

- **GIVEN** a call to a container-mutating method on a receiver, a
  parameter, or an unclassified name
- **WHEN** the detector analyzes the function after decomposition
- **THEN** `ReceiverMutation`, `PointerArgMutation`, or
  `ContainerMutation` SHALL be emitted per the same precedence as before

### Requirement: The complexity suppression is removed

After decomposition, no single handler method SHALL require a `C901`
(complexity) lint suppression. The `# noqa: C901 (complex)` marker on
`_handle_call` SHALL be removed.

#### Scenario: No C901 suppression remains

- **WHEN** `ruff check src/ tests/` runs on the decomposed detector
- **THEN** no `C901` suppression directive SHALL be present on any
  handler method and linting SHALL pass
