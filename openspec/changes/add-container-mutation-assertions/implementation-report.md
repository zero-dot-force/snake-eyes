# Implementation Report: Container Mutation Assertion Mapping

## Task 3.1 Baseline Classification

### Baseline provenance

The baseline was replayed in an isolated worktree at committed revision
`ad0e311` (the reviewed specification commit and pre-implementation state):

```text
uv sync --locked
gaze quality --analyzer snake-eyes --language python --format json .
```

The classification below selects `contract_coverage.gaps` whose type is
`ContainerMutation` and whose classification label is `contractual`, then
deduplicates by `(effect id, source location)`. The replay contains 24 unique
identities across 319 repeated test-pair gap rows. The reviewed proposal records
330 repeated pairings from its earlier workspace run; that environment-sensitive
repetition count is not used as a gate. The unique identity count is 24 in both
the reviewed baseline and this replay.

> **Note on effect IDs and line numbers**: Gaze derives effect IDs from source
> location, so the IDs and `file:line` values in the table below reflect the
> baseline tree at `ad0e311` (before this change added the shared
> `_is_plain_len_call` helper to `analysis/_shared.py`, which shifted
> `ordered_file_list` from lines 113/114 to 124/125). The current tree therefore
> reports re-keyed IDs for those two `ordered_file_list` identities; the
> classification and disposition are unchanged. The table is intentionally
> pinned to the reviewed baseline so Task 4.2/4.3 comparisons use a stable
> identity set.

### Selection rule

- **Observable**: the mutation constructs, orders, deduplicates, or serializes a
  container exposed through the target's returned value. Task 3.2 or 3.3 may add
  a focused assertion only when it strengthens that caller-visible contract.
- **Inaccessible**: the mutation updates analyzer bookkeeping, alias tracking,
  or constructor-invalidation state that is not exposed as a meaningful public
  container result. Task 3.4 must leave it unclaimed rather than add an
  implementation-coupled assertion.

### Classification table

