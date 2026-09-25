# Implementation Report: More Container Mutation Assertion Coverage

## Summary

This is a test-only follow-up to the already-merged `add-container-mutation-assertions`
change. No `src/`, protocol, dependency, or gate changes were made. The change adds
caller-observable container-state assertions (size, projection, ordering, membership)
to additional test call sites that previously asserted only whole-result content or
routed observations through helper wrappers, so that Gaze's provenance resolver can
map those assertions back to `ContainerMutation` side effects.

Result:

- Unique contractual `ContainerMutation` identities: **26 → 26** (stable — none
  removed, none added).
- Repeated gap rows: **330 → 233** (reduction of 97).
- Full suite: **799 passed**, total coverage **93.90%** (gate is 85%).

## Baseline Survey (tasks 1.1–1.4)

Baseline captured at `ad0e311`-era source layout (effect IDs have since re-keyed due to
the `_is_plain_len_call` helper added to `analysis/_shared.py`; identities are compared
by `(effect_type, source_file, source_line)`, not raw effect IDs).

26 unique contractual `ContainerMutation` identities, grouped by disposition:

| Disposition | Count | Owner(s) |
|---|---|---|
| Observable (caller-visible mutated container) | 10 | `ordered_file_list`, `compute_complexity`, `analyze_source`, `analyze_path`, `function_record_to_dict`, `parse_coverage`, `extract_signals` |
| Inaccessible (detector bookkeeping) | 14 | `_ScopeBindingCollector.visit_ClassDef`, `_collect_module_invalidations.visit_scopes` |
| Internal accumulator (new, not in prior baseline) | 2 | `run_test_mapping` (`rows.append`, `rows.sort`) |

The 14 inaccessible identities (tasks 1.4, 3.x) are unchanged in identity and
disposition and remain unclaimed: `se-341aba5d`/`se-2800274a`/`se-547183d2`/
`se-c4a205b3`/`se-08795a99`/`se-291edad3`/`se-f6712dca`/`se-081ab65d`/
`se-551f0633`/`se-f4f67199` (detector.py:1562–1606, `_ScopeBindingCollector.visit_ClassDef`)
and `se-cd3917f0`/`se-0a843f95`/`se-7e14a005`/`se-dceb5fa9` (detector.py:1806–1820,
`_collect_module_invalidations.visit_scopes`). These are all internal bookkeeping
(`statement_results.append`, `class_globals.update`, `class_names.difference_update`,
`class_aliases.pop`, `sources.update`, `invalidated.update`,
`constructor_invalidated.add`), never returned to the caller.

The 2 newly-surfaced internal-accumulator identities (`rows.append`/`rows.sort` in
`run_test_mapping`, pipeline.py:328/349) are not caller-observable: `run_test_mapping`
builds a fresh `mappings` list via comprehension (stripping internal `_line`/`_col`
fields) before returning `TestMappingResult`. They remain unclaimed.

## Additional Observable Assertions (tasks 2.1–2.5)

| Task | Target | Files | Assertions added |
|---|---|---|---|
| 2.1 | `compute_complexity` | `test_complexity_extra.py`, `test_coverage_gaps.py` | `assert len(entries) == N` after each `entries = compute_complexity(...)` (13 sites) |
| 2.2 | `ordered_file_list` | `test_coverage_extra.py` | `assert len(files) == 2` + `assert "pipe.py" in files` (1 site, `test_iter_source_files_non_regular`) |
| 2.3 | `analyze_source` | `test_detector_extra.py`, `test_coverage_extra.py` | `assert len(records) == N` after each `records = analyze_source(...)` (81 sites; special counts for nested/class/descriptor/closure/aenter tests) |
| 2.4 | `parse_coverage` | `test_coverage_gaps.py` | inlined comprehension into `assert [...] == [...]` (`test_ordering_non_trivial_sort_key`); `assert len(result) == 1` (`test_coverage_async_function`) |
| 2.5 | `function_record_to_dict`, `extract_signals` | `test_models.py`, `test_signals_adapter.py` | `assert len(result["side_effects"]) == 1`; `assert len([... for s in signals ...]) == 2`; inlined setcomp `assert {s["source"] for s in signals} == _ALLOWED_SOURCES` |

`analyze_path` had zero call sites in the two scoped files for task 2.3 (confirmed by
grep), so no assertion was added there; its two identities (`all_records.extend`,
`all_records.sort`) are still covered by the existing
`test_functions_ordered_by_file_line_name` ordering test.

### Provenance-qualifying assertion patterns

