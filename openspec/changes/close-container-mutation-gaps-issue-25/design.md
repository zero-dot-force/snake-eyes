## Context

Issue #25 split from #19 after the container-mutation assertion mapping landed. The mapping logic in `src/snake_eyes/quality/mapping.py` now recognizes container-state observations (length, membership, subscript, iteration, comprehension) over a traced target result and maps them to `ContainerMutation` when the target reports that effect. However, several observable `ContainerMutation` effects are still reported as gaps because the tests that exercise those functions assert the final value but do not separately assert the container-state contracts.

A fresh `gaze quality --analyzer snake-eyes --language python --format json .` run identifies the target gaps:

- `compute_complexity` (`src/snake_eyes/analysis/complexity.py`) reports two `ContainerMutation` effects: `.extend()` at line 159 (`se-2ede1f21`) and `.sort()` at line 161 (`se-65715d40`). The existing `test_ordering_by_file_line_name` covers `.extend()` through a list-comprehension equality, but `.sort()` remains a gap in all 27 paired tests.
- `parse_coverage` (`src/snake_eyes/coverage.py`) reports one `ContainerMutation` effect: `.sort()` at line 359 (`se-48443a2b`). It is covered by `test_ordering_by_file_start_line_function` but remains a gap in most other paired tests.
- `function_record_to_dict` (`src/snake_eyes/analysis/models.py`) reports `.append()` at line 64 (`se-21520092`), which is already covered by existing serialization tests.

Because the Gaze analyzer protocol v1.1.0 row schema exposes only the canonical `side_effect_type`, one container-state assertion maps to one `ContainerMutation` identity per test→target pair. When a function has two `ContainerMutation` effects on the same returned object (as `compute_complexity` does), a single assertion cannot cover both identities.

## Goals / Non-Goals

**Goals:**
- Add deterministic, externally visible container-state assertions that close the remaining `.sort()` gap in `compute_complexity` and `parse_coverage`.
- Split the whole-list equality assertion in `compute_complexity` into separate length/membership and ordering assertions so that `.extend()` and `.sort()` can each be mapped in at least one focused test.
- Establish a per-function contract-coverage floor from the fresh baseline.
- Verify the change with a before/after `gaze quality` comparison of unique `(effect_type, source_file, source_line)` identities.

**Non-Goals:**
- Modifying production code or the analyzer's mapping logic.
- Covering internal, unobservable mutations such as the `.pop()` calls in `detector.py:__init__`.
- Covering `MapMutation` effects. `infer_side_effect_type` has no `MapMutation` branch, so those gaps require a separate mapper change and are not addressable by tests alone.
- Raising the global `average_contract_coverage` to a specific target. Contract coverage is computed per test→target pair, so the same effect identity is reported as a gap in every paired test that does not assert it; this change focuses on per-function maxima.

## Decisions

### 1. Assert externally visible container state, not internal mutator calls
Assertions will verify properties of the returned container (length, sorted order, membership) rather than the fact that `.sort()` or `.extend()` was invoked. This keeps tests stable if the implementation is later refactored.

### 2. Use separate assertions for `.extend()` and `.sort()` in `compute_complexity`
`compute_complexity` returns a single list that is both extended and sorted. A single whole-list equality assertion maps to one `ContainerMutation` identity. To give the analyzer two distinct observations, the focused test will contain:
- a length/membership assertion (`len(entries) == N`, `"a_second" in names`) that maps to `.extend()`;
- an ordering assertion (`[e["name"] for e in entries] == [...]` or ordered tuple comparison) that maps to `.sort()`.

### 3. Add the `.sort()` assertion to the canonical value test for `parse_coverage`
`test_ordering_by_file_start_line_function` already covers `.sort()`, but `test_coverage_json_expected_values` (which exercises the happy path) lists `.sort()` as a gap. Adding an ordering assertion there closes the gap in the representative value test.

### 4. Keep `function_record_to_dict` assertions unchanged unless a regression gap appears
The `.append()` effect is already covered by existing serialization tests. No new assertions are required for issue #25.

### 5. Evaluate quality by unique effect identity, not repeated pair rows
The acceptance criterion is that the targeted `ContainerMutation` identities disappear from the gap list of at least one focused test per function. Repeated rows in other tests are expected to remain because those tests do not assert container state; this is a protocol-level representational limitation, not a defect.

## Risks / Trade-offs

- **[Risk] Added assertions become coupled to exact ordering or entry count.** → Mitigation: use deterministic fixtures (fixed file names, fixed line numbers) and assert ordering by the documented `(file, line, name)` / `(file, start_line, function)` keys, not arbitrary positions.
- **[Risk] Gaze attributes both new assertions to the same effect identity.** → Mitigation: keep one assertion focused on length/membership (`.extend()`) and one on ordering (`.sort()`); verify with a before/after `gaze quality` run and adjust if attribution does not match intent.
- **[Risk] Contract-coverage floor is misinterpreted as a global average.** → Mitigation: record per-function maxima (`compute_complexity` ~43%, `parse_coverage` 75%, `function_record_to_dict` 40%) and note the structural ceiling caused by per-pair single attribution.
- **[Trade-off] Some paired tests will still report the same identity as a gap.** This is expected and correct: only tests that assert container state earn coverage for it.
