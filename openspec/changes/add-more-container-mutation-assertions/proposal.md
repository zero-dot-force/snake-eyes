# Proposal: More Container Mutation Assertion Coverage

## Why

The prior change `add-container-mutation-assertions` built the container-state provenance mapping and added qualifying assertions at seven focused test sites, closing the ten observable `ContainerMutation` identities. A workspace-local `gaze quality --analyzer snake-eyes --language python --format json .` run still reports roughly 259 repeated test-pair gap rows because many other tests exercise the same observable functions (`ordered_file_list`, `compute_complexity`, `analyze_source`, `analyze_path`, `function_record_to_dict`, `parse_coverage`, `extract_signals`) without a provenance-qualified container-state assertion. The remaining work is purely test-authoring: the effects are correctly detected and the mapping infrastructure is already in place.

## What Changes

- Add caller-observable container-state assertions (membership, `len()`, subscript, slice, iteration/comprehension, or whole-container ordering/content) to additional tests that exercise the observable container-mutating functions, so more repeated test-pair gaps close through the existing provenance-qualified mapping.
- Re-survey the current Gaze quality report to enumerate the remaining repeated gaps and attribute each to a specific test call site, rather than adding blanket assertions.
- Re-affirm the fourteen inaccessible identities remain unclaimed (no implementation-coupled assertions for detector bookkeeping, `.pop()` invalidation, or constructor-invalidation state).
- Examine the eleven ambiguous `ContainerMutation` identities and add assertions only where the mutated container is genuinely caller-observable; leave the rest visible.
- No `src/` changes, no protocol changes, no new dependencies.

## Capabilities

### New Capabilities

- `container-mutation-assertion-coverage`: The test suite's ContainerMutation assertion coverage contract — which observable container-mutating targets must carry a provenance-qualified container-state assertion, and which inaccessible or ambiguous mutations must remain visibly unclaimed.

### Modified Capabilities

None.

## Impact

- Affected implementation: none (`src/` unchanged). This change reuses the container-state observation and provenance tracing shipped in `add-container-mutation-assertions`.
- Affected tests: `tests/test_complexity_extra.py`, `tests/test_coverage_extra.py`, `tests/test_coverage_gaps.py`, `tests/test_detector_extra.py`, and focused tests for `ordered_file_list`, `compute_complexity`, `analyze_source`, `analyze_path`, `function_record_to_dict`, `parse_coverage`, and `extract_signals`.
- Protocol impact: none. No method, request, response-field, assertion-type, or side-effect-taxonomy changes.
- Dependencies: none.
- Validation: unchanged CI workflow gates, plus a before/after workspace-local Gaze quality comparison by unique `ContainerMutation` effect identity.

## Constitution Check

- **I. Protocol Fidelity - PASS**: No protocol surface changes; mapping output remains deterministic.
- **II. Detection Accuracy - PASS**: Assertions are added only for caller-observable mutations; inaccessible and ambiguous effects remain visible rather than receiving fabricated coverage.
- **III. Python-Native Analysis - PASS**: No analysis code changes; existing `ast`-based provenance is reused.
- **IV. Testability - PASS**: The scope is test coverage; each added assertion is verifiable against an explicit expected value.
- **V. Analysis Safety - PASS**: Test-only change; no execution, import, or subprocess behavior introduced.
