# Tasks: Container Mutation Assertion Mapping

## 1. Assertion Evidence Tests

These test-first tasks define the expected behavior and may fail until the corresponding implementation tasks in section 2 are complete.

- [x] 1.1 Add focused tests in `tests/test_test_mapping_method.py` for membership, `len()`, subscript, slice, iteration, and comprehension observations of direct paired-target results.
- [x] 1.2 Add provenance tests for simple local result bindings and direct bare or qualified target calls, plus negative cases for unrelated values, whole-result equality, arbitrary methods, helpers, aliases, tuple unpacking, nested scopes, control-flow merges, and unsupported AST forms. Exercise provenance-tracer depth exhaustion with a synthetic in-memory AST or targeted fault injection, and assert fallback to the prior mapping rather than relying on deeply indented source.
- [x] 1.3 Add mapper tests that require the `ContainerMutation` override only for qualifying non-error evidence and preserve every existing error, P0, generator, generic, unknown-type, and fallback branch.
- [x] 1.4 Add pipeline and JSON-RPC tests that pin one row per assertion-target pair, the exact eight output keys, unchanged assertion-type values, static-only behavior, complete expected row values and established row order, and byte determinism across hash seeds.

## 2. Assertion Mapping Implementation

- [x] 2.1 Extend `AssertionInfo` and the collector in `src/snake_eyes/quality/assertions.py` with defaulted internal observation descriptors for the supported container-state observation forms while reusing function-scope and `MAX_AST_DEPTH` boundaries.
- [x] 2.2 Add conservative paired-target result tracing in `src/snake_eyes/quality/_provenance.py` (invoked through `pipeline.py`) for direct target calls and simple local bindings without crossing helpers, mutable aliases, tuple unpacking, nested scopes, or control-flow merges; resolve the observation descriptor to an `observes_container_state` boolean for the selected pair.
- [x] 2.3 Update `infer_side_effect_type` in `src/snake_eyes/quality/mapping.py` to consume the internal boolean and select `ContainerMutation` only when qualifying evidence and a detected mutation effect coexist, preserving all prior precedence otherwise without AST traversal in the mapper.
- [x] 2.4 Wire the internal evidence through `run_test_mapping` without adding serialized fields, assertion types, rows, imports of analyzed code, runtime execution, or dependencies.

## 3. Observable Contract Assertions

- [x] 3.1 Classify the 24 unique baseline contractual `ContainerMutation` gaps by effect identity and source location, selecting only targets whose returned value exposes a meaningful container contract; record a reviewable classification table in the implementation report with each gap's observable or inaccessible status and disposition under task 3.2, 3.3, or 3.4.
- [x] 3.2 Add or refine focused ordering and projection assertions for observable results from `compute_complexity`, `parse_coverage`, `analyze_source`, `analyze_path`, and `extract_signals` without duplicating existing whole-result checks.
- [x] 3.3 Add or refine focused membership, size, or indexed-content assertions for observable serialization and discovery results affected by container construction.
- [x] 3.4 Confirm that `.pop()` bookkeeping, constructor-local mutations, and other inaccessible state receive no implementation-coupled assertions and remain visible when not truthfully covered.

## 4. Focused Verification

- [x] 4.1 Run the focused test-mapping, analysis, coverage, signal, model, and discovery tests affected by the new mapping and assertions.
- [x] 4.2 Capture before and after output from the workspace-local `gaze quality --analyzer snake-eyes --language python --format json .` command, extract unique `(effect_type, source_file, source_line)` identities, and compare those sets rather than repeated pair rows.
- [x] 4.3 Verify every representable container-mutation group classified as qualifying in task 3.1 closes at protocol type-level granularity (each qualifying `(owning target, ContainerMutation)` group gains a provenance-qualified mapping) while unrelated, ambiguous, and inaccessible mutation effects remain reported, same-target/same-type effect identities are attributed only to the canonical type the row schema exposes, and no new unique gaps appear for unchanged targets.

## 5. CI Parity

- [x] 5.1 Run `uv sync --locked`.
- [x] 5.2 Run `uv run ruff check src/ tests/`.
- [x] 5.3 Run `uv run ruff format --check src/ tests/`.
- [x] 5.4 Run `uv run mypy src/`.
- [x] 5.5 Run `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85`.
- [x] 5.6 Confirm the implementation changes no protocol schema, dependency constraints, or protected quality and governance gates.

<!-- spec-review: passed -->
<!-- code-review: passed -->
