# Design: Container Mutation Assertion Mapping

## Context

The `test_mapping` pipeline currently collects only an assertion's broad protocol type and source location. `infer_side_effect_type` therefore has no expression or data-flow evidence and maps every equality, comparison, identity, or membership assertion to `ReturnValue` when the paired target has that effect. From the proposal's full workspace result of 35 unique effects across 334 repeated occurrences, independent contract and pairing filters produce the scoped baseline of 24 unique contractual `ContainerMutation` gaps across 330 test pairings; the two dimensions are not an arithmetic partition. Many affected functions return the container they build, so their tests already verify the final value, but the analyzer cannot distinguish a normal return assertion from a focused observation of container state.

The implementation must remain static, deterministic, bounded by existing AST safety limits, and compatible with the Gaze analyzer protocol v1.1.0. The eight-key `test_mapping` row and the six existing `assertion_type` values are external contracts. Side-effect detection and classification are outside this change; the design only improves assertion-to-effect mapping and adds meaningful tests where mutation-built state is observable.

## Goals / Non-Goals

**Goals:**

- Recognize container-state observations that are statically traceable to the result of the paired target call.
- Map those observations to `ContainerMutation` when the paired target reports that effect.
- Preserve current effect precedence for assertions without qualifying container-state evidence.
- Add targeted behavioral assertions for returned ordering, membership, size, indexing, or removal outcomes.
- Reduce genuine `ContainerMutation` quality gaps without claiming coverage for inaccessible local state.
- Keep output byte-stable across hash seeds and preserve all existing safety behavior.

**Non-Goals:**

- Changing side-effect detection, `classify_signals`, confidence scoring, or Gaze's P1 state-mutation taxonomy tier.
- Changing JSON-RPC methods, fields, assertion-type strings, or Gaze's universal quality algorithm.
- Performing general-purpose Python data-flow, symbolic execution, type inference, or runtime test execution.
- Adding assertions solely to increase a metric when they do not strengthen an observable contract.
- Mapping internal constructor bookkeeping or other containers that tests cannot observe through target results.

## Decisions

### 1. Carry internal AST observation evidence, not new protocol fields

The assertion collector will retain enough internal evidence from each assertion expression to decide whether it observes container state. The pipeline will also identify simple names bound directly from a call to the paired target within the same test function. Qualifying observations are limited to deterministic syntax such as:

- membership where the traced result is the container operand;
- `len()` of the traced result;
- subscripts or slices of the traced result;
- iteration or comprehensions over the traced result, including projections used to verify ordering.

Whole-result equality or identity remains an ordinary return-value assertion. Arbitrary method calls and names not traced to the paired target do not qualify.

This evidence remains inside `AssertionInfo` and pipeline calls. Serialized rows retain exactly the existing keys and broad assertion types.

The internal handoff has three owners. `assertions.py` records an immutable observation descriptor on `AssertionInfo`, including the supported observation kind and candidate expression; new fields have defaults so existing construction remains compatible. `pipeline.py` resolves that descriptor against direct target calls and simple local bindings for the selected pair, then passes an `observes_container_state` boolean to `infer_side_effect_type`. `mapping.py` consumes only the assertion type, target effects, and that boolean; it does not traverse AST nodes. This preserves each module's existing responsibility while keeping implementation-only evidence off the wire.

**Alternative considered:** Add `container_state` as a seventh assertion type or add provenance fields to JSON-RPC rows. Rejected because Gaze protocol v1.1.0 already defines the row contract, and no new wire data is needed to choose an existing canonical effect type.

**Alternative considered:** Treat all membership and sequence equality assertions as container mutation coverage. Rejected because assertion shape alone does not prove that the assertion observes the paired target or any mutation.

### 2. Make container-state evidence an explicit mapping override

`infer_side_effect_type` will accept the internal observation evidence. When the assertion observes a traced target result and the paired target contains `ContainerMutation`, the function will return `ContainerMutation`. Otherwise, the existing chains remain unchanged: error assertions prefer error effects, ordinary value assertions prefer `ReturnValue` and then other P0 effects, and generic assertions use their existing fallback.

This keeps the change monotonic and avoids reclassifying unrelated assertions. Multiple target effects of the same canonical type continue to use the protocol's type-level mapping; Snake Eyes will not invent effect IDs that the row schema cannot carry.

**Alternative considered:** Change all result assertions from `ReturnValue` to `ContainerMutation` whenever both effects exist. Rejected because it would create false coverage for incidental mutations and regress valid return-value coverage.

**Alternative considered:** Emit two rows from one assertion, one for each effect. Rejected because one assertion does not necessarily verify two contracts and duplicate rows would change established mapping cardinality semantics.

### 3. Trace only direct, local target-result bindings

The static trace will cover direct calls in the paired test, including a target call assigned to a simple name and a target call used directly inside an assertion. Evidence will not cross helper calls, nested functions, attributes, mutable alias chains, or control-flow merges. Existing pairing selects the target; the trace only confirms that the asserted expression derives from that selected target.

This boundary is intentionally conservative. Unsupported or ambiguous provenance keeps the existing mapping instead of guessing.