| # | Effect identity | Source location | Owning implementation target | Mutation target / operation | Status | Disposition | Review rationale |
|---:|---|---|---|---|---|---|---|
| 1 | `se-8984c68f` | `src/snake_eyes/analysis/_shared.py:113:12` | `ordered_file_list` | `seen.add()` | Observable | Task 3.3 | The set enforces uniqueness in the returned ordered file list; assert caller-visible deduplication, not the set itself. |
| 2 | `se-905e24c2` | `src/snake_eyes/analysis/_shared.py:114:12` | `ordered_file_list` | `ordered.append()` | Observable | Task 3.3 | The returned list exposes selected file membership and source-before-test order. |
| 3 | `se-2ede1f21` | `src/snake_eyes/analysis/complexity.py:159:8` | `compute_complexity` | `all_entries.extend()` | Observable | Task 3.2 | The returned entries expose aggregation across analyzed files. |
| 4 | `se-65715d40` | `src/snake_eyes/analysis/complexity.py:161:4` | `compute_complexity` | `all_entries.sort()` | Observable | Task 3.2 | The API documents and returns deterministic `(file, line, name)` order. |
| 5 | `se-341aba5d` | `src/snake_eyes/analysis/detector.py:1562:12` | `_ScopeBindingCollector.visit_ClassDef` | `statement_results.append()` | Inaccessible | Task 3.4 | Temporary per-statement scope analysis is not returned as a caller-visible container. |
| 6 | `se-2800274a` | `src/snake_eyes/analysis/detector.py:1563:12` | `_ScopeBindingCollector.visit_ClassDef` | `class_globals.update()` | Inaccessible | Task 3.4 | Class-scope global bookkeeping remains internal to detector analysis. |
| 7 | `se-547183d2` | `src/snake_eyes/analysis/detector.py:1575:16` | `_ScopeBindingCollector.visit_ClassDef` | `class_names.difference_update()` | Inaccessible | Task 3.4 | Deleted-name tracking is mutable visitor state, not a returned contract. |
| 8 | `se-c4a205b3` | `src/snake_eyes/analysis/detector.py:1577:20` | `_ScopeBindingCollector.visit_ClassDef` | `class_aliases.pop()` | Inaccessible | Task 3.4 | Alias invalidation is `.pop()` bookkeeping with no observable container result. |
| 9 | `se-08795a99` | `src/snake_eyes/analysis/detector.py:1591:16` | `_ScopeBindingCollector.visit_ClassDef` | `class_names.update()` | Inaccessible | Task 3.4 | Bound-name accumulation is internal class-analysis state. |
| 10 | `se-291edad3` | `src/snake_eyes/analysis/detector.py:1593:20` | `_ScopeBindingCollector.visit_ClassDef` | `class_aliases.pop()` | Inaccessible | Task 3.4 | Alias replacement is `.pop()` bookkeeping with no public result projection. |
| 11 | `se-f6712dca` | `src/snake_eyes/analysis/detector.py:1597:24` | `_ScopeBindingCollector.visit_ClassDef` | `sources.update()` | Inaccessible | Task 3.4 | Transient alias-source expansion is local implementation state. |
| 12 | `se-081ab65d` | `src/snake_eyes/analysis/detector.py:1600:16` | `_ScopeBindingCollector.visit_ClassDef` | `class_names.update()` | Inaccessible | Task 3.4 | Annotated-assignment bookkeeping is not exposed as a container result. |
| 13 | `se-551f0633` | `src/snake_eyes/analysis/detector.py:1602:20` | `_ScopeBindingCollector.visit_ClassDef` | `class_aliases.pop()` | Inaccessible | Task 3.4 | Alias replacement is inaccessible `.pop()` bookkeeping. |
| 14 | `se-f4f67199` | `src/snake_eyes/analysis/detector.py:1606:24` | `_ScopeBindingCollector.visit_ClassDef` | `sources.update()` | Inaccessible | Task 3.4 | Transient annotated-alias source expansion is internal state. |
| 15 | `se-cd3917f0` | `src/snake_eyes/analysis/detector.py:1806:16` | `_collect_module_invalidations.visit_scopes` | `invalidated.update()` | Inaccessible | Task 3.4 | Nested scope invalidation bookkeeping is consumed internally, not a public container contract. |
| 16 | `se-0a843f95` | `src/snake_eyes/analysis/detector.py:1807:16` | `_collect_module_invalidations.visit_scopes` | `invalidated.update()` | Inaccessible | Task 3.4 | Global-rebinding invalidation bookkeeping is internal analysis state. |
| 17 | `se-7e14a005` | `src/snake_eyes/analysis/detector.py:1814:24` | `_collect_module_invalidations.visit_scopes` | `constructor_invalidated.add()` | Inaccessible | Task 3.4 | Constructor-mutation invalidation state is an internal detector implementation detail. |
| 18 | `se-dceb5fa9` | `src/snake_eyes/analysis/detector.py:1820:24` | `_collect_module_invalidations.visit_scopes` | `constructor_invalidated.add()` | Inaccessible | Task 3.4 | Alias-resolved constructor invalidation remains internal bookkeeping. |
| 19 | `se-b5d902b4` | `src/snake_eyes/analysis/detector.py:2283:4` | `analyze_source` | `records.sort()` | Observable | Task 3.2 | The returned function records expose deterministic `(file, line, name)` order. |
| 20 | `se-61244d39` | `src/snake_eyes/analysis/detector.py:2310:8` | `analyze_path` | `all_records.extend()` | Observable | Task 3.2 | The returned records expose complete aggregation across discovered files. |
| 21 | `se-529abc5b` | `src/snake_eyes/analysis/detector.py:2312:4` | `analyze_path` | `all_records.sort()` | Observable | Task 3.2 | The returned records expose deterministic `(file, line, name)` order. |
| 22 | `se-21520092` | `src/snake_eyes/analysis/models.py:64:8` | `function_record_to_dict` | `effects.append()` | Observable | Task 3.3 | The returned serialization exposes effect count, contents, and established order. |
| 23 | `se-48443a2b` | `src/snake_eyes/coverage.py:359:4` | `parse_coverage` | `entries.sort()` | Observable | Task 3.2 | The returned coverage entries expose deterministic `(file, start_line, function)` order. |
| 24 | `se-a579350d` | `src/snake_eyes/signals/adapter.py:85:4` | `extract_signals` | `signals.sort()` | Observable | Task 3.2 | The returned signals expose deterministic package/function/effect/source order. |

### Totals and downstream disposition

| Classification | Task 3.2 | Task 3.3 | Task 3.4 | Total |
|---|---:|---:|---:|---:|
| Observable | 7 | 3 | 0 | 10 |
| Inaccessible | 0 | 0 | 14 | 14 |
| **Total** | **7** | **3** | **14** | **24** |

Task 3.1 changes no tests or production behavior. Tasks 3.2 and 3.3 must use
focused assertions on the stated returned contracts; task 3.4 must confirm the
14 inaccessible identities remain unclaimed.

## Task 3.4 Inaccessible-gap Confirmation

The current implementation worktree was analyzed without adding assertions for
the private bookkeeping targets:

```text
gaze quality --analyzer snake-eyes --language python --format json .
```

The report was filtered to contractual `ContainerMutation` gaps and compared by
`(effect id, source location)` with the 14 Task 3.4 rows above. The result was
`classified_inaccessible=14`, `present_unique=14`, and `missing=0`. Every
identity appeared in exactly one current gap row:

```text
se-341aba5d  se-2800274a  se-547183d2  se-c4a205b3
se-08795a99  se-291edad3  se-f6712dca  se-081ab65d
se-551f0633  se-f4f67199  se-cd3917f0  se-0a843f95
se-7e14a005  se-dceb5fa9
```

