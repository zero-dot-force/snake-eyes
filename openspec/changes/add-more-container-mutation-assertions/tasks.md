# Tasks: More Container Mutation Assertion Coverage

## 1. Baseline Survey

- [x] 1.1 Run `uv sync --locked` and capture the workspace-local `gaze quality --analyzer snake-eyes --language python --format json .` output to a transient file.
- [x] 1.2 Filter the report to contractual `ContainerMutation` gaps and group them by owning target function and source location.
- [x] 1.3 Classify each unique identity as observable (returned value exposes the mutated container) or inaccessible (internal bookkeeping/invalidation), recording a reviewable table in the implementation report.
- [x] 1.4 Confirm the fourteen previously classified inaccessible identities remain unchanged in identity and disposition.

## 2. Additional Observable Assertions

- [x] 2.1 Add ordering, membership, size, or indexed-content assertions to additional `compute_complexity` call sites in `tests/test_complexity_extra.py` and `tests/test_coverage_gaps.py` that currently assert only whole-result content.
- [x] 2.2 Add ordering or deduplication assertions to additional `ordered_file_list` call sites in `tests/test_coverage_extra.py`.
- [x] 2.3 Add projection or serialized-content assertions to additional `analyze_source` and `analyze_path` call sites in `tests/test_detector_extra.py` and `tests/test_coverage_extra.py`.
- [x] 2.4 Add content or ordering assertions to additional `parse_coverage` call sites in `tests/test_coverage_gaps.py`.
- [x] 2.5 Add projection assertions for additional `function_record_to_dict` and `extract_signals` call sites where the returned container is caller-observable.
- [x] 2.6 Re-examine the eleven ambiguous `ContainerMutation` identities and add an assertion only where the mutated container is traceable to an observable target result.

## 3. Inaccessible Confirmation

- [x] 3.1 Confirm no test references `_ScopeBindingCollector`, `_collect_module_invalidations`, or internal bookkeeping variables after the additions.
- [x] 3.2 Confirm no assertion was added for `.pop()` bookkeeping, alias invalidation, or constructor-invalidation state.

## 4. Verification

- [x] 4.1 Re-run the workspace-local `gaze quality` command and compare unique `(effect_type, source_file, source_line)` identities against the baseline: repeated gap rows decrease, unique identity set is stable, no inaccessible identity disappears, and no new unique contractual identity appears.
- [x] 4.2 Run `uv run pytest tests/test_complexity_extra.py tests/test_coverage_extra.py tests/test_coverage_gaps.py tests/test_detector_extra.py` in isolation.

## 5. CI Parity

- [x] 5.1 Run `uv sync --locked`.
- [x] 5.2 Run `uv run ruff check src/ tests/`.
- [x] 5.3 Run `uv run ruff format --check src/ tests/`.
- [x] 5.4 Run `uv run mypy src/`.
- [x] 5.5 Run `uv run pytest --cov=snake_eyes --cov-report=term-missing --cov-fail-under=85`.
- [x] 5.6 Confirm the change modifies no `src/` files, protocol schema, dependency constraints, or protected quality and governance gates.
