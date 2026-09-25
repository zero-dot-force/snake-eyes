# Design: More Container Mutation Assertion Coverage

## Context

The prior change `add-container-mutation-assertions` introduced the internal container-state evidence handoff: `assertions.py` records observation descriptors, `_provenance.py` traces direct target-result bindings, `mapping.py` selects `ContainerMutation` when a qualifying observation coexists with a detected mutation effect, and `pipeline.py` wires the evidence through without changing serialized rows. That change also added qualifying assertions at seven focused test sites, closing ten observable `ContainerMutation` identities.

The remaining work is test-only. A workspace-local `gaze quality` run still reports roughly 259 repeated test-pair gap rows because many additional tests exercise the observable functions (`ordered_file_list`, `compute_complexity`, `analyze_source`, `analyze_path`, `function_record_to_dict`, `parse_coverage`, `extract_signals`) but assert only whole-result equality, which the provenance tracer correctly treats as a `ReturnValue` assertion rather than container-state coverage.

## Goals / Non-Goals

**Goals:**
- Enumerate the remaining observable `ContainerMutation` call sites by re-running the workspace-local Gaze quality command.
- Add caller-observable container-state assertions at additional call sites so more repeated gap rows close through the existing mapping.
- Re-affirm that the fourteen inaccessible identities and any non-observable ambiguous identities remain unclaimed.
- Verify closure by unique effect identity and run the unchanged CI gates.

**Non-Goals:**
- Changing `src/`, the mapping logic, provenance tracing, or any analyzer behavior.
- Changing the Gaze protocol, JSON-RPC schema, assertion types, or side-effect taxonomy.
- Adding assertions for inaccessible bookkeeping, `.pop()` invalidation, or constructor-invalidation state.
- Adding assertions solely to inflate a metric when they do not strengthen a caller-observable contract.

## Decisions

### 1. Reuse the existing provenance-qualified mapping; do not touch source
The prior change's tracing and mapping already implement the full evidence path. The only way to close the remaining repeated gaps is to make more tests express a qualifying container-state projection over the target result. No source change is required, and any source change would risk regressing the protocol contract for no coverage benefit.

**Alternative considered:** Extend provenance tracing to helper returns, attribute chains, and tuple unpacking. Rejected: the prior change deliberately scoped tracing conservatively, and widening it would be a separate analyzer-change proposal with its own correctness and ambiguity risks, not an assertion-coverage task.

### 2. Assert caller-observable outcomes, not internal mutators
Each added assertion verifies a behavior a caller can observe through the returned container — deterministic ordering, membership, size, indexed placement, or serialized content — against an explicit expected value derived from known fixture inputs. Assertions never reference internal names such as `entries`, `all_records`, or local bookkeeping variables, and never re-invoke the target to derive the expected value.

**Alternative considered:** Assert the exact mutated list shape by reconstructing it. Rejected where it couples the test to implementation internals; preferred is a projection (keys, names, lengths, membership) that captures the contract without encoding every internal accumulator.

### 3. Target additional call sites, not every repeated row
The repeated gap rows are the same unique effects surfacing across many paired tests. The change adds one qualifying assertion per distinct test that meaningfully observes container state, not one assertion per raw gap row, mirroring the prior change's decision to avoid duplicate low-value tests.

**Alternative considered:** Add an assertion to every test that calls an observable function. Rejected because many such tests already assert the full result value and would gain no new contract coverage; only tests whose assertion currently fails to observe container state are modified.

### 4. Keep the fourteen inaccessible identities and non-observable ambiguous identities visible
The fourteen detector bookkeeping and invalidation identities are internal analysis state with no caller-observable container. The eleven ambiguous identities are re-examined individually; only those traceable to an observable result gain an assertion, and the rest remain reported as gaps.

**Alternative considered:** Force an assertion for every remaining identity. Rejected: this would encode implementation details into the public test contract, violating Detection Accuracy and the Zero-Waste Mandate.

## Risks / Trade-offs

- **[Risk] A new assertion accidentally changes existing test semantics** → Add assertions without deleting or weakening existing checks; run the affected test files in isolation before the full suite.
- **[Risk] An assertion is written but the provenance tracer does not qualify it (e.g. routed through a helper)** → Keep assertions on direct target-result bindings and simple projections, the forms the tracer supports; verify closure with the before/after Gaze comparison.
- **[Risk] Closure is misread from repeated-row counts** → Compare unique `(effect_type, source_file, source_line)` identities, never raw repeated rows, as required by the prior change's verification method.
- **[Trade-off] Some observable call sites will still not map** → Leave them visible rather than weaken the tracer; the change is a bounded test-authoring increment, not a completeness guarantee.

## Migration Plan

1. Run the workspace-local `gaze quality` command to produce the post-baseline survey.
2. Group remaining contractual `ContainerMutation` gaps by owning target and classify observable vs inaccessible.
3. Add qualifying assertions to additional observable call sites, one per distinct test that benefits.
4. Re-run `gaze quality` and compare unique identities, then run the exact CI workflow commands.

Rollback consists of reverting the test-only diff; there is no persisted data, dependency, or wire-format migration.

## Open Questions

None. Inaccessible and non-observable ambiguous identities remain visible by design and can be revisited only through a separate analyzer-change proposal.