A test-tree audit found no references to `_ScopeBindingCollector`,
`_collect_module_invalidations`, `statement_results`, `class_globals`,
`class_aliases`, or `constructor_invalidated`. In particular, no assertion was
added for the three `.pop()` operations or constructor-invalidation sets. These
14 effects therefore remain visible and truthfully unclaimed.

## Task 4.2 Before/After Gaze Comparison

The before report was captured from an isolated worktree at `ad0e311`; that
worktree was removed before capturing the after report so it could not be
discovered as input to the current workspace analysis. Both sides used the
workspace-local analyzer executable:

```text
# Before, from the isolated ad0e311 worktree
uv sync --locked
PATH="$PWD/.venv/bin:$PATH" gaze quality \
  --analyzer snake-eyes --language python --format json .

# After, from the current implementation worktree
PATH="$PWD/.venv/bin:$PATH" gaze quality \
  --analyzer snake-eyes --language python --format json .
```

For this change's quality scope, each report was filtered to contractual
`ContainerMutation` gaps. The location was split from the right as
`source_file:source_line:column`, and comparisons used only
`(effect_type, source_file, source_line)`:

| Metric | Before | After |
|---|---:|---:|
| Repeated test-pair gap rows | 319 | 259 |
| Unique `(type, file, line)` identities | 24 | 24 |

Set comparison: `removed=0`, `added=0`, and `unchanged=24`. The 60-row decrease
shows that focused assertions close the mutation effect for their selected test
pairs. Gaze still reports the same identity as a gap for other paired tests that
do not cover it, so a global union of all remaining per-test gaps does not make
the 10 observable identities disappear. This distinction must be preserved in
task 4.3 rather than inferring identity closure from the repeated-row decrease.

The full JSON outputs were transient validation inputs and were not added as
generated repository artifacts.

## Task 4.3 Acceptance Verification (Incomplete)

The 10 observable identities form seven representable protocol groups when
keyed by `(owning target, canonical side-effect type)`. This is the granularity
required by protocol v1.1.0 and the reviewed design: a mapping row carries
`side_effect_type`, not an individual effect ID.

| Owning target | Observable identities | Direct returned-container evidence | Current mappings |
|---|---|---|---:|
| `ordered_file_list` | `se-8984c68f`, `se-905e24c2` | `test_ordered_file_list_deduplicates_source_before_tests` | 4 |
| `compute_complexity` | `se-2ede1f21`, `se-65715d40` | `test_ordering_by_file_line_name` | 1 |
| `analyze_source` | `se-b5d902b4` | `test_analyze_source_orders_records_by_line` | 1 |
| `analyze_path` | `se-61244d39`, `se-529abc5b` | `test_functions_ordered_by_file_line_name` | 1 |
| `function_record_to_dict` | `se-21520092` | `test_function_record_to_dict_includes_optionals_when_set` | 2 |
| `parse_coverage` | `se-48443a2b` | `test_ordering_by_file_start_line_function` | 1 |
| `extract_signals` | `se-a579350d` | `test_extract_signals_orders_returned_projection` | 1 |

All seven groups have at least one direct-pair, provenance-qualified
`ContainerMutation` mapping (`covered_groups=7/7`); all listed mappings have
confidence 80. The assertions inspect only caller-visible size, membership,
indexed content, serialized content, or deterministic ordering.

Identity-level evidence is accounted for without inventing precision absent
from the protocol:

- Six identities occur among 61 genuinely removed baseline gap rows:
  `se-2ede1f21`, `se-b5d902b4`, `se-61244d39`, `se-21520092`, `se-48443a2b`, and
  `se-a579350d`.
- `se-8984c68f` is newly credited by the direct `ordered_file_list` report:
  `covered_count=1`; its gaps include sibling `se-905e24c2` but not
  `se-8984c68f`.
- `se-905e24c2`, `se-65715d40`, and `se-529abc5b` are later identities in a
  same-target, same-`ContainerMutation` group. They cannot be independently
  attributed because the protocol exposes only the canonical type and Gaze
  credits that mapping to the first matching identity. Per the reviewed design,
  this is an attribution limitation, not missing truthful assertion evidence.

The global gap union remains 24 to 24 because unrelated paired tests continue
to repeat the same identities; repeated rows fall from 319 to 259 (61 removed,
one added). All 14 inaccessible contractual identities remain visible, all 11
ambiguous `ContainerMutation` identities remain unchanged, and no new unique
contractual identity appears.

The acceptance criterion was reviewed and scoped to protocol type-level
granularity: qualify each representable `(owning target, ContainerMutation)`
group, not every raw effect ID. All seven representable groups now carry a
direct provenance-qualified mapping, so task 4.3 is complete under the
amended group-level criterion. The three later same-target/same-type
identities remain attributed only to the canonical type the row schema
exposes, which is the documented representational limit of Gaze protocol
v1.1.0 rather than a missing assertion.
