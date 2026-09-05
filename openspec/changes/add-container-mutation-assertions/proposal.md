# Proposal: Container Mutation Assertion Mapping

## Why

Issue #19 remains actionable now that snake-eyes #18 and Gaze #246 are closed. A workspace-local quality run reports 35 unique `ContainerMutation` effects across 334 repeated test-pair occurrences. The scoped baseline, filtered independently for contractual effects and qualifying test pairings, contains 24 unique gaps across 330 pairings; these figures are not an arithmetic partition because the unique-effect and repeated-pair dimensions use different filters. Adding assertions alone cannot close the scoped gaps: the current test-mapping pipeline maps equality, comparison, identity, and membership assertions to `ReturnValue` whenever that effect is present. The analyzer needs to distinguish assertions about returned container state from ordinary return-value assertions before targeted test additions can produce truthful quality mappings.

## What Changes

- Preserve ordinary value-assertion mapping to `ReturnValue` while using Python AST evidence to recognize assertions that observe container state derived from a paired target call.
- Map qualifying container-state assertions to a detected `ContainerMutation` effect without changing the Gaze `test_mapping` response shape or the six protocol assertion types.
- Add focused assertions for observable container behavior such as ordering, membership, size, and removal where production functions expose the mutated container through their result.
- Leave purely local, unobservable implementation mutations unasserted rather than adding brittle tests for incidental behavior.
- Add unit, pipeline, JSON-RPC, determinism, safety, and quality-report regression coverage for the new mapping behavior.

## Capabilities

### New Capabilities

- `container-mutation-assertion-mapping`: Statically associate observable container-state assertions with `ContainerMutation` effects while retaining `ReturnValue` mapping for ordinary result assertions.

### Modified Capabilities

None.

## Impact

- Affected implementation: `src/snake_eyes/quality/assertions.py`, `src/snake_eyes/quality/mapping.py`, `src/snake_eyes/quality/pipeline.py`, and the focused `src/snake_eyes/quality/_provenance.py` (import identity, shadowing, mutation invalidation, and paired-target result tracing).
- Affected tests: test-mapping conformance tests and focused tests for functions whose returned state exposes `.sort()`, `.extend()`, or `.append()` behavior; inaccessible `.pop()` bookkeeping remains intentionally unclaimed.
- Protocol impact: no method, capability, request, response-field, assertion-type, or side-effect-taxonomy changes; only more accurate `side_effect_type` values in existing mapping rows.
- Dependencies: no new runtime or development dependencies.
- Validation: the exact CI workflow gates remain unchanged, and a workspace-local Gaze quality run is required to verify that qualifying `ContainerMutation` gaps close without suppressing effects or relabeling incidental mutations as covered.

## Constitution Check

- **I. Protocol Fidelity - PASS**: The existing Gaze protocol v1.1.0 method and row schema remain unchanged, with deterministic mapping output.
- **II. Detection Accuracy - PASS**: Mapping requires static evidence that an assertion observes returned container state; unobservable local mutations remain gaps rather than receiving fabricated coverage.
- **III. Python-Native Analysis - PASS**: The change uses Python `ast` nodes and existing analyzer records instead of reimplementing Python semantics.
- **IV. Testability - PASS**: The scope includes isolated assertion-analysis tests, pipeline and JSON-RPC conformance tests, determinism checks, and quality-report regression validation.
- **V. Analysis Safety - PASS**: All provenance and assertion analysis is static; analyzed source and tests are never imported or executed.