**Alternative considered:** Use Astroid inference or build SSA for test expressions. Rejected as disproportionate to the focused mapping problem and more likely to introduce performance, cache-isolation, and ambiguity risks.

### 4. Add assertions only at observable contract boundaries

Targeted test updates will focus on public results that expose container-built behavior, such as deterministic ordering from `compute_complexity`, `parse_coverage`, `analyze_source`, `analyze_path`, and `extract_signals`, or contents from serialization and discovery helpers. Assertions will verify a behavior a caller can observe, not the fact that a particular internal method such as `.append()` was used.

Existing assertions will be reused when they already express a qualifying state observation. New assertions must add a distinct contract check, such as ordering, membership, size, indexed placement, or absence after removal. Constructor-local bookkeeping and other inaccessible state remain out of scope.

**Alternative considered:** Add one assertion for every repeated Gaze gap row. Rejected because the rows repeat effects across pairings, would create duplicate low-value tests, and would couple the suite to implementation details.

### 5. Verify both protocol conformance and quality behavior

Implementation tests will cover collector evidence, mapping precedence, false-positive boundaries, pipeline integration, exact JSON-RPC row keys, hash-seed determinism, and static-only operation. Determinism fixtures will also assert the complete expected row values and established row order so wrong-but-stable output cannot pass through byte comparison alone. A workspace-local `gaze quality --analyzer snake-eyes --language python --format json .` run will be captured before and after the change. The comparison will extract unique `(effect_type, source_file, source_line)` identities, require every pre-classified qualifying gap to close, and require unrelated or inaccessible mutation gaps to remain visible without new regressions.

The quality run is a validation step, not a CI gate added by this change. Existing CI remains authoritative.

## Risks / Trade-offs

- **[Risk] Conservative tracing misses assertions routed through helpers or aliases**: Preserve existing mapping for unsupported provenance and add only direct, readable assertions in the targeted tests.
- **[Risk] Broad expression matching falsely labels return assertions as mutation coverage**: Require both a traced paired-target result and an approved container-state projection; retain whole-result equality as `ReturnValue`.
- **[Risk] One `ContainerMutation` row can cover several same-type effects in Gaze**: Report only the canonical type as required by the protocol and evaluate quality changes by unique effect IDs and locations, documenting type-level granularity.
- **[Risk] Added assertions become implementation-coupled**: Assert externally visible content or ordering, never the internal mutator call or local variable name.
- **[Risk] Additional AST traversal affects performance or safety**: Reuse the parsed test AST, existing traversal scope, and `MAX_AST_DEPTH`; do not add execution or unbounded inference.
- **[Trade-off] Some legitimate container contracts remain unmapped**: Leave coverage visibly unclaimed rather than making unsupported provenance guesses; continue surfacing those effects as gaps.

## Migration Plan

1. Add isolated failing tests that define the internal evidence contract, then extend the assertion evidence without changing serialized output.
2. Update mapping and pipeline integration while preserving all existing fallback and ordering tests.
3. Add or refine targeted behavioral assertions for observable returned containers.
4. Run the exact CI workflow commands and compare a workspace-local Gaze quality report by unique `ContainerMutation` effect identity.

Rollback consists of reverting the internal evidence, mapping override, and targeted assertions together. There is no persisted data, dependency, configuration, or wire-format migration.

## Coverage Strategy

- Unit tests will exercise each supported observation form and provenance pattern for bare `assert` and applicable unittest forms, plus negative cases for whole-result equality, unrelated containers, arbitrary calls, helper-return provenance, and targets without `ContainerMutation`.
- Mapping tests will pin `ContainerMutation` override precedence and verify that all existing error, P0, generator, generic, unknown-type, and fallback branches remain unchanged.
- Pipeline tests will use temporary Python projects to prove direct target-result tracing and exact eight-key row serialization.
- Protocol tests will assert JSON-RPC success shape, complete expected row values and order, and retain cross-process byte determinism under distinct `PYTHONHASHSEED` values.
- Safety tests will prove no subprocess, import, `exec`, `eval`, coverage read, or analyzed-code execution is introduced. Depth degradation tests will use a synthetic in-memory AST or targeted fault injection so they exercise the analyzer's guard rather than CPython's earlier indentation limit, and will assert fallback to the prior mapping.
- Regression validation will run `uv sync --locked`, Ruff lint and format checks, strict mypy, and pytest with the protected 85% coverage floor exactly as defined in `.github/workflows/ci.yml`.

## Open Questions

None. Unsupported provenance deliberately retains current behavior and can be proposed separately if real projects demonstrate a need.

## Constitution Check

- **I. Protocol Fidelity - PASS**: Internal evidence changes mapping accuracy without changing request, response, taxonomy, ordering, or determinism contracts.
- **II. Detection Accuracy - PASS**: Positive mapping requires target-result provenance and a container-state projection; ambiguous or inaccessible state is not marked covered.
- **III. Python-Native Analysis - PASS**: The design uses the existing Python `ast` tree and detected `FunctionRecord` effects.
- **IV. Testability - PASS**: The coverage strategy spans isolated logic, integration, protocol, determinism, safety, and report-level regression tests.
- **V. Analysis Safety - PASS**: Analysis remains bounded and static, with no imports or execution of analyzed source or tests.