An assertion maps to `ContainerMutation` only when its container-state observation
(`membership`/`len`/`subscript`/`slice`/`iteration`/`comprehension`) resolves to a
name bound once to a direct call of the paired target (qualified
`from snake_eyes… import func`). Consequently:

- `result = target(...)` followed by `len(result)`, `result[k]`, `len(result[k])`,
  `[x for x in result] == [...]`, `x in result`, `{x for x in result} == {...}` qualifies.
- `assert result == []` does **not** qualify (plain equality, no container observation).
- Helper-wrapped observations (`_types(records)`, `_to_dicts(records)`) do **not**
  trace to the target.

## Ambiguous Identities (task 2.6)

The 11 ambiguous `ContainerMutation` identities were re-examined; no assertions were
added, and all remain unclaimed:

- 5 `records`-accumulator identities in `_walk_module_body` (detector.py:2109/2111/
  2135/2136/2151). The `records` list is ultimately returned, but the mutation occurs
  inside a recursive internal helper, so it is classified ambiguous rather than
  contractual. The observable outcome is already exercised by the `len(records)`
  assertions added in task 2.3; reclassification is a `classify_signals` (gaze #246)
  concern, not a test-authoring one.
- 6 clearly-internal identities (detector.py:1493 `targets.update`, :1615
  `local_names.update`, :1662 `annotations.extend`, :1790/1791/1793 `invalidated.update`/
  `constructor_invalidated.update`). None are caller-observable.

## Verification (tasks 4.1–4.2)

### Gaze quality comparison (task 4.1)

Re-ran the workspace-local analyzer and compared normalized identities:

- Unique identities: **26 → 26** (stable).
- Repeated gap rows: **330 → 233** (−97).

Per-identity repeated-row deltas (before → after):

| Identity | Before | After |
|---|---|---|
| `_shared.py:124` `seen.add` | 2 | 1 |
| `_shared.py:125` `ordered.append` | 3 | 3 |
| `complexity.py:159` `all_entries.extend` | 26 | 14 |
| `complexity.py:161` `all_entries.sort` | 27 | 27 |
| `detector.py:1562–1820` (14 inaccessible) | 1 each | 1 each |
| `detector.py:2283` `records.sort` | 145 | 64 |
| `detector.py:2310` `all_records.extend` | 24 | 24 |
| `detector.py:2312` `all_records.sort` | 25 | 25 |
| `models.py:64` `effects.append` | 4 | 3 |
| `coverage.py:359` `entries.sort` | 35 | 33 |
| `pipeline.py:328/349` `rows.append`/`rows.sort` | 9 each | 9 each |
| `signals/adapter.py:85` `signals.sort` | 7 | 7 |

`len` assertions claim size-mutation effects (`extend`/`append`) but not ordering
(`sort`) effects — ordering requires comprehension/subscript projection assertions —
which is why `complexity.py:161`, `detector.py:2312`, and `adapter.py:85` `sort`
identities stayed flat while the corresponding `extend`/`append` identities dropped.
`detector.py:2283` dropped 145→64 because `analyze_source` reports a single
`ContainerMutation` effect, so the `len(records)` observation maps to it. This is
consistent with the task wording ("ordering, membership, size, or indexed-content").

### Isolated pytest (task 4.2)

```
uv run pytest tests/test_complexity_extra.py tests/test_coverage_extra.py \
  tests/test_coverage_gaps.py tests/test_detector_extra.py \
  tests/test_models.py tests/test_signals_adapter.py -q
```
→ **147 passed**.

## CI Parity (tasks 5.1–5.6)

| Gate | Command | Result |
|---|---|---|
| 5.1 | `uv sync --locked` | OK (lockfile integrity intact) |
| 5.2 | `uv run ruff check src/ tests/` | All checks passed |
| 5.3 | `uv run ruff format --check src/ tests/` | 69 files already formatted |
| 5.4 | `uv run mypy src/` | Success: no issues in 28 source files |
| 5.5 | `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85` | 799 passed, 93.90% coverage |
| 5.6 | no src/protocol/dependency/gate changes | Confirmed — diff is 6 test files only (104 insertions, 6 deletions) |

## Discovery Note (task 2.2)

`discovery._walk` does **not** filter FIFOs (it only skips `.pyi` files and symlinks).
Consequently `ordered_file_list` returns both `pipe.py` (a FIFO created via
`os.mkfifo`) and `real.py` in sorted order — `len(files) == 2`. FIFO filtering happens
downstream in `iter_source_files`, so `assert "pipe.py" in files` plus
`assert "pipe.py" not in rel_paths` correctly expresses the caller-observable contract
of both functions.
